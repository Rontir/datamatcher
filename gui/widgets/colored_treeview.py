"""
Colored Treeview widget with row highlighting based on status.
"""
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Any, Optional, Callable


# Color scheme for different states
COLORS = {
    'new': '#c8e6c9',           # Light green - new value (was empty)
    'changed': '#fff9c4',        # Light yellow - changed value
    'unchanged': '#ffffff',      # White - no changes
    'no_match': '#ffcdd2',       # Light red - no match found
    'conflict': '#ffcc80',       # Orange - conflict
    'selected': '#bbdefb',       # Light blue - selected row
    'header': '#e0e0e0',         # Gray - header background
}

# Dark mode colors
COLORS_DARK = {
    'new': '#2e7d32',
    'changed': '#f9a825',
    'unchanged': '#424242',
    'no_match': '#c62828',
    'conflict': '#ef6c00',
    'selected': '#1565c0',
    'header': '#616161',
}


class ColoredTreeview(ttk.Treeview):
    """
    A Treeview widget that supports row coloring based on tags.
    """
    
    def __init__(self, master, columns: List[str], column_widths: Optional[Dict[str, int]] = None,
                 dark_mode: bool = False, **kwargs):
        """
        Initialize ColoredTreeview.
        
        Args:
            master: Parent widget
            columns: List of column identifiers
            column_widths: Optional dict of column -> width
            dark_mode: Use dark color scheme
            **kwargs: Additional ttk.Treeview arguments
        """
        super().__init__(master, columns=columns, show='headings', **kwargs)
        
        self.colors = COLORS_DARK if dark_mode else COLORS
        self._setup_tags()
        self._setup_columns(columns, column_widths or {})
        self._setup_scrollbars(master)
        
        # Selection handling
        self.bind('<<TreeviewSelect>>', self._on_select)
        
        # Double-click handling
        self._double_click_callback: Optional[Callable] = None
        self.bind('<Double-1>', self._on_double_click)
    
    def _setup_tags(self):
        """Configure tags for row coloring."""
        for tag, color in self.colors.items():
            self.tag_configure(tag, background=color)
    
    def _setup_columns(self, columns: List[str], widths: Dict[str, int]):
        """Setup column headers and widths."""
        for col in columns:
            self.heading(col, text=col, anchor=tk.W)
            width = widths.get(col, 100)
            self.column(col, width=width, minwidth=50, anchor=tk.W)
    
    def _setup_scrollbars(self, master):
        """Add scrollbars to the treeview."""
        # Create frame for scrollbars
        self.scroll_frame = ttk.Frame(master)
        
        # Vertical scrollbar
        self.v_scroll = ttk.Scrollbar(master, orient=tk.VERTICAL, command=self.yview)
        self.configure(yscrollcommand=self.v_scroll.set)
        
        # Horizontal scrollbar
        self.h_scroll = ttk.Scrollbar(master, orient=tk.HORIZONTAL, command=self.xview)
        self.configure(xscrollcommand=self.h_scroll.set)
    
    def grid_with_scrollbars(self, row: int, column: int, **kwargs):
        """Place treeview with scrollbars using grid layout."""
        self.grid(row=row, column=column, sticky='nsew', **kwargs)
        self.v_scroll.grid(row=row, column=column + 1, sticky='ns')
        self.h_scroll.grid(row=row + 1, column=column, sticky='ew')
    
    def pack_with_scrollbars(self, **kwargs):
        """Place treeview with scrollbars using pack layout."""
        frame = ttk.Frame(self.master)
        frame.pack(**kwargs)
        
        self.pack(in_=frame, side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scroll.pack(in_=frame, side=tk.RIGHT, fill=tk.Y)
    
    def _on_select(self, event):
        """Handle selection change."""
        pass  # Can be overridden
    
    def _on_double_click(self, event):
        """Handle double-click."""
        if self._double_click_callback:
            item = self.identify_row(event.y)
            if item:
                self._double_click_callback(item)
    
    def set_double_click_callback(self, callback: Callable):
        """Set callback for double-click events."""
        self._double_click_callback = callback
    
    def clear(self):
        """Clear all items from the treeview."""
        for item in self.get_children():
            self.delete(item)
    
    def add_row(self, values: tuple, tag: str = 'unchanged', **kwargs) -> str:
        """
        Add a row with specified tag.
        
        Args:
            values: Tuple of values for each column
            tag: Tag for row coloring
            **kwargs: Additional insert arguments
            
        Returns:
            Item ID
        """
        return self.insert('', tk.END, values=values, tags=(tag,), **kwargs)
    
    def add_rows(self, rows: List[tuple], tags: Optional[List[str]] = None):
        """
        Add multiple rows at once.
        
        Args:
            rows: List of value tuples
            tags: Optional list of tags for each row
        """
        if tags is None:
            tags = ['unchanged'] * len(rows)
        
        for values, tag in zip(rows, tags):
            self.add_row(values, tag)
    
    def update_row(self, item_id: str, values: tuple, tag: Optional[str] = None):
        """
        Update an existing row.
        
        Args:
            item_id: ID of the item to update
            values: New values
            tag: Optional new tag
        """
        self.item(item_id, values=values)
        if tag:
            self.item(item_id, tags=(tag,))
    
    def get_selected_items(self) -> List[str]:
        """Get list of selected item IDs."""
        return list(self.selection())
    
    def get_row_data(self, item_id: str) -> tuple:
        """Get values for a specific row."""
        return self.item(item_id, 'values')
    
    def set_columns(self, columns: List[str], widths: Optional[Dict[str, int]] = None):
        """Change columns dynamically."""
        self['columns'] = columns
        self._setup_columns(columns, widths or {})
    
    def auto_resize_columns(self):
        """Automatically resize columns based on content."""
        for col in self['columns']:
            max_width = len(str(col)) * 10  # Header width
            
            for item in self.get_children():
                values = self.item(item, 'values')
                col_idx = list(self['columns']).index(col)
                if col_idx < len(values):
                    width = len(str(values[col_idx])) * 8
                    max_width = max(max_width, width)
            
            max_width = min(max_width, 300)  # Cap at 300
            self.column(col, width=max_width)


class MappingsTreeview(ColoredTreeview):
    """
    Specialized Treeview for displaying column mappings.
    """
    
    COLUMNS = ['Nr', 'Źródło', 'Kolumna źródłowa', '→', 'Kolumna docelowa', 'Tryb', 'Transformacja']
    WIDTHS = {
        'Nr': 40,
        'Źródło': 150,
        'Kolumna źródłowa': 150,
        '→': 30,
        'Kolumna docelowa': 150,
        'Tryb': 120,
        'Transformacja': 100
    }
    
    def __init__(self, master, **kwargs):
        super().__init__(master, columns=self.COLUMNS, column_widths=self.WIDTHS, **kwargs)
        
        # Center the arrow column
        self.column('→', anchor=tk.CENTER)
        self.heading('→', text='→', anchor=tk.CENTER)


class PreviewTreeview(ColoredTreeview):
    """
    Specialized Treeview for data preview with status icons.
    """
    
    # Unicode status indicators
    ICONS = {
        'new': '🟢',
        'changed': '🟡', 
        'unchanged': '⚪',
        'no_match': '🔴',
        'conflict': '🟠'
    }
    
    def __init__(self, master, columns: List[str], **kwargs):
        # Add status column
        all_columns = ['Status'] + columns
        super().__init__(master, columns=all_columns, **kwargs)
        
        self.column('Status', width=60, anchor=tk.CENTER)
        self.heading('Status', text='', anchor=tk.CENTER)
    
    def add_row_with_status(self, values: tuple, status: str = 'unchanged') -> str:
        """
        Add a row with status icon.
        
        Args:
            values: Data values (without status)
            status: Row status for icon and coloring
            
        Returns:
            Item ID
        """
        icon = self.ICONS.get(status, '⚪')
        full_values = (icon,) + values
        return self.add_row(full_values, tag=status)
