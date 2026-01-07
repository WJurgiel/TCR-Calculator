import os
from typing import Callable, Dict, List, Tuple, Optional


class MaterialsManager:
    """Business logic for materials and TIMs, UI-agnostic.
    Implements a simple Observer pattern for events.
    """
    def __init__(self, app=None):
        self._observers: List[Callable[[str, dict], None]] = []
        self.app = app
        self.materials: Dict[str, Dict[str, object]] = {}
        self.tims: List[Dict[str, object]] = []
        self._tim_next_id: int = 1
        self._system_geoms: List[object] = []
        self._system_interfaces: List[object] = []

    # Observer API
    def subscribe(self, callback: Callable[[str, dict], None]):
        self._observers.append(callback)

    def _notify(self, event_type: str, data: Optional[dict] = None):
        payload = data or {}
        for cb in list(self._observers):
            try:
                cb(event_type, payload)
            except Exception:
                pass

    # System context
    def set_system(self, geoms: List[object], interfaces: List[object]):
        self._system_geoms = geoms or []
        self._system_interfaces = interfaces or []
        self._notify('materials_system_set', {'geoms_count': len(self._system_geoms)})

    def get_system(self):
        return self._system_geoms, self._system_interfaces

    # Materials accessors
    def get_materials(self) -> Dict[str, Dict[str, object]]:
        return self.materials

    def set_materials(self, materials: Dict[str, Dict[str, object]]):
        self.materials = materials or {}
        self._notify('materials_updated', {'count': len(self.materials)})

    def ensure_material_entry(self, name: str):
        if name not in self.materials:
            self.materials[name] = {
                'material_name': '',
                'k': '',
                'young': '',
                'poisson': '',
                'sigma': '',
                'm': '',
                'hc': ''
            }
        return self.materials[name]

    # TIMs accessors
    def get_tims(self) -> List[Dict[str, object]]:
        return self.tims

    def set_tims(self, tims: List[Dict[str, object]]):
        self.tims = tims or []
        # Keep next id monotonic
        max_id = max([t.get('id', 0) for t in self.tims], default=0)
        self._tim_next_id = max(self._tim_next_id, max_id + 1)
        self._notify('tims_updated', {'count': len(self.tims)})

    def add_tim(self) -> Tuple[bool, str]:
        tid = self._tim_next_id
        self._tim_next_id += 1
        self.tims.append({'id': tid, 'name': '', 'k': '', 'type': 'gas', 'pressure_dependent': False})
        self._notify('tim_added', {'id': tid})
        return True, 'Dodano nowy TIM do biblioteki'

    def clear_all_tims(self) -> Tuple[bool, str]:
        count = len(self.tims)
        self.tims.clear()
        self._notify('tims_cleared', {'count': count})
        return True, f'Wyczyściłem listę TIM-ów ({count} pozycji)'

    def import_tim_file(self, file_path: str) -> Tuple[bool, str]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
        except Exception as e:
            return False, f'Błąd przy czytaniu pliku TIM: {e}'

        imported = 0
        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                # skip malformed
                continue
            tim_name = parts[0]
            tim_k_str = parts[1]
            try:
                tim_k = float(tim_k_str)
            except ValueError:
                continue
            tid = self._tim_next_id
            self._tim_next_id += 1
            self.tims.append({'id': tid, 'name': tim_name, 'k': tim_k, 'type': 'gas', 'pressure_dependent': False})
            imported += 1
        if imported:
            self._notify('tims_imported', {'count': imported, 'file': os.path.basename(file_path)})
            return True, f'Importowano {imported} TIM-ów z pliku'
        return False, 'Nie udało się importować TIM-ów z pliku (brak prawidłowych wpisów)'

    # Materials import
    def import_materials_from_file(self, file_path: str) -> Tuple[bool, str, int]:
        geoms = self._system_geoms
        interfaces = self._system_interfaces or []
        if not geoms:
            return False, 'Brak systemu do załadowania. Zdefiniuj system w zakładce System i naciśnij Save System.', 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
        except Exception as e:
            return False, f'Failed to open file: {e}', 0

        geom_names = {getattr(g, 'name', '') for g in geoms}
        iface_names = set()
        for it in interfaces:
            try:
                if getattr(it, 'has_tcr', False):
                    iface_names.add(it.geom_top.name)
                    iface_names.add(it.geom_bottom.name)
            except Exception:
                pass

        imported = 0
        for i, line in enumerate(lines, start=1):
            parts = line.split()
            if not parts:
                continue
            name = parts[0]
            if name not in geom_names:
                # unknown geometry -> skip
                continue
            allowed_all = name in iface_names
            self.ensure_material_entry(name)
            # material_name
            if len(parts) >= 2:
                self.materials[name]['material_name'] = parts[1]
            # k
            if len(parts) >= 3:
                try:
                    self.materials[name]['k'] = float(parts[2])
                except ValueError:
                    pass
            # remaining numeric fields
            field_names = ['young', 'poisson', 'sigma', 'm', 'hc']
            for idx, fname in enumerate(field_names, start=3):
                if len(parts) > idx:
                    if not allowed_all:
                        continue
                    try:
                        self.materials[name][fname] = float(parts[idx])
                    except ValueError:
                        pass
            imported += 1
        self._notify('materials_imported', {'count': imported, 'file': os.path.basename(file_path)})
        return True, f'Import materiałów zakończony', imported

    # Validation before save
    def validate_before_save(self) -> Tuple[bool, str, List[str]]:
        interfaces_with_tcr = [it for it in (self._system_interfaces or []) if getattr(it, 'has_tcr', False)]
        if interfaces_with_tcr and not self.tims:
            return False, 'Brak zdefiniowanych TIM-ów, mimo że system zawiera interfejsy z TCR. Zdefiniuj przynajmniej jeden TIM.', []

        geom_names_required = set()
        for it in interfaces_with_tcr:
            try:
                geom_names_required.add(it.geom_top.name)
                geom_names_required.add(it.geom_bottom.name)
            except Exception:
                pass

        missing_errors: List[str] = []
        required_fields = ['material_name', 'k', 'young', 'poisson', 'sigma', 'm', 'hc']
        for gname in sorted(geom_names_required):
            vals = self.materials.get(gname, {})
            for fld in required_fields:
                if fld not in vals or vals.get(fld, '') == '':
                    missing_errors.append(f'Bryła "{gname}": brak pola {fld}')
                else:
                    if fld != 'material_name':
                        try:
                            float(vals.get(fld))
                        except Exception:
                            missing_errors.append(f'Bryła "{gname}": pole {fld} ma nieprawidłową wartość')
        if missing_errors:
            return False, 'Nie wszystkie wymagane parametry materiałowe są zdefiniowane dla brył w interfejsach TCR. Sprawdź konsolę.', missing_errors
        return True, 'OK', []
