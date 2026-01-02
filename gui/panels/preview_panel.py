"""
Preview Panel - Panel for previewing changes before execution.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, List, Dict, Any
import pandas as pd

from gui.widgets.tooltip import ToolTip
from gui.widgets.colored_treeview import PreviewTreeview, COLORS
from core.matcher import ChangeType


class PreviewPanel(ttk.LabelFrame):
    """
    Panel for previewing data changes with color coding.
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, text="👁️ PODGLĄD WYNIKU", padding=10, **kwargs)
        
        self.preview_data: Optional[pd.DataFrame] = None
        self.changes: List[Any] = []
        self.column_names: List[str] = []
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all widgets."""
        # Filter toolbar
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(filter_frame, text="Filtr:").pack(side=tk.LEFT)
        
        self.filter_var = tk.StringVar(value="all")
        
        filters = [
            ("Wszystkie", "all"),
            ("Tylko zmienione", "changed"),
            ("Niedopasowane", "unmatched")
        ]
        
        for text, value in filters:
            rb = ttk.Radiobutton(
                filter_frame, text=text, value=value,
                variable=self.filter_var, command=self._apply_filter
            )
            rb.pack(side=tk.LEFT, padx=5)
        
        # Search
        ttk.Label(filter_frame, text="🔍").pack(side=tk.LEFT, padx=(20, 5))
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self._apply_filter())
        
        self.search_entry = ttk.Entry(filter_frame, textvariable=self.search_var, width=20)
        self.search_entry.pack(side=tk.LEFT)
        ToolTip(self.search_entry, "Wyszukaj w danych")
        
        # Refresh button
        self.refresh_btn = ttk.Button(
            filter_frame, text="🔄 Odśwież",
            command=self._refresh,
            width=10
        )
        self.refresh_btn.pack(side=tk.RIGHT)
        ToolTip(self.refresh_btn, "Odśwież podgląd (F5)")
        
        # Treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create with placeholder columns - will be updated when data is set
        self.tree = PreviewTreeview(tree_frame, columns=['Dane'])
        self.tree.grid_with_scrollbars(0, 0)
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Legend
        legend_frame = ttk.Frame(self)
        legend_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(legend_frame, text="Legenda:").pack(side=tk.LEFT)
        
        legend_items = [
            ("🟢 Nowa wartość", COLORS['new']),
            ("🟡 Zmieniona", COLORS['changed']),
            ("⚪ Bez zmian", COLORS['unchanged']),
            ("🔴 Brak dopasowania", COLORS['no_match'])
        ]
        
        for text, color in legend_items:
            lbl = ttk.Label(legend_frame, text=text)
            lbl.pack(side=tk.LEFT, padx=10)
        
        # Stats bar
        self.stats_frame = ttk.Frame(self)
        self.stats_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.stats_label = ttk.Label(
            self.stats_frame,
            text="STATYSTYKI: -",
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
        """
        Set the preview data to display.
        
        Args:
            df: DataFrame to preview
            changes: List of CellChange objects for coloring
        """
        self.preview_data = df
        self.changes = changes or []
        self.column_names = list(df.columns)
        
        # Rebuild tree with correct columns
        self._rebuild_tree()
        self._apply_filter()
    
    def _rebuild_tree(self):
        """Rebuild tree with current columns."""
        if not self.column_names:
            return
        
        # Get parent frame
        tree_frame = self.tree.master
        
        # Destroy old tree and scrollbars
        self.tree.v_scroll.destroy()
        self.tree.h_scroll.destroy()
        self.tree.destroy()
        
        # Create new tree with correct columns
        self.tree = PreviewTreeview(tree_frame, columns=self.column_names)
        self.tree.grid_with_scrollbars(0, 0)
    
    def _apply_filter(self):
        """Apply current filter to preview."""
        if self.preview_data is None:
            return
        
        self.tree.clear()
        
        filter_type = self.filter_var.get()
        search_text = self.search_var.get().lower()
        
        # Build change lookup: (row_idx, column) -> change_type
        change_lookup: Dict[tuple, ChangeType] = {}
        row_status: Dict[int, str] = {}  # row_idx -> worst status
        
        for change in self.changes:
            key = (change.row_index, change.column)
            change_lookup[key] = change.change_type
            
            # Track worst status per row
            current = row_status.get(change.row_index, 'unchanged')
            if change.change_type == ChangeType.NO_MATCH:
                row_status[change.row_index] = 'no_match'
            elif change.change_type == ChangeType.CHANGED and current != 'no_match':
                row_status[change.row_index] = 'changed'
            elif change.change_type == ChangeType.NEW and current not in ('no_match', 'changed'):
                row_status[change.row_index] = 'new'
        
        # Filter and display rows
        count = 0
        max_rows = 500  # Limit for performance
        
        for idx, row in self.preview_data.iterrows():
            if count >= max_rows:
                break
            
            status = row_status.get(idx, 'unchanged')
            
            # Apply filter
            if filter_type == 'changed' and status == 'unchanged':
                continue
            if filter_type == 'unmatched' and status != 'no_match':
                continue
            
            # Apply search
            if search_text:
                row_text = ' '.join(str(v).lower() for v in row.values)
                if search_text not in row_text:
                    continue
            
            # Add row
            values = tuple(str(v)[:50] if pd.notna(v) else '' for v in row.values)
            self.tree.add_row_with_status(values, status)
            count += 1
        
        if count >= max_rows:
            self.tree.add_row(('...', f'(pokazano {max_rows} z {len(self.preview_data)} wierszy)') + ('',) * (len(self.column_names) - 1), tag='unchanged')
    
    def _refresh(self):
        """Refresh preview (trigger external refresh)."""
        # This will be connected to external refresh logic
        pass
    
    def set_refresh_callback(self, callback: Callable):
        """Set callback for refresh button."""
        self.refresh_btn.config(command=callback)
    
    def update_stats(self, stats: Dict[str, Any]):
        """Update statistics display."""
        total = stats.get('total_rows', 0)
        matched = total - stats.get('rows_no_match', 0)
        cells_mod = stats.get('cells_total_modified', 0)
        match_pct = stats.get('match_percent', 0)
        
        self.stats_label.config(
            text=f"STATYSTYKI: Dopasowano {matched:,}/{total:,} ({match_pct:.1f}%) │ "
                 f"Komórek do zmiany: {cells_mod:,}"
        )
        
        self.progress_var.set(match_pct)
    
    def clear(self):
        """Clear preview."""
        self.tree.clear()
        self.preview_data = None
        self.changes = []
        self.stats_label.config(text="STATYSTYKI: -")
        self.progress_var.set(0)
