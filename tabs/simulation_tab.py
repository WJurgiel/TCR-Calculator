"""
Simulation tab for thermal resistance calculations.
Handles TIM assignment, boundary conditions, microsurface reports, and simulation execution.
Refactored for maintainability and modularity.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os
import math

class SimulationTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Storage: interface_idx -> {'tim_name': str, 'layer_thickness': float, ...}
        self.interface_config = {}

        self._setup_ui()
        
        # Load interfaces when tab is shown
        self.bind('<Visibility>', self._on_visibility)

    def _setup_ui(self):
        """Builds the UI components."""
        # Header
        frm_header = ttk.Frame(self)
        frm_header.pack(fill='x', padx=10, pady=8)
        ttk.Label(frm_header, text='Symulacja — Parametry i modele', font=('', 12, 'bold')).pack(side='left')

        # 1. Interface & TIM Assignment
        frm_tim = ttk.LabelFrame(self, text='1. Przypisanie TIM i parametry szczeliny', padding=10)
        frm_tim.pack(fill='both', expand=True, padx=10, pady=5)

        # Scrollable container setup
        self.canvas = tk.Canvas(frm_tim, height=200)
        vsb = ttk.Scrollbar(frm_tim, orient='vertical', command=self.canvas.yview)
        self.scroll_inner = ttk.Frame(self.canvas)
        
        self.canvas.configure(yscrollcommand=vsb.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        
        self.window_id = self.canvas.create_window((0, 0), window=self.scroll_inner, anchor='nw')
        
        self.scroll_inner.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfig(self.window_id, width=e.width))

        # 2. Boundary Conditions
        frm_bc = ttk.LabelFrame(self, text='2. Warunki brzegowe', padding=10)
        frm_bc.pack(fill='x', padx=10, pady=5)

        grid_frm = ttk.Frame(frm_bc)
        grid_frm.pack(fill='x')
        
        ttk.Label(grid_frm, text='T_hot [K] (góra):').grid(row=0, column=0, padx=5, pady=5)
        self.ent_thot = ttk.Entry(grid_frm, width=10)
        self.ent_thot.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(grid_frm, text='T_cold [K] (dół):').grid(row=0, column=2, padx=5, pady=5)
        self.ent_tcold = ttk.Entry(grid_frm, width=10)
        self.ent_tcold.grid(row=0, column=3, padx=5, pady=5)

        # 3. Actions & Models
        frm_actions = ttk.LabelFrame(self, text='3. Obliczenia i Raporty', padding=10)
        frm_actions.pack(fill='x', padx=10, pady=10)

        ttk.Button(frm_actions, text='Raport parametrów mikrostyków', 
                   command=self._show_microsurface_report).pack(side='left', padx=5)
        
        ttk.Separator(frm_actions, orient='vertical').pack(side='left', fill='y', padx=10)
        
        ttk.Label(frm_actions, text='Uruchom model:').pack(side='left', padx=5)

        # Model buttons
        ttk.Button(frm_actions, text='Mikic (Sprężyste)', 
                   command=lambda: self._run_generic_simulation('Mikic-Sprężyste', self._calc_hc_mikic_elastic)).pack(side='left', padx=2)
        
        ttk.Button(frm_actions, text='Mikic (Plastyczne)', 
                   command=lambda: self._run_generic_simulation('Mikic-Plastyczne', self._calc_hc_mikic_plastic)).pack(side='left', padx=2)
        
        ttk.Button(frm_actions, text='CMY', 
                   command=lambda: self._run_generic_simulation('CMY', self._calc_hc_cmy)).pack(side='left', padx=2)
        
        ttk.Button(frm_actions, text='Yovanovich', 
                   command=lambda: self._run_generic_simulation('Yovanovich', self._calc_hc_yovanovich)).pack(side='left', padx=2)

    def _on_visibility(self, event):
        self._rebuild_interface_list()

    def _rebuild_interface_list(self):
        """Rebuilds the interface TIM assignment list dynamically."""
        for w in self.scroll_inner.winfo_children():
            w.destroy()

        interfaces = getattr(self.app, 'system_interfaces', []) or []
        tcr_interfaces = [(idx, it) for idx, it in enumerate(interfaces) if getattr(it, 'has_tcr', False)]

        if not tcr_interfaces:
            ttk.Label(self.scroll_inner, text='(Brak zdefiniowanych interfejsów z TCR)').pack(padx=10, pady=10)
            return

        tims = getattr(self.app, 'system_tims', []) or []
        tim_names = [tim.get('name', f'TIM_{i}') for i, tim in enumerate(tims)]

        self.interface_config = {}

        for row_idx, (iface_idx, iface) in enumerate(tcr_interfaces):
            row_frame = ttk.Frame(self.scroll_inner)
            row_frame.pack(fill='x', expand=True, pady=2)

            # Name
            iface_name = f"{iface.geom_top.name} → {iface.geom_bottom.name}"
            ttk.Label(row_frame, text=iface_name, width=30).pack(side='left', padx=5)

            # TIM Dropdown
            var_tim = tk.StringVar()
            if tim_names: var_tim.set(tim_names[0])
            
            cmb = ttk.Combobox(row_frame, textvariable=var_tim, values=tim_names, state='readonly', width=15)
            cmb.pack(side='left', padx=5)

            # Thickness Entry
            lbl_th = ttk.Label(row_frame, text='Grubość [m]:')
            lbl_th.pack(side='left', padx=5)
            
            ent_th = ttk.Entry(row_frame, width=10)
            ent_th.pack(side='left', padx=5)

            # Logic to show/hide thickness based on TIM type
            def update_visibility(event=None, v_tim=var_tim, l=lbl_th, e=ent_th):
                sel_name = v_tim.get()
                sel_tim = next((t for t in tims if t.get('name') == sel_name), None)
                if sel_tim:
                    # Logic: if pressure dependent -> hide manual thickness? 
                    # Assuming standard behavior: always show thickness unless it's strictly calculated internally
                    # For now keeping logic simple:
                    if sel_tim.get('type') == 'paste':
                        l.config(text='BLT [m]:')
                    else:
                        l.config(text='Szczelina [m]:')
            
            cmb.bind('<<ComboboxSelected>>', update_visibility)
            update_visibility() # Init

            self.interface_config[iface_idx] = {
                'interface': iface,
                'tim_var': var_tim,
                'thickness_entry': ent_th
            }

    # =========================================================================
    #  CORE CALCULATION LOGIC (Helpers)
    # =========================================================================

    def _get_interface_params(self, iface, materials):
        """
        Extracts and calculates effective parameters for a single interface.
        Returns a dictionary with SI units.
        """
        name_top = iface.geom_top.name
        name_bottom = iface.geom_bottom.name
        
        mat_top = materials.get(name_top, {})
        mat_bottom = materials.get(name_bottom, {})

        try:
            # Helper to safely get float
            def get_val(d, k, scale=1.0): 
                return float(d.get(k, 0)) * scale

            # 1. Roughness (sigma) [µm -> m]
            sig_1 = get_val(mat_top, 'sigma', 1e-6)
            sig_2 = get_val(mat_bottom, 'sigma', 1e-6)
            sig_s = math.sqrt(sig_1**2 + sig_2**2)

            # 2. Slope (m) [absolute]
            m_1 = get_val(mat_top, 'm')
            m_2 = get_val(mat_bottom, 'm')
            m_s = math.sqrt(m_1**2 + m_2**2)

            # 3. Thermal Conductivity (k) [W/mK]
            k_1 = get_val(mat_top, 'k')
            k_2 = get_val(mat_bottom, 'k')
            # Harmonic mean for contact
            k_s = (2 * k_1 * k_2) / (k_1 + k_2) if (k_1 + k_2) > 0 else 0

            # 4. Young's Modulus (E) [GPa -> Pa] & Poisson
            e_1 = get_val(mat_top, 'young', 1e9)
            e_2 = get_val(mat_bottom, 'young', 1e9)
            v_1 = get_val(mat_top, 'poisson')
            v_2 = get_val(mat_bottom, 'poisson')
            
            denom = e_2 * (1 - v_1**2) + e_1 * (1 - v_2**2)
            e_s = (e_1 * e_2) / denom if denom > 0 else 0

            # 5. Microhardness (Hc) [MPa -> Pa]
            # Use the softer material
            hc_1 = get_val(mat_top, 'hc', 1e6)
            hc_2 = get_val(mat_bottom, 'hc', 1e6)
            # Filter out zeros if any material data is missing
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
        except Exception as e:
            print(f"Error extracting params: {e}")
            return None

    # =========================================================================
    #  MODELS (Callback strategies)
    # =========================================================================

    def _calc_hc_mikic_elastic(self, params, P):
        k_s, m_s, sig_s, e_s = params['k_s'], params['m_s'], params['sig_s'], params['e_s']
        
        if sig_s > 0 and m_s > 0 and e_s > 0:
            inner = (math.sqrt(2) * P) / (m_s * e_s)
            if inner > 0:
                return 1.54 * k_s * (m_s / sig_s) * (inner ** 0.94)
        return 0.0

    def _calc_hc_mikic_plastic(self, params, P):
        k_s, m_s, sig_s, hc = params['k_s'], params['m_s'], params['sig_s'], params['hc_soft']
        
        if sig_s > 0 and m_s > 0 and hc > 0:
            rel_p = P / hc
            if rel_p > 0:
                return 1.13 * k_s * (m_s / sig_s) * (rel_p ** 0.94)
        return 0.0

    def _calc_hc_cmy(self, params, P):
        k_s, m_s, sig_s, hc = params['k_s'], params['m_s'], params['sig_s'], params['hc_soft']

        if sig_s > 0 and m_s > 0 and hc > 0:
            rel_p = P / hc
            if rel_p > 0:
                return 1.45 * k_s * (m_s / sig_s) * (rel_p ** 0.985)
        return 0.0

    def _calc_hc_yovanovich(self, params, P):
        k_s, m_s, sig_s, hc = params['k_s'], params['m_s'], params['sig_s'], params['hc_soft']

        if sig_s > 0 and m_s > 0 and hc > 0:
            rel_p = P / hc
            if rel_p > 0:
                return 1.25 * k_s * (m_s / sig_s) * (rel_p ** 0.95)

    # =========================================================================
    #  GENERIC SIMULATION RUNNER
    # =========================================================================

    def _run_generic_simulation(self, model_name, calculation_func):
        """
        Generic method to run any contact model.
        
        Args:
            model_name (str): Name for display/files.
            calculation_func (callable): Function(params, Pressure_Pa) -> h_c [W/m2K]
        """
        # 1. Validation
        if not self.interface_config:
            messagebox.showwarning('Błąd', 'Brak skonfigurowanych interfejsów.')
            return
        
        try:
            thot = float(self.ent_thot.get().replace(',', '.'))
            tcold = float(self.ent_tcold.get().replace(',', '.'))
        except ValueError:
            messagebox.showerror('Błąd', 'Sprawdź temperatury T_hot i T_cold.')
            return

        forces = self._get_forces()
        if not forces:
            messagebox.showwarning('Błąd', 'Brak zdefiniowanych sił w systemie.')
            return

        # 2. Preparation
        materials = getattr(self.app, 'system_materials', {}) or {}
        tims_list = getattr(self.app, 'system_tims', []) or []
        
        results_tcr = []
        iface_tcr_accumulation = {} # For system Q calculation
        
        # 3. Loop through Interfaces
        # We iterate over stored config which maps iface_idx -> user selection
        for iface_idx, cfg in self.interface_config.items():
            iface = cfg['interface']
            
            # Get processed params (SI units)
            params = self._get_interface_params(iface, materials)
            if not params:
                continue

            # Get TIM Info
            tim_name = cfg['tim_var'].get()
            selected_tim = next((t for t in tims_list if t['name'] == tim_name), None)
            
            try:
                blt = float(cfg['thickness_entry'].get().replace(',', '.'))
            except ValueError:
                blt = 0.0 # Default or error

            # 4. Loop through Forces
            for force_val in forces:
                A_nom = params['A_nom']
                if A_nom <= 0: continue

                Pressure = force_val / A_nom

                # --- A. Contact Conductance (Model Specific) ---
                h_c = calculation_func(params, Pressure)

                # --- B. Gap Conductance (TIM) ---
                h_int = 0.0
                if selected_tim and blt > 0:
                    k_tim = float(selected_tim.get('k', 0))
                    h_int = k_tim / blt
                
                # --- C. Effective Resistance ---
                # h_eff = h_c + h_int (parallel conductance -> series resistance in concept of layers?)
                # Actually for contact interface: h_total = h_contact + h_gap (parallel paths)
                # So R_eff = 1 / ( (h_c + h_int) * Area )
                
                h_eff = h_c + h_int
                
                if h_eff > 0:
                    R_eff = 1.0 / (h_eff * A_nom)
                    TCR = R_eff
                    K_eff = 0.0001 / (TCR * A_nom) # Just a legacy metric?
                else:
                    R_eff = float('inf')
                    TCR = float('inf')
                    K_eff = 0.0

                # Store result row
                results_tcr.append({
                    'force_N': force_val,
                    'interface': params['name'],
                    'pressure_Pa': Pressure,
                    'h_c': h_c,
                    'h_int': h_int,
                    'h_eff': h_eff,
                    'TCR': TCR,
                    'K': K_eff
                })

                # Accumulate for Q calculation
                key = params['name']
                iface_tcr_accumulation.setdefault(key, []).append({
                    'force': force_val, 
                    'R_val': TCR
                })

        # 5. System Calculations (Q)
        results_q = self._calculate_system_q(forces, iface_tcr_accumulation, thot, tcold, materials)

        # 6. Export & Show
        self._export_and_show_results(model_name, results_tcr, results_q)

    def _get_forces(self):
        """Parses forces from app system."""
        raw = getattr(self.app, 'system_forces', []) or []
        vals = []
        for f in raw:
            try:
                v = float(f.get('value', f)) if isinstance(f, dict) else float(f)
                vals.append(v)
            except: pass
        return vals

    def _calculate_system_q(self, forces, tcr_data, thot, tcold, materials):
        """Calculates total system resistance and heat flow for each force case."""
        # 1. Bulk Resistance (R_bulk)
        geoms = getattr(self.app, 'system_geometries', []) or []
        R_bulk_total = 0.0
        
        for g in geoms:
            try:
                mat = materials.get(g.name, {})
                k = float(mat.get('k', 0))
                if k > 0:
                    area = float(g.length) * float(g.width)
                    R_bulk_total += float(g.height) / (k * area)
            except: pass

        # 2. Combine with TCR for each force
        q_rows = []
        dT = abs(thot - tcold)
        
        # Determine minimal area for h_sys calculation (conventional)
        # Just taking the first interface area or generic approach
        # For simplicity, we just report R_total and Q
        
        for f in forces:
            sum_R_interface = 0.0
            valid = True
            
            # Sum up TCR of all interfaces for this force
            # Note: This assumes SERIES connection of all interfaces
            found_interfaces = 0
            for iface_name, entries in tcr_data.items():
                # Find entry for this force
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
                'R_bulk': R_bulk_total,
                'R_iface': sum_R_interface,
                'R_total': R_total,
                'Q': Q
            })
            
        return q_rows

    def _export_and_show_results(self, model_name, tcr_rows, q_rows):
        """Handles CSV export and window display."""
        # Filenames
        tag = model_name.lower().replace(' ', '_').replace('-', '_')

        output_dir = os.path.join(os.getcwd(), 'results', tag)
        os.makedirs(output_dir, exist_ok=True)

        path_tcr = os.path.join(output_dir, f"TCR.csv")
        path_q = os.path.join(output_dir, f"Q.csv")

        # Save TCR
        try:
            with open(path_tcr, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Force[N]', 'Interface', 'Pressure[Pa]', 'h_contact', 'h_gap', 'h_eff', 'R_th[K/W]', 'K'])
                for r in tcr_rows:
                    writer.writerow([
                        r['force_N'], r['interface'], f"{r['pressure_Pa']:.4f}",
                        f"{r['h_c']:.4f}", f"{r['h_int']:.4f}", f"{r['h_eff']:.4f}",
                        (f"{r['TCR']:.4f}" if r['TCR'] != float('inf') else 'INF'),
                        f"{r['K']:.4f}"
                    ])
        except Exception as e:
            self.app.log(f"Error saving TCR: {e}")

        # Save Q
        try:
            with open(path_q, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Force[N]', 'R_Bulk', 'R_Interfaces', 'R_Total', 'Q[W]'])
                for r in q_rows:
                    writer.writerow([
                        r['force_N'], f"{r['R_bulk']:.4f}", f"{r['R_iface']:.4f}",
                        (f"{r['R_total']:.4f}" if r['R_total'] != float('inf') else 'INF'),
                        f"{r['Q']:.4f}"
                    ])
        except Exception as e:
            self.app.log(f"Error saving Q: {e}")

        self.app.log(f"Sim {model_name} completed. Files saved.")
        
        # Show Result Windows
        self._show_results_window(f"{model_name} - Szczegóły (TCR)", tcr_rows, 
                                  ['force_N', 'interface', 'pressure_Pa', 'h_c', 'h_int', 'h_eff', 'TCR', 'K'])
        self._show_results_window(f"{model_name} - Podsumowanie (Q)", q_rows, 
                                  ['force_N', 'R_bulk', 'R_iface', 'R_total', 'Q'])

    def _show_results_window(self, title, data, keys):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("800x400")
        
        tree = ttk.Treeview(win, columns=keys, show='headings')
        for k in keys:
            tree.heading(k, text=k)
            tree.column(k, width=90)
        
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')

        for item in data:
            vals = []
            for k in keys:
                v = item.get(k)
                if isinstance(v, float):
                    if v == float('inf'): vals.append("INF")
                    else: vals.append(f"{v:.4g}")
                else:
                    vals.append(str(v))
            tree.insert('', 'end', values=vals)

    def _show_microsurface_report(self):
        """Displays calculated surface parameters."""
        materials = getattr(self.app, 'system_materials', {}) or {}
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        tcr_ifaces = [i for i in interfaces if getattr(i, 'has_tcr', False)]
        
        data = []
        for iface in tcr_ifaces:
            p = self._get_interface_params(iface, materials)
            if p:
                data.append(p)
        
        if not data:
            messagebox.showinfo("Info", "Brak interfejsów do raportowania.")
            return

        self._show_results_window("Raport Mikropowierzchni", data, ['name', 'sig_s', 'm_s', 'k_s', 'e_s', 'hc_soft'])