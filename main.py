"""
TCR (Thermal Contact Resistance) Analysis Application
Main entry point and application window.
"""
import tkinter as tk
from tkinter import ttk
from tabs import SystemTab, MaterialsTab, ForcesTab, SimulationTab


class App(tk.Tk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        self.title('TCR — Inżynierska aplikacja do analizy oporów kontaktowych')
        self.geometry('1000x700')

        # System state
        self.system = None
        self.system_geometries = []
        self.system_interfaces = []
        self.system_materials = {}
        self.system_tims = {}
        self.system_forces = []

        # Create main frame
        frm_main = ttk.Frame(self)
        frm_main.pack(fill='both', expand=True)

        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(frm_main)
        notebook.pack(fill='both', expand=True)

        # Create tabs
        self.system_tab = SystemTab(notebook, self)
        self.materials_tab = MaterialsTab(notebook, self)
        self.forces_tab = ForcesTab(notebook, self)
        self.simulation_tab = SimulationTab(notebook, self)

        # Add tabs to notebook
        notebook.add(self.system_tab, text='System')
        notebook.add(self.materials_tab, text='Materiały')
        notebook.add(self.forces_tab, text='Naciski')
        notebook.add(self.simulation_tab, text='Symulacja')

        # Create console at bottom
        frm_console = ttk.LabelFrame(frm_main, text='Console', height=150)
        frm_console.pack(fill='x', padx=10, pady=10)
        frm_console.pack_propagate(False)

        # Text widget with scrollbar
        scrollbar = ttk.Scrollbar(frm_console)
        scrollbar.pack(side='right', fill='y')

        self.console = tk.Text(frm_console, height=8, wrap='word', yscrollcommand=scrollbar.set)
        self.console.pack(fill='both', expand=True, padx=5, pady=5)
        self.console.config(state='disabled')
        scrollbar.config(command=self.console.yview)

    def log(self, message):
        """Add message to console."""
        self.console.config(state='normal')
        self.console.insert('end', message + '\n')
        self.console.see('end')  # Auto-scroll to bottom
        self.console.config(state='disabled')


def main():
    """Application entry point."""
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()