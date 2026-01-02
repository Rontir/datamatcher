"""
Preview Panel - Panel for previewing changes before execution.
Enhanced with before/after view, search, diff export, and batch control.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional, Callable, List, Dict, Any
import pandas as pd

from gui.widgets.tooltip import ToolTip
from gui.widgets.colored_treeview import PreviewTreeview, COLORS
from core.matcher import ChangeType


class PreviewPanel(ttk.LabelFrame):
    """
    Panel for previewing data changes with color coding.
    Supports search, before/after view, diff export, and batch filtering.
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, text="👁️ PODGLĄD WYNIKU", padding=10, **kwargs)
        
        self.preview_data: Optional[pd.DataFrame] = None
        self.changes: List[Any] = []
        self.column_names: List[str] = []
        self.before_after_mode = False
        self._refresh_callback = None
        
        # Store before values for before/after display
        self.before_values: Dict[tuple, Any] = {}  # (row_idx, col) -> old_value
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all widgets."""
        # === CONTROL TOOLBAR ===
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Filter options
        ttk.Label(control_frame, text="Filtr:").pack(side=tk.LEFT)
        
        self.filter_var = tk.StringVar(value="all")
        
        filters = [
            ("Wszystkie", "all"),
            ("Zmienione", "changed"),
            ("Niedopasowane", "unmatched"),
            ("Pominięte", "skipped")
        ]
        
        for text, value in filters:
            rb = ttk.Radiobutton(
                control_frame, text=text, value=value,
                variable=self.filter_var, command=self._apply_filter
            )
            rb.pack(side=tk.LEFT, padx=3)
        
        # Before/After toggle
        self.before_after_var = tk.BooleanVar(value=False)
        self.before_after_check = ttk.Checkbutton(
            control_frame, text="📊 Przed/Po",
            variable=self.before_after_var,
            command=self._toggle_before_after
        )
        self.before_after_check.pack(side=tk.LEFT, padx=(15, 5))
        ToolTip(self.before_after_check, "Pokaż stare i nowe wartości obok siebie")
        
        # === SEARCH & LIMIT TOOLBAR ===
        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Search box
        ttk.Label(search_frame, text="🔍 Szukaj:").pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._apply_filter())
        
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        ToolTip(self.search_entry, "Wpisz fragment klucza lub wartości aby filtrować")
        
        ttk.Button(
            search_frame, text="✖", width=2,
            command=lambda: self.search_var.set('')
        ).pack(side=tk.LEFT)
        
        # Limit spinbox
        ttk.Label(search_frame, text="│ Limit wierszy:").pack(side=tk.LEFT, padx=(15, 5))
        
        self.limit_var = tk.IntVar(value=500)
        self.limit_spinbox = ttk.Spinbox(
            search_frame, 
            from_=50, to=10000, increment=50,
            textvariable=self.limit_var,
            width=8,
            command=self._apply_filter
        )
        self.limit_spinbox.pack(side=tk.LEFT)
        self.limit_spinbox.bind('<Return>', lambda e: self._apply_filter())
        
        # Export buttons
        self.export_diff_btn = ttk.Button(
            search_frame, text="📤 Eksport różnic",
            command=self._export_diff
        )
        self.export_diff_btn.pack(side=tk.RIGHT, padx=5)
        ToolTip(self.export_diff_btn, "Eksportuj tylko zmienione wiersze do nowego pliku Excel")
        
        self.refresh_btn = ttk.Button(
            search_frame, text="🔄 Odśwież (F5)",
            command=self._refresh
        )
        self.refresh_btn.pack(side=tk.RIGHT)
        
        # === TREEVIEW ===
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = PreviewTreeview(tree_frame, columns=['Dane'])
        self.tree.grid_with_scrollbars(0, 0)
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # === LEGEND ===
        legend_frame = ttk.Frame(self)
        legend_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(legend_frame, text="Legenda:").pack(side=tk.LEFT)
        
        legend_items = [
            ("🟢 Nowa", COLORS['new']),
            ("🟡 Zmieniona", COLORS['changed']),
            ("⚪ Bez zmian", COLORS['unchanged']),
            ("🔴 Brak dopasowania", COLORS['no_match']),
            ("⚫ Pominięta", COLORS.get('skipped', '#888888'))
        ]
        
        for text, color in legend_items:
            lbl = ttk.Label(legend_frame, text=text)
            lbl.pack(side=tk.LEFT, padx=8)
        
        # === STATS BAR ===
        self.stats_frame = ttk.Frame(self)
        self.stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.stats_label = ttk.Label(
            self.stats_frame,
            text="STATYSTYKI: Wczytaj dane i wykonaj podgląd",
            font=('Segoe UI', 9, 'bold')
        )
        self.stats_label.pack(anchor='w')
        
        # Progress bar
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.stats_frame,
            variable=self.progress_var,
            maximum=100,
            length=400
        )
        self.progress_bar.pack(fill=tk.X, pady=(5, 0))
    
    def set_preview_data(self, df: pd.DataFrame, changes: List[Any] = None):
        """Set the preview data to display."""
        self.preview_data = df
        self.changes = changes or []
        self.column_names = list(df.columns)
        
        # Build before_values lookup from changes
        self.before_values = {}
        for change in self.changes:
            if change.change_type in (ChangeType.NEW, ChangeType.CHANGED):
                self.before_values[(change.row_index, change.column)] = change.old_value
        
        # Rebuild tree
        self._rebuild_tree()
        self._apply_filter()
    
    def _rebuild_tree(self):
        """Rebuild tree with current columns."""
        if not self.column_names:
            return
        
        tree_frame = self.tree.master
        
        # Destroy old tree
        self.tree.v_scroll.destroy()
        self.tree.h_scroll.destroy()
        self.tree.destroy()
        
        # Determine columns based on mode
        if self.before_after_mode:
            # Create paired columns: [Col1_OLD, Col1_NEW, Col2_OLD, Col2_NEW, ...]
            display_columns = []
            for col in self.column_names[:10]:  # Limit for readability
                display_columns.append(f"{col} (PRZED)")
                display_columns.append(f"{col} (PO)")
        else:
            display_columns = self.column_names
        
        self.tree = PreviewTreeview(tree_frame, columns=display_columns)
        self.tree.grid_with_scrollbars(0, 0)
    
    def _toggle_before_after(self):
        """Toggle before/after display mode."""
        self.before_after_mode = self.before_after_var.get()
        self._rebuild_tree()
        self._apply_filter()
    
    def _apply_filter(self):
        """Apply current filter to preview."""
        if self.preview_data is None:
            return
        
        self.tree.clear()
        
        filter_type = self.filter_var.get()
        search_text = self.search_var.get().lower()
        max_rows = self.limit_var.get()
        
        # Build change lookup
        change_lookup: Dict[tuple, ChangeType] = {}
        row_status: Dict[int, str] = {}
        
        for change in self.changes:
            key = (change.row_index, change.column)
            change_lookup[key] = change.change_type
            
            current = row_status.get(change.row_index, 'unchanged')
            if change.change_type == ChangeType.NO_MATCH:
                row_status[change.row_index] = 'no_match'
            elif change.change_type == ChangeType.SKIPPED:
                if current not in ('no_match', 'changed', 'new'):
                    row_status[change.row_index] = 'skipped'
            elif change.change_type == ChangeType.CHANGED and current not in ('no_match',):
                row_status[change.row_index] = 'changed'
            elif change.change_type == ChangeType.NEW and current not in ('no_match', 'changed'):
                row_status[change.row_index] = 'new'
        
        # Filter and display
        count = 0
        
        for idx, row in self.preview_data.iterrows():
            if count >= max_rows:
                break
            
            status = row_status.get(idx, 'unchanged')
            
            # Apply filter
            if filter_type == 'changed' and status not in ('changed', 'new'):
                continue
            if filter_type == 'unmatched' and status != 'no_match':
                continue
            if filter_type == 'skipped' and status != 'skipped':
                continue
            
            # Apply search
            if search_text:
                row_text = ' '.join(str(v).lower() for v in row.values)
                if search_text not in row_text:
                    continue
            
            # Build row values
            if self.before_after_mode:
                # Paired columns
                values = []
                for col in self.column_names[:10]:
                    old_val = self.before_values.get((idx, col), '')
                    new_val = row.get(col, '')
                    
                    old_str = str(old_val)[:30] if pd.notna(old_val) and old_val != '' else '-'
                    new_str = str(new_val)[:30] if pd.notna(new_val) else ''
                    
                    values.append(old_str)
                    values.append(new_str)
                
                values = tuple(values)
            else:
                values = tuple(str(v)[:50] if pd.notna(v) else '' for v in row.values)
            
            self.tree.add_row_with_status(values, status)
            count += 1
        
        # Show limit warning
        if count >= max_rows:
            remaining = len(self.preview_data) - max_rows
            if self.before_after_mode:
                cols_count = len(self.column_names[:10]) * 2
            else:
                cols_count = len(self.column_names)
            
            msg = ('...', f'(pokazano {max_rows}, pozostało {remaining:,})') + ('',) * (cols_count - 2)
            self.tree.add_row(msg, tag='unchanged')
    
    def _export_diff(self):
        """Export only changed rows to Excel file."""
        if self.preview_data is None or not self.changes:
            from tkinter import messagebox
            messagebox.showwarning("Brak danych", "Najpierw wygeneruj podgląd.")
            return
        
        # Collect changed row indices
        changed_rows = set()
        for change in self.changes:
            if change.change_type in (ChangeType.NEW, ChangeType.CHANGED):
                changed_rows.add(change.row_index)
        
        if not changed_rows:
            from tkinter import messagebox
            messagebox.showinfo("Brak zmian", "Nie ma żadnych zmian do wyeksportowania.")
            return
        
        # Ask for file path
        filepath = filedialog.asksaveasfilename(
            title="Eksportuj różnice",
            defaultextension=".xlsx",
            initialfile="diff_report.xlsx",
            filetypes=[("Excel", "*.xlsx"), ("All", "*.*")]
        )
        
        if not filepath:
            return
        
        try:
            # Create diff dataframe
            diff_df = self.preview_data.loc[list(changed_rows)].copy()
            
            # Add before columns
            for col in self.column_names:
                old_values = []
                for idx in diff_df.index:
                    old_val = self.before_values.get((idx, col), '')
                    old_values.append(old_val)
                diff_df[f'{col}_PRZED'] = old_values
            
            # Reorder columns: [original, before, original, before, ...]
            new_order = []
            for col in self.column_names:
                new_order.append(f'{col}_PRZED')
                new_order.append(col)
            
            diff_df = diff_df[[c for c in new_order if c in diff_df.columns]]
            
            # Save with styling
            from utils.file_handlers import save_excel
            save_excel(diff_df, filepath)
            
            from tkinter import messagebox
            messagebox.showinfo(
                "Eksport zakończony",
                f"Wyeksportowano {len(diff_df)} zmienionych wierszy do:\n{filepath}"
            )
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Błąd eksportu", str(e))
    
    def _refresh(self):
        """Refresh preview."""
        if self._refresh_callback:
            self._refresh_callback()
    
    def set_refresh_callback(self, callback: Callable):
        """Set callback for refresh button."""
        self._refresh_callback = callback
        self.refresh_btn.config(command=callback)
    
    def update_stats(self, stats: Dict[str, Any]):
        """Update statistics display."""
        total = stats.get('total_rows', 0)
        matched = total - stats.get('rows_no_match', 0)
        cells_new = stats.get('cells_new', 0)
        cells_changed = stats.get('cells_changed', 0)
        cells_skipped = stats.get('cells_skipped', 0)
        match_pct = stats.get('match_percent', 0)
        warnings = stats.get('validation_warnings_count', 0)
        
        warning_text = f" ⚠️ {warnings} ostrzeżeń" if warnings > 0 else ""
        
        self.stats_label.config(
            text=f"STATYSTYKI: Dopasowano {matched:,}/{total:,} ({match_pct:.1f}%) │ "
                 f"Nowe: {cells_new:,} │ Zmienione: {cells_changed:,} │ Pominięte: {cells_skipped:,}"
                 f"{warning_text}"
        )
        
        self.progress_var.set(match_pct)
    
    def clear(self):
        """Clear preview."""
        self.tree.clear()
        self.preview_data = None
        self.changes = []
        self.before_values = {}
        self.stats_label.config(text="STATYSTYKI: -")
        self.progress_var.set(0)
