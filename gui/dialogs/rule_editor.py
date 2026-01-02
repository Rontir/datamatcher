"""
Rule Editor Dialog - Dialog for creating/editing conditional mapping rules.
"""
import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, List, Any

from core.mapping import RuleCondition, RuleOperator


class RuleEditorDialog(tk.Toplevel):
    """
    Dialog for creating or editing conditional rules for a mapping.
    """
    
    def __init__(self, parent, 
                 source_columns: List[str],
                 target_columns: List[str],
                 existing_conditions: List[RuleCondition] = None,
                 condition_logic: str = "AND"):
        super().__init__(parent)
        
        self.source_columns = source_columns
        self.target_columns = target_columns
        self.conditions = existing_conditions.copy() if existing_conditions else []
        self.condition_logic = condition_logic
        self.result: Optional[Dict] = None
        
        self.title("Edytor reguł warunkowych")
        self.geometry("700x500")
        self.minsize(600, 400)
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._refresh_list()
        
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
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="Reguły warunkowe:", font=('Segoe UI', 11, 'bold')).pack(side=tk.LEFT)
        
        # Logic selector
        ttk.Label(header_frame, text="Logika:").pack(side=tk.LEFT, padx=(20, 5))
        
        self.logic_var = tk.StringVar(value=self.condition_logic)
        logic_combo = ttk.Combobox(
            header_frame, textvariable=self.logic_var,
            values=["AND", "OR"], state='readonly', width=8
        )
        logic_combo.pack(side=tk.LEFT)
        
        ttk.Label(header_frame, text="(AND = wszystkie muszą być spełnione, OR = wystarczy jedna)", 
                  foreground='gray').pack(side=tk.LEFT, padx=10)
        
        # Conditions list
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        columns = ('column', 'operator', 'value', 'type')
        self.tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)
        
        self.tree.heading('column', text='Kolumna')
        self.tree.heading('operator', text='Operator')
        self.tree.heading('value', text='Wartość')
        self.tree.heading('type', text='Typ')
        
        self.tree.column('column', width=150)
        self.tree.column('operator', width=150)
        self.tree.column('value', width=200)
        self.tree.column('type', width=80)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add condition form
        add_frame = ttk.LabelFrame(main_frame, text="Dodaj regułę", padding=10)
        add_frame.pack(fill=tk.X, pady=10)
        
        # Row 1: Column type and column selection
        row1 = ttk.Frame(add_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="Sprawdź kolumnę:").pack(side=tk.LEFT)
        
        self.col_type_var = tk.StringVar(value="source")
        ttk.Radiobutton(row1, text="Źródłową", variable=self.col_type_var, 
                       value="source", command=self._update_column_list).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(row1, text="Docelową", variable=self.col_type_var, 
                       value="target", command=self._update_column_list).pack(side=tk.LEFT, padx=5)
        
        self.column_var = tk.StringVar()
        self.column_combo = ttk.Combobox(row1, textvariable=self.column_var, width=25, state='readonly')
        self.column_combo['values'] = self.source_columns
        self.column_combo.pack(side=tk.LEFT, padx=10)
        
        # Row 2: Operator and value
        row2 = ttk.Frame(add_frame)
        row2.pack(fill=tk.X, pady=2)
        
        ttk.Label(row2, text="Operator:").pack(side=tk.LEFT)
        
        self.operator_var = tk.StringVar(value=RuleOperator.EQUALS.value)
        self.operator_combo = ttk.Combobox(row2, textvariable=self.operator_var, width=20, state='readonly')
        operator_options = [(op.value, RuleOperator.get_display_name(op)) for op in RuleOperator]
        self.operator_display_to_value = {display: value for value, display in operator_options}
        self.operator_combo['values'] = [display for _, display in operator_options]
        self.operator_combo.set(RuleOperator.get_display_name(RuleOperator.EQUALS))
        self.operator_combo.pack(side=tk.LEFT, padx=10)
        
        ttk.Label(row2, text="Wartość:").pack(side=tk.LEFT, padx=(20, 5))
        
        self.value_var = tk.StringVar()
        self.value_entry = ttk.Entry(row2, textvariable=self.value_var, width=25)
        self.value_entry.pack(side=tk.LEFT)
        
        ttk.Button(row2, text="➕ Dodaj", command=self._add_condition).pack(side=tk.LEFT, padx=10)
        
        # Remove button
        remove_frame = ttk.Frame(main_frame)
        remove_frame.pack(fill=tk.X)
        
        ttk.Button(remove_frame, text="🗑️ Usuń zaznaczoną", command=self._remove_selected).pack(side=tk.LEFT)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        ttk.Button(btn_frame, text="Anuluj", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Zapisz reguły", command=self._save, 
                  style='Accent.TButton').pack(side=tk.RIGHT)
    
    def _update_column_list(self):
        """Update column combo based on selected type."""
        if self.col_type_var.get() == "source":
            self.column_combo['values'] = self.source_columns
        else:
            self.column_combo['values'] = self.target_columns
        self.column_var.set('')
    
    def _add_condition(self):
        """Add a new condition."""
        column = self.column_var.get()
        operator_display = self.operator_combo.get()
        value = self.value_var.get()
        
        if not column:
            return
        
        # Get operator value
        operator_value = self.operator_display_to_value.get(operator_display, 'equals')
        
        condition = RuleCondition(
            column=column,
            operator=RuleOperator(operator_value),
            value=value,
            is_source_column=(self.col_type_var.get() == "source")
        )
        
        self.conditions.append(condition)
        self._refresh_list()
        
        # Clear inputs
        self.column_var.set('')
        self.value_var.set('')
    
    def _remove_selected(self):
        """Remove selected condition."""
        selected = self.tree.selection()
        if not selected:
            return
        
        idx = self.tree.index(selected[0])
        if 0 <= idx < len(self.conditions):
            self.conditions.pop(idx)
            self._refresh_list()
    
    def _refresh_list(self):
        """Refresh the conditions list."""
        self.tree.delete(*self.tree.get_children())
        
        for cond in self.conditions:
            col_type = "Źródło" if cond.is_source_column else "Cel"
            self.tree.insert('', tk.END, values=(
                cond.column,
                RuleOperator.get_display_name(cond.operator),
                cond.value if cond.value else "(puste)",
                col_type
            ))
    
    def _save(self):
        """Save and close."""
        self.result = {
            'conditions': self.conditions,
            'condition_logic': self.logic_var.get()
        }
        self.destroy()
    
    def _cancel(self):
        """Cancel and close."""
        self.result = None
        self.destroy()


