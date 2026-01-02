"""
Report Viewer Dialog - Dialog for viewing execution reports.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional


class ReportViewerDialog(tk.Toplevel):
    """
    Dialog for displaying execution report.
    """
    
    def __init__(self, parent, report_text: str, title: str = "Raport wykonania"):
        super().__init__(parent)
        
        self.report_text = report_text
        
        self.title(title)
        self.geometry("800x600")
        self.minsize(600, 400)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.focus_set()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        # Text area with scrollbar
        text_frame = ttk.Frame(self, padding=10)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.text = tk.Text(
            text_frame,
            wrap=tk.NONE,
            font=('Consolas', 10),
            bg='#1e1e1e',
            fg='#d4d4d4',
            insertbackground='white'
        )
        
        v_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        h_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=self.text.xview)
        
        self.text.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.text.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)
        
        # Insert report text
        self.text.insert('1.0', self.report_text)
        self.text.config(state='disabled')
        
        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(
            btn_frame, text="📋 Kopiuj do schowka",
            command=self._copy_to_clipboard,
            width=20
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            btn_frame, text="💾 Zapisz jako...",
            command=self._save_report,
            width=15
        ).pack(side=tk.LEFT, padx=10)
        
        ttk.Button(
            btn_frame, text="Zamknij",
            command=self.destroy,
            width=15
        ).pack(side=tk.RIGHT)
    
    def _copy_to_clipboard(self):
        """Copy report to clipboard."""
        self.clipboard_clear()
        self.clipboard_append(self.report_text)
        
        from tkinter import messagebox
        messagebox.showinfo(
            "Skopiowano",
            "Raport został skopiowany do schowka.",
            parent=self
        )
    
    def _save_report(self):
        """Save report to file."""
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Zapisz raport",
            defaultextension=".txt",
            filetypes=[
                ("Pliki tekstowe", "*.txt"),
                ("Wszystkie pliki", "*.*")
            ]
        )
        
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.report_text)
                
                from tkinter import messagebox
                messagebox.showinfo(
                    "Zapisano",
                    f"Raport został zapisany:\n{filepath}",
                    parent=self
                )
            except Exception as e:
                from tkinter import messagebox
                messagebox.showerror(
                    "Błąd",
                    f"Nie można zapisać raportu:\n{e}",
                    parent=self
                )
