"""
Transform Editor Dialog - Dialog for advanced transformations.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict


class TransformEditorDialog(tk.Toplevel):
    """
    Dialog for editing advanced transformations (regex, value mapping).
    """
    
    def __init__(self, parent, transform_type: str = "regex", 
                 initial_value: Optional[Dict] = None,
                 title: str = "Edycja transformacji"):
        super().__init__(parent)
        
        self.transform_type = transform_type
        self.result: Optional[Dict] = None
        
        self.title(title)
        self.geometry("500x350")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
        if initial_value:
            self._load_value(initial_value)
        
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
        
        # Type selector
        type_frame = ttk.Frame(main_frame)
        type_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(type_frame, text="Typ transformacji:").pack(side=tk.LEFT)
        
        self.type_var = tk.StringVar(value=self.transform_type)
        
        types = [
            ("Regex (znajdź/zamień)", "regex"),
            ("Mapowanie wartości", "value_map"),
            ("Szablon", "template")
        ]
        
        for text, value in types:
            rb = ttk.Radiobutton(
                type_frame, text=text, value=value,
                variable=self.type_var, command=self._on_type_changed
            )
            rb.pack(side=tk.LEFT, padx=10)
        
        # Content frame (changes based on type)
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_regex_content()
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(
            btn_frame, text="Anuluj",
            command=self._cancel,
            width=15
        ).pack(side=tk.RIGHT, padx=(5, 0))
        
        ttk.Button(
            btn_frame, text="Zapisz",
            command=self._save,
            style='Accent.TButton',
            width=15
        ).pack(side=tk.RIGHT)
    
    def _on_type_changed(self):
        """Handle type change."""
        # Clear content frame
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        trans_type = self.type_var.get()
        
        if trans_type == "regex":
            self._create_regex_content()
        elif trans_type == "value_map":
            self._create_value_map_content()
        elif trans_type == "template":
            self._create_template_content()
    
    def _create_regex_content(self):
        """Create regex transformation content."""
        ttk.Label(self.content_frame, text="Wzorzec (regex):").pack(anchor='w')
        
        self.pattern_var = tk.StringVar()
        pattern_entry = ttk.Entry(self.content_frame, textvariable=self.pattern_var, width=50)
        pattern_entry.pack(fill=tk.X, pady=(5, 15))
        
        ttk.Label(self.content_frame, text="Zamień na:").pack(anchor='w')
        
        self.replacement_var = tk.StringVar()
        replacement_entry = ttk.Entry(self.content_frame, textvariable=self.replacement_var, width=50)
        replacement_entry.pack(fill=tk.X, pady=(5, 15))
        
        # Help text
        help_text = """Przykłady:
• Usuń HTML tagi: Wzorzec: <[^>]+>  Zamień: (puste)
• Tylko cyfry: Wzorzec: [^0-9]  Zamień: (puste)
• Zamień przecinki na kropki: Wzorzec: ,  Zamień: ."""
        
        ttk.Label(
            self.content_frame, text=help_text,
            foreground='gray', justify=tk.LEFT
        ).pack(anchor='w', pady=(10, 0))
    
    def _create_value_map_content(self):
        """Create value mapping content."""
        ttk.Label(
            self.content_frame, 
            text="Mapowanie wartości (jedna para na linię: stara=nowa):"
        ).pack(anchor='w')
        
        self.map_text = tk.Text(self.content_frame, height=8, width=50)
        self.map_text.pack(fill=tk.BOTH, expand=True, pady=(5, 15))
        
        # Help text
        help_text = """Przykład:
tak=Tak
nie=Nie
brak=N/A"""
        
        ttk.Label(
            self.content_frame, text=help_text,
            foreground='gray', justify=tk.LEFT
        ).pack(anchor='w')
    
    def _create_template_content(self):
        """Create template transformation content."""
        ttk.Label(
            self.content_frame,
            text="Szablon (użyj {nazwa_kolumny} jako placeholder):"
        ).pack(anchor='w')
        
        self.template_var = tk.StringVar()
        template_entry = ttk.Entry(self.content_frame, textvariable=self.template_var, width=50)
        template_entry.pack(fill=tk.X, pady=(5, 15))
        
        # Help text
        help_text = """Przykład:
{Imię} {Nazwisko}
Produkt: {Nazwa} (SKU: {SKU})"""
        
        ttk.Label(
            self.content_frame, text=help_text,
            foreground='gray', justify=tk.LEFT
        ).pack(anchor='w')
    
    def _load_value(self, value: Dict):
        """Load existing value into form."""
        trans_type = value.get('type', 'regex')
        self.type_var.set(trans_type)
        self._on_type_changed()
        
        if trans_type == 'regex':
            self.pattern_var.set(value.get('pattern', ''))
            self.replacement_var.set(value.get('replacement', ''))
        elif trans_type == 'value_map':
            mapping = value.get('mapping', {})
            lines = [f"{k}={v}" for k, v in mapping.items()]
            self.map_text.insert('1.0', '\n'.join(lines))
        elif trans_type == 'template':
            self.template_var.set(value.get('template', ''))
    
    def _save(self):
        """Save transformation."""
        trans_type = self.type_var.get()
        
        if trans_type == 'regex':
            pattern = self.pattern_var.get()
            if not pattern:
                from tkinter import messagebox
                messagebox.showerror("Błąd", "Podaj wzorzec regex", parent=self)
                return
            
            # Validate regex
            from core.transformer import validate_regex
            valid, error = validate_regex(pattern)
            if not valid:
                from tkinter import messagebox
                messagebox.showerror("Błąd", f"Nieprawidłowy regex:\n{error}", parent=self)
                return
            
            self.result = {
                'type': 'regex',
                'pattern': pattern,
                'replacement': self.replacement_var.get()
            }
        
        elif trans_type == 'value_map':
            text = self.map_text.get('1.0', 'end').strip()
            mapping = {}
            for line in text.split('\n'):
                if '=' in line:
                    key, val = line.split('=', 1)
                    mapping[key.strip()] = val.strip()
            
            self.result = {
                'type': 'value_map',
                'mapping': mapping
            }
        
        elif trans_type == 'template':
            template = self.template_var.get()
            if not template:
                from tkinter import messagebox
                messagebox.showerror("Błąd", "Podaj szablon", parent=self)
                return
            
            self.result = {
                'type': 'template',
                'template': template
            }
        
        self.destroy()
    
    def _cancel(self):
        """Cancel and close dialog."""
        self.result = None
        self.destroy()
