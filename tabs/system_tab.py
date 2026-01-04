"""
System tab for defining geometry and interfaces.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import Canvas
import os
from models import Geometry, Interface
from dialogs import GeometryDialog


class SystemTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        
        # System state
        self.geometries = []  # List of Geometry objects
        self.interfaces = []  # List of Interface objects
        self.system_saved = False
        
        # Main layout
        frm_top = ttk.Frame(self)
        frm_top.pack(fill='x', padx=10, pady=10)
        
        ttk.Label(frm_top, text='System Definition').pack(anchor='w')
        
        frm_buttons = ttk.Frame(frm_top)
        frm_buttons.pack(fill='x', pady=5)
        
        ttk.Button(frm_buttons, text='Import from File', command=self._import_file).pack(side='left', padx=2)
        ttk.Button(frm_buttons, text='Save System', command=self._save_system).pack(side='left', padx=2)
        ttk.Button(frm_buttons, text='Export System', command=self._export_system).pack(side='left', padx=2)
        
        # Canvas for visualization
        frm_canvas = ttk.Frame(self)
        frm_canvas.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Add buttons above canvas
        frm_above = ttk.Frame(frm_canvas)
        frm_above.pack(fill='x', pady=5)
        ttk.Button(frm_above, text='+ Add geometry above', command=lambda: self._add_geometry_at(0)).pack()
        
        self.canvas = Canvas(frm_canvas, bg='white', height=300, relief='sunken', bd=1)
        self.canvas.pack(fill='both', expand=True, side='left')
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        
        # Right panel: TCR checkboxes
        frm_right = ttk.Frame(frm_canvas)
        frm_right.pack(side='left', fill='y', padx=10)
        
        ttk.Label(frm_right, text='TCR').pack()
        self.tcr_frame = ttk.Frame(frm_right)
        self.tcr_frame.pack(fill='y', expand=True)
        
        # Add buttons below canvas
        frm_below = ttk.Frame(self)
        frm_below.pack(fill='x', padx=10, pady=5)
        ttk.Button(frm_below, text='+ Add geometry below', command=self._add_geometry).pack()
        
        # Schedule redraw after canvas is rendered
        self.canvas.after(100, self._redraw_canvas)
    
    def _add_geometry(self, index=None):
        """Add a new geometry (optionally at specific index)."""
        dialog = GeometryDialog(self)
        self.wait_window(dialog)
        
        if dialog.result:
            # Check for name uniqueness
            new_name = dialog.result.name
            existing_names = [g.name for g in self.geometries]
            if new_name in existing_names:
                messagebox.showwarning('Warning', f'Bryła "{new_name}" już istnieje. Zmień nazwę.')
                self.app.log(f'! Próba dodania bryły z istniejącą nazwą: {new_name} — odrzucono')
                return
            
            if index is None:
                self.geometries.append(dialog.result)
            else:
                self.geometries.insert(index, dialog.result)
            
            # Rebuild interfaces
            self._rebuild_interfaces()
            self._redraw_canvas()

            # Log to console
            geom = dialog.result
            self.app.log(f'✓ Dodano Geometrię: {geom.name} (a={geom.length}, b={geom.width}, h={geom.height})')
    
    def _add_geometry_at(self, index):
        """Add geometry at specific position (for 'above' button)."""
        self._add_geometry(index)
    
    def _rebuild_interfaces(self):
        """Rebuild interface list based on current geometries."""
        old_interfaces = {(g.geom_top.name, g.geom_bottom.name): g.has_tcr
                          for g in self.interfaces if isinstance(g, Interface)}

        # Determine current geometry names for removed-geometry detection
        current_names = {g.name for g in self.geometries}

        # Build new interfaces, preserving TCR flags where possible
        new_keys = []
        new_interfaces = []
        for i in range(len(self.geometries) - 1):
            geom_top = self.geometries[i]
            geom_bottom = self.geometries[i + 1]
            key = (geom_top.name, geom_bottom.name)
            new_keys.append(key)
            has_tcr = old_interfaces.get(key, False)
            new_interfaces.append(Interface(geom_top, geom_bottom, has_tcr))

        # Log any TCRs that existed previously but are no longer present
        removed_tcrs = [k for k, v in old_interfaces.items() if v and k not in new_keys]
        for top_name, bot_name in removed_tcrs:
            # try to detect which geometry was removed
            removed_geom = None
            if top_name not in current_names:
                removed_geom = top_name
            elif bot_name not in current_names:
                removed_geom = bot_name

            if removed_geom:
                self.app.log(f'✗ Usunięto TCR: {top_name}→{bot_name} na skutek usunięcia bryły: {removed_geom}')
            else:
                self.app.log(f'✗ Usunięto TCR: {top_name}→{bot_name}')

        self.interfaces = new_interfaces
    
    def _redraw_canvas(self):
        """Redraw the visualization of geometries and interfaces."""
        self.canvas.delete('all')
        
        if not self.geometries:
            # Calculate canvas dimensions for centering
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1:
                canvas_width = 400
            if canvas_height <= 1:
                canvas_height = 300
            
            center_x = canvas_width / 2
            center_y = canvas_height / 2
            
            self.canvas.create_text(center_x, center_y, text='No geometries defined. Click button above to add.', fill='gray')
            for w in self.tcr_frame.winfo_children():
                w.destroy()
            return
        
        # Calculate total height and max width
        total_height = sum(g.height for g in self.geometries)
        max_width = max(g.width for g in self.geometries)
        
        # Canvas dimensions
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        
        if canvas_width <= 1:
            canvas_width = 400
        if canvas_height <= 1:
            canvas_height = 300
        
        margin = 30
        draw_width = canvas_width - 2 * margin
        draw_height = canvas_height - 2 * margin
        
        # Draw geometries
        y_pos = margin
        self.geometry_rects = []  # Store rect info for click handling
        
        for i, geom in enumerate(self.geometries):
            # Scale height
            scaled_height = (geom.height / total_height) * draw_height if total_height > 0 else draw_height / len(self.geometries)
            # Scale width
            scaled_width = (geom.width / max_width) * draw_width if max_width > 0 else draw_width
            
            # Center the rectangle horizontally
            x_offset = (draw_width - scaled_width) / 2
            x1, y1 = margin + x_offset, y_pos
            x2, y2 = x1 + scaled_width, y_pos + scaled_height
            
            # Draw rectangle
            rect = self.canvas.create_rectangle(x1, y1, x2, y2, fill='lightblue', outline='black', width=2)
            
            # Draw name
            self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=geom.name, font=('Arial', 10, 'bold'))
            
            # Draw validation symbol
            symbol = '✓' if geom.is_valid() else '⚠'
            symbol_color = 'green' if geom.is_valid() else 'red'
            self.canvas.create_text(x2 + 10, (y1 + y2) / 2, text=symbol, font=('Arial', 12, 'bold'), fill=symbol_color)
            
            self.geometry_rects.append((i, rect, x1, y1, x2, y2))
            y_pos = y2
        
        # Redraw TCR checkboxes
        self._redraw_tcr_checkboxes()
    
    def _redraw_tcr_checkboxes(self):
        """Redraw TCR checkboxes in the right panel."""
        for w in self.tcr_frame.winfo_children():
            w.destroy()
        
        for i, interface in enumerate(self.interfaces):
            var = tk.BooleanVar(value=interface.has_tcr)
            cb = ttk.Checkbutton(
                self.tcr_frame,
                text=f'{interface.geom_top.name}→{interface.geom_bottom.name}',
                variable=var,
                command=lambda idx=i, v=var: self._on_tcr_change(idx, v)
            )
            cb.pack(anchor='w', padx=5, pady=2)
            self.interfaces[i]._tcr_var = var  # Store reference
    
    def _on_tcr_change(self, interface_idx, var):
        """Update TCR flag when checkbox is toggled."""
        if 0 <= interface_idx < len(self.interfaces):
            new_val = var.get()
            self.interfaces[interface_idx].has_tcr = new_val
            top = self.interfaces[interface_idx].geom_top.name
            bot = self.interfaces[interface_idx].geom_bottom.name
            if new_val:
                self.app.log(f'✓ Dodano TCR: {top}→{bot}')
            else:
                self.app.log(f'✗ Usunięto TCR: {top}→{bot}')
    
    def _on_canvas_click(self, event):
        """Handle click on geometry rectangle to edit it."""
        if not hasattr(self, 'geometry_rects'):
            return
        
        for idx, rect, x1, y1, x2, y2 in self.geometry_rects:
            if x1 <= event.x <= x2 and y1 <= event.y <= y2:
                self._edit_geometry(idx)
                return
    
    def _edit_geometry(self, index):
        """Edit an existing geometry."""
        geom = self.geometries[index]
        
        def on_delete():
            """Callback when delete is requested."""
            self.geometries.pop(index)
            self.app.log(f'✗ Usunięto Geometrię: {geom.name}')
            self._rebuild_interfaces()
            self._redraw_canvas()
        
        dialog = GeometryDialog(self, geometry=geom, on_delete=on_delete)
        self.wait_window(dialog)
        
        # Only update if not deleted and result is valid
        if dialog.delete_requested:
            return
        
        if dialog.result:
            # Check if name changed and if new name already exists in another geometry
            new_name = dialog.result.name
            old_name = geom.name
            if new_name != old_name:
                other_names = [g.name for i, g in enumerate(self.geometries) if i != index]
                if new_name in other_names:
                    messagebox.showwarning('Warning', f'Bryła "{new_name}" już istnieje. Zmień nazwę.')
                    self.app.log(f'! Próba zmiany nazwy na istniejącą: {new_name} — odrzucono')
                    return
            
            self.geometries[index] = dialog.result
            self.app.log(f'✓ Edytowano Geometrię: {dialog.result.name} (a={dialog.result.length}, b={dialog.result.width}, h={dialog.result.height})')
            self._rebuild_interfaces()
            self._redraw_canvas()
    
    def _import_file(self):
        """Import geometry from file."""
        file_path = filedialog.askopenfilename(
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialdir=os.path.dirname(os.path.abspath(__file__))
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
            
            geometries = []
            
            for i, line in enumerate(lines):
                # Parse geometry line
                parts = line.split()
                if len(parts) < 4:
                    messagebox.showerror('Error', f'Invalid format at line {i+1}')
                    return
                
                try:
                    name = parts[0]
                    length = float(parts[1])
                    width = float(parts[2])
                    height = float(parts[3])
                    geometries.append(Geometry(name, length, width, height))
                except ValueError:
                    messagebox.showerror('Error', f'Invalid numbers at line {i+1}')
                    return
            
            # Check for duplicate names
            names = [g.name for g in geometries]
            if len(names) != len(set(names)):
                duplicates = [n for n in set(names) if names.count(n) > 1]
                messagebox.showerror('Error', f'Nieprawidłowe dane: dwie bryły o takich samych nazwach: {", ".join(duplicates)}')
                self.app.log(f'! Import przerwany: duplikaty nazw brył — {", ".join(duplicates)}')
                return
            
            self.geometries = geometries
            self._rebuild_interfaces()
            self._redraw_canvas()
            messagebox.showinfo('Success', f'Imported {len(geometries)} geometries')
            self.app.log(f'✓ Zaimportowano {len(geometries)} geometrii z pliku')
        
        except Exception as e:
            messagebox.showerror('Error', f'Failed to import: {str(e)}')
    
    def _export_system(self):
        """Export geometry system to file."""
        if not self.geometries:
            messagebox.showwarning('Warning', 'No geometries to export')
            return
        
        file_path = filedialog.asksaveasfilename(
            filetypes=[('Text files', '*.txt')],
            defaultextension='.txt',
            initialdir=os.path.dirname(os.path.abspath(__file__))
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w') as f:
                for geom in self.geometries:
                    f.write(f'{geom.name}\t{geom.length}\t{geom.width}\t{geom.height}\n')
            
            messagebox.showinfo('Success', f'Exported to {os.path.basename(file_path)}')
            self.app.log(f'✓ Wyeksportowano system do pliku: {os.path.basename(file_path)}')
        
        except Exception as e:
            messagebox.showerror('Error', f'Failed to export: {str(e)}')
    
    def _save_system(self):
        """Save and validate the system before moving to next tab."""
        if not self.geometries:
            messagebox.showwarning('Warning', 'Define at least one geometry')
            return
        
        invalid = [g for g in self.geometries if not g.is_valid()]
        if invalid:
            names = ', '.join(g.name for g in invalid)
            messagebox.showerror('Error', f'Invalid geometries: {names}')
            return
        
        # Store system in parent app
        if hasattr(self.app, 'system_geometries'):
            self.app.system_geometries = self.geometries
            self.app.system_interfaces = self.interfaces
            
            # Create simple system object for easier access
            class System:
                pass
            sys = System()
            sys.geometries = self.geometries
            sys.interfaces = self.interfaces
            self.app.system = sys

        self.system_saved = True
        # Log and notify other tabs
        try:
            self.app.log('✓ System saved successfully')
        except Exception:
            pass

        # If MaterialsTab is present, prompt it to load the new system
        try:
            if hasattr(self.app, 'materials_tab') and hasattr(self.app.materials_tab, 'load_system'):
                self.app.materials_tab.load_system()
                self.app.log('i Zakładka "Materiały" została zaktualizowana ze zdefiniowanego systemu')
        except Exception as e:
            # Do not block saving on downstream errors
            self.app.log(f'! Błąd podczas odświeżania zakładki Materiały: {e}')

        messagebox.showinfo('Success', 'System saved successfully')
