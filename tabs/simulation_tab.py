"""
Simulation tab for thermal resistance calculations.
Handles TIM assignment, boundary conditions, microsurface reports, and simulation execution.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os


class SimulationTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Storage: interface_idx -> {'tim_name': str, 'layer_thickness': float, ...}
        self.interface_config = {}

        # Header
        frm_header = ttk.Frame(self)
        frm_header.pack(fill='x', padx=10, pady=8)

        lbl_title = ttk.Label(frm_header, text='Symulacja — Parametry symulacji i wyniki')
        lbl_title.pack(side='left', anchor='w')

        # Scrollable container for interface TIM assignments
        frm_scroll_label = ttk.Frame(self)
        frm_scroll_label.pack(fill='x', padx=10, pady=4)
        ttk.Label(frm_scroll_label, text='1. Przypisz TIM-y do interfejsów z TCR:', font=('', 9, 'bold')).pack(anchor='w')

        self.frm_interfaces = ttk.Frame(self)
        self.frm_interfaces.pack(fill='both', expand=True, padx=10, pady=4)

        # Boundary conditions
        frm_bc = ttk.LabelFrame(self, text='2. Warunki brzegowe', padding=10)
        frm_bc.pack(fill='x', padx=10, pady=10)

        ttk.Label(frm_bc, text='T_hot [K] (góra):').grid(row=0, column=0, sticky='w', padx=4, pady=4)
        self.ent_thot = ttk.Entry(frm_bc, width=15)
        self.ent_thot.grid(row=0, column=1, sticky='w', padx=4, pady=4)
        self.ent_thot.insert(0, '')

        ttk.Label(frm_bc, text='T_cold [K] (dół):').grid(row=1, column=0, sticky='w', padx=4, pady=4)
        self.ent_tcold = ttk.Entry(frm_bc, width=15)
        self.ent_tcold.grid(row=1, column=1, sticky='w', padx=4, pady=4)
        self.ent_tcold.insert(0, '')

        # Action buttons: microsurface report + model buttons
        frm_actions = ttk.Frame(self)
        frm_actions.pack(fill='x', padx=10, pady=10)

        ttk.Button(frm_actions, text='Raport parametrów mikrostyków', 
              command=self._show_microsurface_report).pack(side='left', padx=4)

        # Model buttons in one row
        frm_models = ttk.Frame(frm_actions)
        frm_models.pack(side='left', padx=8)

        ttk.Button(frm_models, text='Mikic-Sprężyste', command=self._run_mikic_spr).pack(side='left', padx=4)
        ttk.Button(frm_models, text='Mikic-Plastyczne', command=self._run_mikic_plast).pack(side='left', padx=4)
        ttk.Button(frm_models, text='CMY', command=lambda: messagebox.showinfo('Info', 'Niezaimplementowane')).pack(side='left', padx=4)
        ttk.Button(frm_models, text='Yovanovich', command=lambda: messagebox.showinfo('Info', 'Niezaimplementowane')).pack(side='left', padx=4)

        # Load interfaces when tab is shown
        self.bind('<Visibility>', self._on_visibility)

    def _on_visibility(self, event):
        """Rebuild interface list when tab becomes visible."""
        self._rebuild_interface_list()

    def _rebuild_interface_list(self):
        """Rebuild the interface TIM assignment list."""
        # Clear container
        for w in self.frm_interfaces.winfo_children():
            w.destroy()

        # Get TCR interfaces
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        tcr_interfaces = [(idx, it) for idx, it in enumerate(interfaces) if getattr(it, 'has_tcr', False)]

        if not tcr_interfaces:
            lbl = ttk.Label(self.frm_interfaces, text='(brak interfejsów z TCR)')
            lbl.pack(padx=10, pady=10)
            return

        # Get available TIMs
        tims = getattr(self.app, 'system_tims', []) or []
        tim_names = [tim.get('name', f'TIM_{i}') for i, tim in enumerate(tims)]

        # Create scrollable canvas for interfaces
        canvas = tk.Canvas(self.frm_interfaces, height=250)
        vsb = ttk.Scrollbar(self.frm_interfaces, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)

        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        # Factory function to create event handler for each interface (prevents closure issues in loop)
        def make_on_tim_selected(lbl, ent, var, tims_list):
            """Factory function to create TIM selection handler with proper closure."""
            def _on_tim_selected(event=None):
                """Update layer thickness label based on selected TIM."""
                selected_tim_name = var.get()
                selected_tim = None
                for tim in tims_list:
                    if tim.get('name') == selected_tim_name:
                        selected_tim = tim
                        break

                if selected_tim:
                    if selected_tim.get('pressure_dependent', False):
                        # Hide for pressure-dependent TIM
                        lbl.grid_remove()
                        ent.grid_remove()
                    else:
                        # Show for pressure-independent TIM
                        lbl.grid()
                        ent.grid()
                        # Update label based on TIM type
                        tim_type = selected_tim.get('type', 'gas')
                        if tim_type == 'paste':
                            lbl.config(text='BLT [m]:')
                        else:
                            lbl.config(text='Grubość szczeliny [m]:')
                else:
                    lbl.grid_remove()
                    ent.grid_remove()
            return _on_tim_selected

        # Build rows for each interface
        self.interface_config = {}
        for row_idx, (iface_idx, iface) in enumerate(tcr_interfaces):
            iface_name = f"{iface.geom_top.name} → {iface.geom_bottom.name}"

            # Interface name (read-only)
            ttk.Label(inner, text=iface_name, font=('', 9)).grid(row=row_idx, column=0, sticky='w', padx=4, pady=4)

            # TIM selection dropdown
            var_tim = tk.StringVar(value=tim_names[0] if tim_names else '')
            cmb_tim = ttk.Combobox(inner, textvariable=var_tim, values=tim_names, state='readonly', width=15)
            cmb_tim.grid(row=row_idx, column=1, sticky='w', padx=4, pady=4)

            # Label and entry for layer thickness (dynamically updated)
            lbl_thick = ttk.Label(inner, text='Grubość szczeliny [m]:', font=('', 9))
            lbl_thick.grid(row=row_idx, column=2, sticky='w', padx=4, pady=4)
            ent_thick = ttk.Entry(inner, width=12)
            ent_thick.grid(row=row_idx, column=3, sticky='w', padx=4, pady=4)
            ent_thick.insert(0, '')

            # Create and bind event handler (factory ensures each interface gets its own handler)
            on_tim_selected = make_on_tim_selected(lbl_thick, ent_thick, var_tim, tims)
            cmb_tim.bind('<<ComboboxSelected>>', on_tim_selected)
            
            # Call initially to set correct label
            on_tim_selected()

            # Store config for this interface
            self.interface_config[iface_idx] = {
                'interface': iface,
                'iface_idx': iface_idx,
                'tim_var': var_tim,
                'thickness_entry': ent_thick,
                'row': row_idx
            }

        # Configure scrolling
        def _on_config_inner(event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas_config(event):
            try:
                canvas.itemconfig(window_id, width=event.width)
            except Exception:
                pass

        inner.bind('<Configure>', _on_config_inner)
        canvas.bind('<Configure>', _on_canvas_config)

    def _show_microsurface_report(self):
        """Generate and display microsurface parameters report for TCR interfaces."""
        # Get TCR interfaces
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        tcr_interfaces = [it for it in interfaces if getattr(it, 'has_tcr', False)]

        if not tcr_interfaces:
            messagebox.showwarning('Brak interfejsów', 'Nie ma żadnych interfejsów z TCR')
            return

        # Get materials
        materials = getattr(self.app, 'system_materials', {}) or {}

        # Build report data
        report_data = []
        for iface in tcr_interfaces:
            try:
                name_top = iface.geom_top.name
                name_bottom = iface.geom_bottom.name
                iface_name = f"{name_top} → {name_bottom}"

                # Get material properties for both geometries
                mat_top = materials.get(name_top, {})
                mat_bottom = materials.get(name_bottom, {})

                # Extract surface parameters
                # Read raw values and convert to SI units
                # sigma provided in µm -> convert to meters
                sig_1 = float(mat_top.get('sigma', 0)) * 1e-6
                sig_2 = float(mat_bottom.get('sigma', 0)) * 1e-6
                # m is unitless (mean slope)
                m_1 = float(mat_top.get('m', 0))
                m_2 = float(mat_bottom.get('m', 0))

                # k in W/mK is OK; young provided in GPa -> convert to Pa
                k_1 = float(mat_top.get('k', 0))
                k_2 = float(mat_bottom.get('k', 0))
                e_1 = float(mat_top.get('young', 0)) * 1e9
                e_2 = float(mat_bottom.get('young', 0)) * 1e9
                v_1 = float(mat_top.get('poisson', 0))
                v_2 = float(mat_bottom.get('poisson', 0))

                # Calculate effective parameters (all in SI)
                sig_s = (sig_1**2 + sig_2**2) ** 0.5
                m_s = (m_1**2 + m_2**2) ** 0.5
                k_s = 2 * k_1 * k_2 / (k_1 + k_2) if (k_1 + k_2) > 0 else 0
                denom = e_2 * (1 - v_1**2) + e_1 * (1 - v_2**2)
                e_s = (e_1 * e_2) / denom if denom > 0 else 0

                report_data.append({
                    'interface': iface_name,
                    'sig_s': sig_s,
                    'm_s': m_s,
                    'k_s': k_s,
                    'e_s': e_s
                })
            except Exception as e:
                self.app.log(f'! Błąd przy obliczaniu parametrów dla interfejsu: {e}')
                continue

        if not report_data:
            messagebox.showerror('Błąd', 'Nie udało się obliczyć parametrów mikrostyków')
            return

        # Show report window
        self._show_microsurface_window(report_data)

    def _show_microsurface_window(self, report_data):
        """Display microsurface report in a new window."""
        report_win = tk.Toplevel(self.app)
        report_win.title('Raport: Parametry mikrostyków')
        report_win.geometry('900x500')

        # Toolbar
        frm_toolbar = ttk.Frame(report_win)
        frm_toolbar.pack(fill='x', padx=10, pady=8)

        ttk.Button(frm_toolbar, text='Export to CSV',
                  command=lambda: self._export_microsurface_csv(report_data)).pack(side='left', padx=4)

        # Table
        frm_table = ttk.Frame(report_win)
        frm_table.pack(fill='both', expand=True, padx=10, pady=10)

        canvas = tk.Canvas(frm_table)
        vsb = ttk.Scrollbar(frm_table, orient='vertical', command=canvas.yview)
        hsb = ttk.Scrollbar(frm_table, orient='horizontal', command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        canvas.pack(side='left', fill='both', expand=True)

        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        # Headers
        headers = ['Interfejs', 'sig_s [m]', 'm_s [rad]', 'k_s [W/mK]', 'E_s [Pa]']
        for col, header_text in enumerate(headers):
            lbl = ttk.Label(inner, text=header_text, font=('', 9, 'bold'), background='lightgray')
            lbl.grid(row=0, column=col, padx=4, pady=2, sticky='we')

        # Data rows
        for row_idx, row_data in enumerate(report_data, start=1):
            ttk.Label(inner, text=row_data['interface']).grid(row=row_idx, column=0, padx=4, pady=2, sticky='w')
            ttk.Label(inner, text=f"{row_data['sig_s']:.4f}").grid(row=row_idx, column=1, padx=4, pady=2)
            ttk.Label(inner, text=f"{row_data['m_s']:.4f}").grid(row=row_idx, column=2, padx=4, pady=2)
            ttk.Label(inner, text=f"{row_data['k_s']:.4f}").grid(row=row_idx, column=3, padx=4, pady=2)
            ttk.Label(inner, text=f"{row_data['e_s']:.4f}").grid(row=row_idx, column=4, padx=4, pady=2)

        # Configure scrolling
        def _on_config_inner(event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas_config(event):
            try:
                canvas.itemconfig(window_id, width=event.width)
            except Exception:
                pass

        inner.bind('<Configure>', _on_config_inner)
        canvas.bind('<Configure>', _on_canvas_config)

    def _export_microsurface_csv(self, report_data):
        """Export microsurface report to CSV."""
        file_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All', '*.*')]
        )
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # Header
                writer.writerow(['Interfejs', 'sig_s [m]', 'm_s [rad]', 'k_s [W/mK]', 'E_s [Pa]'])
                # Data rows
                for row_data in report_data:
                    writer.writerow([
                        row_data['interface'],
                        f"{row_data['sig_s']:.4f}",
                        f"{row_data['m_s']:.4f}",
                        f"{row_data['k_s']:.4f}",
                        f"{row_data['e_s']:.4f}"
                    ])
            
            self.app.log(f'✓ Eksportowano raport mikrostyków do: {os.path.basename(file_path)}')
            messagebox.showinfo('Sukces', f'Raport został wyeksportowany do:\n{file_path}')
        except Exception as e:
            messagebox.showerror('Błąd', f'Nie udało się wyeksportować raportu: {e}')
            self.app.log(f'! Błąd przy eksporcie: {e}')

    def _run_mikic_spr(self):
        """Run Mikic (sprężyste) model and show/export results."""
        # Basic validations
        if not self.interface_config:
            messagebox.showwarning('Błąd', 'Brak interfejsów z TCR do symulacji')
            return

        try:
            thot = float(self.ent_thot.get())
            tcold = float(self.ent_tcold.get())
        except ValueError:
            messagebox.showerror('Błąd', 'T_hot i T_cold muszą być liczbami')
            return

        # Gather forces
        forces = getattr(self.app, 'system_forces', []) or []
        force_values = []
        for f in forces:
            try:
                v = float(f.get('value', f)) if isinstance(f, dict) else float(f)
                force_values.append(v)
            except Exception:
                continue

        if not force_values:
            messagebox.showwarning('Brak nacisków', 'Brak zdefiniowanych przypadków nacisku (forces)')
            return

        # Prepare interfaces
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        tcr_interfaces = [it for it in interfaces if getattr(it, 'has_tcr', False)]
        if not tcr_interfaces:
            messagebox.showwarning('Brak interfejsów', 'Nie ma interfejsów z TCR')
            return

        materials = getattr(self.app, 'system_materials', {}) or {}
        tims = getattr(self.app, 'system_tims', []) or []

        # Build microsurface and simulation per interface
        tcr_rows = []
        # We'll also collect TCR per interface (per-area) to later compute system R
        iface_tcr_per_area = {}

        for iface in tcr_interfaces:
            name_top = iface.geom_top.name
            name_bottom = iface.geom_bottom.name
            iface_name = f"{name_top} → {name_bottom}"

            mat_top = materials.get(name_top, {})
            mat_bottom = materials.get(name_bottom, {})

            # Convert units: sigma from µm -> m, young from GPa -> Pa
            sig_1 = float(mat_top.get('sigma', 0)) * 1e-6
            sig_2 = float(mat_bottom.get('sigma', 0)) * 1e-6
            m_1 = float(mat_top.get('m', 0))
            m_2 = float(mat_bottom.get('m', 0))
            k_1 = float(mat_top.get('k', 0))
            k_2 = float(mat_bottom.get('k', 0))
            e_1 = float(mat_top.get('young', 0)) * 1e9
            e_2 = float(mat_bottom.get('young', 0)) * 1e9
            v_1 = float(mat_top.get('poisson', 0))
            v_2 = float(mat_bottom.get('poisson', 0))

            sig_s = (sig_1**2 + sig_2**2) ** 0.5 if (sig_1 or sig_2) else 0
            m_s = (m_1**2 + m_2**2) ** 0.5 if (m_1 or m_2) else 0
            k_s = 2 * k_1 * k_2 / (k_1 + k_2) if (k_1 + k_2) > 0 else 0
            denom = e_2 * (1 - v_1**2) + e_1 * (1 - v_2**2)
            e_s = (e_1 * e_2) / denom if denom > 0 else 0

            # find TIM assigned to this interface from interface_config if exists
            # interface_config keys are indices in system_interfaces
            try:
                idx = interfaces.index(iface)
            except ValueError:
                idx = None

            selected_tim = None
            thickness_val = None
            if idx is not None and idx in self.interface_config:
                cfg = self.interface_config[idx]
                tim_name = cfg['tim_var'].get()
                for tim in tims:
                    if tim.get('name') == tim_name:
                        selected_tim = tim
                        break
                # thickness
                try:
                    thickness_val = float(cfg['thickness_entry'].get()) if cfg.get('thickness_entry') else None
                except Exception:
                    thickness_val = None

            # For each force, compute row
            for f in force_values:
                A_nom = getattr(iface, 'A_nominal', None) or 0
                p = f / A_nom if A_nom > 0 else 0

                # Mikic-sprężyste formula
                try:
                    if sig_s > 0 and m_s > 0 and e_s > 0 and k_s > 0:
                        inner = (2**0.5) * p / (m_s * e_s)
                        h_c = 1.54 * k_s * m_s / sig_s * (inner ** 0.94) if inner > 0 else 0
                    else:
                        h_c = 0
                except Exception:
                    h_c = 0

                # R_c = 1 / (h_c * A_nominal) in K/W
                if h_c > 0 and A_nom > 0:
                    R_c = 1.0 / (h_c * A_nom)
                else:
                    R_c = float('inf')

                # Percent contact: p / Hc (use softer material hc)
                # hc provided by user in MPa -> convert to Pa
                hc_top = float(mat_top.get('hc', 0)) * 1e6 if mat_top.get('hc') is not None else 0
                hc_bottom = float(mat_bottom.get('hc', 0)) * 1e6 if mat_bottom.get('hc') is not None else 0
                hc_soft = min([v for v in (hc_top, hc_bottom) if v > 0], default=0)
                if hc_soft > 0:
                    pct_styku = 100.0 * p / hc_soft
                else:
                    pct_styku = 0.0
                if pct_styku < 0:
                    pct_styku = 0.0
                if pct_styku > 100.0:
                    pct_styku = 100.0
                pct_int = 100.0 - pct_styku

                # TIM conduction h_int = k_tim / thickness
                h_int = 0.0
                R_int = float('inf')
                if selected_tim and thickness_val and thickness_val > 0:
                    try:
                        k_tim = float(selected_tim.get('k', 0))
                        if k_tim > 0:
                            h_int = k_tim / thickness_val
                            # R_int = 1 / (h_int * A_nominal) in K/W
                            if h_int > 0 and A_nom > 0:
                                R_int = 1.0 / (h_int * A_nom)
                            else:
                                R_int = float('inf')
                    except Exception:
                        h_int = 0.0
                        R_int = float('inf')
                # Effective combined resistance (series): R_eff = R_c + R_int
                if R_c == float('inf') and R_int == float('inf'):
                    R_eff = float('inf')
                    h_eff = 0.0
                else:
                    R_c_val = R_c if R_c != float('inf') else 0.0
                    R_int_val = R_int if R_int != float('inf') else 0.0
                    h_eff = h_c + h_int
                    R_eff = R_c_val * R_int_val / (R_c_val + R_int_val)
                    # h_eff = 1.0 / R_eff if R_eff > 0 else 0.0

                # TCR = R_eff (already in K/W)
                TCR = R_eff

                # K = 0.0001 / (TCR * A_nominal) [W/mK]
                if TCR > 0 and TCR != float('inf') and A_nom > 0:
                    K_eff = 0.0001 / (TCR * A_nom)
                else:
                    K_eff = 0.0

                # store per-interface per-force TCR per-area
                # Use A_nom for later area conversions
                key = iface_name
                iface_tcr_per_area.setdefault(key, []).append({'force': f, 'TCR_area': TCR, 'A_nom': A_nom})

                tcr_rows.append({
                    'force_N': f,
                    'interface': iface_name,
                    'pressure_Pa': p,
                    'A_used': A_nom,
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

        # Auto-export TCR table to CSV
        model_tag = 'mikic_sprezyste'
        tcr_filename = f"{model_tag}_tcr.csv"
        tcr_path = os.path.join(os.getcwd(), tcr_filename)
        try:
            with open(tcr_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Force[N]', 'Interface', 'A_used[m2]', 'Pressure[Pa]', '%styku', '%int', 'h_c[W/m2K]', 'R_c[K/W]', 'h_int[W/m2K]', 'R_int[K/W]', 'h_eff[W/m2K]', 'TCR[K/W]', 'K[W/mK]'])
                for r in tcr_rows:
                    writer.writerow([
                        f"{r['force_N']:.4f}", r['interface'], f"{r.get('A_used',0):.4f}", f"{r['pressure_Pa']:.4f}", f"{r['pct_styku']:.4f}", f"{r['pct_int']:.4f}",
                        f"{r['h_c']:.4f}", (f"{r['R_c']:.4f}" if r['R_c'] != float('inf') else 'inf'),
                        f"{r['h_int']:.4f}", (f"{r['R_int']:.4f}" if r['R_int'] != float('inf') else 'inf'),
                        f"{r['h_eff']:.4f}", (f"{r['TCR']:.4f}" if r['TCR'] != float('inf') else 'inf'), f"{r['K']:.4f}"
                    ])
            self.app.log(f'✓ Eksportowano TCR raport: {tcr_filename}')
        except Exception as e:
            self.app.log(f'! Błąd przy zapisie TCR CSV: {e}')

        # Compute R_u per geometry and overall R/Q per force case
        geometries = getattr(self.app, 'system_geometries', []) or []
        R_u_list = []
        for geom in geometries:
            try:
                a = float(getattr(geom, 'length', 0))
                b = float(getattr(geom, 'width', 0))
                h_block = float(getattr(geom, 'height', 0))
                mat = materials.get(getattr(geom, 'name', ''), {})
                k_mat = float(mat.get('k', 0))
                if k_mat > 0 and a > 0 and b > 0:
                    R_u = h_block / (k_mat * (a * b))
                else:
                    R_u = float('inf')
            except Exception:
                R_u = float('inf')
            R_u_list.append({'geom': getattr(geom, 'name', ''), 'R_u': R_u})

        R_U = sum([r['R_u'] for r in R_u_list if r['R_u'] != float('inf')])

        # Find smallest nominal area among interfaces
        areas = [getattr(it, 'A_nominal', 0) for it in tcr_interfaces]
        A_min = min([a for a in areas if a > 0], default=0)

        # Build overall Q table per force
        q_rows = []
        for f in force_values:
            # sum TCR values (already in K/W)
            sum_TCR_K = 0.0
            for key, entries in iface_tcr_per_area.items():
                for ent in entries:
                    if abs(ent['force'] - f) < 1e-12:
                        tcr_area = ent.get('TCR_area', float('inf'))
                        if tcr_area == float('inf'):
                            sum_TCR_K = float('inf')
                        elif sum_TCR_K != float('inf'):
                            sum_TCR_K += tcr_area

            if R_U == float('inf') or sum_TCR_K == float('inf'):
                R_total = float('inf')
                h_sys = 0.0
                Q = 0.0
            else:
                R_total = R_U + sum_TCR_K
                if R_total > 0 and A_min > 0:
                    h_sys = 1.0 / (R_total * A_min)
                    dT = abs(thot - tcold)
                    Q = h_sys * A_min * dT
                else:
                    h_sys = 0.0
                    Q = 0.0

            q_rows.append({'force_N': f, 'R_U': R_U, 'sum_TCR_K': sum_TCR_K, 'R_total': R_total, 'h_sys': h_sys, 'Q': Q})

        # Auto-export Q table CSV
        q_filename = f"{model_tag}_Q.csv"
        q_path = os.path.join(os.getcwd(), q_filename)
        try:
            with open(q_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Force[N]', 'R_U[K/W]', 'Sum_TCR[K/W]', 'R_total[K/W]', 'h_sys[W/m2K]', 'Q[W]'])
                for r in q_rows:
                    writer.writerow([
                        f"{r['force_N']:.4f}", (f"{r['R_U']:.4f}" if r['R_U'] != float('inf') else 'inf'),
                        (f"{r['sum_TCR_K']:.4f}" if r['sum_TCR_K'] != float('inf') else 'inf'),
                        (f"{r['R_total']:.4f}" if r['R_total'] != float('inf') else 'inf'),
                        f"{r['h_sys']:.4f}", f"{r['Q']:.4f}"
                    ])
            self.app.log(f'✓ Eksportowano Q raport: {q_filename}')
        except Exception as e:
            self.app.log(f'! Błąd przy zapisie Q CSV: {e}')

        # Show TCR report window and Q report window
        self._show_tcr_report_window(tcr_rows, model_name='Mikic - sprężyste', tcr_path=tcr_path, q_rows=q_rows, q_path=q_path)

    def _run_mikic_plast(self):
        """Run Mikic (plastyczne) model and show/export results."""
        # Basic validations (reuse same checks as elastic)
        if not self.interface_config:
            messagebox.showwarning('Błąd', 'Brak interfejsów z TCR do symulacji')
            return

        try:
            thot = float(self.ent_thot.get())
            tcold = float(self.ent_tcold.get())
        except ValueError:
            messagebox.showerror('Błąd', 'T_hot i T_cold muszą być liczbami')
            return

        forces = getattr(self.app, 'system_forces', []) or []
        force_values = []
        for f in forces:
            try:
                v = float(f.get('value', f)) if isinstance(f, dict) else float(f)
                force_values.append(v)
            except Exception:
                continue

        if not force_values:
            messagebox.showwarning('Brak nacisków', 'Brak zdefiniowanych przypadków nacisku (forces)')
            return

        interfaces = getattr(self.app, 'system_interfaces', []) or []
        tcr_interfaces = [it for it in interfaces if getattr(it, 'has_tcr', False)]
        if not tcr_interfaces:
            messagebox.showwarning('Brak interfejsów', 'Nie ma interfejsów z TCR')
            return

        materials = getattr(self.app, 'system_materials', {}) or {}
        tims = getattr(self.app, 'system_tims', []) or []

        tcr_rows = []
        iface_tcr_per_area = {}

        for iface in tcr_interfaces:
            name_top = iface.geom_top.name
            name_bottom = iface.geom_bottom.name
            iface_name = f"{name_top} → {name_bottom}"

            mat_top = materials.get(name_top, {})
            mat_bottom = materials.get(name_bottom, {})

            # Units: sigma µm->m, Hc MPa->Pa, young not used here
            sig_1 = float(mat_top.get('sigma', 0)) * 1e-6
            sig_2 = float(mat_bottom.get('sigma', 0)) * 1e-6
            m_1 = float(mat_top.get('m', 0))
            m_2 = float(mat_bottom.get('m', 0))
            k_1 = float(mat_top.get('k', 0))
            k_2 = float(mat_bottom.get('k', 0))
            hc_top = float(mat_top.get('hc', 0)) * 1e6 if mat_top.get('hc') is not None else 0
            hc_bottom = float(mat_bottom.get('hc', 0)) * 1e6 if mat_bottom.get('hc') is not None else 0

            sig_s = (sig_1**2 + sig_2**2) ** 0.5 if (sig_1 or sig_2) else 0
            m_s = (m_1**2 + m_2**2) ** 0.5 if (m_1 or m_2) else 0
            k_s = 2 * k_1 * k_2 / (k_1 + k_2) if (k_1 + k_2) > 0 else 0
            hc_soft = min([v for v in (hc_top, hc_bottom) if v > 0], default=0)

            # find TIM and thickness
            try:
                idx = interfaces.index(iface)
            except ValueError:
                idx = None

            selected_tim = None
            thickness_val = None
            if idx is not None and idx in self.interface_config:
                cfg = self.interface_config[idx]
                tim_name = cfg['tim_var'].get()
                for tim in tims:
                    if tim.get('name') == tim_name:
                        selected_tim = tim
                        break
                try:
                    thickness_val = float(cfg['thickness_entry'].get()) if cfg.get('thickness_entry') else None
                except Exception:
                    thickness_val = None

            for f in force_values:
                A_nom = getattr(iface, 'A_nominal', None) or 0
                p = f / A_nom if A_nom > 0 else 0

                # Mikic-plastyczne formula: h_c = 1.13 * k_s * m_s / sig_s * (p / Hc)^0.94
                try:
                    if sig_s > 0 and m_s > 0 and hc_soft > 0 and k_s > 0:
                        inner = p / hc_soft
                        h_c = 1.13 * k_s * m_s / sig_s * (inner ** 0.94) if inner > 0 else 0
                    else:
                        h_c = 0
                except Exception:
                    h_c = 0

                # R_c = 1 / (h_c * A_nom)
                if h_c > 0 and A_nom > 0:
                    R_c = 1.0 / (h_c * A_nom)
                else:
                    R_c = float('inf')

                # Percent contact
                if hc_soft > 0:
                    pct_styku = 100.0 * p / hc_soft
                else:
                    pct_styku = 0.0
                pct_styku = max(0.0, min(100.0, pct_styku))
                pct_int = 100.0 - pct_styku

                # TIM conduction
                h_int = 0.0
                R_int = float('inf')
                if selected_tim and thickness_val and thickness_val > 0:
                    try:
                        k_tim = float(selected_tim.get('k', 0))
                        if k_tim > 0:
                            h_int = k_tim / thickness_val
                            if h_int > 0 and A_nom > 0:
                                R_int = 1.0 / (h_int * A_nom)
                            else:
                                R_int = float('inf')
                    except Exception:
                        h_int = 0.0
                        R_int = float('inf')

                # Combine resistances
                if R_c == float('inf') and R_int == float('inf'):
                    R_eff = float('inf')
                    h_eff = 0.0
                else:
                    R_c_val = R_c if R_c != float('inf') else 0.0
                    R_int_val = R_int if R_int != float('inf') else 0.0
                    R_eff = R_c_val + R_int_val
                    h_eff = 1.0 / R_eff if R_eff > 0 else 0.0

                TCR = R_eff

                # K calculation same as other model
                if TCR > 0 and TCR != float('inf') and A_nom > 0:
                    K_eff = 0.0001 / (TCR * A_nom)
                else:
                    K_eff = 0.0

                key = iface_name
                iface_tcr_per_area.setdefault(key, []).append({'force': f, 'TCR_area': TCR, 'A_nom': A_nom})

                tcr_rows.append({
                    'force_N': f,
                    'interface': iface_name,
                    'pressure_Pa': p,
                    'A_used': A_nom,
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

        # Export CSVs and show windows (reuse filenames)
        model_tag = 'mikic_plastyczne'
        tcr_filename = f"{model_tag}_tcr.csv"
        tcr_path = os.path.join(os.getcwd(), tcr_filename)
        try:
            with open(tcr_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Force[N]', 'Interface', 'A_used[m2]', 'Pressure[Pa]', '%styku', '%int', 'h_c[W/m2K]', 'R_c[K/W]', 'h_int[W/m2K]', 'R_int[K/W]', 'h_eff[W/m2K]', 'TCR[K/W]', 'K[W/mK]'])
                for r in tcr_rows:
                    writer.writerow([
                        f"{r['force_N']:.4f}", r['interface'], f"{r.get('A_used',0):.4f}", f"{r['pressure_Pa']:.4f}", f"{r['pct_styku']:.4f}", f"{r['pct_int']:.4f}",
                        f"{r['h_c']:.4f}", (f"{r['R_c']:.4f}" if r['R_c'] != float('inf') else 'inf'),
                        f"{r['h_int']:.4f}", (f"{r['R_int']:.4f}" if r['R_int'] != float('inf') else 'inf'),
                        f"{r['h_eff']:.4f}", (f"{r['TCR']:.4f}" if r['TCR'] != float('inf') else 'inf'), f"{r['K']:.4f}"
                    ])
            self.app.log(f'✓ Eksportowano TCR raport: {tcr_filename}')
        except Exception as e:
            self.app.log(f'! Błąd przy zapisie TCR CSV: {e}')

        # Compute R_U and Q rows same as in _run_mikic_spr
        geometries = getattr(self.app, 'system_geometries', []) or []
        R_u_list = []
        for geom in geometries:
            try:
                a = float(getattr(geom, 'length', 0))
                b = float(getattr(geom, 'width', 0))
                h_block = float(getattr(geom, 'height', 0))
                mat = materials.get(getattr(geom, 'name', ''), {})
                k_mat = float(mat.get('k', 0))
                if k_mat > 0 and a > 0 and b > 0:
                    R_u = h_block / (k_mat * (a * b))
                else:
                    R_u = float('inf')
            except Exception:
                R_u = float('inf')
            R_u_list.append({'geom': getattr(geom, 'name', ''), 'R_u': R_u})

        R_U = sum([r['R_u'] for r in R_u_list if r['R_u'] != float('inf')])
        areas = [getattr(it, 'A_nominal', 0) for it in tcr_interfaces]
        A_min = min([a for a in areas if a > 0], default=0)

        q_rows = []
        for f in force_values:
            sum_TCR_K = 0.0
            for key, entries in iface_tcr_per_area.items():
                for ent in entries:
                    if abs(ent['force'] - f) < 1e-12:
                        tcr_area = ent.get('TCR_area', float('inf'))
                        if tcr_area == float('inf'):
                            sum_TCR_K = float('inf')
                        elif sum_TCR_K != float('inf'):
                            sum_TCR_K += tcr_area

            if R_U == float('inf') or sum_TCR_K == float('inf'):
                R_total = float('inf')
                h_sys = 0.0
                Q = 0.0
            else:
                R_total = R_U + sum_TCR_K
                if R_total > 0 and A_min > 0:
                    h_sys = 1.0 / (R_total * A_min)
                    dT = abs(thot - tcold)
                    Q = h_sys * A_min * dT
                else:
                    h_sys = 0.0
                    Q = 0.0

            q_rows.append({'force_N': f, 'R_U': R_U, 'sum_TCR_K': sum_TCR_K, 'R_total': R_total, 'h_sys': h_sys, 'Q': Q})

        q_filename = f"{model_tag}_Q.csv"
        q_path = os.path.join(os.getcwd(), q_filename)
        try:
            with open(q_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Force[N]', 'R_U[K/W]', 'Sum_TCR[K/W]', 'R_total[K/W]', 'h_sys[W/m2K]', 'Q[W]'])
                for r in q_rows:
                    writer.writerow([
                        f"{r['force_N']:.4f}", (f"{r['R_U']:.4f}" if r['R_U'] != float('inf') else 'inf'),
                        (f"{r['sum_TCR_K']:.4f}" if r['sum_TCR_K'] != float('inf') else 'inf'),
                        (f"{r['R_total']:.4f}" if r['R_total'] != float('inf') else 'inf'),
                        f"{r['h_sys']:.4f}", f"{r['Q']:.4f}"
                    ])
            self.app.log(f'✓ Eksportowano Q raport: {q_filename}')
        except Exception as e:
            self.app.log(f'! Błąd przy zapisie Q CSV: {e}')

        self._show_tcr_report_window(tcr_rows, model_name='Mikic - plastyczne', tcr_path=tcr_path, q_rows=q_rows, q_path=q_path)

    def _show_tcr_report_window(self, tcr_rows, model_name='Model', tcr_path=None, q_rows=None, q_path=None):
        """Display TCR result window with export button and link to Q table."""
        win = tk.Toplevel(self.app)
        win.title(f'{model_name}, TCR')
        win.geometry('1000x600')

        frm_toolbar = ttk.Frame(win)
        frm_toolbar.pack(fill='x', padx=8, pady=6)
        if tcr_path:
            ttk.Button(frm_toolbar, text='Export CSV', command=lambda: messagebox.showinfo('Saved', f'Zapisano automatycznie: {tcr_path}')).pack(side='left', padx=4)

        ttk.Label(win, text=f'{model_name}, TCR', font=('', 11, 'bold')).pack(anchor='w', padx=8)

        # Table area
        frm_table = ttk.Frame(win)
        frm_table.pack(fill='both', expand=True, padx=8, pady=8)

        canvas = tk.Canvas(frm_table)
        vsb = ttk.Scrollbar(frm_table, orient='vertical', command=canvas.yview)
        hsb = ttk.Scrollbar(frm_table, orient='horizontal', command=canvas.xview)
        canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side='right', fill='y')
        hsb.pack(side='bottom', fill='x')
        canvas.pack(side='left', fill='both', expand=True)

        inner = ttk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        headers = ['Force[N]', 'Interface', 'A_used[m2]', 'Pressure[Pa]', '%styku', '%int', 'h_c[W/m2K]', 'R_c[K/W]', 'h_int[W/m2K]', 'R_int[K/W]', 'h_eff[W/m2K]', 'TCR[K/W]', 'K[W/mK]']
        for col, h in enumerate(headers):
            lbl = ttk.Label(inner, text=h, font=('', 9, 'bold'), background='lightgray')
            lbl.grid(row=0, column=col, padx=4, pady=2, sticky='we')

        for r_idx, r in enumerate(tcr_rows, start=1):
            ttk.Label(inner, text=f"{r['force_N']:.4f}").grid(row=r_idx, column=0, padx=4, pady=2)
            ttk.Label(inner, text=r['interface']).grid(row=r_idx, column=1, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r.get('A_used',0):.4f}")).grid(row=r_idx, column=2, padx=4, pady=2)
            ttk.Label(inner, text=f"{r['pressure_Pa']:.4f}").grid(row=r_idx, column=3, padx=4, pady=2)
            ttk.Label(inner, text=f"{r['pct_styku']:.4f}").grid(row=r_idx, column=4, padx=4, pady=2)
            ttk.Label(inner, text=f"{r['pct_int']:.4f}").grid(row=r_idx, column=5, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r['h_c']:.4f}" if r['h_c'] else '0')).grid(row=r_idx, column=6, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r['R_c']:.4f}" if r['R_c'] != float('inf') else 'inf')).grid(row=r_idx, column=7, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r['h_int']:.4f}" if r['h_int'] else '0')).grid(row=r_idx, column=8, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r['R_int']:.4f}" if r['R_int'] != float('inf') else 'inf')).grid(row=r_idx, column=9, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r['h_eff']:.4f}" if r['h_eff'] else '0')).grid(row=r_idx, column=10, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r['TCR']:.4f}" if r['TCR'] != float('inf') else 'inf')).grid(row=r_idx, column=11, padx=4, pady=2)
            ttk.Label(inner, text=(f"{r['K']:.4f}" if r['K'] else '0')).grid(row=r_idx, column=12, padx=4, pady=2)

        def _on_cfg(event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        inner.bind('<Configure>', _on_cfg)

        # Also show Q table in separate window
        if q_rows is not None:
            self._show_Q_window(q_rows, model_name=model_name, q_path=q_path)

    def _show_Q_window(self, q_rows, model_name='Model', q_path=None):
        win = tk.Toplevel(self.app)
        win.title(f'{model_name} - Q')
        win.geometry('700x300')

        frm_toolbar = ttk.Frame(win)
        frm_toolbar.pack(fill='x', padx=8, pady=6)
        if q_path:
            ttk.Button(frm_toolbar, text='Export CSV', command=lambda: messagebox.showinfo('Saved', f'Zapisano automatycznie: {q_path}')).pack(side='left', padx=4)

        ttk.Label(win, text=f'{model_name} — Całkowity przepływ ciepła', font=('', 11, 'bold')).pack(anchor='w', padx=8)

        frm_table = ttk.Frame(win)
        frm_table.pack(fill='both', expand=True, padx=8, pady=8)

        headers = ['Force[N]', 'R_U[K/W]', 'Sum_TCR[K/W]', 'R_total[K/W]', 'h_sys[W/m2K]', 'Q[W]']
        for c, h in enumerate(headers):
            lbl = ttk.Label(frm_table, text=h, font=('', 9, 'bold'), background='lightgray')
            lbl.grid(row=0, column=c, padx=4, pady=2, sticky='we')

        for r_idx, r in enumerate(q_rows, start=1):
            ttk.Label(frm_table, text=f"{r['force_N']:.4f}").grid(row=r_idx, column=0, padx=4, pady=2)
            ttk.Label(frm_table, text=(f"{r['R_U']:.4f}" if r['R_U'] != float('inf') else 'inf')).grid(row=r_idx, column=1, padx=4, pady=2)
            ttk.Label(frm_table, text=(f"{r['sum_TCR_K']:.4f}" if r['sum_TCR_K'] != float('inf') else 'inf')).grid(row=r_idx, column=2, padx=4, pady=2)
            ttk.Label(frm_table, text=(f"{r['R_total']:.4f}" if r['R_total'] != float('inf') else 'inf')).grid(row=r_idx, column=3, padx=4, pady=2)
            ttk.Label(frm_table, text=f"{r['h_sys']:.4f}").grid(row=r_idx, column=4, padx=4, pady=2)
            ttk.Label(frm_table, text=f"{r['Q']:.4f}").grid(row=r_idx, column=5, padx=4, pady=2)

    def _run_simulation(self):
        """Placeholder for running the simulation."""
        # Validation: check that all interfaces have TIM selected and boundary conditions set
        if not self.interface_config:
            messagebox.showwarning('Błąd', 'Brak interfejsów z TCR do symulacji')
            return

        try:
            thot = float(self.ent_thot.get())
            tcold = float(self.ent_tcold.get())
        except ValueError:
            messagebox.showerror('Błąd', 'T_hot i T_cold muszą być liczbami')
            return

        # Check that all interfaces have TIM selected
        for iface_idx, config in self.interface_config.items():
            if not config['tim_var'].get():
                messagebox.showerror('Błąd', f'Interfejs {iface_idx} nie ma wybranego TIM-u')
                return

        messagebox.showinfo('Symulacja', 'Symulacja będzie uruchomiona (placeholder - czeka na wzory)')
        self.app.log('! Symulacja: czeka na implementację (placeholder)')
