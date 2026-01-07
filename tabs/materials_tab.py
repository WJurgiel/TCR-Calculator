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


class MaterialsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Internal storage: name -> dict of material properties
        self.materials = {}
        self.row_widgets = {}  # geom_idx -> dict of widgets for the row
        
        # TIM storage: list of TIM definitions (each TIM: {name, k, type, pressure_dependent})
        self.tims = []
        self.tim_widgets = {}  # tim_idx -> dict of TIM widgets
        self._tim_next_id = 1

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

        # Build table UI with index-based TCR participation determination
        self._build_table(geoms)

    def _build_table(self, geoms):
        # First, save current TIM values from widgets before clearing
        for tim_idx, widgets in self.tim_widgets.items():
            if tim_idx < len(self.tims):
                try:
                    self.tims[tim_idx]['name'] = widgets['name'].get()
                    k_val = widgets['k'].get()
                    self.tims[tim_idx]['k'] = float(k_val) if k_val != '' else ''
                    self.tims[tim_idx]['type'] = widgets['type'].get()
                    self.tims[tim_idx]['pressure_dependent'] = widgets['pressure_dependent'].get()
                except Exception:
                    pass
        
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
            if g.name not in self.materials:
                self.materials[g.name] = {
                    'material_name': '',
                    'k': '',
                    'young': '',
                    'poisson': '',
                    'sigma': '',
                    'm': '',
                    'hc': ''
                }

            lbl = ttk.Label(inner, text=name)
            lbl.grid(row=r, column=0, padx=4, pady=2, sticky='w')

            def make_entry(val_key, col, state='normal'):
                ent = ttk.Entry(inner)
                ent.grid(row=r, column=col, padx=4, pady=2, sticky='we')
                ent.delete(0, 'end')
                ent.insert(0, str(self.materials.get(name, {}).get(val_key, '')))
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
        for tim_idx, tim_data in enumerate(self.tims):
            # Ensure each TIM has a stable unique id
            if 'id' not in tim_data:
                tid = self._tim_next_id
                self._tim_next_id += 1
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

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
        except Exception as e:
            messagebox.showerror('Error', f'Failed to open file: {e}')
            return

        geoms = getattr(self.app, 'system_geometries', None)
        if not geoms:
            self.app.log('! Import przerwany: brak załadowanego systemu (zapisz system w zakładce System).')
            return

        geom_names = {g.name for g in geoms}
        interfaces = getattr(self.app, 'system_interfaces', []) or []
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
                self.app.log(f'! Import: nieznana bryła "{name}" w linii {i} — pomijam')
                continue

            # Determine allowed fields
            # Only geometries participating in interfaces with TCR allow all fields
            allowed_all = name in iface_names

            # Fill values if present
            # parts indices: 0:name,1:material_name,2:k,3:young,4:poisson,5:sigma,6:m,7:hc
            row_errors = []
            # material_name
            if len(parts) >= 2:
                self.materials[name]['material_name'] = parts[1]
            # k (mandatory numeric)
            if len(parts) >= 3:
                try:
                    self.materials[name]['k'] = float(parts[2])
                except ValueError:
                    row_errors.append('k (invalid number)')
            else:
                row_errors.append('k (missing)')

            # remaining numeric fields
            field_names = ['young', 'poisson', 'sigma', 'm', 'hc']
            for idx, fname in enumerate(field_names, start=3):
                if len(parts) > idx:
                    if not allowed_all:
                        row_errors.append(f'{fname} (not allowed for non-interface body)')
                        continue
                    try:
                        self.materials[name][fname] = float(parts[idx])
                    except ValueError:
                        row_errors.append(f'{fname} (invalid number)')

            if row_errors:
                self.app.log(f'! Import: nieprawidłowe wartości dla bryły {name} (linia {i}): {", ".join(row_errors)} — pomijam błędne pola')
            else:
                imported += 1

        # If table exists, refresh displayed values for all rows matching imported names
        if self.row_widgets:
            for name, row_indices in getattr(self, 'rows_by_name', {}).items():
                vals = self.materials.get(name, {})
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
        # Read from widgets into self.materials — iterate rows (there may be multiple rows with same name)
        for r, widgets in self.row_widgets.items():
            name = widgets.get('name')
            if not name:
                continue
            if name not in self.materials:
                self.materials[name] = {}
            for key, ent in widgets.items():
                if key == 'name':
                    continue
                try:
                    if 'disabled' in ent.state():
                        val = ent.get()
                    else:
                        val = ent.get()
                except Exception:
                    val = ent.get()
                if key == 'material_name':
                    # keep last provided string
                    self.materials[name][key] = val
                else:
                    if val == '':
                        # keep as empty
                        self.materials[name][key] = ''
                    else:
                        try:
                            self.materials[name][key] = float(val)
                        except ValueError:
                            self.materials[name][key] = val
                            self.app.log(f'! Zapis materiałów: pole {key} dla bryły {name} ma nieprawidłową wartość: "{val}"')

        # Read from TIM widgets into self.tims (now a list)
        self.tims = []
        for tim_idx in sorted(self.tim_widgets.keys()):
            widgets = self.tim_widgets[tim_idx]
            tim_data = {}
            
            # Preserve or assign id
            wid_id = widgets.get('id')
            if not wid_id:
                wid_id = self._tim_next_id
                self._tim_next_id += 1
            tim_data['id'] = wid_id

            # Read TIM name
            try:
                tim_name = widgets['name'].get().strip()
                if not tim_name:
                    continue  # Skip empty TIM entries
                tim_data['name'] = tim_name
            except Exception:
                continue
            
            # Read k [W/mK]
            try:
                tim_k = widgets['k'].get()
                if tim_k == '':
                    tim_data['k'] = ''
                else:
                    tim_data['k'] = float(tim_k)
            except ValueError:
                self.app.log(f'! Zapis TIM: pole k ma nieprawidłową wartość: "{tim_k}"')
                continue
            except Exception:
                continue
            
            # Read type (gas/paste)
            try:
                tim_type = widgets['type'].get()
                tim_data['type'] = tim_type
            except Exception:
                tim_data['type'] = 'gas'
            
            # Read pressure_dependent
            try:
                tim_pressure = widgets['pressure_dependent'].get()
                # Secondary validation: if paste, force false
                if tim_data['type'] == 'paste':
                    tim_pressure = False
                tim_data['pressure_dependent'] = tim_pressure
            except Exception:
                tim_data['pressure_dependent'] = False
            
            self.tims.append(tim_data)

        # VALIDATION
        # Check if there are interfaces with TCR
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        interfaces_with_tcr = [it for it in interfaces if getattr(it, 'has_tcr', False)]

        # If there are TCR interfaces but no TIMs defined -> abort
        if interfaces_with_tcr and not self.tims:
            msg = 'Brak zdefiniowanych TIM-ów, mimo że system zawiera interfejsy z TCR. Zdefiniuj przynajmniej jeden TIM.'
            messagebox.showerror('Błąd zapisu', msg)
            self.app.log('! Zapis przerwany: brak TIM-ów, a istnieją interfejsy z TCR')
            return

        # For geometries participating in any TCR interface require full material params
        geom_names_required = set()
        for it in interfaces_with_tcr:
            try:
                geom_names_required.add(it.geom_top.name)
                geom_names_required.add(it.geom_bottom.name)
            except Exception:
                pass

        missing_errors = []
        required_fields = ['material_name', 'k', 'young', 'poisson', 'sigma', 'm', 'hc']
        for gname in sorted(geom_names_required):
            vals = self.materials.get(gname, {})
            for fld in required_fields:
                if fld not in vals or vals.get(fld, '') == '':
                    missing_errors.append(f'Bryła "{gname}": brak pola {fld}')
                else:
                    # numeric checks for numeric fields
                    if fld != 'material_name':
                        try:
                            float(vals.get(fld))
                        except Exception:
                            missing_errors.append(f'Bryła "{gname}": pole {fld} ma nieprawidłową wartość')

        if missing_errors:
            # Show summary popup and log details
            messagebox.showerror('Błąd zapisu', 'Nie wszystkie wymagane parametry materiałowe są zdefiniowane dla brył w interfejsach TCR. Sprawdź konsolę.')
            for e in missing_errors:
                self.app.log('! ' + e)
            return

        # Save to app
        self.app.system_materials = self.materials.copy()
        self.app.system_tims = self.tims.copy()
        self.app.log('✓ Zapisano materiały i TIM-y do systemu')

    def _add_tim_row(self):
        """Add a new empty TIM row to the library."""
        tid = self._tim_next_id
        self._tim_next_id += 1
        self.tims.append({
            'id': tid,
            'name': '',
            'k': '',
            'type': 'gas',
            'pressure_dependent': False
        })
        self.app.log('✓ Dodano nowy TIM do biblioteki')
        self.load_system()  # Rebuild table to show new row

    def _clear_all_tims(self):
        """Clear the entire TIM library."""
        if not self.tims:
            self.app.log('! Lista TIM-ów jest pusta')
            return
        count = len(self.tims)
        self.tims.clear()
        self.app.log(f'✓ Wyczyściłem listę TIM-ów ({count} pozycji)')
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

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
        except Exception as e:
            self.app.log(f'! Błąd przy czytaniu pliku TIM: {e}')
            return

        imported_count = 0
        for line in lines:
            parts = line.split()
            if len(parts) < 2:
                self.app.log(f'! Import TIM: linia "{line}" ma nieprawidłowy format (oczekiwano: nazwa k)')
                continue
            
            tim_name = parts[0]
            tim_k_str = parts[1]
            
            # Try to parse k as float
            try:
                tim_k = float(tim_k_str)
            except ValueError:
                self.app.log(f'! Import TIM: wartość k dla "{tim_name}" jest nieprawidłowa: "{tim_k_str}"')
                continue
            
            # Add to tims list with unique id
            tid = self._tim_next_id
            self._tim_next_id += 1
            self.tims.append({
                'id': tid,
                'name': tim_name,
                'k': tim_k,
                'type': 'gas',  # default
                'pressure_dependent': False  # default
            })
            imported_count += 1
        
        if imported_count > 0:
            self.app.log(f'✓ Importowano {imported_count} TIM-ów z pliku')
            self.load_system()  # Rebuild table
        else:
            self.app.log('! Nie udało się importować TIM-ów z pliku (brak prawidłowych wpisów)')