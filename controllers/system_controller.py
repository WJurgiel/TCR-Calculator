import os
from typing import Callable, List, Tuple, Optional
from models import Geometry, Interface


class SystemManager:
    """Business logic (controller) for system geometries and interfaces.
    Does not depend on UI. Implements simple Observer pattern.
    """

    def __init__(self, app=None):
        self._observers: List[Callable[[str, dict], None]] = []
        self.geometries: List[Geometry] = []
        self.interfaces: List[Interface] = []
        self.app = app  # Optional, used only for logging convenience if needed

    # --- Observer API ---
    def subscribe(self, callback: Callable[[str, dict], None]):
        self._observers.append(callback)

    def unsubscribe(self, callback: Callable[[str, dict], None]):
        try:
            self._observers.remove(callback)
        except ValueError:
            pass

    def _notify(self, event_type: str, data: Optional[dict] = None):
        payload = data or {}
        for cb in list(self._observers):
            try:
                cb(event_type, payload)
            except Exception:
                # Do not stop notification chain on observer errors
                pass

    # --- Helpers ---
    def _name_exists(self, name: str, exclude_index: Optional[int] = None) -> bool:
        for i, g in enumerate(self.geometries):
            if exclude_index is not None and i == exclude_index:
                continue
            if g.name == name:
                return True
        return False

    # --- Public API: mutations ---
    def add_geometry(self, geometry: Geometry, index: Optional[int] = None) -> Tuple[bool, str]:
        if self._name_exists(geometry.name):
            return False, f'Bryła "{geometry.name}" już istnieje. Zmień nazwę.'
        if index is None:
            self.geometries.append(geometry)
        else:
            self.geometries.insert(index, geometry)
        self.rebuild_interfaces()
        self._notify('geometry_added', {'geometry': geometry})
        return True, f'Dodano Geometrię: {geometry.name} (a={geometry.length}, b={geometry.width}, h={geometry.height})'

    def remove_geometry(self, index: int) -> Tuple[bool, str]:
        if 0 <= index < len(self.geometries):
            removed = self.geometries.pop(index)
            self.rebuild_interfaces()
            self._notify('geometry_removed', {'geometry': removed})
            return True, f'Usunięto Geometrię: {removed.name}'
        return False, 'Nieprawidłowy indeks bryły'

    def update_geometry(self, index: int, geometry: Geometry) -> Tuple[bool, str]:
        if not (0 <= index < len(self.geometries)):
            return False, 'Nieprawidłowy indeks bryły'
        if self._name_exists(geometry.name, exclude_index=index):
            return False, f'Bryła "{geometry.name}" już istnieje. Zmień nazwę.'
        self.geometries[index] = geometry
        self.rebuild_interfaces()
        self._notify('geometry_updated', {'index': index, 'geometry': geometry})
        return True, f'Edytowano Geometrię: {geometry.name} (a={geometry.length}, b={geometry.width}, h={geometry.height})'

    def set_tcr_flag(self, interface_index: int, value: bool) -> Tuple[bool, str]:
        if 0 <= interface_index < len(self.interfaces):
            self.interfaces[interface_index].has_tcr = value
            self._notify('tcr_changed', {'index': interface_index, 'value': value})
            top = self.interfaces[interface_index].geom_top.name
            bot = self.interfaces[interface_index].geom_bottom.name
            if value:
                return True, f'Dodano TCR: {top}→{bot}'
            else:
                return True, f'Usunięto TCR: {top}→{bot}'
        return False, 'Nieprawidłowy indeks interfejsu'

    # --- Public API: structure ---
    def rebuild_interfaces(self) -> Tuple[bool, str]:
        old_interfaces = {(g.geom_top.name, g.geom_bottom.name): g.has_tcr
                          for g in self.interfaces if isinstance(g, Interface)}
        current_names = {g.name for g in self.geometries}

        new_keys = []
        new_interfaces: List[Interface] = []
        for i in range(len(self.geometries) - 1):
            geom_top = self.geometries[i]
            geom_bottom = self.geometries[i + 1]
            key = (geom_top.name, geom_bottom.name)
            new_keys.append(key)
            has_tcr = old_interfaces.get(key, False)
            new_interfaces.append(Interface(geom_top, geom_bottom, has_tcr))

        removed_tcrs = [k for k, v in old_interfaces.items() if v and k not in new_keys]
        self.interfaces = new_interfaces
        self._notify('interfaces_rebuilt', {'removed_tcrs': removed_tcrs})
        return True, 'Interfejsy przebudowane'

    # --- Public API: validation ---
    def validate_system(self) -> Tuple[bool, str]:
        if not self.geometries:
            return False, 'Zdefiniuj przynajmniej jedną bryłę'
        invalid = [g for g in self.geometries if not g.is_valid()]
        if invalid:
            names = ', '.join(g.name for g in invalid)
            return False, f'Nieprawidłowe bryły: {names}'
        return True, 'System poprawny'

    # --- Import/Export ---
    def import_from_file(self, file_path: str) -> Tuple[bool, str]:
        try:
            with open(file_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
            geometries: List[Geometry] = []
            for i, line in enumerate(lines):
                parts = line.split()
                if len(parts) < 4:
                    return False, f'Invalid format at line {i+1}'
                try:
                    name = parts[0]
                    length = float(parts[1])
                    width = float(parts[2])
                    height = float(parts[3])
                    geometries.append(Geometry(name, length, width, height))
                except ValueError:
                    return False, f'Invalid numbers at line {i+1}'
            names = [g.name for g in geometries]
            if len(names) != len(set(names)):
                duplicates = [n for n in set(names) if names.count(n) > 1]
                return False, f'Nieprawidłowe dane: dwie bryły o takich samych nazwach: {", ".join(duplicates)}'
            self.geometries = geometries
            self.rebuild_interfaces()
            self._notify('imported', {'count': len(geometries), 'file': os.path.basename(file_path)})
            return True, f'Imported {len(geometries)} geometries'
        except Exception as e:
            return False, f'Failed to import: {str(e)}'

    def export_to_file(self, file_path: str) -> Tuple[bool, str]:
        if not self.geometries:
            return False, 'No geometries to export'
        try:
            with open(file_path, 'w') as f:
                for geom in self.geometries:
                    f.write(f'{geom.name}\t{geom.length}\t{geom.width}\t{geom.height}\n')
            self._notify('exported', {'file': os.path.basename(file_path)})
            return True, f'Exported to {os.path.basename(file_path)}'
        except Exception as e:
            return False, f'Failed to export: {str(e)}'

    # --- Accessors ---
    def get_geometries(self) -> List[Geometry]:
        return self.geometries

    def get_interfaces(self) -> List[Interface]:
        return self.interfaces
