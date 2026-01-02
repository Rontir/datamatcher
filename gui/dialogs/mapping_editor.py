"""
Mapping Editor Dialog - Dialog for creating/editing column mappings.
Enhanced with smart auto-suggestion of matching columns using fuzzy logic and synonyms.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Any
import re
import difflib

from core.mapping import ColumnMapping, WriteMode
from core.transformer import get_transform_names


# Patterns for matching similar column names (Synonyms) - EXTENDED
COLUMN_PATTERNS = {
    # Key columns
    'mdm': ['indeks mdm', 'mdm', 'indeks_mdm', 'mdm_index', 'index mdm', 'indeks mdm produktu', 'mdm id', 'id produktu', 'product id', 'id'],
    'ean': ['ean', 'kod ean', 'ean13', 'ean 13', 'gtin', 'barcode', 'kod kreskowy', 'ean code', 'upc'],
    'sku': ['sku', 'kod', 'kod produktu', 'product_code', 'kod katalogowy', 'symbol', 'nr katalogowy', 'artykul', 'artikul', 'item_code'],
    'gold': ['indeks gold', 'gold', 'index gold', 'gold_index', 'kod gold', 'gold code'],
    
    # Names and titles
    'nazwa': ['nazwa', 'tytuł', 'tytul', 'name', 'title', 'nazwa produktu', 'tytuł .com', 'tytuł.com', 'opis krótki', 'product name', 'nazwa artykułu', 'nazwa towaru', 'tytul produktu', 'product title', 'nazwa wyswietlana', 'display name'],
    'marka': ['marka', 'brand', 'marka produktu', 'producent', 'manufacturer', 'brand name', 'firma'],
    'producent': ['producent', 'manufacturer', 'producer', 'marka', 'dostawca', 'supplier', 'vendor'],
    
    # Pricing
    'cena': ['cena', 'price', 'cena zakupu', 'cena sprzedaży', 'cena netto', 'cena brutto', 'koszt', 'wartość', 'cena detal', 'cena hurt', 'cena jednostkowa', 'unit price', 'cost', 'cena katalogowa', 'msrp', 'rrp'],
    'cena_promocyjna': ['cena promocyjna', 'promo price', 'sale price', 'cena wyprzedażowa', 'cena przeceniona', 'cena specjalna'],
    
    # Availability
    'dostepnosc': ['dostępność', 'dostepnosc', 'availability', 'stan', 'stock', 'ilość', 'ilosc', 'magazyn', 'qty', 'quantity', 'stan magazynowy', 'available', 'in stock', 'na stanie'],
    'widocznosc': ['widoczność', 'widocznosc', 'visibility', 'aktywny', 'active', 'status', 'czy widoczny', 'visible', 'opublikowany', 'published', 'enabled'],
    
    # Categories
    'struktura': ['struktura', 'category', 'kategoria', 'struktura gold', 'struktura towarowa', 'ścieżka', 'drzewo kategorii', 'path', 'category path', 'klasyfikacja', 'dział'],
    'kategoria': ['kategoria', 'category', 'dział', 'sekcja', 'grupa', 'group', 'rodzaj', 'type', 'typ produktu'],
    
    # Descriptions
    'opis': ['opis', 'description', 'opis produktu', 'opis pełny', 'szczegóły', 'opis marketingowy', 'long description', 'opis długi', 'tresc', 'content', 'opis szczegółowy', 'opis techniczny'],
    'opis_krotki': ['opis krótki', 'short description', 'skrócony opis', 'lead', 'zajawka', 'podsumowanie', 'summary'],
    
    # Physical attributes
    'waga': ['waga', 'weight', 'masa', 'ciężar', 'waga brutto', 'waga netto', 'gross weight', 'net weight'],
    'wymiary': ['wymiary', 'dimensions', 'wysokość', 'szerokość', 'głębokość', 'rozmiar', 'gabaryt', 'size', 'height', 'width', 'depth', 'length', 'długość'],
    
    # Tax
    'vat': ['vat', 'stawka vat', 'podatek', 'tax', 'tax rate', 'stawka podatku', 'vat rate'],
    
    # Images
    'zdjecie': ['zdjęcie', 'zdjecie', 'image', 'obrazek', 'foto', 'photo', 'grafika', 'picture', 'img', 'url zdjęcia', 'image url', 'main image', 'zdjecie glowne'],
    
    # Attributes
    'kolor': ['kolor', 'color', 'colour', 'barwa'],
    'rozmiar': ['rozmiar', 'size', 'wymiar', 'format'],
    'material': ['materiał', 'material', 'tworzywo', 'surowiec'],
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


def calculate_similarity(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings."""
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def find_matching_column(source_col: str, target_columns: List[str]) -> Optional[str]:
    """
    Find best matching target column for a source column.
    Returns the matching target column name or None.
    Uses multi-stage matching: direct -> synonyms -> fuzzy -> word overlap.
    """
    source_norm = normalize_column_name(source_col)
    
    # 1. Direct match (exact or normalized)
    for target in target_columns:
        if normalize_column_name(target) == source_norm:
            return target
    
    # 2. Pattern-based matching (Synonyms) - check if source belongs to a pattern group
    source_pattern = None
    for pattern_key, variants in COLUMN_PATTERNS.items():
        for variant in variants:
            # Check if variant matches source (partial match allowed)
            if variant == source_norm or variant in source_norm or source_norm in variant:
                source_pattern = pattern_key
                break
        if source_pattern:
            break
    
    if source_pattern:
        # Look for target with same pattern
        for target in target_columns:
            target_norm = normalize_column_name(target)
            for variant in COLUMN_PATTERNS[source_pattern]:
                if variant in target_norm or target_norm in variant:
                    return target
    
    # 3. Fuzzy matching with relaxed threshold
    best_match = None
    best_score = 0.0
    
    for target in target_columns:
        target_norm = normalize_column_name(target)
        score = calculate_similarity(source_norm, target_norm)
        
        if score > best_score:
            best_score = score
            best_match = target
    
    # Lowered threshold from 0.85 to 0.65 to catch more matches
    if best_score > 0.65:
        return best_match
    
    # 4. Partial word match (fallback) - at least one meaningful word in common
    source_words = set(source_norm.split())
    for target in target_columns:
        target_words = set(normalize_column_name(target).split())
        common = source_words & target_words
        # Accept if any common word has 3+ characters
        meaningful = [w for w in common if len(w) >= 3]
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
        source_norm = normalize_column_name(source_col)
        
        # Try to find match
        match = find_matching_column(source_col, [t for t in target_columns if t not in used_targets])
        
        if match:
            match_norm = normalize_column_name(match)
            
            # Determine confidence
            confidence = 'low'
            if source_norm == match_norm:
                confidence = 'high'
            elif calculate_similarity(source_norm, match_norm) > 0.8:
                confidence = 'high'
            elif any(p in source_norm and p in match_norm for p in COLUMN_PATTERNS):
                confidence = 'medium'
            else:
                confidence = 'medium'
                
            suggestions.append({
                'source_column': source_col,
                'target_column': match,
                'target_is_new': False,
                'confidence': confidence
            })
            used_targets.add(match)
        else:
            # Suggest creating new column
            suggestions.append({
                'source_column': source_col,
                'target_column': source_col,
                'target_is_new': True,
                'confidence': 'low'
            })
    
    # Sort by confidence (High -> Medium -> Low)
    confidence_order = {'high': 0, 'medium': 1, 'low': 2}
    suggestions.sort(key=lambda x: confidence_order[x['confidence']])
    
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
    Each row is editable - user can choose target column from dropdown or create new.
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
        
        # Store row widgets
        self.row_widgets = []  # List of dicts with widgets per row
        
        self.title("Inteligentne sugestie mapowań")
        self.geometry("900x600")
        self.minsize(800, 500)
        
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
            font=('Segoe UI', 12, 'bold')
        )
        header.pack(anchor='w', pady=(0, 5))
        
        info = ttk.Label(
            main_frame,
            text="Zaznacz mapowania i wybierz kolumnę docelową dla każdego. Możesz wybrać istniejącą lub utworzyć nową.",
            foreground='gray', wraplength=800
        )
        info.pack(anchor='w', pady=(0, 15))
        
        # Column headers
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header_frame, text="✓", width=3, font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Kolumna źródłowa", width=25, font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="→", width=3).pack(side=tk.LEFT)
        ttk.Label(header_frame, text="Kolumna docelowa", width=30, font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Tryb", width=15, font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        ttk.Label(header_frame, text="Status", width=15, font=('Segoe UI', 9, 'bold')).pack(side=tk.LEFT, padx=5)
        
        # Scrollable frame for rows
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Enable mousewheel scrolling
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(btn_frame, text="✓ Zaznacz wszystkie", command=self._select_all).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="✗ Odznacz wszystkie", command=self._deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="🔄 Sugestie od nowa", command=self._reset_to_suggestions).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="Anuluj", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="✓ Zastosuj wybrane", command=self._apply, style='Accent.TButton').pack(side=tk.RIGHT)
    
    def _generate_suggestions(self):
        """Generate and display editable suggestions."""
        suggestions = get_all_column_suggestions(self.source_columns, self.target_columns)
        
        # Prepare target options: existing columns + "(NOWA KOLUMNA)" option
        target_options = ["(NOWA KOLUMNA)"] + self.target_columns
        
        # Write mode options
        mode_display = {
            WriteMode.OVERWRITE: "Nadpisz",
            WriteMode.FILL_EMPTY: "Uzupełnij puste",
            WriteMode.APPEND: "Dopisz",
            WriteMode.OVERWRITE_IF_NOT_EMPTY: "Nadpisz jeśli jest"
        }
        mode_options = list(mode_display.values())
        
        self.row_widgets = []
        
        for i, sug in enumerate(suggestions):
            row_frame = ttk.Frame(self.scrollable_frame)
            row_frame.pack(fill=tk.X, pady=2)
            
            # Checkbox
            selected_var = tk.BooleanVar(value=(sug['confidence'] == 'high'))
            chk = ttk.Checkbutton(row_frame, variable=selected_var, width=2)
            chk.pack(side=tk.LEFT)
            
            # Source column (read-only)
            source_label = ttk.Label(row_frame, text=sug['source_column'], width=25)
            source_label.pack(side=tk.LEFT, padx=5)
            
            # Arrow
            ttk.Label(row_frame, text="→", width=3).pack(side=tk.LEFT)
            
            # Target column dropdown (editable)
            target_var = tk.StringVar()
            
            # Set initial value based on suggestion
            if sug['target_is_new']:
                target_var.set("(NOWA KOLUMNA)")
            else:
                target_var.set(sug['target_column'])
            
            target_combo = ttk.Combobox(
                row_frame, textvariable=target_var, 
                values=target_options, width=28
            )
            target_combo.pack(side=tk.LEFT, padx=5)
            
            # Mode dropdown
            mode_var = tk.StringVar(value="Nadpisz")
            mode_combo = ttk.Combobox(
                row_frame, textvariable=mode_var,
                values=mode_options, state='readonly', width=15
            )
            mode_combo.pack(side=tk.LEFT, padx=5)
            
            # Status indicator
            status_icons = {'high': '🟢 Dopasowano', 'medium': '🟡 Podobne', 'low': '⚪ Nowa'}
            status = status_icons.get(sug['confidence'], '⚪')
            status_label = ttk.Label(row_frame, text=status, width=15)
            status_label.pack(side=tk.LEFT, padx=5)
            
            # Store widgets
            self.row_widgets.append({
                'index': i,
                'source_column': sug['source_column'],
                'selected_var': selected_var,
                'target_var': target_var,
                'mode_var': mode_var,
                'original_suggestion': sug
            })
        
        self.suggestions = suggestions
    
    def _select_all(self):
        """Select all items."""
        for row in self.row_widgets:
            row['selected_var'].set(True)
    
    def _deselect_all(self):
        """Deselect all items."""
        for row in self.row_widgets:
            row['selected_var'].set(False)
    
    def _reset_to_suggestions(self):
        """Reset all dropdowns to original suggestions."""
        for row in self.row_widgets:
            sug = row['original_suggestion']
            if sug['target_is_new']:
                row['target_var'].set("(NOWA KOLUMNA)")
            else:
                row['target_var'].set(sug['target_column'])
            row['selected_var'].set(sug['confidence'] == 'high')
    
    def _apply(self):
        """Apply selected mappings."""
        self.result = []
        
        mode_reverse = {
            "Nadpisz": WriteMode.OVERWRITE,
            "Uzupełnij puste": WriteMode.FILL_EMPTY,
            "Dopisz": WriteMode.APPEND,
            "Nadpisz jeśli jest": WriteMode.OVERWRITE_IF_NOT_EMPTY
        }
        
        for row in self.row_widgets:
            if row['selected_var'].get():
                target = row['target_var'].get()
                is_new = (target == "(NOWA KOLUMNA)")
                
                if is_new:
                    # Use source column name as new column name
                    target = row['source_column']
                
                mode_str = row['mode_var'].get()
                mode = mode_reverse.get(mode_str, WriteMode.OVERWRITE)
                
                self.result.append({
                    'source_column': row['source_column'],
                    'target_column': target,
                    'target_is_new': is_new,
                    'write_mode': mode,
                    'confidence': row['original_suggestion'].get('confidence', 'medium')
                })
        
        self.destroy()
    
    def _cancel(self):
        """Cancel dialog."""
        self.result = None
        self.destroy()
