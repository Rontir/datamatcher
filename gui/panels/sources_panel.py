"""
Sources Panel - Panel for managing data sources.
"""
import tkinter as tk
from tkinter import ttk, filedialog
from typing import Optional, Callable, List, Dict, Any

from utils.file_handlers import load_file, get_file_info
from utils.key_normalizer import detect_key_column
from core.data_source import DataSource
from gui.widgets.tooltip import ToolTip


class SourceCard(ttk.Frame):
    """Card widget representing a single data source."""
    
    def __init__(self, master, source: DataSource, 
                 on_key_changed: Optional[Callable] = None,
                 on_preview: Optional[Callable] = None,
                 on_remove: Optional[Callable] = None,
                 **kwargs):
        super().__init__(master, **kwargs)
        
        self.source = source
        self.on_key_changed_callback = on_key_changed
        self.on_preview_callback = on_preview
        self.on_remove_callback = on_remove
        self.base_keys = set()  # Store base keys for analysis
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create card widgets."""
        # Configure border style
        self.configure(relief='solid', borderwidth=1, padding=5)
        
        # Header with filename
        header = ttk.Frame(self)
        header.pack(fill=tk.X)
        
        self.file_label = ttk.Label(
            header, 
            text=f"📄 {self.source.filename}",
            font=('Segoe UI', 10, 'bold')
        )
        self.file_label.pack(side=tk.LEFT)
        
        # Key column selector
        key_frame = ttk.Frame(self)
        key_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(key_frame, text="Klucz:").pack(side=tk.LEFT)
        
        self.key_var = tk.StringVar(value=self.source.key_column)
        self.key_combo = ttk.Combobox(
            key_frame, textvariable=self.key_var,
            state='readonly', width=20
        )
        self.key_combo['values'] = self.source.get_columns()
        self.key_combo.pack(side=tk.LEFT, padx=5)
        self.key_combo.bind('<<ComboboxSelected>>', self._on_key_changed)
        ToolTip(self.key_combo, "Kolumna klucza do dopasowywania z plikiem bazowym")
        
        # Match stats
        stats_frame = ttk.Frame(self)
        stats_frame.pack(anchor='w', fill=tk.X)
        
        self.stats_label = ttk.Label(stats_frame, text="Dopasowano: -/-")
        self.stats_label.pack(side=tk.LEFT)
        
        # Unmatched link (clickable)
        self.unmatched_link = ttk.Label(
            stats_frame, 
            text="", 
            foreground='red', 
            cursor='hand2'
        )
        self.unmatched_link.pack(side=tk.LEFT, padx=(10, 0))
        self.unmatched_link.bind('<Button-1>', self._show_unmatched)
        
        self.unmatched_keys = []  # Store for preview
        
        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.preview_btn = ttk.Button(
            btn_frame, text="👁️ Podgląd",
            command=self._on_preview,
            width=10
        )
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.remove_btn = ttk.Button(
            btn_frame, text="🗑️ Usuń",
            command=self._on_remove,
            width=10,
            style='danger.TButton'
        )
        self.remove_btn.pack(side=tk.LEFT)
    
    def _on_key_changed(self, event=None):
        """Handle key column change."""
        key_col = self.key_var.get()
        if key_col:
            self.source.set_key_column(key_col)
            if self.on_key_changed_callback:
                self.on_key_changed_callback(self.source)
    
    def _on_preview(self):
        """Show source preview."""
        if self.on_preview_callback:
            self.on_preview_callback(self.source)
    
    def _on_remove(self):
        """Remove this source."""
        if self.on_remove_callback:
            self.on_remove_callback(self.source)
    
    def _show_unmatched(self, event=None):
        """Show dialog with unmatched keys."""
        if not self.unmatched_keys:
            return
        
        # Custom dialog window
        dialog = tk.Toplevel(self)
        dialog.title(f"Niedopasowane: {self.source.filename}")
        dialog.geometry("700x600")
        
        # Main frame
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        ttk.Label(
            frame, 
            text=f"Niedopasowane klucze ({len(self.unmatched_keys)}):",
            font=('Segoe UI', 10, 'bold')
        ).pack(fill=tk.X, pady=(0, 10))
        
        # Analysis logic
        fixable_map = {}  # key -> fixed_key
        
        # Debug prints
        print(f"DEBUG: Unmatched keys count: {len(self.unmatched_keys)}")
        print(f"DEBUG: Base keys count: {len(self.base_keys)}")
        if self.base_keys:
            print(f"DEBUG: Sample base key: {list(self.base_keys)[0]} (type: {type(list(self.base_keys)[0])})")
        if self.unmatched_keys:
            print(f"DEBUG: Sample unmatched key: {self.unmatched_keys[0]} (type: {type(self.unmatched_keys[0])})")

        for key in self.unmatched_keys:
            s_key = str(key)
            # Try stripping .0
            if s_key.endswith('.0'):
                fixed = s_key[:-2]
                if fixed in self.base_keys:
                    fixable_map[key] = fixed
                    continue
            
            # Try stripping whitespace
            fixed = s_key.strip()
            if fixed != s_key and fixed in self.base_keys:
                fixable_map[key] = fixed
                continue
                
            # Try lowercase
            fixed = s_key.lower()
            if fixed != s_key and fixed in self.base_keys:
                fixable_map[key] = fixed
                continue
        
        # Listbox with scrollbar
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Use Treeview for better styling than Listbox
        tree = ttk.Treeview(
            list_frame, 
            columns=('key', 'fix'), 
            show='headings', 
            yscrollcommand=scrollbar.set,
            selectmode='extended'
        )
        tree.heading('key', text="Klucz źródłowy")
        tree.heading('fix', text="Proponowana naprawa")
        tree.column('key', width=300)
        tree.column('fix', width=300)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar.config(command=tree.yview)
        
        # Populate
        for key in self.unmatched_keys:
            fix = fixable_map.get(key, "")
            tags = ('fixable',) if fix else ()
            tree.insert('', tk.END, values=(str(key), fix), tags=tags)
            
        tree.tag_configure('fixable', foreground='green')
            
        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        def copy_to_clipboard():
            keys_str = "\n".join(str(k) for k in self.unmatched_keys)
            dialog.clipboard_clear()
            dialog.clipboard_append(keys_str)
            
        def fix_selected():
            selected_items = tree.selection()
            if not selected_items:
                # If nothing selected, select all fixable
                all_items = tree.get_children()
                selected_items = [item for item in all_items if tree.item(item)['values'][1]]
            
            if not selected_items:
                from tkinter import messagebox
                messagebox.showinfo("Info", "Brak kluczy do naprawy.")
                return
            
            count = 0
            # Apply fixes
            df = self.source.dataframe
            key_col = self.source.key_column
            
            for item in selected_items:
                values = tree.item(item)['values']
                original = values[0]
                fixed = values[1]
                
                if fixed:
                    # Update dataframe
                    # Note: This is a bit slow for many rows, but safe
                    # Assuming original is unique or we update all occurrences
                    mask = df[key_col].astype(str) == original
                    df.loc[mask, key_col] = fixed
                    count += 1
            
            if count > 0:
                # Rebuild index and refresh
                self.source.build_key_lookup(force=True)
                if self.on_key_changed_callback:
                    self.on_key_changed_callback(self.source)
                
                dialog.destroy()
                from tkinter import messagebox
                messagebox.showinfo("Sukces", f"Naprawiono {count} kluczy.")
        
        ttk.Button(
            btn_frame, text="Kopiuj do schowka",
            command=copy_to_clipboard
        ).pack(side=tk.LEFT)
        
        if fixable_map:
            ttk.Button(
                btn_frame, text=f"🔧 Napraw możliwe ({len(fixable_map)})",
                command=fix_selected,
                style='success.TButton'
            ).pack(side=tk.LEFT, padx=10)
            
        # Manual fix buttons (Force Fix)
        force_frame = ttk.LabelFrame(frame, text="Wymuś naprawę (wszystkie niedopasowane)", padding=5)
        force_frame.pack(fill=tk.X, pady=(10, 0))
        
        def force_fix_dot_zero():
            count = 0
            df = self.source.dataframe
            key_col = self.source.key_column
            
            # Get all unmatched keys that end with .0
            targets = [k for k in self.unmatched_keys if str(k).endswith('.0')]
            
            if not targets:
                from tkinter import messagebox
                messagebox.showinfo("Info", "Brak kluczy z końcówką .0")
                return
                
            for key in targets:
                s_key = str(key)
                fixed = s_key[:-2]
                
                mask = df[key_col].astype(str) == s_key
                df.loc[mask, key_col] = fixed
                count += 1
            
            if count > 0:
                self.source.build_key_lookup(force=True)
                if self.on_key_changed_callback:
                    self.on_key_changed_callback(self.source)
                dialog.destroy()
                from tkinter import messagebox
                messagebox.showinfo("Sukces", f"Naprawiono {count} kluczy (usunięto .0).")

        ttk.Button(
            force_frame, text="Usuń końcówki .0",
            command=force_fix_dot_zero
        ).pack(side=tk.LEFT, padx=5)
        
        def force_fix_whitespace():
            count = 0
            df = self.source.dataframe
            key_col = self.source.key_column
            
            targets = [k for k in self.unmatched_keys if str(k).strip() != str(k)]
            
            if not targets:
                from tkinter import messagebox
                messagebox.showinfo("Info", "Brak kluczy ze spacjami do usunięcia")
                return

            for key in targets:
                s_key = str(key)
                fixed = s_key.strip()
                
                mask = df[key_col].astype(str) == s_key
                df.loc[mask, key_col] = fixed
                count += 1
                
            if count > 0:
                self.source.build_key_lookup(force=True)
                if self.on_key_changed_callback:
                    self.on_key_changed_callback(self.source)
                dialog.destroy()
                from tkinter import messagebox
                messagebox.showinfo("Sukces", f"Naprawiono {count} kluczy (usunięto spacje).")

        ttk.Button(
            force_frame, text="Usuń spacje (trim)",
            command=force_fix_whitespace
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame, text="Zamknij",
            command=dialog.destroy,
            style='Accent.TButton'
        ).pack(side=tk.RIGHT)
    
    def update_stats(self, matched: int, total: int, unmatched_keys: list = None, base_keys: list = None):
        """Update match statistics display."""
        pct = (matched / total * 100) if total > 0 else 0
        unmatched = total - matched
        
        self.stats_label.config(text=f"Dopasowano: {matched:,} / {total:,} ({pct:.1f}%)")
        
        # Store unmatched keys for preview
        self.unmatched_keys = unmatched_keys or []
        
        # Store base keys for analysis
        if base_keys:
            self.base_keys = set(base_keys)
        
        # Update unmatched link
        if unmatched > 0:
            self.unmatched_link.config(text=f"⚠️ Niedopasowane: {unmatched:,} (kliknij)")
        else:
            self.unmatched_link.config(text="✅ Wszystkie dopasowane")
            self.unmatched_link.config(foreground='green')
        
        # Color based on match rate
        if pct >= 90:
            self.stats_label.config(foreground='green')
        elif pct >= 70:
            self.stats_label.config(foreground='orange')
        else:
            self.stats_label.config(foreground='red')


class SourcesPanel(ttk.LabelFrame):
    """
    Panel for managing multiple data sources.
    """
    
    def __init__(self, master, 
                 on_source_added: Optional[Callable] = None,
                 on_source_removed: Optional[Callable] = None,
                 on_source_key_changed: Optional[Callable] = None,
                 **kwargs):
        super().__init__(master, text="📊 ŹRÓDŁA DANYCH", padding=10, **kwargs)
        
        self.on_source_added = on_source_added
        self.on_source_removed = on_source_removed
        self.on_source_key_changed = on_source_key_changed
        
        self.sources: Dict[str, DataSource] = {}
        self.source_cards: Dict[str, SourceCard] = {}
        
        self._create_widgets()
    
    def _create_widgets(self):
        """Create all widgets."""
        # Add source button
        self.add_btn = ttk.Button(
            self, text="➕ Dodaj źródło...",
            command=self._add_source,
            style='Accent.TButton'
        )
        self.add_btn.pack(fill=tk.X, pady=(0, 10))
        ToolTip(self.add_btn, "Dodaj plik źródłowy z danymi do połączenia (Ctrl+Shift+O)")
        
        # Scrollable frame for source cards
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(self.canvas_frame, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        
        self.cards_frame = ttk.Frame(self.canvas)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor='nw')
        
        self.cards_frame.bind('<Configure>', self._on_frame_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        # Empty state label
        self.empty_label = ttk.Label(
            self.cards_frame, 
            text="Brak źródeł danych.\nKliknij '+ Dodaj źródło' aby dodać.",
            foreground='gray',
            justify=tk.CENTER
        )
        self.empty_label.pack(pady=20)
    
    def _on_frame_configure(self, event):
        """Handle frame resize."""
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
    
    def _on_canvas_configure(self, event):
        """Handle canvas resize."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def _add_source(self):
        """Open file dialog and add source."""
        filetypes = [
            ("Pliki Excel", "*.xlsx *.xls *.xlsm *.xlsb"),
            ("Pliki CSV", "*.csv *.tsv *.txt"),
            ("Wszystkie pliki", "*.*")
        ]
        
        filepaths = filedialog.askopenfilenames(
            title="Wybierz pliki źródłowe",
            filetypes=filetypes
        )
        
        for filepath in filepaths:
            self._add_source_threaded(filepath)
    
    def _add_source_threaded(self, filepath: str, sheet: Optional[str] = None,
                              key_column: Optional[str] = None):
        """Add source in background thread with loading indicator."""
        # Show loading state
        self.add_btn.config(state='disabled', text="⏳ Wczytywanie...")
        
        import threading
        
        def load_task():
            try:
                source = DataSource(filepath=filepath)
                source.load(sheet)
                
                # Auto-detect key column
                if not key_column:
                    columns = source.get_columns()
                    detected_key = detect_key_column(columns, source.dataframe)
                else:
                    detected_key = key_column
                    
                if detected_key:
                    source.set_key_column(detected_key)
                
                return (source, None)
            except Exception as e:
                return (None, str(e))
        
        def on_complete(result):
            source, error = result
            
            # Restore button
            self.add_btn.config(state='normal', text="➕ Dodaj źródło...")
            
            if error:
                from tkinter import messagebox
                messagebox.showerror("Błąd", f"Nie można wczytać źródła:\n{error}")
                return
            
            # Add to sources
            self.sources[source.id] = source
            
            # Create card
            self._create_source_card(source)
            
            # Hide empty label
            self.empty_label.pack_forget()
            
            # Notify callback
            if self.on_source_added:
                self.on_source_added(source)
        
        def thread_target():
            result = load_task()
            self.after(0, lambda: on_complete(result))
        
        threading.Thread(target=thread_target, daemon=True).start()
    
    def add_source_from_path(self, filepath: str, sheet: Optional[str] = None, 
                              key_column: Optional[str] = None) -> Optional[DataSource]:
        """Add a source from file path (public API - synchronous for session restore)."""
        try:
            source = DataSource(filepath=filepath)
            source.load(sheet)
            
            # Auto-detect key column if not specified
            if not key_column:
                columns = source.get_columns()
                key_column = detect_key_column(columns, source.dataframe)
            
            if key_column:
                source.set_key_column(key_column)
            
            # Add to sources
            self.sources[source.id] = source
            
            # Create card
            self._create_source_card(source)
            
            # Hide empty label
            self.empty_label.pack_forget()
            
            # Notify callback
            if self.on_source_added:
                self.on_source_added(source)
            
            return source
            
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("Błąd", f"Nie można wczytać źródła:\n{e}")
            return None
    
    def _create_source_card(self, source: DataSource):
        """Create a card widget for a source."""
        card = SourceCard(
            self.cards_frame,
            source,
            on_key_changed=self._on_source_key_changed,
            on_preview=self._on_source_preview,
            on_remove=self._on_source_remove
        )
        card.pack(fill=tk.X, pady=5, padx=5)
        self.source_cards[source.id] = card
    
    def _on_source_key_changed(self, source: DataSource):
        """Handle source key column change."""
        if self.on_source_key_changed:
            self.on_source_key_changed(source)
    
    def _on_source_preview(self, source: DataSource):
        """Show source preview dialog."""
        from gui.dialogs.source_preview import SourcePreviewDialog
        SourcePreviewDialog(
            self.winfo_toplevel(),
            source.dataframe,
            title=f"Podgląd: {source.filename}"
        )
    
    def _on_source_remove(self, source: DataSource):
        """Remove a source."""
        from tkinter import messagebox
        
        if not messagebox.askyesno(
            "Potwierdzenie",
            f"Czy na pewno usunąć źródło '{source.filename}'?\n"
            "Zostaną usunięte również powiązane mapowania."
        ):
            return
        
        # Remove card
        if source.id in self.source_cards:
            self.source_cards[source.id].destroy()
            del self.source_cards[source.id]
        
        # Remove source
        if source.id in self.sources:
            del self.sources[source.id]
        
        # Show empty label if no sources
        if not self.sources:
            self.empty_label.pack(pady=20)
        
        # Notify callback
        if self.on_source_removed:
            self.on_source_removed(source)
    
    def update_match_stats(self, base_keys: List[str]):
        """Update match statistics for all sources."""
        for source_id, source in self.sources.items():
            stats = source.calculate_match_stats(base_keys)
            if source_id in self.source_cards:
                self.source_cards[source_id].update_stats(
                    stats['matched'],
                    stats['total_base'],
                    stats.get('unmatched_keys', []),
                    base_keys
                )
    
    def get_sources(self) -> Dict[str, DataSource]:
        """Get all sources."""
        return self.sources
    
    def get_source(self, source_id: str) -> Optional[DataSource]:
        """Get a specific source."""
        return self.sources.get(source_id)
    
    def get_all_source_columns(self) -> Dict[str, List[str]]:
        """Get columns for all sources."""
        return {
            sid: s.get_columns() 
            for sid, s in self.sources.items()
        }
    
    def reset(self):
        """Reset panel to initial state."""
        # Remove all cards
        for card in self.source_cards.values():
            card.destroy()
        
        self.sources.clear()
        self.source_cards.clear()
        
        # Show empty label
        self.empty_label.pack(pady=20)
