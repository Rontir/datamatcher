"""
Mapping Editor Dialog - Dialog for creating/editing column mappings.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List

from core.mapping import ColumnMapping, WriteMode
from core.transformer import get_transform_names


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
        self.geometry("500x450")
        self.resizable(False, False)
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        
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
            state='readonly', width=40
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
            state='readonly', width=40
        )
        self.source_col_combo.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        
        # Arrow
        ttk.Label(main_frame, text="↓", font=('Segoe UI', 16)).grid(
            row=4, column=0, columnspan=2, pady=5
        )
        
        # Target column
        ttk.Label(main_frame, text="Kolumna docelowa:").grid(
            row=5, column=0, sticky='w', pady=(0, 5)
        )
        
        self.target_col_var = tk.StringVar()
        self.target_col_combo = ttk.Combobox(
            main_frame, textvariable=self.target_col_var,
            width=40
        )
        # Add "+ NOWA KOLUMNA" option
        self.target_col_combo['values'] = self.target_columns + ['+ NOWA KOLUMNA...']
        self.target_col_combo.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(0, 5))
        self.target_col_combo.bind('<<ComboboxSelected>>', self._on_target_changed)
        
        # New column name entry (hidden by default)
        self.new_col_frame = ttk.Frame(main_frame)
        self.new_col_frame.grid(row=7, column=0, columnspan=2, sticky='ew', pady=(0, 15))
        
        ttk.Label(self.new_col_frame, text="Nazwa nowej kolumny:").pack(side=tk.LEFT)
        self.new_col_var = tk.StringVar()
        self.new_col_entry = ttk.Entry(self.new_col_frame, textvariable=self.new_col_var, width=30)
        self.new_col_entry.pack(side=tk.LEFT, padx=5)
        self.new_col_frame.grid_remove()
        
        # Write mode
        ttk.Label(main_frame, text="Tryb zapisu:").grid(
            row=8, column=0, sticky='w', pady=(0, 5)
        )
        
        self.mode_var = tk.StringVar(value='overwrite')
        self.mode_combo = ttk.Combobox(
            main_frame, textvariable=self.mode_var,
            state='readonly', width=40
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
            state='readonly', width=40
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
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=13, column=0, columnspan=2, sticky='ew')
        
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
        
        # Configure grid
        main_frame.columnconfigure(0, weight=1)
    
    def _on_source_changed(self, event=None):
        """Handle source selection change."""
        source_name = self.source_var.get()
        source_id = self.source_name_to_id.get(source_name)
        
        if source_id and source_id in self.source_columns:
            self.source_col_combo['values'] = self.source_columns[source_id]
            if self.source_columns[source_id]:
                self.source_col_var.set(self.source_columns[source_id][0])
    
    def _on_target_changed(self, event=None):
        """Handle target column selection change."""
        target = self.target_col_var.get()
        
        if target == '+ NOWA KOLUMNA...':
            self.new_col_frame.grid()
            self.new_col_entry.focus_set()
        else:
            self.new_col_frame.grid_remove()
    
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
        
        # Mode
        self.mode_combo.set(WriteMode.get_display_name(self.mapping.write_mode))
        
        # Transform
        if self.mapping.transform:
            transforms = get_transform_names()
            if self.mapping.transform in transforms:
                self.transform_combo.set(transforms[self.mapping.transform])
    
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
