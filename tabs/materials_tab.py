"""Materials tab for defining material properties for each geometry in system.

Behavior:
- Loads system only after user saved it in System tab.
- Shows instruction if no saved system is available.
- When system present displays a scrollable table with one row per geometry.
- First column: geometry name (read-only). Other columns editable according to whether geometry
  participates in any interface (if not, only thermal conductivity editable).
- Supports importing materials from a text file (ignores lines starting with '#'). Invalid values
  are reported in console and skipped for that geometry.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from controllers import MaterialsManager


class MaterialsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Manager for business logic
        self.manager = MaterialsManager(app=self.app)
        self.manager.subscribe(self._on_manager_event)

        # View state
        self.row_widgets = {}  # geom_idx -> dict of widgets for the row
        self.tim_widgets = {}  # tim_idx -> dict of TIM widgets

        # Header / controls
        frm_top = ttk.Frame(self)
        frm_top.pack(fill='x', padx=10, pady=8)

        self.lbl_title = ttk.Label(frm_top, text='Materiały — parametry materiałowe brył')
        self.lbl_title.pack(side='left')

        frm_buttons = ttk.Frame(frm_top)
        frm_buttons.pack(side='right')

        ttk.Button(frm_buttons, text='Load System', command=self.load_system).pack(side='left', padx=4)
        ttk.Button(frm_buttons, text='Import from File', command=self.import_from_file).pack(side='left', padx=4)
        ttk.Button(frm_buttons, text='Save', command=self.save_materials).pack(side='left', padx=4)

        # Container for either instruction or table
        self.container = ttk.Frame(self)
        self.container.pack(fill='both', expand=True, padx=10, pady=6)

        # Initially show instruction
        self._show_no_system()

    def _clear_container(self):
        for w in self.container.winfo_children():
            w.destroy()

    def _show_no_system(self):
        self._clear_container()
        lbl = ttk.Label(self.container,
                        text='Brak zdefiniowanego systemu. Zdefiniuj system w zakładce "System" i naciśnij "Save System".',
                        foreground='gray')
        lbl.pack(padx=10, pady=20, anchor='center')

    def load_system(self):
        """Load system geometries and interfaces from `self.app` and build table."""
        geoms = getattr(self.app, 'system_geometries', None)
        if not geoms:
            self._show_no_system()
            self.app.log('! Brak systemu do załadowania. Zdefiniuj system w zakładce System i naciśnij Save System.')
            return
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        self.manager.set_system(geoms, interfaces)
        # Build table UI
        self._build_table(geoms)

    def _build_table(self, geoms):
        # First, save current TIM values from widgets before clearing
        current_tims = []
        for tim_idx, widgets in self.tim_widgets.items():
            try:
                ent_name = widgets['name'].get()
                k_val = widgets['k'].get()
                type_val = widgets['type'].get()
                press_val = widgets['pressure_dependent'].get()
                tid = widgets.get('id')
                if ent_name.strip() == '' and k_val == '':
                    continue
                tim_obj = {
                    'id': tid,
                    'name': ent_name,
                    'k': float(k_val) if k_val != '' else '',
                    'type': type_val,
                    'pressure_dependent': press_val
                }
                current_tims.append(tim_obj)
            except Exception:
                pass
        if current_tims:
            self.manager.set_tims(current_tims)
        
        self._clear_container()

        # Scrollable area
        canvas = tk.Canvas(self.container)
        vsb = ttk.Scrollbar(self.container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        # Column headers
        cols = ['Geometry', 'Material name', 'k [W/mK]', 'Young [GPa]', 'Poisson [-]', 'RMS sigma [µm]', 'm [-]', 'Hc [MPa]']
        for i, c in enumerate(cols):
            lbl = ttk.Label(inner, text=c, relief='sunken')
            lbl.grid(row=0, column=i, padx=4, pady=4, sticky='ew')

        # Get interfaces info from app
        interfaces = getattr(self.app, 'system_interfaces', []) or []

        # Populate rows
        self.row_widgets = {}  # row_idx -> {'name': name, ...widgets}
        self.rows_by_name = {}  # name -> list of row_idx
        self.tim_widgets = {}  # Reset TIM widgets for rebuild
        for r, g in enumerate(geoms, start=1):  # Start from row 1 (row 0 is header)
            name = g.name

            # Determine if this geometry (by index position) has TCR on either side
            has_tcr_on_side = False
            for it in interfaces:
                try:
                    if not getattr(it, 'has_tcr', False):
                        continue
                    # Check if this geometry is geom_top or geom_bottom in a TCR interface
                    if (it.geom_top.name == name) or (it.geom_bottom.name == name):
                        has_tcr_on_side = True
                        break
                except Exception:
                    pass

            # Initialize materials dict for this geometry name (preserve existing values)
            self.manager.ensure_material_entry(g.name)

            lbl = ttk.Label(inner, text=name)
            lbl.grid(row=r, column=0, padx=4, pady=2, sticky='w')

            materials = self.manager.get_materials()
            def make_entry(val_key, col, state='normal'):
                ent = ttk.Entry(inner)
                ent.grid(row=r, column=col, padx=4, pady=2, sticky='we')
                ent.delete(0, 'end')
                ent.insert(0, str(materials.get(name, {}).get(val_key, '')))
                if state == 'disabled':
                    ent.state(['disabled'])
                else:
                    ent.state(['!disabled'])
                return ent

            e_material = make_entry('material_name', 1, state='normal')
            e_k = make_entry('k', 2, state='normal')
            e_young = make_entry('young', 3, state='normal' if has_tcr_on_side else 'disabled')
            e_poisson = make_entry('poisson', 4, state='normal' if has_tcr_on_side else 'disabled')
            e_sigma = make_entry('sigma', 5, state='normal' if has_tcr_on_side else 'disabled')
            e_m = make_entry('m', 6, state='normal' if has_tcr_on_side else 'disabled')
            e_hc = make_entry('hc', 7, state='normal' if has_tcr_on_side else 'disabled')

            # Store row index by r-1 to map back to geometry index
            geom_idx = r - 1
            self.row_widgets[geom_idx] = {
                'name': name,
                'material_name': e_material,
                'k': e_k,
                'young': e_young,
                'poisson': e_poisson,
                'sigma': e_sigma,
                'm': e_m,
                'hc': e_hc,
            }

            self.rows_by_name.setdefault(name, []).append(geom_idx)

        # Make columns expand responsively
        for col_idx in range(len(cols)):
            try:
                inner.grid_columnconfigure(col_idx, weight=1)
            except Exception:
                pass

        # Configure scrolling region
        def _on_config_inner(event):
            canvas.configure(scrollregion=canvas.bbox('all'))

        def _on_canvas_config(event):
            # Make inner window width match canvas width for responsive columns
            try:
                canvas.itemconfig(window_id, width=event.width)
            except Exception:
                pass

        inner.bind('<Configure>', _on_config_inner)
        canvas.bind('<Configure>', _on_canvas_config)

        # ===== TIM (Thermal Interface Material) SECTION =====
        r = len(geoms) + 1  # Start row after materials section
        
        # Add separator
        sep = ttk.Separator(inner, orient='horizontal')
        sep.grid(row=r, column=0, columnspan=len(cols), sticky='we', pady=10)
        r += 1
        
        # Add TIM title with Add button
        frm_tim_header = ttk.Frame(inner)
        frm_tim_header.grid(row=r, column=0, columnspan=len(cols), sticky='we', padx=4, pady=4)
        
        lbl_tim_title = ttk.Label(frm_tim_header, text='Materiały pośredniczące (TIM)', font=('', 10, 'bold'))
        lbl_tim_title.pack(side='left')
        
        btn_add_tim = ttk.Button(frm_tim_header, text='+ Add TIM', command=self._add_tim_row)
        btn_add_tim.pack(side='right', padx=2)
        
        btn_import_tim = ttk.Button(frm_tim_header, text='Import from File', command=self._import_tim_file)
        btn_import_tim.pack(side='right', padx=2)
        
        btn_clear_tim = ttk.Button(frm_tim_header, text='Clear All TIMs', command=self._clear_all_tims)
        btn_clear_tim.pack(side='right', padx=2)
        
        r += 1
        
        # TIM table headers
        tim_headers = ['Name', 'k [W/mK]', 'Type (Gas/Paste)', 'Pressure-dependent', 'Actions']
        for col, header_text in enumerate(tim_headers):
            lbl = ttk.Label(inner, text=header_text, font=('', 9, 'bold'), background='lightgray')
            lbl.grid(row=r, column=col, padx=4, pady=2, sticky='we')
        r += 1
        
        # Build TIM definition rows
        for tim_idx, tim_data in enumerate(self.manager.get_tims()):
            # Ensure each TIM has a stable unique id
            if 'id' not in tim_data:
                # Ask manager to maintain id sequence on set_tims/save
                tid = tim_data.get('id') or None
                if tid is None:
                    # generate a temporary id for UI; real id will be set on save
                    tid = - (tim_idx + 1)
                tim_data['id'] = tid
            # Column 0: TIM Name
            ent_tim_name = ttk.Entry(inner)
            ent_tim_name.grid(row=r, column=0, padx=4, pady=2, sticky='we')
            ent_tim_name.delete(0, 'end')
            ent_tim_name.insert(0, tim_data.get('name', ''))
            
            # Column 1: k [W/mK]
            ent_tim_k = ttk.Entry(inner)
            ent_tim_k.grid(row=r, column=1, padx=4, pady=2, sticky='we')
            ent_tim_k.delete(0, 'end')
            ent_tim_k.insert(0, str(tim_data.get('k', '')))
            
            # Column 2: Type (Radio buttons: Gas/Paste)
            frm_type = ttk.Frame(inner)
            frm_type.grid(row=r, column=2, padx=4, pady=2, sticky='we')
            var_type = tk.StringVar(value=tim_data.get('type', 'gas'))
            
            # Column 3: Pressure-dependent (Radio buttons: Yes/No)
            frm_pressure = ttk.Frame(inner)
            frm_pressure.grid(row=r, column=3, padx=4, pady=2, sticky='we')
            var_pressure = tk.BooleanVar(value=tim_data.get('pressure_dependent', False))
            
            rb_yes = ttk.Radiobutton(frm_pressure, text='Yes', variable=var_pressure, value=True)
            rb_yes.pack(side='left', padx=2)
            rb_no = ttk.Radiobutton(frm_pressure, text='No', variable=var_pressure, value=False)
            rb_no.pack(side='left', padx=2)

            # --- Logic to handle interaction between Type and Pressure Dependency ---
            def update_pressure_state(_=None, v_type=var_type, v_press=var_pressure, r_y=rb_yes, r_n=rb_no):
                if v_type.get() == 'paste':
                    # Paste cannot be pressure dependent -> force No and disable
                    v_press.set(False)
                    r_y.configure(state='disabled')
                    r_n.configure(state='disabled')
                else:
                    # Gas -> enable choice
                    r_y.configure(state='normal')
                    r_n.configure(state='normal')

            # Bind the update to radio buttons
            rb_gas = ttk.Radiobutton(frm_type, text='Gas', variable=var_type, value='gas', 
                                     command=update_pressure_state)
            rb_gas.pack(side='left', padx=2)
            rb_paste = ttk.Radiobutton(frm_type, text='Paste', variable=var_type, value='paste',
                                       command=update_pressure_state)
            rb_paste.pack(side='left', padx=2)

            # Initialize state
            update_pressure_state()

            # Column 4: Actions (no per-row remove when using global clear)
            frm_actions = ttk.Frame(inner)
            frm_actions.grid(row=r, column=4, padx=4, pady=2, sticky='we')
            
            # Store widget references (include id for persistence)
            self.tim_widgets[tim_idx] = {
                'id': tim_data.get('id'),
                'name': ent_tim_name,
                'k': ent_tim_k,
                'type': var_type,
                'pressure_dependent': var_pressure
            }
            
            r += 1

    def import_from_file(self):
        """Import material values from text file (ignore lines starting with '#').

        Expected format per line (tab/space-separated):
        name material_name k young poisson sigma m hc
        Only material_name (string) and k (number) are strictly required for valid import.
        For geometries that do not participate in interfaces only 'k' is accepted; other fields
        for such geometries are treated as invalid and skipped.
        """
        file_path = filedialog.askopenfilename(filetypes=[('Text files', '*.txt'), ('All', '*.*')])
        if not file_path:
            return

        geoms = getattr(self.app, 'system_geometries', None)
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        if not geoms:
            self.app.log('! Import przerwany: brak załadowanego systemu (zapisz system w zakładce System).')
            return
        # Ensure manager knows current system
        self.manager.set_system(geoms, interfaces)
        success, msg, imported = self.manager.import_materials_from_file(file_path)
        if not success:
            messagebox.showerror('Error', msg)
            return

        # If table exists, refresh displayed values for all rows matching imported names
        if self.row_widgets:
            for name, row_indices in getattr(self, 'rows_by_name', {}).items():
                vals = self.manager.get_materials().get(name, {})
                for r in row_indices:
                    widgets = self.row_widgets.get(r, {})
                    for key, ent in widgets.items():
                        if key == 'name':
                            continue
                        # update only if entry is enabled
                        try:
                            if 'disabled' in ent.state():
                                continue
                        except Exception:
                            pass
                        val = vals.get(key, '')
                        ent.delete(0, 'end')
                        ent.insert(0, str(val))

        self.app.log(f'✓ Import materiałów zakończony. Zaimportowano poprawnie: {imported} rekordów. (Plik: {os.path.basename(file_path)})')

    def save_materials(self):
        """Collect values from table and save into app.system_materials and app.system_tims."""
        # Read from widgets into local materials
        materials = self.manager.get_materials().copy()
        for r, widgets in self.row_widgets.items():
            name = widgets.get('name')
            if not name:
                continue
            if name not in materials:
                materials[name] = {}
            for key, ent in widgets.items():
                if key == 'name':
                    continue
                try:
                    val = ent.get()
                except Exception:
                    val = ent.get()
                if key == 'material_name':
                    materials[name][key] = val
                else:
                    if val == '':
                        materials[name][key] = ''
                    else:
                        try:
                            materials[name][key] = float(val)
                        except ValueError:
                            materials[name][key] = val
                            self.app.log(f'! Zapis materiałów: pole {key} dla bryły {name} ma nieprawidłową wartość: "{val}"')

        # Read from TIM widgets into tims list
        tims = []
        for tim_idx in sorted(self.tim_widgets.keys()):
            widgets = self.tim_widgets[tim_idx]
            tim_data = {}
            wid_id = widgets.get('id')
            tim_data['id'] = wid_id if wid_id else None
            try:
                tim_name = widgets['name'].get().strip()
                if not tim_name:
                    continue
                tim_data['name'] = tim_name
            except Exception:
                continue
            try:
                tim_k = widgets['k'].get()
                tim_data['k'] = float(tim_k) if tim_k != '' else ''
            except ValueError:
                self.app.log(f'! Zapis TIM: pole k ma nieprawidłową wartość: "{tim_k}"')
                continue
            try:
                tim_type = widgets['type'].get()
                tim_data['type'] = tim_type
            except Exception:
                tim_data['type'] = 'gas'
            try:
                tim_pressure = widgets['pressure_dependent'].get()
                if tim_data['type'] == 'paste':
                    tim_pressure = False
                tim_data['pressure_dependent'] = tim_pressure
            except Exception:
                tim_data['pressure_dependent'] = False
            tims.append(tim_data)

        # Update manager and validate
        self.manager.set_materials(materials)
        self.manager.set_tims(tims)
        ok, msg, errors = self.manager.validate_before_save()
        if not ok:
            messagebox.showerror('Błąd zapisu', msg)
            for e in errors:
                self.app.log('! ' + e)
            return
        # Save to app
        self.app.system_materials = self.manager.get_materials().copy()
        self.app.system_tims = self.manager.get_tims().copy()
        self.app.log('✓ Zapisano materiały i TIM-y do systemu')

    def _add_tim_row(self):
        """Add a new empty TIM row to the library."""
        success, msg = self.manager.add_tim()
        if success:
            self.app.log('✓ ' + msg)
        self.load_system()  # Rebuild table to show new row

    def _clear_all_tims(self):
        """Clear the entire TIM library."""
        success, msg = self.manager.clear_all_tims()
        self.app.log(('✓ ' if success else '! ') + msg)
        self.load_system()

    def _import_tim_file(self):
        """Import TIM definitions from file (ignore lines starting with '#').
        
        Expected format per line (tab/space-separated):
        name k
        Example:
            powietrze    0.029
            pasta_1      1.5
        """
        file_path = filedialog.askopenfilename(filetypes=[('Text files', '*.txt'), ('All', '*.*')])
        if not file_path:
            return
        success, msg = self.manager.import_tim_file(file_path)
        self.app.log(('✓ ' if success else '! ') + msg)
        if success:
            self.load_system()

    # --- Manager events ---
    def _on_manager_event(self, event_type, data):
        if event_type in ('materials_updated', 'tims_updated', 'tim_added', 'tims_cleared', 'tims_imported', 'materials_imported', 'materials_system_set'):
            # For simplicity, leave redraw to caller actions (load_system/save/import) to avoid flicker
            pass