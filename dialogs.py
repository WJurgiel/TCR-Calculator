"""
Dialog windows for the TCR application.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from models import Geometry


class GeometryDialog(tk.Toplevel):
    """Dialog to input/edit geometry parameters."""
    def __init__(self, parent, geometry=None, on_delete=None):
        super().__init__(parent)
        self.title('Define Geometry' if geometry is None else 'Edit Geometry')
        self.geometry('300x250' if geometry else '300x200')
        self.resizable(False, False)
        self.grab_set()
        
        self.result = None
        self.delete_requested = False
        self.geometry_obj = geometry
        self.on_delete = on_delete
        
        # Name
        ttk.Label(self, text='Name:').grid(row=0, column=0, sticky='w', padx=10, pady=5)
        self.entry_name = ttk.Entry(self, width=25)
        self.entry_name.grid(row=0, column=1, padx=10, pady=5)
        if geometry:
            self.entry_name.insert(0, geometry.name)
        
        # Length
        ttk.Label(self, text='Length (m):').grid(row=1, column=0, sticky='w', padx=10, pady=5)
        self.entry_length = ttk.Entry(self, width=25)
        self.entry_length.grid(row=1, column=1, padx=10, pady=5)
        if geometry:
            self.entry_length.insert(0, str(geometry.length))
        
        # Width
        ttk.Label(self, text='Width (m):').grid(row=2, column=0, sticky='w', padx=10, pady=5)
        self.entry_width = ttk.Entry(self, width=25)
        self.entry_width.grid(row=2, column=1, padx=10, pady=5)
        if geometry:
            self.entry_width.insert(0, str(geometry.width))
        
        # Height
        ttk.Label(self, text='Height (m):').grid(row=3, column=0, sticky='w', padx=10, pady=5)
        self.entry_height = ttk.Entry(self, width=25)
        self.entry_height.grid(row=3, column=1, padx=10, pady=5)
        if geometry:
            self.entry_height.insert(0, str(geometry.height))
        
        # Buttons
        frm_btn = ttk.Frame(self)
        frm_btn.grid(row=4, column=0, columnspan=2, pady=10)
        ttk.Button(frm_btn, text='Define', command=self._on_define).pack(side='left', padx=5)
        ttk.Button(frm_btn, text='Cancel', command=self.destroy).pack(side='left', padx=5)
        
        # Delete button (only in edit mode)
        if geometry:
            ttk.Button(frm_btn, text='Delete', command=self._on_delete).pack(side='left', padx=5)
    
    def _on_define(self):
        try:
            name = self.entry_name.get().strip()
            length = float(self.entry_length.get())
            width = float(self.entry_width.get())
            height = float(self.entry_height.get())
            
            if not name:
                messagebox.showerror('Error', 'Name cannot be empty')
                return
            if length <= 0 or width <= 0 or height <= 0:
                messagebox.showerror('Error', 'All dimensions must be positive')
                return
            
            self.result = Geometry(name, length, width, height)
            self.destroy()
        except ValueError:
            messagebox.showerror('Error', 'Invalid number format')
    
    def _on_delete(self):
        """Delete the geometry."""
        if messagebox.askyesno('Confirm', f'Delete geometry "{self.geometry_obj.name}"?'):
            self.delete_requested = True
            if self.on_delete:
                self.on_delete()
            self.destroy()

