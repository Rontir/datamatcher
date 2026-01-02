"""
Mapping Editor Dialog - Dialog for creating/editing column mappings.
Enhanced with smart auto-suggestion of matching columns.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List
import re

from core.mapping import ColumnMapping, WriteMode
from core.transformer import get_transform_names


# Patterns for matching similar column names
COLUMN_PATTERNS = {
    # Key columns
    'mdm': ['indeks mdm', 'mdm', 'indeks_mdm', 'mdm_index', 'index mdm', 'indeks mdm produktu'],
    'ean': ['ean', 'kod ean', 'ean13', 'gtin', 'barcode'],
    'sku': ['sku', 'kod', 'kod produktu', 'product_code', 'kod katalogowy'],
    'gold': ['indeks gold', 'gold', 'index gold', 'gold_index'],
    
    # Common data columns
    'nazwa': ['nazwa', 'tytuł', 'tytul', 'name', 'title', 'nazwa produktu', 'tytuł .com', 'tytuł.com'],
    'marka': ['marka', 'brand', 'marka produktu'],
    'producent': ['producent', 'manufacturer', 'producer'],
    'cena': ['cena', 'price', 'cena zakupu', 'cena sprzedaży', 'cena netto', 'cena brutto'],
    'dostepnosc': ['dostępność', 'dostepnosc', 'availability', 'stan', 'stock'],
    'widocznosc': ['widoczność', 'widocznosc', 'visibility', 'aktywny', 'active'],
    'struktura': ['struktura', 'category', 'kategoria', 'struktura gold', 'struktura towarowa'],
    'opis': ['opis', 'description', 'opis produktu', 'opis krótki', 'opis pełny'],
    'waga': ['waga', 'weight', 'masa'],
    'wymiary': ['wymiary', 'dimensions', 'wysokość', 'szerokość', 'głębokość'],
}


def normalize_column_name(name: str) -> str:
    """Normalize column name for matching."""
    if not name:
        return ""
    # Lowercase, remove extra chars, normalize spaces
    s = name.lower().strip()
    s = re.sub(r'[_\-\.]+', ' ', s)
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'\([^)]*\)', '', s)  # Remove parentheses content like (600)
    return s.strip()


def find_matching_column(source_col: str, target_columns: List[str]) -> Optional[str]:
    """
    Find best matching target column for a source column.
    Returns the matching target column name or None.
    """
    source_norm = normalize_column_name(source_col)
    
    # Direct match first
    for target in target_columns:
        if normalize_column_name(target) == source_norm:
            return target
    
    # Pattern-based matching
    source_pattern = None
    for pattern_key, variants in COLUMN_PATTERNS.items():
        for variant in variants:
            if variant in source_norm or source_norm in variant:
                source_pattern = pattern_key
                break
        if source_pattern:
            break
    
    if source_pattern:
        for target in target_columns:
            target_norm = normalize_column_name(target)
            for variant in COLUMN_PATTERNS[source_pattern]:
                if variant in target_norm or target_norm in variant:
                    return target
    
    # Partial match - at least one significant word matches
    source_words = set(source_norm.split())
    for target in target_columns:
        target_words = set(normalize_column_name(target).split())
        # Find meaningful matches (words longer than 2 chars)
        common = source_words & target_words
        meaningful = [w for w in common if len(w) > 2]
        if meaningful:
            return target
    
    return None


def get_all_column_suggestions(source_columns: List[str], target_columns: List[str]) -> List[Dict]:
    """
    Generate smart suggestions for all source columns.
    Returns list of dicts with source_col, target_col, confidence.
    """
    suggestions = []
    used_targets = set()
    
    for source_col in source_columns:
        match = find_matching_column(source_col, [t for t in target_columns if t not in used_targets])
        if match:
            suggestions.append({
                'source_column': source_col,
                'target_column': match,
                'target_is_new': False,
                'confidence': 'high' if normalize_column_name(source_col) == normalize_column_name(match) else 'medium'
            })
            used_targets.add(match)
        else:
            # Suggest creating new column with same name
            suggestions.append({
                'source_column': source_col,
                'target_column': source_col,
                'target_is_new': True,
                'confidence': 'low'
            })
    
    return suggestions


class MappingEditorDialog(tk.Toplevel):
    """
    Dialog for creating or editing a column mapping.
    """
    
    def __init__(self, parent, 
                 sources: Dict[str, str],
                 source_columns: Dict[str, List[str]],
                 target_columns: List[str],
                 mapping: Optional[ColumnMapping] = None,
                 title: str = "Mapowanie"):
        super().__init__(parent)
        
        self.sources = sources  # id -> name
        self.source_columns = source_columns  # id -> columns
        self.target_columns = target_columns
        self.mapping = mapping
        self.result: Optional[ColumnMapping] = None
        
        self.title(title)
        self.geometry("550x520")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        # Auto-select first source if available
        if self.sources and not mapping:
            first_source = list(self.sources.values())[0]
            self.source_var.set(first_source)
            self._on_source_changed()
        
        if mapping:
            self._load_mapping()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.focus_set()
        self.wait_window()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Source selection
        ttk.Label(main_frame, text="Źródło danych:", font=('Segoe UI', 10, 'bold')).grid(
            row=0, column=0, sticky='w', pady=(0, 5)
        )
        
        self.source_var = tk.StringVar()
        self.source_combo = ttk.Combobox(
            main_frame, textvariable=self.source_var,
            state='readonly', width=45
        )
        # Create mapping of display name -> id
        self.source_name_to_id = {name: sid for sid, name in self.sources.items()}
        self.source_combo['values'] = list(self.sources.values())
        self.source_combo.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        self.source_combo.bind('<<ComboboxSelected>>', self._on_source_changed)
        
        # Source column
        ttk.Label(main_frame, text="Kolumna źródłowa:").grid(
            row=2, column=0, sticky='w', pady=(0, 5)
        )
        
        self.source_col_var = tk.StringVar()
        self.source_col_combo = ttk.Combobox(
            main_frame, textvariable=self.source_col_var,
            state='readonly', width=45
        )
        self.source_col_combo.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        self.source_col_combo.bind('<<ComboboxSelected>>', self._on_source_col_changed)
        
        # Arrow with suggestion indicator
        self.arrow_frame = ttk.Frame(main_frame)
        self.arrow_frame.grid(row=4, column=0, columnspan=2, pady=5)
        
        ttk.Label(self.arrow_frame, text="↓", font=('Segoe UI', 16)).pack(side=tk.LEFT)
        self.suggestion_label = ttk.Label(self.arrow_frame, text="", foreground='green')
        self.suggestion_label.pack(side=tk.LEFT, padx=10)
        
        # Target column
        ttk.Label(main_frame, text="Kolumna docelowa:").grid(
            row=5, column=0, sticky='w', pady=(0, 5)
        )
        
        self.target_col_var = tk.StringVar()
        self.target_col_combo = ttk.Combobox(
            main_frame, textvariable=self.target_col_var,
            width=45
        )
        # Add "+ NOWA KOLUMNA" option
        self.target_col_combo['values'] = self.target_columns + ['+ NOWA KOLUMNA...']
        self.target_col_combo.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(0, 5))
        self.target_col_combo.bind('<<ComboboxSelected>>', self._on_target_changed)
        self.target_col_combo.bind('<KeyRelease>', self._on_target_typed)
        
        # New column name entry
        self.new_col_frame = ttk.Frame(main_frame)
        self.new_col_frame.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        
        ttk.Label(self.new_col_frame, text="Nazwa nowej kolumny:").pack(side=tk.LEFT)
        self.new_col_var = tk.StringVar()
        self.new_col_entry = ttk.Entry(self.new_col_frame, textvariable=self.new_col_var, width=30)
        self.new_col_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.new_col_frame.grid_remove()  # Hidden by default
        
        # Write mode
        ttk.Label(main_frame, text="Tryb zapisu:").grid(
            row=8, column=0, sticky='w', pady=(0, 5)
        )
        
        self.mode_var = tk.StringVar(value='overwrite')
        self.mode_combo = ttk.Combobox(
            main_frame, textvariable=self.mode_var,
            state='readonly', width=45
        )
        modes = [(mode.value, WriteMode.get_display_name(mode)) for mode in WriteMode]
        self.mode_display_to_value = {display: value for value, display in modes}
        self.mode_combo['values'] = [display for _, display in modes]
        self.mode_combo.set(WriteMode.get_display_name(WriteMode.OVERWRITE))
        self.mode_combo.grid(row=9, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        
        # Transform
        ttk.Label(main_frame, text="Transformacja:").grid(
            row=10, column=0, sticky='w', pady=(0, 5)
        )
        
        self.transform_var = tk.StringVar(value='none')
        self.transform_combo = ttk.Combobox(
            main_frame, textvariable=self.transform_var,
            state='readonly', width=45
        )
        transforms = get_transform_names()
        self.transform_name_to_id = {name: tid for tid, name in transforms.items()}
        self.transform_combo['values'] = list(transforms.values())
        self.transform_combo.set(transforms['none'])
        self.transform_combo.grid(row=11, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        
        # Separator
        ttk.Separator(main_frame, orient='horizontal').grid(
            row=12, column=0, columnspan=2, sticky='ew', pady=10
        )
        
        # Buttons - always at bottom
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=13, column=0, columnspan=2, sticky='ew')
        
        ttk.Button(
            btn_frame, text="Anuluj",
            command=self._cancel,
            width=15
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        self.save_btn = ttk.Button(
            btn_frame, text="Zapisz",
            command=self._save,
            style='Accent.TButton',
            width=15
        )
        self.save_btn.pack(side=tk.RIGHT)
        
        # Configure grid
        main_frame.columnconfigure(0, weight=1)
    
    def _on_source_changed(self, event=None):
        """Handle source selection change."""
        source_name = self.source_var.get()
        source_id = self.source_name_to_id.get(source_name)
        
        if source_id and source_id in self.source_columns:
            cols = self.source_columns[source_id]
            self.source_col_combo['values'] = cols
            if cols:
                self.source_col_var.set(cols[0])
                self._on_source_col_changed()
    
    def _on_source_col_changed(self, event=None):
        """Handle source column selection - auto-suggest target."""
        source_col = self.source_col_var.get()
        if not source_col:
            return
        
        # Find matching target column
        match = find_matching_column(source_col, self.target_columns)
        
        if match:
            self.target_col_var.set(match)
            self.suggestion_label.config(text="✓ Znaleziono dopasowanie", foreground='green')
            self.new_col_frame.grid_remove()
        else:
            # Suggest new column with same name
            self.target_col_var.set('+ NOWA KOLUMNA...')
            self.new_col_var.set(source_col)
            self.suggestion_label.config(text="→ Nowa kolumna", foreground='blue')
            self.new_col_frame.grid()
    
    def _on_target_changed(self, event=None):
        """Handle target column selection change."""
        target = self.target_col_var.get()
        
        if target == '+ NOWA KOLUMNA...':
            # Pre-fill with source column name if empty
            if not self.new_col_var.get():
                self.new_col_var.set(self.source_col_var.get())
            self.new_col_frame.grid()
            self.new_col_entry.focus_set()
            self.suggestion_label.config(text="→ Nowa kolumna", foreground='blue')
        else:
            self.new_col_frame.grid_remove()
            self.suggestion_label.config(text="", foreground='green')
    
    def _on_target_typed(self, event=None):
        """Handle typing in target combo for custom column name."""
        pass  # Allow typing for search
    
    def _load_mapping(self):
        """Load existing mapping into form."""
        if not self.mapping:
            return
        
        # Source
        source_name = self.sources.get(self.mapping.source_id, self.mapping.source_name)
        self.source_var.set(source_name)
        self._on_source_changed()
        
        # Source column
        self.source_col_var.set(self.mapping.source_column)
        
        # Target column
        if self.mapping.target_is_new:
            self.target_col_var.set('+ NOWA KOLUMNA...')
            self.new_col_var.set(self.mapping.target_column)
            self.new_col_frame.grid()
        else:
            self.target_col_var.set(self.mapping.target_column)
            self.new_col_frame.grid_remove()
        
        # Mode
        self.mode_combo.set(WriteMode.get_display_name(self.mapping.write_mode))
        
        # Transform
        if self.mapping.transform:
            transforms = get_transform_names()
            if self.mapping.transform in transforms:
                self.transform_combo.set(transforms[self.mapping.transform])
        
        # Clear suggestion when editing
        self.suggestion_label.config(text="")
    
    def _validate(self) -> bool:
        """Validate form inputs."""
        if not self.source_var.get():
            self._show_error("Wybierz źródło danych")
            return False
        
        if not self.source_col_var.get():
            self._show_error("Wybierz kolumnę źródłową")
            return False
        
        target = self.target_col_var.get()
        if not target:
            self._show_error("Wybierz kolumnę docelową")
            return False
        
        if target == '+ NOWA KOLUMNA...' and not self.new_col_var.get().strip():
            self._show_error("Podaj nazwę nowej kolumny")
            return False
        
        return True
    
    def _show_error(self, message: str):
        """Show error message."""
        from tkinter import messagebox
        messagebox.showerror("Błąd", message, parent=self)
    
    def _save(self):
        """Save the mapping."""
        if not self._validate():
            return
        
        # Get source ID
        source_name = self.source_var.get()
        source_id = self.source_name_to_id.get(source_name, '')
        
        # Get target column
        target = self.target_col_var.get()
        target_is_new = target == '+ NOWA KOLUMNA...'
        if target_is_new:
            target = self.new_col_var.get().strip()
        
        # Get write mode
        mode_display = self.mode_combo.get()
        mode_value = self.mode_display_to_value.get(mode_display, 'overwrite')
        
        # Get transform
        transform_display = self.transform_combo.get()
        transform_id = self.transform_name_to_id.get(transform_display, 'none')
        if transform_id == 'none':
            transform_id = None
        
        # Create or update mapping
        if self.mapping:
            self.mapping.source_id = source_id
            self.mapping.source_name = source_name
            self.mapping.source_column = self.source_col_var.get()
            self.mapping.target_column = target
            self.mapping.target_is_new = target_is_new
            self.mapping.write_mode = WriteMode(mode_value)
            self.mapping.transform = transform_id
            self.result = self.mapping
        else:
            self.result = ColumnMapping(
                source_id=source_id,
                source_name=source_name,
                source_column=self.source_col_var.get(),
                target_column=target,
                target_is_new=target_is_new,
                write_mode=WriteMode(mode_value),
                transform=transform_id
            )
        
        self.destroy()
    
    def _cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.destroy()


class SmartMappingSuggestionDialog(tk.Toplevel):
    """
    Dialog showing smart suggestions for all column mappings.
    """
    
    def __init__(self, parent, 
                 source_name: str,
                 source_columns: List[str],
                 target_columns: List[str]):
        super().__init__(parent)
        
        self.source_name = source_name
        self.source_columns = source_columns
        self.target_columns = target_columns
        self.result: Optional[List[Dict]] = None
        
        self.title("Inteligentne sugestie mapowań")
        self.geometry("700x500")
        self.minsize(600, 400)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._generate_suggestions()
        
        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.focus_set()
        self.wait_window()
    
    def _create_widgets(self):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header = ttk.Label(
            main_frame,
            text=f"Sugestie mapowań dla: {self.source_name}",
            font=('Segoe UI', 11, 'bold')
        )
        header.pack(anchor='w', pady=(0, 10))
        
        info = ttk.Label(
            main_frame,
            text="Zaznacz mapowania które chcesz zastosować:",
            foreground='gray'
        )
        info.pack(anchor='w', pady=(0, 10))
        
        # Treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        
        columns = ('select', 'source', 'arrow', 'target', 'status')
        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=15)
        
        self.tree.heading('select', text='✓')
        self.tree.heading('source', text='Kolumna źródłowa')
        self.tree.heading('arrow', text='')
        self.tree.heading('target', text='Kolumna docelowa')
        self.tree.heading('status', text='Status')
        
        self.tree.column('select', width=40, anchor='center')
        self.tree.column('source', width=200)
        self.tree.column('arrow', width=40, anchor='center')
        self.tree.column('target', width=200)
        self.tree.column('status', width=150)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree.bind('<ButtonRelease-1>', self._on_click)
        
        # Selected items tracking
        self.selected_items = set()
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(btn_frame, text="Zaznacz wszystkie", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Odznacz wszystkie", command=self._deselect_all).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Anuluj", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Zastosuj wybrane", command=self._apply, style='Accent.TButton').pack(side=tk.RIGHT)
    
    def _generate_suggestions(self):
        """Generate and display suggestions."""
        suggestions = get_all_column_suggestions(self.source_columns, self.target_columns)
        
        for i, sug in enumerate(suggestions):
            status_icons = {'high': '🟢 Dopasowano', 'medium': '🟡 Podobne', 'low': '⚪ Nowa kolumna'}
            status = status_icons.get(sug['confidence'], '')
            
            target_display = sug['target_column']
            if sug['target_is_new']:
                target_display = f"+ {target_display} (NOWA)"
            
            item = self.tree.insert('', tk.END, values=(
                '☐',
                sug['source_column'],
                '→',
                target_display,
                status
            ))
            
            # Store suggestion data
            self.tree.set(item, 'data', str(i))
            
            # Auto-select high confidence matches
            if sug['confidence'] == 'high':
                self.selected_items.add(item)
                self.tree.set(item, 'select', '☑')
        
        self.suggestions = suggestions
    
    def _on_click(self, event):
        """Handle click to toggle selection."""
        region = self.tree.identify_region(event.x, event.y)
        if region == 'cell':
            column = self.tree.identify_column(event.x)
            item = self.tree.identify_row(event.y)
            
            if column == '#1' and item:  # Select column
                if item in self.selected_items:
                    self.selected_items.remove(item)
                    self.tree.set(item, 'select', '☐')
                else:
                    self.selected_items.add(item)
                    self.tree.set(item, 'select', '☑')
    
    def _select_all(self):
        """Select all items."""
        for item in self.tree.get_children():
            self.selected_items.add(item)
            self.tree.set(item, 'select', '☑')
    
    def _deselect_all(self):
        """Deselect all items."""
        for item in self.tree.get_children():
            if item in self.selected_items:
                self.selected_items.remove(item)
            self.tree.set(item, 'select', '☐')
    
    def _apply(self):
        """Apply selected mappings."""
        self.result = []
        
        for item in self.selected_items:
            idx = int(self.tree.index(item))
            if idx < len(self.suggestions):
                self.result.append(self.suggestions[idx])
        
        self.destroy()
    
    def _cancel(self):
        """Cancel dialog."""
        self.result = None
        self.destroy()
