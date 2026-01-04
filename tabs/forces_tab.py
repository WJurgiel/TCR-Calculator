"""
Forces tab for defining forces (in Newtons) and calculating contact pressures.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import csv
import os


class ForcesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Internal storage: list of forces in Newtons
        self.forces = []
        self.force_widgets = {}  # idx -> entry widget for force value

        # Header / controls
        frm_top = ttk.Frame(self)
        frm_top.pack(fill='x', padx=10, pady=8)

        self.lbl_title = ttk.Label(frm_top, text='Naciski — definicja sił w Newtonach')
        self.lbl_title.pack(side='left')

        # Buttons
        frm_buttons = ttk.Frame(frm_top)
        frm_buttons.pack(side='right', padx=0, pady=0)

        ttk.Button(frm_buttons, text='+ Add Force', command=self._add_force_row).pack(side='left', padx=4)
        ttk.Button(frm_buttons, text='Import from File', command=self._import_forces_file).pack(side='left', padx=4)
        ttk.Button(frm_buttons, text='Clear All', command=self._clear_all_forces).pack(side='left', padx=4)
        ttk.Button(frm_buttons, text='Generate Report', command=self._generate_report).pack(side='left', padx=4)

        # Scrollable area for forces list
        self.container = ttk.Frame(self)
        self.container.pack(fill='both', expand=True, padx=10, pady=10)

    def _add_force_row(self):
        """Add a new empty force row."""
        self.forces.append({'value': ''})
        self.app.log('✓ Dodano nową siłę do listy')
        self._rebuild_forces_list()

    def _clear_all_forces(self):
        """Clear all forces."""
        if not self.forces:
            self.app.log('! Lista sił jest pusta')
            return
        count = len(self.forces)
        self.forces.clear()
        self.app.log(f'✓ Wyczyściłem listę sił ({count} pozycji)')
        self._rebuild_forces_list()

    def _import_forces_file(self):
        """Import forces from file (one force per line)."""
        file_path = filedialog.askopenfilename(filetypes=[('Text files', '*.txt'), ('All', '*.*')])
        if not file_path:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().startswith('#')]
        except Exception as e:
            self.app.log(f'! Błąd przy czytaniu pliku sił: {e}')
            return

        imported_count = 0
        for line in lines:
            try:
                force_val = float(line)
                self.forces.append({'value': force_val})
                imported_count += 1
            except ValueError:
                self.app.log(f'! Import sił: nieprawidłowa wartość "{line}" — pomijam')
                continue

        if imported_count > 0:
            self.app.log(f'✓ Importowano {imported_count} sił z pliku')
            self._rebuild_forces_list()
        else:
            self.app.log('! Nie udało się importować sił z pliku (brak prawidłowych wpisów)')

    def _rebuild_forces_list(self):
        """Rebuild the forces list UI."""
        # Clear container
        for widget in self.container.winfo_children():
            widget.destroy()

        if not self.forces:
            lbl = ttk.Label(self.container, text='(brak zdefiniowanych sił)')
            lbl.pack(padx=10, pady=10)
            return

        # Canvas and scrollbar for forces
        canvas = tk.Canvas(self.container)
        vsb = ttk.Scrollbar(self.container, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)

        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor='nw')

        # Header
        frm_header = ttk.Frame(inner)
        frm_header.grid(row=0, column=0, columnspan=2, sticky='we', padx=4, pady=4)
        ttk.Label(frm_header, text='Siła [N]', font=('', 9, 'bold')).pack(side='left')

        # Force rows
        self.force_widgets = {}
        for idx, force_data in enumerate(self.forces, start=1):
            ent = ttk.Entry(inner, width=15)
            ent.grid(row=idx, column=0, padx=4, pady=2, sticky='w')
            ent.delete(0, 'end')
            ent.insert(0, str(force_data.get('value', '')))
            self.force_widgets[idx - 1] = ent

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

    def _save_forces(self):
        """Save forces from widgets back to self.forces."""
        for idx, ent in self.force_widgets.items():
            if idx < len(self.forces):
                try:
                    val_str = ent.get().strip()
                    if val_str == '':
                        self.forces[idx]['value'] = ''
                    else:
                        self.forces[idx]['value'] = float(val_str)
                except ValueError:
                    self.app.log(f'! Siła o indeksie {idx} ma nieprawidłową wartość: "{val_str}"')
                    self.forces[idx]['value'] = ''

        self.app.system_forces = self.forces.copy()
        self.app.log('✓ Zapisano siły do systemu')

    def _generate_report(self):
        """Generate and display contact pressure report for each force and TCR interface."""
        # Save current forces first
        self._save_forces()

        # Check if there are forces
        if not self.forces:
            messagebox.showwarning('Brak sił', 'Zdefiniuj przynajmniej jedną siłę do generowania raportu')
            return

        # Get TCR interfaces
        interfaces = getattr(self.app, 'system_interfaces', []) or []
        tcr_interfaces = [it for it in interfaces if getattr(it, 'has_tcr', False)]

        if not tcr_interfaces:
            messagebox.showwarning('Brak interfejsów TCR', 'Nie ma żadnych interfejsów ze zdefiniowanym TCR')
            return

        # Build report data: for each force case and each interface, calculate pressure
        report_data = []
        for force_idx, force_data in enumerate(self.forces):
            try:
                force_val = float(force_data.get('value', 0))
            except (ValueError, TypeError):
                continue

            for iface in tcr_interfaces:
                try:
                    a_nominal = iface.A_nominal  # m^2
                    pressure = force_val / a_nominal if a_nominal > 0 else 0  # Pa
                    iface_name = f"{iface.geom_top.name} → {iface.geom_bottom.name}"
                    
                    report_data.append({
                        'force_idx': force_idx,
                        'force_value': force_val,
                        'interface': iface_name,
                        'area': a_nominal,
                        'pressure': pressure
                    })
                except Exception as e:
                    self.app.log(f'! Błąd przy liczeniu ciśnienia dla interfejsu: {e}')
                    continue

        if not report_data:
            messagebox.showerror('Błąd', 'Nie udało się wygenerować raportu')
            return

        # Open report window
        self._show_report_window(report_data)

    def _show_report_window(self, report_data):
        """Display report in a new window with table and CSV export."""
        report_win = tk.Toplevel(self.app)
        report_win.title('Raport: Nacisk i Ciśnienie Kontaktowe')
        report_win.geometry('900x600')

        # Toolbar with Export button
        frm_toolbar = ttk.Frame(report_win)
        frm_toolbar.pack(fill='x', padx=10, pady=8)

        ttk.Button(frm_toolbar, text='Export to CSV', 
                  command=lambda: self._export_report_csv(report_data)).pack(side='left', padx=4)

        # Table with scrollbars
        frm_table = ttk.Frame(report_win)
        frm_table.pack(fill='both', expand=True, padx=10, pady=10)

        # Canvas for scrolling
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
        headers = ['Siła [N]', 'Interfejs', 'Pow. Nom. [m²]', 'Ciśnienie [Pa]', 'Ciśnienie [MPa]']
        for col, header_text in enumerate(headers):
            lbl = ttk.Label(inner, text=header_text, font=('', 9, 'bold'), background='lightgray')
            lbl.grid(row=0, column=col, padx=4, pady=2, sticky='we')

        # Data rows
        for row_idx, row_data in enumerate(report_data, start=1):
            force_val = row_data['force_value']
            iface_name = row_data['interface']
            area = row_data['area']
            pressure_pa = row_data['pressure']
            pressure_mpa = pressure_pa / 1e6

            ttk.Label(inner, text=f"{force_val:.2f}").grid(row=row_idx, column=0, padx=4, pady=2)
            ttk.Label(inner, text=iface_name).grid(row=row_idx, column=1, padx=4, pady=2)
            ttk.Label(inner, text=f"{area:.6e}").grid(row=row_idx, column=2, padx=4, pady=2)
            ttk.Label(inner, text=f"{pressure_pa:.2e}").grid(row=row_idx, column=3, padx=4, pady=2)
            ttk.Label(inner, text=f"{pressure_mpa:.4f}").grid(row=row_idx, column=4, padx=4, pady=2)

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

    def _export_report_csv(self, report_data):
        """Export report data to CSV file."""
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
                writer.writerow(['Siła [N]', 'Interfejs', 'Pow. Nom. [m²]', 'Ciśnienie [Pa]', 'Ciśnienie [MPa]'])
                # Data rows
                for row_data in report_data:
                    force_val = row_data['force_value']
                    iface_name = row_data['interface']
                    area = row_data['area']
                    pressure_pa = row_data['pressure']
                    pressure_mpa = pressure_pa / 1e6
                    writer.writerow([f"{force_val:.2f}", iface_name, f"{area:.6e}", 
                                   f"{pressure_pa:.2e}", f"{pressure_mpa:.4f}"])
            
            self.app.log(f'✓ Eksportowano raport do pliku: {os.path.basename(file_path)}')
            messagebox.showinfo('Sukces', f'Raport został wyeksportowany do:\n{file_path}')
        except Exception as e:
            messagebox.showerror('Błąd', f'Nie udało się wyeksportować raportu: {e}')
            self.app.log(f'! Błąd przy eksporcie: {e}')
