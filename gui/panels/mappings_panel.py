"""
Mappings Panel - Panel for defining column mappings.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, List, Dict, Any

from core.mapping import ColumnMapping, WriteMode, MappingManager
from gui.widgets.tooltip import ToolTip
from gui.widgets.colored_treeview import MappingsTreeview


class MappingsPanel(ttk.LabelFrame):
    """
    Panel for managing column mappings between sources and target.
    """
    
    def __init__(self, master, 
                 on_mapping_changed: Optional[Callable] = None,
                 **kwargs):
        super().__init__(master, text="🔗 MAPOWANIA KOLUMN", padding=10, **kwargs)
        
        self.on_mapping_changed = on_mapping_changed
        self.mapping_manager = MappingManager()
        
        # Available options
        self.sources: Dict[str, str] = {}  # id -> name
        self.source_columns: Dict[str, List[str]] = {}  # id -> columns
        self.target_columns: List[str] = []
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all widgets."""
        # Toolbar
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        self.add_btn = ttk.Button(
            toolbar, text="➕ Dodaj mapowanie",
            command=self._add_mapping,
            style='Accent.TButton'
        )
        self.add_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.add_btn, "Dodaj nowe mapowanie kolumn")
        
        self.remove_btn = ttk.Button(
            toolbar, text="🗑️ Usuń zaznaczone",
            command=self._remove_selected,
            state='disabled'
        )
        self.remove_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.remove_btn, "Usuń zaznaczone mapowania (Delete)")
        
        self.up_btn = ttk.Button(toolbar, text="⬆️", command=self._move_up, width=3)
        self.up_btn.pack(side=tk.LEFT, padx=(10, 2))
        ToolTip(self.up_btn, "Przesuń w górę (wyższy priorytet)")
        
        self.down_btn = ttk.Button(toolbar, text="⬇️", command=self._move_down, width=3)
        self.down_btn.pack(side=tk.LEFT)
        ToolTip(self.down_btn, "Przesuń w dół (niższy priorytet)")
        
        self.undo_btn = ttk.Button(toolbar, text="↩️ Cofnij", command=self._undo)
        self.undo_btn.pack(side=tk.RIGHT)
        ToolTip(self.undo_btn, "Cofnij ostatnią zmianę (Ctrl+Z)")
        
        # Mappings treeview
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        self.tree = MappingsTreeview(tree_frame)
        self.tree.grid_with_scrollbars(0, 0)
        
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        
        # Bind events
        self.tree.bind('<<TreeviewSelect>>', self._on_selection_changed)
        self.tree.set_double_click_callback(self._on_double_click)
        self.tree.bind('<Delete>', lambda e: self._remove_selected())
        
        # Empty state
        self.empty_label = ttk.Label(
            self,
            text="Brak mapowań.\nKliknij '+ Dodaj mapowanie' aby zdefiniować mapowania kolumn.",
            foreground='gray',
            justify=tk.CENTER
        )
    
    def _add_mapping(self):
        """Open dialog to add new mapping."""
        if not self.sources:
            from tkinter import messagebox
            messagebox.showwarning(
                "Brak źródeł",
                "Najpierw dodaj źródła danych."
            )
            return
        
        from gui.dialogs.mapping_editor import MappingEditorDialog
        
        dialog = MappingEditorDialog(
            self.winfo_toplevel(),
            sources=self.sources,
            source_columns=self.source_columns,
            target_columns=self.target_columns,
            title="Nowe mapowanie"
        )
        
        if dialog.result:
            mapping = dialog.result
            self.mapping_manager.add(mapping)
            self._refresh_tree()
            self._notify_change()
    
    def _remove_selected(self):
        """Remove selected mappings."""
        selected = self.tree.get_selected_items()
        if not selected:
            return
        
        for item in selected:
            # Get mapping ID from tree item
            values = self.tree.get_row_data(item)
            if values:
                # Find mapping by index
                idx = int(values[0]) - 1
                if 0 <= idx < len(self.mapping_manager.mappings):
                    mapping = self.mapping_manager.mappings[idx]
                    self.mapping_manager.remove(mapping.id)
        
        self._refresh_tree()
        self._notify_change()
    
    def _move_up(self):
        """Move selected mapping up."""
        selected = self.tree.get_selected_items()
        if not selected:
            return
        
        values = self.tree.get_row_data(selected[0])
        if values:
            idx = int(values[0]) - 1
            if idx > 0:
                mapping = self.mapping_manager.mappings[idx]
                self.mapping_manager.move_up(mapping.id)
                self._refresh_tree()
                self._notify_change()
    
    def _move_down(self):
        """Move selected mapping down."""
        selected = self.tree.get_selected_items()
        if not selected:
            return
        
        values = self.tree.get_row_data(selected[0])
        if values:
            idx = int(values[0]) - 1
            if idx < len(self.mapping_manager.mappings) - 1:
                mapping = self.mapping_manager.mappings[idx]
                self.mapping_manager.move_down(mapping.id)
                self._refresh_tree()
                self._notify_change()
    
    def _undo(self):
        """Undo last change."""
        if self.mapping_manager.undo():
            self._refresh_tree()
            self._notify_change()
    
    def _on_selection_changed(self, event):
        """Handle selection change."""
        selected = self.tree.get_selected_items()
        state = 'normal' if selected else 'disabled'
        self.remove_btn.config(state=state)
    
    def _on_double_click(self, item):
        """Handle double-click to edit mapping."""
        values = self.tree.get_row_data(item)
        if not values:
            return
        
        idx = int(values[0]) - 1
        if 0 <= idx < len(self.mapping_manager.mappings):
            mapping = self.mapping_manager.mappings[idx]
            
            from gui.dialogs.mapping_editor import MappingEditorDialog
            
            dialog = MappingEditorDialog(
                self.winfo_toplevel(),
                sources=self.sources,
                source_columns=self.source_columns,
                target_columns=self.target_columns,
                mapping=mapping,
                title="Edycja mapowania"
            )
            
            if dialog.result:
                self.mapping_manager.update(dialog.result)
                self._refresh_tree()
                self._notify_change()
    
    def _refresh_tree(self):
        """Refresh tree view with current mappings."""
        self.tree.clear()
        
        from core.transformer import get_transform_names
        transform_names = get_transform_names()
        
        for i, mapping in enumerate(self.mapping_manager.mappings, 1):
            source_name = self.sources.get(mapping.source_id, mapping.source_name)
            mode_name = WriteMode.get_display_name(mapping.write_mode)
            transform_name = transform_names.get(mapping.transform, '-') if mapping.transform else '-'
            
            target_display = mapping.target_column
            if mapping.target_is_new:
                target_display = f"+ {mapping.target_column} (NOWA)"
            
            values = (
                str(i),
                source_name[:20],
                mapping.source_column[:20],
                '→',
                target_display[:20],
                mode_name[:15],
                transform_name[:12]
            )
            
            tag = 'unchanged' if mapping.enabled else 'conflict'
            self.tree.add_row(values, tag=tag)
        
        # Show/hide empty label
        if len(self.mapping_manager) == 0:
            self.empty_label.pack(pady=20)
        else:
            self.empty_label.pack_forget()
    
    def _notify_change(self):
        """Notify that mappings changed."""
        if self.on_mapping_changed:
            self.on_mapping_changed(self.mapping_manager)
    
    def set_sources(self, sources: Dict[str, str], source_columns: Dict[str, List[str]]):
        """Update available sources."""
        self.sources = sources
        self.source_columns = source_columns
    
    def set_target_columns(self, columns: List[str]):
        """Update available target columns."""
        self.target_columns = columns
    
    def get_mapping_manager(self) -> MappingManager:
        """Get the mapping manager."""
        return self.mapping_manager
    
    def load_mappings(self, mappings_data: List[Dict[str, Any]]):
        """Load mappings from data."""
        self.mapping_manager.from_list(mappings_data)
        self._refresh_tree()
    
    def reset(self):
        """Reset panel to initial state."""
        self.mapping_manager.clear()
        self.sources.clear()
        self.source_columns.clear()
        self.target_columns.clear()
        self._refresh_tree()