class TemplateEditorDialog(tk.Toplevel):
    """
    Dialog for creating column templates (joining multiple columns).
    """
    
    def __init__(self, parent, source_columns: List[str], current_template: str = ""):
        super().__init__(parent)
        
        self.source_columns = source_columns
        self.result: Optional[str] = None
        
        self.title("Edytor szablonu kolumn")
        self.geometry("550x350")
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets(current_template)
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.focus_set()
        self.wait_window()
    
    def _create_widgets(self, current_template: str):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Szablon łączenia kolumn:", 
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        
        ttk.Label(main_frame, 
                  text="Użyj {NazwaKolumny} aby wstawić wartość z kolumny źródłowej.",
                  foreground='gray').pack(anchor='w', pady=(0, 10))
        
        # Template entry
        self.template_var = tk.StringVar(value=current_template)
        template_entry = ttk.Entry(main_frame, textvariable=self.template_var, width=60)
        template_entry.pack(fill=tk.X, pady=(0, 10))
        
        # Available columns
        ttk.Label(main_frame, text="Dostępne kolumny (kliknij aby wstawić):").pack(anchor='w')
        
        cols_frame = ttk.Frame(main_frame)
        cols_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create buttons for each column
        for i, col in enumerate(self.source_columns[:20]):  # Limit to 20
            btn = ttk.Button(
                cols_frame, text=col,
                command=lambda c=col: self._insert_column(c)
            )
            btn.grid(row=i//4, column=i%4, padx=2, pady=2, sticky='ew')
        
        for i in range(4):
            cols_frame.columnconfigure(i, weight=1)
        
        # Example
        example_frame = ttk.Frame(main_frame)
        example_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(example_frame, text="Przykład:").pack(side=tk.LEFT)
        ttk.Label(example_frame, text='{Marka} - {Model} ({Rok})', 
                  foreground='blue').pack(side=tk.LEFT, padx=5)
        ttk.Label(example_frame, text='→ "Nike - Air Max (2024)"', 
                  foreground='green').pack(side=tk.LEFT)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="Anuluj", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Zapisz", command=self._save, 
                  style='Accent.TButton').pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Wyczyść", command=lambda: self.template_var.set('')).pack(side=tk.LEFT)
    
    def _insert_column(self, col_name: str):
        """Insert column placeholder into template."""
        current = self.template_var.get()
        self.template_var.set(current + f'{{{col_name}}}')
    
    def _save(self):
        """Save template."""
        self.result = self.template_var.get()
        self.destroy()
    
    def _cancel(self):
        """Cancel."""
        self.result = None
        self.destroy()


