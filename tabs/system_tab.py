"""
System tab for defining geometry and interfaces.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import Canvas
import os
from models import Geometry, Interface
from dialogs import GeometryDialog
from controllers.system_controller import SystemManager


class SystemTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        # Controller (business logic)
        self.manager = SystemManager(app=self.app)
        self.manager.subscribe(self._on_manager_event)

        # View state
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
            success, msg = self.manager.add_geometry(dialog.result, index)
            if success:
                self.app.log(f'✓ {msg}')
                self._redraw_canvas()
            else:
                messagebox.showwarning('Warning', msg)
                self.app.log(f'! {msg} — odrzucono')
    
    def _add_geometry_at(self, index):
        """Add geometry at specific position (for 'above' button)."""
        self._add_geometry(index)
    
    def _rebuild_interfaces(self):
        """Wrapper delegating to manager."""
        success, _ = self.manager.rebuild_interfaces()
        if success:
            # Logging of removed TCRs handled in event callback
            pass
    
    def _redraw_canvas(self):
        """Redraw the visualization of geometries and interfaces."""
        self.canvas.delete('all')
        
        geoms = self.manager.get_geometries()
        if not geoms:
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
        total_height = sum(g.height for g in geoms)
        max_width = max(g.width for g in geoms)
        
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
        
        for i, geom in enumerate(geoms):
            # Scale height
            scaled_height = (geom.height / total_height) * draw_height if total_height > 0 else draw_height / len(geoms)
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
        
        for i, interface in enumerate(self.manager.get_interfaces()):
            var = tk.BooleanVar(value=interface.has_tcr)
            cb = ttk.Checkbutton(
                self.tcr_frame,
                text=f'{interface.geom_top.name}→{interface.geom_bottom.name}',
                variable=var,
                command=lambda idx=i, v=var: self._on_tcr_change(idx, v)
            )
            cb.pack(anchor='w', padx=5, pady=2)
            # Store reference on interface object for UI convenience
            self.manager.interfaces[i]._tcr_var = var
    
    def _on_tcr_change(self, interface_idx, var):
        """Update TCR flag when checkbox is toggled."""
        if 0 <= interface_idx < len(self.manager.interfaces):
            new_val = var.get()
            success, msg = self.manager.set_tcr_flag(interface_idx, new_val)
            if success:
                symbol = '✓' if new_val else '✗'
                self.app.log(f'{symbol} {msg}')
    
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
        geoms = self.manager.get_geometries()
        geom = geoms[index]
        
        def on_delete():
            """Callback when delete is requested."""
            success, msg = self.manager.remove_geometry(index)
            if success:
                self.app.log(f'✗ {msg}')
                self._redraw_canvas()
        
        dialog = GeometryDialog(self, geometry=geom, on_delete=on_delete)
        self.wait_window(dialog)
        
        # Only update if not deleted and result is valid
        if dialog.delete_requested:
            return
        
        if dialog.result:
            success, msg = self.manager.update_geometry(index, dialog.result)
            if success:
                self.app.log(f'✓ {msg}')
                self._redraw_canvas()
            else:
                messagebox.showwarning('Warning', msg)
                self.app.log(f'! {msg} — odrzucono')
    
    def _import_file(self):
        """Import geometry from file."""
        file_path = filedialog.askopenfilename(
            filetypes=[('Text files', '*.txt'), ('All files', '*.*')],
            initialdir=os.path.dirname(os.path.abspath(__file__))
        )
        
        if not file_path:
            return
        
        success, msg = self.manager.import_from_file(file_path)
        if success:
            # Count taken from message, ensure UI refresh
            self._redraw_canvas()
            messagebox.showinfo('Success', msg)
            self.app.log(f'✓ Zaimportowano geometrię z pliku — {msg}')
        else:
            messagebox.showerror('Error', msg)
    
    def _export_system(self):
        """Export geometry system to file."""
        # Manager will validate export preconditions
        
        file_path = filedialog.asksaveasfilename(
            filetypes=[('Text files', '*.txt')],
            defaultextension='.txt',
            initialdir=os.path.dirname(os.path.abspath(__file__))
        )
        
        if not file_path:
            return
        
        success, msg = self.manager.export_to_file(file_path)
        if success:
            messagebox.showinfo('Success', msg)
            self.app.log(f'✓ Wyeksportowano system do pliku: {os.path.basename(file_path)}')
        else:
            messagebox.showerror('Error', msg)
    
    def _save_system(self):
        """Save and validate the system before moving to next tab."""
        ok, validation_msg = self.manager.validate_system()
        if not ok:
            # Map manager messages to original UI wording
            if validation_msg.startswith('Zdefiniuj'):
                messagebox.showwarning('Warning', 'Define at least one geometry')
            else:
                messagebox.showerror('Error', validation_msg.replace('Nieprawidłowe', 'Invalid'))
            return
        
        # Store system in parent app
        if hasattr(self.app, 'system_geometries'):
            self.app.system_geometries = self.manager.get_geometries()
            self.app.system_interfaces = self.manager.get_interfaces()
            
            # Create simple system object for easier access
            class System:
                pass
            sys = System()
            sys.geometries = self.manager.get_geometries()
            sys.interfaces = self.manager.get_interfaces()
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

    # --- Manager events -> View updates ---
    def _on_manager_event(self, event_type, data):
        if event_type in ('geometry_added', 'geometry_removed', 'geometry_updated', 'interfaces_rebuilt', 'imported'):
            # Handle removed TCR logs
            if event_type == 'interfaces_rebuilt':
                removed_tcrs = data.get('removed_tcrs', [])
                current_names = {g.name for g in self.manager.get_geometries()}
                for top_name, bot_name in removed_tcrs:
                    removed_geom = None
                    if top_name not in current_names:
                        removed_geom = top_name
                    elif bot_name not in current_names:
                        removed_geom = bot_name
                    if removed_geom:
                        self.app.log(f'✗ Usunięto TCR: {top_name}→{bot_name} na skutek usunięcia bryły: {removed_geom}')
                    else:
                        self.app.log(f'✗ Usunięto TCR: {top_name}→{bot_name}')
            # Redraw UI consistently
            self._redraw_canvas()
