"""
Intermediates tab for managing intermediate substances.
"""
from tkinter import ttk


class IntermediatesTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        lbl = ttk.Label(self, text='Zakładka 3 — Substancje pośredniczące: lista substancji')
        lbl.pack(padx=10, pady=10, anchor='w')
