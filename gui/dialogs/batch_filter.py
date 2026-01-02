"""
Batch Filter Dialog - Dialog for selecting which rows/indices to process.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, List

from utils.session import BatchFilter


class BatchFilterDialog(tk.Toplevel):
    """
    Dialog for configuring batch processing filters.
    Allows selecting specific rows, key ranges, or limits.
    """
    
    def __init__(self, parent, current_filter: Optional[BatchFilter] = None):
        super().__init__(parent)
        
        self.result: Optional[BatchFilter] = None
        self.filter = current_filter or BatchFilter()
        
        self.title("Filtr przetwarzania")
        self.geometry("500x450")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._load_current()
        
        # Center
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
        
        ttk.Label(main_frame, text="Wybierz które wiersze przetworzyć:",
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(0, 15))
        
        # Enable/Disable
        self.enabled_var = tk.BooleanVar(value=self.filter.enabled)
        ttk.Checkbutton(
            main_frame, text="Włącz filtrowanie (domyślnie: wszystkie wiersze)",
            variable=self.enabled_var, command=self._toggle_enabled
        ).pack(anchor='w', pady=(0, 10))
        
        # Mode selection
        self.mode_var = tk.StringVar(value=self.filter.mode)
        
        modes_frame = ttk.LabelFrame(main_frame, text="Tryb filtrowania", padding=10)
        modes_frame.pack(fill=tk.X, pady=10)
        
        # Option 1: Range
        range_frame = ttk.Frame(modes_frame)
        range_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(range_frame, text="Zakres wierszy (od-do):",
                       variable=self.mode_var, value="range").pack(side=tk.LEFT)
        
        self.start_var = tk.IntVar(value=self.filter.start_index)
        self.end_var = tk.IntVar(value=self.filter.end_index if self.filter.end_index > 0 else 0)
        
        ttk.Label(range_frame, text="Od:").pack(side=tk.LEFT, padx=(15, 5))
        ttk.Spinbox(range_frame, from_=0, to=1000000, textvariable=self.start_var, width=8).pack(side=tk.LEFT)
        
        ttk.Label(range_frame, text="Do:").pack(side=tk.LEFT, padx=(10, 5))
        ttk.Spinbox(range_frame, from_=0, to=1000000, textvariable=self.end_var, width=8).pack(side=tk.LEFT)
        ttk.Label(range_frame, text="(0 = koniec)", foreground='gray').pack(side=tk.LEFT, padx=5)
        
        # Option 2: Limit
        limit_frame = ttk.Frame(modes_frame)
        limit_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(limit_frame, text="Limit pierwszych N wierszy:",
                       variable=self.mode_var, value="limit").pack(side=tk.LEFT)
        
        self.limit_var = tk.IntVar(value=self.filter.limit if self.filter.limit > 0 else 1000)
        ttk.Spinbox(limit_frame, from_=1, to=1000000, textvariable=self.limit_var, width=10).pack(side=tk.LEFT, padx=15)
        
        # Option 3: Key list
        list_frame = ttk.Frame(modes_frame)
        list_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(list_frame, text="Lista konkretnych kluczy:",
                       variable=self.mode_var, value="list").pack(side=tk.LEFT)
        
        self.key_list_var = tk.StringVar(value='\n'.join(self.filter.key_list))
        
        key_input_frame = ttk.Frame(modes_frame)
        key_input_frame.pack(fill=tk.X, pady=5, padx=(20, 0))
        
        self.key_text = tk.Text(key_input_frame, height=5, width=40)
        self.key_text.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.key_text.insert('1.0', '\n'.join(self.filter.key_list))
        
        ttk.Label(key_input_frame, text="(jeden klucz\nna linię)", foreground='gray').pack(side=tk.LEFT, padx=5)
        
        # Option 4: Pattern
        pattern_frame = ttk.Frame(modes_frame)
        pattern_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(pattern_frame, text="Wzorzec regex klucza:",
                       variable=self.mode_var, value="pattern").pack(side=tk.LEFT)
        
        self.pattern_var = tk.StringVar(value=self.filter.key_pattern)
        ttk.Entry(pattern_frame, textvariable=self.pattern_var, width=30).pack(side=tk.LEFT, padx=15)
        ttk.Label(pattern_frame, text="np. ^123|^456", foreground='gray').pack(side=tk.LEFT)
        
        # All (disabled filtering)
        ttk.Radiobutton(modes_frame, text="Wszystkie wiersze (bez filtra)",
                       variable=self.mode_var, value="all").pack(anchor='w', pady=5)
        
        # Preview
        preview_frame = ttk.Frame(main_frame)
        preview_frame.pack(fill=tk.X, pady=15)
        
        self.preview_label = ttk.Label(preview_frame, text="", foreground='blue')
        self.preview_label.pack(anchor='w')
        
        self.mode_var.trace('w', lambda *a: self._update_preview())
        self._update_preview()
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="Anuluj", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Zastosuj", command=self._save, style='Accent.TButton').pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Wyczyść filtr", command=self._clear).pack(side=tk.LEFT)
    
    def _toggle_enabled(self):
        """Toggle filter enabled state."""
        pass
    
    def _load_current(self):
        """Load current filter settings."""
        self.enabled_var.set(self.filter.enabled)
        self.mode_var.set(self.filter.mode)
        self.start_var.set(self.filter.start_index)
        self.end_var.set(self.filter.end_index if self.filter.end_index > 0 else 0)
        self.limit_var.set(self.filter.limit if self.filter.limit > 0 else 1000)
        self.pattern_var.set(self.filter.key_pattern)
        self.key_text.delete('1.0', tk.END)
        self.key_text.insert('1.0', '\n'.join(self.filter.key_list))
    
    def _update_preview(self):
        """Update preview text."""
        mode = self.mode_var.get()
        
        if mode == "range":
            start = self.start_var.get()
            end = self.end_var.get()
            text = f"📋 Przetwarzane wiersze: {start} - {'koniec' if end <= 0 else end}"
        elif mode == "limit":
            text = f"📋 Przetwarzanych: pierwsze {self.limit_var.get()} wierszy"
        elif mode == "list":
            keys = self.key_text.get('1.0', tk.END).strip().split('\n')
            keys = [k.strip() for k in keys if k.strip()]
            text = f"📋 Przetwarzanych: {len(keys)} konkretnych kluczy"
        elif mode == "pattern":
            text = f"📋 Przetwarzane: klucze pasujące do wzorca '{self.pattern_var.get()}'"
        else:
            text = "📋 Przetwarzane: wszystkie wiersze"
        
        self.preview_label.config(text=text)
    
    def _clear(self):
        """Clear filter (process all)."""
        self.result = BatchFilter()
        self.result.enabled = False
        self.destroy()
    
    def _save(self):
        """Save filter settings."""
        self.result = BatchFilter()
        self.result.enabled = self.enabled_var.get()
        self.result.mode = self.mode_var.get()
        self.result.start_index = self.start_var.get()
        self.result.end_index = self.end_var.get() if self.end_var.get() > 0 else -1
        self.result.limit = self.limit_var.get()
        self.result.key_pattern = self.pattern_var.get()
        
        # Parse key list
        keys = self.key_text.get('1.0', tk.END).strip().split('\n')
        self.result.key_list = [k.strip() for k in keys if k.strip()]
        
        self.destroy()
    
    def _cancel(self):
        """Cancel dialog."""
        self.result = None
        self.destroy()


class LastSessionDialog(tk.Toplevel):
    """
    Dialog shown on startup if a previous session exists.
    """
    
    def __init__(self, parent, session_info: dict):
        super().__init__(parent)
        
        self.result: Optional[str] = None  # "load", "new", or None
        
        self.title("Ostatnia sesja")
        self.geometry("400x200")
        self.resizable(False, False)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets(session_info)
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.focus_set()
        self.wait_window()
    
    def _create_widgets(self, info: dict):
        """Create widgets."""
        main_frame = ttk.Frame(self, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="🕐 Znaleziono zapisaną sesję",
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w')
        
        details = ttk.Frame(main_frame)
        details.pack(fill=tk.X, pady=15)
        
        ttk.Label(details, text=f"Plik bazowy: {info.get('base_file', 'Brak')}").pack(anchor='w')
        ttk.Label(details, text=f"Źródeł: {info.get('sources_count', 0)}").pack(anchor='w')
        ttk.Label(details, text=f"Mapowań: {info.get('mappings_count', 0)}").pack(anchor='w')
        ttk.Label(details, text=f"Zapisano: {info.get('saved_at', '-')}", foreground='gray').pack(anchor='w')
        
        ttk.Label(main_frame, text="Czy chcesz wczytać tę sesję?").pack(pady=10)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="📂 Wczytaj sesję", 
                  command=lambda: self._choose("load"),
                  style='Accent.TButton').pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        
        ttk.Button(btn_frame, text="🆕 Nowa sesja", 
                  command=lambda: self._choose("new")).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
    
    def _choose(self, choice: str):
        self.result = choice
        self.destroy()
