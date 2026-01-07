"""
Simulation tab for thermal resistance calculations.
Handles TIM assignment, boundary conditions, microsurface reports, and simulation execution.
Refactored for maintainability and modularity.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os
from controllers import SimulationManager

class SimulationTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Manager for business logic
        self.manager = SimulationManager(app=self.app)
        self.manager.subscribe(self._on_manager_event)

        # UI state
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
                    is_paste = (sel_tim.get('type') == 'paste')
                    is_gas = (sel_tim.get('type') == 'gas')
                    is_press_dep = sel_tim.get('pressure_dependent', False)

                    if is_gas and is_press_dep:
                        # Gas + Pressure Dependent -> Calculated via Antonetti
                        l.config(text='Szczelina [m]:')
                        e.delete(0, 'end')
                        e.insert(0, 'Auto')
                        e.state(['disabled'])
                    elif is_paste:
                        # Paste -> BLT required
                        l.config(text='BLT [m]:')
                        e.state(['!disabled'])
                        if e.get() == 'Auto': e.delete(0, 'end')
                    else:
                        # Gas + Not Pressure Dependent -> Fixed gap required
                        l.config(text='Szczelina [m]:')
                        e.state(['!disabled'])
                        if e.get() == 'Auto': e.delete(0, 'end')

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
        # Delegated to manager for business logic
        return self.manager.get_interface_params(iface)

    # =========================================================================
    #  MODELS (Callback strategies)
    # =========================================================================

    def _calc_hc_mikic_elastic(self, params, P):
        return self.manager.calc_mikic_elastic(params, P)

    def _calc_hc_mikic_plastic(self, params, P):
        return self.manager.calc_mikic_plastic(params, P)

    def _calc_hc_cmy(self, params, P):
        return self.manager.calc_cmy(params, P)

    def _calc_hc_yovanovich(self, params, P):
        return self.manager.calc_yovanovich(params, P)

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

        # Set context on manager
        materials = getattr(self.app, 'system_materials', {}) or {}
        tims_list = getattr(self.app, 'system_tims', []) or []
        geoms = getattr(self.app, 'system_geometries', []) or []
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        self.manager.set_context(geoms, interfaces, materials, tims_list, forces)

        ok, msg, results_tcr, results_q = self.manager.run_model(model_name, calculation_func, self.interface_config, thot, tcold)
        if not ok:
            if 'sił' in msg:
                messagebox.showwarning('Błąd', msg)
            else:
                messagebox.showerror('Błąd', msg)
            return

        path_tcr, path_q = self.manager.export_results(model_name, results_tcr, results_q)
        self.app.log(f"Sim {model_name} completed. Files saved.")
        self._show_results_window(f"{model_name} - Szczegóły (TCR)", results_tcr, 
                                  ['force_N', 'interface', 'pressure_Pa', 'pct_styku', 'pct_int', 'h_c', 'R_c', 'h_int', 'R_int', 'h_eff', 'TCR', 'K'])
        self._show_results_window(f"{model_name} - Podsumowanie (Q)", results_q, 
                                  ['force_N', 'R_U', 'TCRsum', 'Q'])

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
        # Deprecated (handled in manager)
        return self.manager._calculate_system_q(forces, tcr_data, thot, tcold)

    def _export_and_show_results(self, model_name, tcr_rows, q_rows):
        """Handles CSV export and window display with specific requested format."""
        # Filenames
        tag = model_name.lower().replace(' ', '_').replace('-', '_')

        output_dir = os.path.join(os.getcwd(), 'results', tag)
        os.makedirs(output_dir, exist_ok=True)

        path_tcr = os.path.join(output_dir, f"TCR.csv")
        path_q = os.path.join(output_dir, f"Q.csv")

        # --- Save TCR CSV ---
        # Requested Format: ciśnienie [Pa], %styku, %int, hc [W/m^2K], Rc [K/W], h_int[W/m^2K], R_int [K/W], h_eff [W/m^2K, TCR [K/W], K_warstwy
        # (Keeping Force/Interface at the start for data integrity)
        try:
            with open(path_tcr, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                headers = [
                    'Force[N]', 'Interface', 
                    'ciśnienie [Pa]', '%styku', '%int', 
                    'hc [W/m^2K]', 'Rc [K/W]', 
                    'h_int[W/m^2K]', 'R_int [K/W]', 
                    'h_eff [W/m^2K]', 'TCR [K/W]', 'K_warstwy'
                ]
                writer.writerow(headers)
                
                for r in tcr_rows:
                    writer.writerow([
                        r['force_N'], 
                        r['interface'], 
                        f"{r['pressure_Pa']:.4f}",
                        f"{r['pct_styku']:.2f}",
                        f"{r['pct_int']:.2f}",
                        f"{r['h_c']:.4f}",
                        (f"{r['R_c']:.4f}" if r['R_c'] != float('inf') else 'INF'),
                        f"{r['h_int']:.4f}",
                        (f"{r['R_int']:.4f}" if r['R_int'] != float('inf') else 'INF'),
                        f"{r['h_eff']:.4f}",
                        (f"{r['TCR']:.4f}" if r['TCR'] != float('inf') else 'INF'),
                        f"{r['K']:.4f}"
                    ])
        except Exception as e:
            self.app.log(f"Error saving TCR: {e}")

        # --- Save Q CSV ---
        # Requested Format: R_U (całkowity opor przenikania)[K/W], TCRsum (całkowity opór tcr w systemie,suma wszystkich TCR) [K/W], Q [W]
        try:
            with open(path_q, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                headers = ['Force[N]', 'R_U [K/W]', 'TCRsum [K/W]', 'Q [W]']
                writer.writerow(headers)
                
                for r in q_rows:
                    writer.writerow([
                        r['force_N'], 
                        f"{r['R_U']:.4f}", 
                        f"{r['TCRsum']:.4f}",
                        f"{r['Q']:.4f}"
                    ])
        except Exception as e:
            self.app.log(f"Error saving Q: {e}")

        self.app.log(f"Sim {model_name} completed. Files saved.")
        
        # Show Result Windows (mapped keys to display)
        # handled in run_generic

    def _show_results_window(self, title, data, keys):
        win = tk.Toplevel(self)
        win.title(title)
        win.geometry("1100x400") # Wider for more columns
        
        tree = ttk.Treeview(win, columns=keys, show='headings')
        for k in keys:
            tree.heading(k, text=k)
            tree.column(k, width=80)
        
        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(win, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        tree.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')

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
        geoms = getattr(self.app, 'system_geometries', []) or []
        self.manager.set_context(geoms, interfaces, materials, getattr(self.app, 'system_tims', []) or [], self._get_forces())
        data = self.manager.microsurface_report()
        if not data:
            messagebox.showinfo("Info", "Brak interfejsów do raportowania.")
            return
        self._show_results_window("Raport Mikropowierzchni", data, ['name', 'sig_s', 'm_s', 'k_s', 'e_s', 'hc_soft'])

    # --- Manager events ---
    def _on_manager_event(self, event_type, data):
        # currently UI handled directly; hook reserved for future updates
        pass