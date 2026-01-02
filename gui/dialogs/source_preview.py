"""
Source Preview Dialog - Dialog for previewing data source contents.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional
import pandas as pd


class SourcePreviewDialog(tk.Toplevel):
    """
    Dialog for previewing DataFrame contents.
    """
    
    def __init__(self, parent, df: pd.DataFrame, title: str = "Podgląd danych", 
                 max_rows: int = 500):
        super().__init__(parent)
        
        self.df = df
        self.max_rows = max_rows
        
        self.title(title)
        self.geometry("900x600")
        self.minsize(600, 400)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._load_data()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.focus_set()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        # Info bar
        info_frame = ttk.Frame(self, padding=10)
        info_frame.pack(fill=tk.X)
        
        ttk.Label(
            info_frame,
            text=f"Wierszy: {len(self.df):,} │ Kolumn: {len(self.df.columns)}",
            font=('Segoe UI', 10, 'bold')
        ).pack(side=tk.LEFT)
        
        # Search
        ttk.Label(info_frame, text="🔍").pack(side=tk.LEFT, padx=(20, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._filter_data())
        
        search_entry = ttk.Entry(info_frame, textvariable=self.search_var, width=25)
        search_entry.pack(side=tk.LEFT)
        
        # Treeview
        tree_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = list(self.df.columns)
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings')
        
        # Configure columns
        for col in columns:
            self.tree.heading(col, text=col, anchor=tk.W)
            # Auto-size based on header and first few values
            width = max(len(str(col)) * 10, 80)
            self.tree.column(col, width=min(width, 200), minwidth=50)
        
        # Scrollbars
        v_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        h_scroll = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        
        self.tree.grid(row=0, column=0, sticky='nsew')
        v_scroll.grid(row=0, column=1, sticky='ns')
        h_scroll.grid(row=1, column=0, sticky='ew')
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Buttons
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(
            btn_frame, text="Zamknij",
            command=self.destroy,
            width=15
        ).pack(side=tk.RIGHT)
    
    def _load_data(self):
        """Load data into treeview."""
        self._populate_tree(self.df)
    
    def _filter_data(self):
        """Filter data based on search."""
        search_text = self.search_var.get().lower()
        
        if not search_text:
            self._populate_tree(self.df)
            return
        
        # Filter rows containing search text
        mask = self.df.apply(
            lambda row: any(search_text in str(v).lower() for v in row),
            axis=1
        )
        filtered_df = self.df[mask]
        self._populate_tree(filtered_df)
    
    def _populate_tree(self, df: pd.DataFrame):
        """Populate treeview with data."""
        # Clear
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add rows (limit for performance)
        for idx, (_, row) in enumerate(df.head(self.max_rows).iterrows()):
            values = tuple(
                str(v)[:100] if pd.notna(v) else ''
                for v in row.values
            )
            self.tree.insert('', tk.END, values=values)
        
        if len(df) > self.max_rows:
            self.tree.insert(
                '', tk.END,
                values=(f"... (pokazano {self.max_rows} z {len(df)} wierszy)",) + ('',) * (len(df.columns) - 1)
            )