class ScriptEditorDialog(tk.Toplevel):
    """
    Dialog for editing custom Python transformation scripts.
    """
    
    def __init__(self, parent, current_script: str = ""):
        super().__init__(parent)
        
        self.result: Optional[str] = None
        
        self.title("Edytor skryptu Python")
        self.geometry("600x400")
        
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets(current_script)
        
        # Center
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        self.focus_set()
        self.wait_window()
    
    def _create_widgets(self, current_script: str):
        """Create dialog widgets."""
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(main_frame, text="Skrypt transformacji Python:", 
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w')
        
        ttk.Label(main_frame, 
                  text="Użyj 'x' jako zmiennej wejściowej lub napisz pełną lambdę.",
                  foreground='gray').pack(anchor='w', pady=(0, 10))
        
        # Script text area
        self.script_text = tk.Text(main_frame, height=8, font=('Consolas', 10))
        self.script_text.pack(fill=tk.BOTH, expand=True)
        self.script_text.insert('1.0', current_script)
        
        # Examples
        examples_frame = ttk.LabelFrame(main_frame, text="Przykłady", padding=5)
        examples_frame.pack(fill=tk.X, pady=10)
        
        examples = [
            ("Wielkie litery", "x.upper()"),
            ("Usuń spacje", "x.strip()"),
            ("Zamień", "x.replace('stary', 'nowy')"),
            ("Zaokrąglij", "round(float(x), 2)"),
            ("Lambda", "lambda x: x.title() if x else ''"),
        ]
        
        for i, (name, code) in enumerate(examples):
            btn = ttk.Button(
                examples_frame, text=name,
                command=lambda c=code: self._insert_example(c)
            )
            btn.grid(row=0, column=i, padx=2, pady=2)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(btn_frame, text="Anuluj", command=self._cancel).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(btn_frame, text="Zapisz", command=self._save, 
                  style='Accent.TButton').pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="Testuj", command=self._test).pack(side=tk.LEFT)
    
    def _insert_example(self, code: str):
        """Insert example code."""
        self.script_text.delete('1.0', tk.END)
        self.script_text.insert('1.0', code)
    
    def _test(self):
        """Test the script."""
        script = self.script_text.get('1.0', tk.END).strip()
        test_value = "Test Value 123"
        
        try:
            safe_globals = {
                '__builtins__': {
                    'str': str, 'int': int, 'float': float, 'bool': bool,
                    'len': len, 'abs': abs, 'round': round, 'min': min, 'max': max,
                }
            }
            
            if script.startswith('lambda'):
                func = eval(script, safe_globals)
                result = func(test_value)
            else:
                safe_globals['x'] = test_value
                result = eval(script, safe_globals)
            
            from tkinter import messagebox
            messagebox.showinfo("Test OK", f"Wejście: '{test_value}'\nWynik: '{result}'")
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Błąd skryptu", f"Błąd: {e}")
    
    def _save(self):
        """Save script."""
        self.result = self.script_text.get('1.0', tk.END).strip()
        self.destroy()
    
    def _cancel(self):
        """Cancel."""
        self.result = None
        self.destroy()
