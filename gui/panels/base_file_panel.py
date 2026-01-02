"""
Base File Panel - Panel for loading and configuring the base file.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional, Callable, List, Dict, Any

from utils.file_handlers import load_file, get_file_info
from utils.key_normalizer import get_key_stats, detect_key_column
from core.data_source import DataSource
from gui.widgets.tooltip import ToolTip


class BaseFilePanel(ttk.LabelFrame):
    """
    Panel for loading and configuring the base/target file.
    """
    
    def __init__(self, master, on_file_loaded: Optional[Callable] = None, 
                 on_key_changed: Optional[Callable] = None, **kwargs):
        super().__init__(master, text="📁 PLIK BAZOWY", padding=10, **kwargs)
        
        self.on_file_loaded = on_file_loaded
        self.on_key_changed = on_key_changed
        
        self.data_source: Optional[DataSource] = None
        self.sheets: List[str] = []
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all widgets."""
        # Load button
        self.load_btn = ttk.Button(
            self, text="📂 Wczytaj plik bazowy...", 
            command=self._load_file,
            style='Accent.TButton'
        )
        self.load_btn.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        ToolTip(self.load_btn, "Wczytaj plik Excel lub CSV jako bazę danych (Ctrl+O)")
        
        # File info
        self.file_label = ttk.Label(self, text="Plik: (nie wczytano)")
        self.file_label.grid(row=1, column=0, columnspan=2, sticky='w')
        
        # Sheet selector (for Excel files)
        self.sheet_frame = ttk.Frame(self)
        self.sheet_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=5)
        
        ttk.Label(self.sheet_frame, text="Arkusz:").pack(side=tk.LEFT)
        self.sheet_var = tk.StringVar()
        self.sheet_combo = ttk.Combobox(
            self.sheet_frame, textvariable=self.sheet_var,
            state='readonly', width=25
        )
        self.sheet_combo.pack(side=tk.LEFT, padx=5)
        self.sheet_combo.bind('<<ComboboxSelected>>', self._on_sheet_changed)
        ToolTip(self.sheet_combo, "Wybierz arkusz do przetworzenia")
        self.sheet_frame.grid_remove()  # Hide until Excel file loaded
        
        # Stats
        self.stats_frame = ttk.Frame(self)
        self.stats_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)
        
        self.rows_label = ttk.Label(self.stats_frame, text="Wierszy: -")
        self.rows_label.pack(anchor='w')
        
        self.cols_label = ttk.Label(self.stats_frame, text="Kolumn: -")
        self.cols_label.pack(anchor='w')
        
        # Separator
        ttk.Separator(self, orient='horizontal').grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)
        
        # Key column selector
        ttk.Label(self, text="Kolumna klucza:").grid(row=5, column=0, sticky='w')
        
        self.key_var = tk.StringVar()
        self.key_combo = ttk.Combobox(
            self, textvariable=self.key_var,
            state='readonly', width=30
        )
        self.key_combo.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(0, 5))
        self.key_combo.bind('<<ComboboxSelected>>', self._on_key_changed)
        ToolTip(self.key_combo, "Wybierz kolumnę używaną do dopasowywania (np. MDM, EAN, SKU)")
        
        # Key stats
        self.key_stats_frame = ttk.Frame(self)
        self.key_stats_frame.grid(row=7, column=0, columnspan=2, sticky='ew')
        
        self.unique_label = ttk.Label(self.key_stats_frame, text="Unikalne klucze: -")
        self.unique_label.pack(anchor='w')
        
        self.duplicates_label = ttk.Label(self.key_stats_frame, text="Duplikaty: -")
        self.duplicates_label.pack(anchor='w')
        
        self.empty_label = ttk.Label(self.key_stats_frame, text="Puste klucze: -")
        self.empty_label.pack(anchor='w')
        
        # Preview button
        self.preview_btn = ttk.Button(
            self, text="👁️ Podgląd danych...",
            command=self._show_preview,
            state='disabled'
        )
        self.preview_btn.grid(row=8, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        ToolTip(self.preview_btn, "Pokaż podgląd wczytanych danych")
        
        # Configure grid
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
    
    def _load_file(self):
        """Open file dialog and load selected file."""
        filetypes = [
            ("Pliki Excel", "*.xlsx *.xls *.xlsm *.xlsb"),
            ("Pliki CSV", "*.csv *.tsv *.txt"),
            ("Wszystkie pliki", "*.*")
        ]
        
        filepath = filedialog.askopenfilename(
            title="Wybierz plik bazowy",
            filetypes=filetypes
        )
        
        if not filepath:
            return
        
        self._load_file_threaded(filepath)
    
    def _load_file_threaded(self, filepath: str, sheet: Optional[str] = None):
        """Load file in a separate thread."""
        self.load_btn.config(state='disabled', text="⏳ Wczytywanie pliku...")
        self.file_label.config(text=f"Wczytywanie: {filepath}...")
        
        import threading
        
        def load_task():
            try:
                # Create data source (heavy IO)
                data_source = DataSource(filepath=filepath)
                sheets = data_source.load(sheet)
                return (data_source, sheets, None)
            except Exception as e:
                return (None, None, str(e))
        
        def on_complete(result):
            data_source, sheets, error = result
            
            self.load_btn.config(state='normal', text="📂 Wczytaj plik bazowy...")
            
            if error:
                from tkinter import messagebox
                messagebox.showerror("Błąd", f"Nie można wczytać pliku:\n{error}")
                self.file_label.config(text="Plik: (błąd wczytywania)")
                return
            
            # Success - update UI
            self.data_source = data_source
            self.sheets = sheets
            
            # Update file info
            file_info = get_file_info(filepath)
            self.file_label.config(text=f"Plik: {file_info['name']}")
            
            # Show/hide sheet selector
            if file_info['is_excel'] and len(self.sheets) > 1:
                self.sheet_combo['values'] = self.sheets
                self.sheet_var.set(self.data_source.sheet or self.sheets[0])
                self.sheet_frame.grid()
            else:
                self.sheet_frame.grid_remove()
            
            # Update stats
            self._update_stats()
            
            # Update key column options
            columns = self.data_source.get_columns()
            self.key_combo['values'] = columns
            
            # Try to auto-detect key column
            suggested = detect_key_column(columns, self.data_source.dataframe)
            if suggested:
                self.key_var.set(suggested)
                self._on_key_changed()
            
            # Enable preview
            self.preview_btn.config(state='normal')
            
            # Notify callback
            if self.on_file_loaded:
                self.on_file_loaded(self.data_source)
        
        def thread_target():
            result = load_task()
            self.after(0, lambda: on_complete(result))
            
        threading.Thread(target=thread_target, daemon=True).start()
    
    def load_from_path(self, filepath: str, sheet: Optional[str] = None):
        """Load file from specified path (public API)."""
        self._load_file_threaded(filepath, sheet)
    
    def _on_sheet_changed(self, event=None):
        """Handle sheet selection change."""
        if not self.data_source:
            return
        
        sheet = self.sheet_var.get()
        self.data_source.load(sheet)
        self._update_stats()
        
        # Update columns
        columns = self.data_source.get_columns()
        self.key_combo['values'] = columns
        
        # Reset key if not in new columns
        if self.key_var.get() not in columns:
            self.key_var.set('')
            self._update_key_stats()
    
    def _on_key_changed(self, event=None):
        """Handle key column selection change."""
        if not self.data_source:
            return
        
        key_col = self.key_var.get()
        if key_col:
            self.data_source.set_key_column(key_col)
            self._update_key_stats()
            
            if self.on_key_changed:
                self.on_key_changed(self.data_source)
    
    def _update_stats(self):
        """Update row/column statistics."""
        if not self.data_source or self.data_source.dataframe is None:
            return
        
        rows = len(self.data_source.dataframe)
        cols = len(self.data_source.dataframe.columns)
        
        self.rows_label.config(text=f"Wierszy: {rows:,}")
        self.cols_label.config(text=f"Kolumn: {cols}")
    
    def _update_key_stats(self):
        """Update key column statistics."""
        if not self.data_source or not self.data_source.key_column:
            self.unique_label.config(text="Unikalne klucze: -")
            self.duplicates_label.config(text="Duplikaty: -")
            self.empty_label.config(text="Puste klucze: -")
            return
        
        stats = get_key_stats(
            self.data_source.dataframe,
            self.data_source.key_column,
            self.data_source.key_options
        )
        
        self.unique_label.config(text=f"Unikalne klucze: {stats['unique']:,}")
        
        if stats['duplicates'] > 0:
            self.duplicates_label.config(
                text=f"Duplikaty: {stats['duplicates']} ⚠️",
                foreground='orange'
            )
        else:
            self.duplicates_label.config(text="Duplikaty: 0", foreground='')
        
        if stats['empty'] > 0:
            self.empty_label.config(
                text=f"Puste klucze: {stats['empty']} ⚠️",
                foreground='orange'
            )
        else:
            self.empty_label.config(text="Puste klucze: 0", foreground='')
    
    def _show_preview(self):
        """Show data preview dialog."""
        if not self.data_source or self.data_source.dataframe is None:
            return
        
        from gui.dialogs.source_preview import SourcePreviewDialog
        SourcePreviewDialog(
            self.winfo_toplevel(),
            self.data_source.dataframe,
            title=f"Podgląd: {self.data_source.filename}"
        )
    
    def get_data_source(self) -> Optional[DataSource]:
        """Get the current data source."""
        return self.data_source
    
    def get_key_column(self) -> str:
        """Get selected key column name."""
        return self.key_var.get()
    
    def get_columns(self) -> List[str]:
        """Get list of available columns."""
        if self.data_source:
            return self.data_source.get_columns()
        return []
    
    def reset(self):
        """Reset panel to initial state."""
        self.data_source = None
        self.sheets = []
        self.file_label.config(text="Plik: (nie wczytano)")
        self.sheet_combo['values'] = []
        self.sheet_var.set('')
        self.sheet_frame.grid_remove()
        self.rows_label.config(text="Wierszy: -")
        self.cols_label.config(text="Kolumn: -")
        self.key_combo['values'] = []
        self.key_var.set('')
        self.unique_label.config(text="Unikalne klucze: -")
        self.duplicates_label.config(text="Duplikaty: -", foreground='')
        self.empty_label.config(text="Puste klucze: -", foreground='')
        self.preview_btn.config(state='disabled')
