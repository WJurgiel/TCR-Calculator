import os
import math
import csv
from typing import Callable, Dict, List, Tuple, Optional


class SimulationManager:
    """Business logic for simulation calculations (UI-agnostic)."""

    def __init__(self, app=None):
        self.app = app
        self._observers = []
        self.geometries = []
        self.interfaces = []
        self.materials: Dict[str, Dict[str, float]] = {}
        self.tims: List[Dict[str, object]] = []
        self.forces: List[float] = []

    # Observer pattern (not heavily used yet)
    def subscribe(self, cb: Callable[[str, dict], None]):
        self._observers.append(cb)

    def _notify(self, event_type: str, data: Optional[dict] = None):
        payload = data or {}
        for cb in list(self._observers):
            try:
                cb(event_type, payload)
            except Exception:
                pass

    # Context setters
    def set_context(self, geometries, interfaces, materials, tims, forces: List[float]):
        self.geometries = geometries or []
        self.interfaces = interfaces or []
        self.materials = materials or {}
        self.tims = tims or []
        self.forces = forces or []
        self._notify('sim_context_set', {'geoms': len(self.geometries), 'interfaces': len(self.interfaces)})

    # Interface params (SI units)
    def get_interface_params(self, iface) -> Optional[dict]:
        name_top = iface.geom_top.name
        name_bottom = iface.geom_bottom.name
        mat_top = self.materials.get(name_top, {})
        mat_bottom = self.materials.get(name_bottom, {})

        try:
            def get_val(d, k, scale=1.0):
                return float(d.get(k, 0)) * scale

            sig_1 = get_val(mat_top, 'sigma', 1e-6)
            sig_2 = get_val(mat_bottom, 'sigma', 1e-6)
            sig_s = math.sqrt(sig_1**2 + sig_2**2)

            m_1 = get_val(mat_top, 'm')
            m_2 = get_val(mat_bottom, 'm')
            m_s = math.sqrt(m_1**2 + m_2**2)

            k_1 = get_val(mat_top, 'k')
            k_2 = get_val(mat_bottom, 'k')
            k_s = (2 * k_1 * k_2) / (k_1 + k_2) if (k_1 + k_2) > 0 else 0

            e_1 = get_val(mat_top, 'young', 1e9)
            e_2 = get_val(mat_bottom, 'young', 1e9)
            v_1 = get_val(mat_top, 'poisson')
            v_2 = get_val(mat_bottom, 'poisson')
            denom = e_2 * (1 - v_1**2) + e_1 * (1 - v_2**2)
            e_s = (e_1 * e_2) / denom if denom > 0 else 0

            hc_1 = get_val(mat_top, 'hc', 1e6)
            hc_2 = get_val(mat_bottom, 'hc', 1e6)
            valid_hcs = [h for h in (hc_1, hc_2) if h > 0]
            hc_soft = min(valid_hcs) if valid_hcs else 0

            return {
                'name': f"{name_top} → {name_bottom}",
                'sig_s': sig_s,
                'm_s': m_s,
                'k_s': k_s,
                'e_s': e_s,
                'hc_soft': hc_soft,
                'A_nom': getattr(iface, 'A_nominal', 0) or 0
            }
        except Exception:
            return None

    # Model kernels
    @staticmethod
    def calc_mikic_elastic(params, P):
        k_s, m_s, sig_s, e_s = params['k_s'], params['m_s'], params['sig_s'], params['e_s']
        if sig_s > 0 and m_s > 0 and e_s > 0:
            inner = (math.sqrt(2) * P) / (m_s * e_s)
            if inner > 0:
                return 1.54 * k_s * (m_s / sig_s) * (inner ** 0.94)
        return 0.0

    @staticmethod
    def calc_mikic_plastic(params, P):
        k_s, m_s, sig_s, hc = params['k_s'], params['m_s'], params['sig_s'], params['hc_soft']
        if sig_s > 0 and m_s > 0 and hc > 0:
            rel_p = P / hc
            if rel_p > 0:
                return 1.13 * k_s * (m_s / sig_s) * (rel_p ** 0.94)
        return 0.0

    @staticmethod
    def calc_cmy(params, P):
        k_s, m_s, sig_s, hc = params['k_s'], params['m_s'], params['sig_s'], params['hc_soft']
        if sig_s > 0 and m_s > 0 and hc > 0:
            rel_p = P / hc
            if rel_p > 0:
                return 1.45 * k_s * (m_s / sig_s) * (rel_p ** 0.985)
        return 0.0

    @staticmethod
    def calc_yovanovich(params, P):
        k_s, m_s, sig_s, hc = params['k_s'], params['m_s'], params['sig_s'], params['hc_soft']
        if sig_s > 0 and m_s > 0 and hc > 0:
            rel_p = P / hc
            if rel_p > 0:
                return 1.25 * k_s * (m_s / sig_s) * (rel_p ** 0.95)
        return 0.0

    # Report: microsurface
    def microsurface_report(self) -> List[dict]:
        data = []
        tcr_ifaces = [i for i in self.interfaces if getattr(i, 'has_tcr', False)]
        for iface in tcr_ifaces:
            p = self.get_interface_params(iface)
            if p:
                data.append(p)
        return data

    # Main simulation runner
    def run_model(self, model_name: str, calc_func: Callable, interface_configs: dict, thot: float, tcold: float):
        if not interface_configs:
            return False, 'Brak skonfigurowanych interfejsów.', [], []
        if not self.forces:
            return False, 'Brak zdefiniowanych sił w systemie.', [], []

        results_tcr = []
        iface_tcr_accumulation = {}

        for iface_idx, cfg in interface_configs.items():
            iface = cfg['interface']
            params = self.get_interface_params(iface)
            if not params:
                continue

            tim_name = cfg['tim_var'].get()
            selected_tim = next((t for t in self.tims if t.get('name') == tim_name), None)

            user_blt_str = cfg['thickness_entry'].get().replace(',', '.')
            is_gas = (selected_tim.get('type') == 'gas') if selected_tim else False
            is_press_dep = selected_tim.get('pressure_dependent', False) if selected_tim else False

            for force_val in self.forces:
                A_nom = params['A_nom']
                if A_nom <= 0:
                    continue
                Pressure = force_val / A_nom

                h_c = calc_func(params, Pressure)

                h_int = 0.0
                if selected_tim:
                    k_tim = float(selected_tim.get('k', 0))
                    if is_gas and is_press_dep:
                        hc_soft = params['hc_soft']
                        sig_s = params['sig_s']
                        if hc_soft > 0 and sig_s > 0 and Pressure > 0:
                            try:
                                delta = 1.53 * sig_s * ((Pressure / hc_soft) ** -0.097)
                                if delta > 0:
                                    h_int = k_tim / delta
                            except Exception:
                                h_int = 0.0
                    else:
                        try:
                            blt_val = float(user_blt_str)
                            if blt_val > 0:
                                h_int = k_tim / blt_val
                        except ValueError:
                            h_int = 0.0

                h_eff = h_c + h_int
                R_c = 1.0 / (h_c * A_nom) if h_c > 0 else float('inf')
                R_int = 1.0 / (h_int * A_nom) if h_int > 0 else float('inf')

                pct_styku = 0.0
                if params['hc_soft'] > 0:
                    pct_styku = min(100.0, (Pressure / params['hc_soft']) * 100.0)
                pct_int = 100.0 - pct_styku

                if h_eff > 0:
                    R_eff = 1.0 / (h_eff * A_nom)
                    TCR = R_eff
                    K_eff = 0.0001 / (TCR * A_nom)
                else:
                    R_eff = float('inf')
                    TCR = float('inf')
                    K_eff = 0.0

                results_tcr.append({
                    'force_N': force_val,
                    'interface': params['name'],
                    'pressure_Pa': Pressure,
                    'pct_styku': pct_styku,
                    'pct_int': pct_int,
                    'h_c': h_c,
                    'R_c': R_c,
                    'h_int': h_int,
                    'R_int': R_int,
                    'h_eff': h_eff,
                    'TCR': TCR,
                    'K': K_eff
                })

                iface_tcr_accumulation.setdefault(params['name'], []).append({'force': force_val, 'R_val': TCR})

        results_q = self._calculate_system_q(self.forces, iface_tcr_accumulation, thot, tcold)
        return True, 'OK', results_tcr, results_q

    def _calculate_system_q(self, forces, tcr_data, thot, tcold):
        geoms = self.geometries or []
        R_bulk_total = 0.0
        for g in geoms:
            try:
                mat = self.materials.get(g.name, {})
                k = float(mat.get('k', 0))
                if k > 0:
                    area = float(g.length) * float(g.width)
                    R_bulk_total += float(g.height) / (k * area)
            except Exception:
                pass

        q_rows = []
        dT = abs(thot - tcold)
        for f in forces:
            sum_R_interface = 0.0
            valid = True
            found_interfaces = 0
            for iface_name, entries in tcr_data.items():
                entry = next((e for e in entries if abs(e['force'] - f) < 1e-9), None)
                if entry:
                    if entry['R_val'] == float('inf'):
                        valid = False
                    else:
                        sum_R_interface += entry['R_val']
                    found_interfaces += 1
            if not valid or found_interfaces == 0:
                R_total = float('inf')
                Q = 0.0
            else:
                R_total = R_bulk_total + sum_R_interface
                Q = dT / R_total if R_total > 0 else 0.0

            q_rows.append({
                'force_N': f,
                'R_U': R_bulk_total,
                'TCRsum': sum_R_interface,
                'R_total': R_total,
                'Q': Q
            })
        return q_rows

    def export_results(self, model_name: str, tcr_rows: List[dict], q_rows: List[dict]):
        tag = model_name.lower().replace(' ', '_').replace('-', '_')
        output_dir = os.path.join(os.getcwd(), 'results', tag)
        os.makedirs(output_dir, exist_ok=True)
        path_tcr = os.path.join(output_dir, "TCR.csv")
        path_q = os.path.join(output_dir, "Q.csv")

        try:
            with open(path_tcr, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                headers = [
                    'Force[N]', 'Interface', 'ciśnienie [Pa]', '%styku', '%int',
                    'hc [W/m^2K]', 'Rc [K/W]', 'h_int[W/m^2K]', 'R_int [K/W]',
                    'h_eff [W/m^2K]', 'TCR [K/W]', 'K_warstwy'
                ]
                writer.writerow(headers)
                for r in tcr_rows:
                    writer.writerow([
                        r['force_N'], r['interface'], f"{r['pressure_Pa']:.4f}", f"{r['pct_styku']:.2f}", f"{r['pct_int']:.2f}",
                        f"{r['h_c']:.4f}", (f"{r['R_c']:.4f}" if r['R_c'] != float('inf') else 'INF'),
                        f"{r['h_int']:.4f}", (f"{r['R_int']:.4f}" if r['R_int'] != float('inf') else 'INF'),
                        f"{r['h_eff']:.4f}", (f"{r['TCR']:.4f}" if r['TCR'] != float('inf') else 'INF'), f"{r['K']:.4f}"
                    ])
        except Exception as e:
            self._notify('export_error', {'target': 'TCR', 'error': str(e)})

        try:
            with open(path_q, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                headers = ['Force[N]', 'R_U [K/W]', 'TCRsum [K/W]', 'Q [W]']
                writer.writerow(headers)
                for r in q_rows:
                    writer.writerow([
                        r['force_N'], f"{r['R_U']:.4f}", f"{r['TCRsum']:.4f}", f"{r['Q']:.4f}"
                    ])
        except Exception as e:
            self._notify('export_error', {'target': 'Q', 'error': str(e)})

        self._notify('export_done', {'path_tcr': path_tcr, 'path_q': path_q})
        return path_tcr, path_q
