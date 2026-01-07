import os
import csv
from typing import Callable, List, Dict, Tuple, Optional


class ForcesManager:
    """Business logic for forces and pressure report generation. UI-agnostic."""

    def __init__(self, app=None):
        self._observers: List[Callable[[str, dict], None]] = []
        self.app = app
        self.forces: List[Dict[str, object]] = []  # each: {'value': number}
        self._system_interfaces: List[object] = []

    # Observer pattern
    def subscribe(self, cb: Callable[[str, dict], None]):
        self._observers.append(cb)

    def _notify(self, event_type: str, data: Optional[dict] = None):
        payload = data or {}
        for cb in list(self._observers):
            try:
                cb(event_type, payload)
            except Exception:
                pass

    # System context
    def set_system(self, interfaces: List[object]):
        self._system_interfaces = interfaces or []
        self._notify('forces_system_set', {'interfaces': len(self._system_interfaces)})

    # Forces CRUD
    def get_forces(self) -> List[Dict[str, object]]:
        return self.forces

    def set_forces(self, forces: List[Dict[str, object]]):
        self.forces = forces or []
        self._notify('forces_updated', {'count': len(self.forces)})

    def add_force(self) -> Tuple[bool, str]:
        self.forces.append({'value': ''})
        self._notify('force_added', {'count': len(self.forces)})
        return True, 'Dodano nową siłę do listy'

    def clear_forces(self) -> Tuple[bool, str]:
        count = len(self.forces)
        self.forces.clear()
        self._notify('forces_cleared', {'count': count})
        if count == 0:
            return False, 'Lista sił jest pusta'
        return True, f'Wyczyściłem listę sił ({count} pozycji)'

    def import_forces_file(self, file_path: str) -> Tuple[bool, str, int]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
        except Exception as e:
            return False, f'Błąd przy czytaniu pliku sił: {e}', 0

        imported = 0
        for line in lines:
            try:
                val = float(line)
                self.forces.append({'value': val})
                imported += 1
            except ValueError:
                continue
        self._notify('forces_imported', {'count': imported, 'file': os.path.basename(file_path)})
        if imported:
            return True, f'Importowano {imported} sił z pliku', imported
        return False, 'Nie udało się importować sił z pliku (brak prawidłowych wpisów)', 0

    # Update values from UI entries
    def update_force_values(self, values: List[str]) -> List[Dict[str, object]]:
        new_forces: List[Dict[str, object]] = []
        for v in values:
            if v == '':
                new_forces.append({'value': ''})
            else:
                try:
                    new_forces.append({'value': float(v)})
                except ValueError:
                    new_forces.append({'value': ''})
        self.forces = new_forces
        self._notify('forces_updated', {'count': len(self.forces)})
        return self.forces

    # Report generation
    def generate_report(self) -> Tuple[bool, str, List[Dict[str, object]]]:
        if not self.forces:
            return False, 'Zdefiniuj przynajmniej jedną siłę do generowania raportu', []
        tcr_interfaces = [it for it in (self._system_interfaces or []) if getattr(it, 'has_tcr', False)]
        if not tcr_interfaces:
            return False, 'Nie ma żadnych interfejsów ze zdefiniowanym TCR', []

        report_data: List[Dict[str, object]] = []
        for force_idx, fobj in enumerate(self.forces):
            try:
                force_val = float(fobj.get('value', 0))
            except (ValueError, TypeError):
                continue
            for iface in tcr_interfaces:
                try:
                    a_nominal = getattr(iface, 'A_nominal', 0)
                    pressure = force_val / a_nominal if a_nominal > 0 else 0
                    iface_name = f"{iface.geom_top.name} → {iface.geom_bottom.name}"
                    report_data.append({
                        'force_idx': force_idx,
                        'force_value': force_val,
                        'interface': iface_name,
                        'area': a_nominal,
                        'pressure': pressure
                    })
                except Exception:
                    continue
        if not report_data:
            return False, 'Nie udało się wygenerować raportu', []
        self._notify('report_generated', {'rows': len(report_data)})
        return True, 'OK', report_data

    def export_report_csv(self, file_path: str, report_data: List[Dict[str, object]]) -> Tuple[bool, str]:
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Siła [N]', 'Interfejs', 'Pow. Nom. [m²]', 'Ciśnienie [Pa]', 'Ciśnienie [MPa]'])
                for row in report_data:
                    force_val = row['force_value']
                    iface_name = row['interface']
                    area = row['area']
                    pressure_pa = row['pressure']
                    pressure_mpa = pressure_pa / 1e6
                    writer.writerow([
                        f"{force_val:.2f}", iface_name, f"{area:.6e}", f"{pressure_pa:.2e}", f"{pressure_mpa:.4f}"
                    ])
            self._notify('report_exported', {'file': os.path.basename(file_path)})
            return True, f'Raport został wyeksportowany do: {file_path}'
        except Exception as e:
            return False, f'Nie udało się wyeksportować raportu: {e}'
