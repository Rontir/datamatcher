"""
Conflict Resolver Dialog - allows user to pick between multiple matching rows with data.
"""
import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Any, Optional

class ConflictResolverDialog(tk.Toplevel):
    """
    Dialog for resolving matching conflicts (multiple source rows with data for one base key).
    """
    
    def __init__(self, parent, conflicts: List[Dict[str, Any]], result_df):
        super().__init__(parent)
        self.title("🔍 Rozwiązywanie konfliktów duplikatów")
        self.geometry("900x600")
        self.transient(parent)
        self.grab_set()
        
        self.conflicts = conflicts
        self.result_df = result_df
        self.selections = {}  # conflict_idx -> row_dict
        
        self._create_widgets()
        self._center_window()
        
    def _create_widgets(self):
        main_frame = ttk.Frame(self, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(
            main_frame, 
            text="Wykryto wiele wierszy źródłowych z danymi dla tych samych kluczy.\nWybierz, którą wartość chcesz zastosować:",
            font=('', 10, 'bold')
        ).pack(pady=(0, 10))
        
        # Scrollable area
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        # Add mousewheel scrolling
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Populate conflicts
        for i, conflict in enumerate(self.conflicts):
            self._add_conflict_row(i, conflict)
            
        # Buttons
        btn_frame = ttk.Frame(main_frame, padding=(0, 10, 0, 0))
        btn_frame.pack(fill=tk.X)
        
        self.apply_btn = ttk.Button(
            btn_frame, 
            text="✅ Zatwierdź i zaktualizuj wyniki", 
            command=self._apply_selections, 
            style='Accent.TButton'
        )
        self.apply_btn.pack(side=tk.RIGHT, padx=5)
        
        ttk.Button(btn_frame, text="Anuluj", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        
    def _add_conflict_row(self, idx, conflict):
        key = conflict['key']
        src_col = conflict['column']
        target_col = conflict['target_column']
        rows = conflict['rows']
        
        frame = ttk.LabelFrame(self.scrollable_frame, text=f"Klucz: {key} (Kolumna: {src_col})", padding=5)
        frame.pack(fill=tk.X, pady=5, padx=5)
        
        # Choice variable
        choice_var = tk.IntVar(value=0)
        self.selections[idx] = (choice_var, conflict)
        
        for i, row in enumerate(rows):
            val = row.get(src_col)
            # Show a few other columns for context
            context = []
            for k in list(row.keys())[:3]:
                if k != src_col and k != 'Indeks Gold' and k != 'Indeks MDM':
                    context.append(f"{k}: {row[k]}")
            
            label_text = f"Wartość: {val}"
            if context:
                label_text += f" ({', '.join(context)})"
                
            rb = ttk.Radiobutton(
                frame, 
                text=label_text, 
                variable=choice_var, 
                value=i
            )
            rb.pack(anchor='w', padx=10, pady=2)

    def _apply_selections(self):
        """Update result_df with user selections."""
        for idx, (var, conflict) in self.selections.items():
            selected_idx = var.get()
            selected_row = conflict['rows'][selected_idx]
            val = selected_row.get(conflict['column'])
            
            # Update the result dataframe at the specific row and column
            row_idx = conflict['row_index']
            target_col = conflict['target_column']
            self.result_df.at[row_idx, target_col] = val
            
        self.destroy()

    def _center_window(self):
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
