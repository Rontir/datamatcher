"""
Mappings Panel - Panel for defining column mappings.
Enhanced with Quick Mapping Bar for faster workflow.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable, List, Dict, Any

from core.mapping import ColumnMapping, WriteMode, MappingManager
from gui.widgets.tooltip import ToolTip
from gui.widgets.colored_treeview import MappingsTreeview
from gui.dialogs.mapping_editor import find_matching_column


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
        
        # Mappings for quick bar
        self.source_name_to_id: Dict[str, str] = {}
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all widgets."""
        
        # --- Quick Mapping Bar ---
        quick_frame = ttk.LabelFrame(self, text="Szybkie dodawanie", padding=5)
        quick_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Source
        self.quick_source_var = tk.StringVar()
        self.quick_source_combo = ttk.Combobox(
            quick_frame, textvariable=self.quick_source_var,
            state='readonly', width=20
        )
        self.quick_source_combo.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.quick_source_combo, "Wybierz źródło")
        self.quick_source_combo.bind('<<ComboboxSelected>>', self._on_quick_source_changed)
        
        # Source Column
        self.quick_source_col_var = tk.StringVar()
        self.quick_source_col_combo = ttk.Combobox(
            quick_frame, textvariable=self.quick_source_col_var,
            state='readonly', width=25
        )
        self.quick_source_col_combo.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.quick_source_col_combo, "Kolumna źródłowa")
        self.quick_source_col_combo.bind('<<ComboboxSelected>>', self._on_quick_source_col_changed)
        
        ttk.Label(quick_frame, text="→").pack(side=tk.LEFT, padx=2)
        
        # Target Column
        self.quick_target_col_var = tk.StringVar()
        self.quick_target_col_combo = ttk.Combobox(
            quick_frame, textvariable=self.quick_target_col_var,
            width=25
        )
        self.quick_target_col_combo.pack(side=tk.LEFT, padx=(5, 5))
        ToolTip(self.quick_target_col_combo, "Kolumna docelowa")
        
        # Mode
        self.quick_mode_var = tk.StringVar(value=WriteMode.get_display_name(WriteMode.FILL_EMPTY))
        self.quick_mode_combo = ttk.Combobox(
            quick_frame, textvariable=self.quick_mode_var,
            state='readonly', width=15
        )
        modes = [(mode.value, WriteMode.get_display_name(mode)) for mode in WriteMode]
        self.mode_display_to_value = {display: value for value, display in modes}
        self.quick_mode_combo['values'] = [display for _, display in modes]
        self.quick_mode_combo.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.quick_mode_combo, "Tryb zapisu")
        
        # Add Button
        self.quick_add_btn = ttk.Button(
            quick_frame, text="➕", width=3,
            command=self._quick_add,
            style='Accent.TButton'
        )
        self.quick_add_btn.pack(side=tk.LEFT)
        ToolTip(self.quick_add_btn, "Dodaj mapowanie")
        
        # --- Toolbar ---
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        self.suggest_btn = ttk.Button(
            toolbar, text="🪄 Sugestie",
            command=self._show_suggestions
        )
        self.suggest_btn.pack(side=tk.LEFT, padx=(0, 5))
        ToolTip(self.suggest_btn, "Automatycznie znajdź dopasowania kolumn")
        
        self.remove_btn = ttk.Button(
            toolbar, text="🗑️ Usuń zaznaczone",
            command=self._remove_selected,
            state='disabled'
        )
        self.remove_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.up_btn = ttk.Button(toolbar, text="⬆️", command=self._move_up, width=3)
        self.up_btn.pack(side=tk.LEFT, padx=(10, 2))
        
        self.down_btn = ttk.Button(toolbar, text="⬇️", command=self._move_down, width=3)
        self.down_btn.pack(side=tk.LEFT)
        
        self.undo_btn = ttk.Button(toolbar, text="↩️ Cofnij", command=self._undo)
        self.undo_btn.pack(side=tk.RIGHT)
        
        # --- Treeview ---
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
            text="Brak mapowań.\nUżyj paska 'Szybkie dodawanie' powyżej lub kliknij '🪄 Sugestie'.",
            foreground='gray',
            justify=tk.CENTER
        )
    
    def _on_quick_source_changed(self, event=None):
        """Handle quick source selection."""
        source_name = self.quick_source_var.get()
        source_id = self.source_name_to_id.get(source_name)
        
        if source_id and source_id in self.source_columns:
            cols = self.source_columns[source_id]
            self.quick_source_col_combo['values'] = cols
            if cols:
                self.quick_source_col_var.set(cols[0])
                self._on_quick_source_col_changed()
    
    def _on_quick_source_col_changed(self, event=None):
        """Handle quick source column selection - auto-suggest target."""
        source_col = self.quick_source_col_var.get()
        if not source_col:
            return
            
        # Try to find match
        match = find_matching_column(source_col, self.target_columns)
        if match:
            self.quick_target_col_var.set(match)
        else:
            self.quick_target_col_var.set(source_col) # Default to same name (new column)
    
    def _quick_add(self):
        """Add mapping from quick bar."""
        source_name = self.quick_source_var.get()
        source_id = self.source_name_to_id.get(source_name)
        source_col = self.quick_source_col_var.get()
        target_col = self.quick_target_col_var.get()
        mode_display = self.quick_mode_var.get()
        
        if not all([source_id, source_col, target_col]):
            return
            
        # Check if target is new
        target_is_new = target_col not in self.target_columns
        
        mapping = ColumnMapping(
            source_id=source_id,
            source_name=source_name,
            source_column=source_col,
            target_column=target_col,
            target_is_new=target_is_new,
            write_mode=WriteMode(self.mode_display_to_value.get(mode_display, 'overwrite'))
        )
        
        self.mapping_manager.add(mapping)
        self._refresh_tree()
        self._notify_change()
    
    def _show_suggestions(self):
        """Show smart mapping suggestions dialog."""
        if not self.sources:
            from tkinter import messagebox
            messagebox.showwarning("Brak źródeł", "Najpierw dodaj źródła danych.")
            return
        
        if not self.target_columns:
            from tkinter import messagebox
            messagebox.showwarning("Brak pliku bazowego", "Najpierw wczytaj plik bazowy.")
            return
        
        from gui.dialogs.mapping_editor import SmartMappingSuggestionDialog
        
        # Use first source for suggestions (or currently selected in quick bar)
        source_name = self.quick_source_var.get()
        if not source_name and self.sources:
            source_name = list(self.sources.values())[0]
            
        source_id = self.source_name_to_id.get(source_name)
        if not source_id:
            return
            
        source_cols = self.source_columns.get(source_id, [])
        
        dialog = SmartMappingSuggestionDialog(
            self.winfo_toplevel(),
            source_name=source_name,
            source_columns=source_cols,
            target_columns=self.target_columns
        )
        
        if dialog.result:
            added_count = 0
            for sug in dialog.result:
                # Get write_mode from dialog or default to OVERWRITE
                write_mode = sug.get('write_mode', WriteMode.OVERWRITE)
                if isinstance(write_mode, str):
                    write_mode = WriteMode(write_mode)
                
                mapping = ColumnMapping(
                    source_id=source_id,
                    source_name=source_name,
                    source_column=sug['source_column'],
                    target_column=sug['target_column'],
                    target_is_new=sug.get('target_is_new', False),
                    write_mode=write_mode
                )
                self.mapping_manager.add(mapping)
                added_count += 1
            
            self._refresh_tree()
            self._notify_change()
            
            # Show confirmation
            from tkinter import messagebox
            messagebox.showinfo("Dodano mapowania", f"Dodano {added_count} mapowań z sugestii.")
    
    def _remove_selected(self):
        """Remove selected mappings."""
        selected = self.tree.get_selected_items()
        if not selected:
            return
        
        for item in selected:
            values = self.tree.get_row_data(item)
            if values:
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
                
                # Restore selection (new index is idx - 1)
                self._select_index(idx - 1)
    
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
                
                # Restore selection (new index is idx + 1)
                self._select_index(idx + 1)
    
    def _select_index(self, index: int):
        """Select row by index."""
        children = self.tree.get_children()
        if 0 <= index < len(children):
            item = children[index]
            self.tree.selection_set(item)
            self.tree.focus(item)
            self.tree.see(item)
    
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
        self.source_name_to_id = {name: sid for sid, name in sources.items()}
        
        # Update quick bar combos
        self.quick_source_combo['values'] = list(sources.values())
        if sources:
            # Select first source if none selected
            if not self.quick_source_var.get():
                first_source = list(sources.values())[0]
                self.quick_source_var.set(first_source)
                self._on_quick_source_changed()
    
    def set_target_columns(self, columns: List[str]):
        """Update available target columns."""
        self.target_columns = columns
        self.quick_target_col_combo['values'] = columns + ['+ NOWA KOLUMNA...']
    
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
        self.quick_source_combo.set('')
        self.quick_source_col_combo.set('')
        self.quick_target_col_combo.set('')
        self._refresh_tree()
