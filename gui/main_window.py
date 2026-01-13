"""
Main Window - The main application window for DataMatcher Pro.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from typing import Optional, List
from pathlib import Path
from datetime import datetime

# Try to import ttkbootstrap for modern theme
try:
    import ttkbootstrap as ttk_bs
    from ttkbootstrap.constants import *
    HAS_TTKBOOTSTRAP = True
except ImportError:
    HAS_TTKBOOTSTRAP = False

from gui.panels.base_file_panel import BaseFilePanel
from gui.panels.sources_panel import SourcesPanel
from gui.panels.mappings_panel import MappingsPanel
from gui.panels.preview_panel import PreviewPanel
from gui.dialogs.report_viewer import ReportViewerDialog
from gui.dialogs.mapping_editor import SmartMappingSuggestionDialog, get_all_column_suggestions

from core.data_source import DataSource
from core.matcher import DataMatcher
from core.reporter import Reporter
from core.mapping import ColumnMapping, WriteMode
from utils.config import Config, Profile, list_profiles
from utils.file_handlers import save_excel, create_backup
from utils.session import SessionManager, BatchFilter


class MainApplication:
    """Main application class for DataMatcher Pro."""
    
    def __init__(self):
        self.config = Config.load()
        
        # Create root window
        if HAS_TTKBOOTSTRAP:
            self.root = ttk_bs.Window(
                title="DataMatcher Pro",
                themename=self.config.theme if self.config.theme else "cosmo",
                size=(self.config.window_width, self.config.window_height)
            )
        else:
            self.root = tk.Tk()
            self.root.title("DataMatcher Pro")
            self.root.geometry(f"{self.config.window_width}x{self.config.window_height}")
        
        self.root.minsize(1200, 800)
        
        # Restore window position
        if self.config.window_x and self.config.window_y:
            self.root.geometry(f"+{self.config.window_x}+{self.config.window_y}")
        
        # Data matcher engine
        self.matcher = DataMatcher()
        
        # Current result
        self.current_result = None
        
        # Setup UI
        self._create_menu()
        self._create_main_layout()
        self._create_status_bar()
        self._bind_shortcuts()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _create_menu(self):
        """Create menu bar."""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        # File menu
        file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Plik", menu=file_menu)
        
        file_menu.add_command(label="Wczytaj plik bazowy...", command=self._load_base_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Dodaj źródło...", command=self._add_source, accelerator="Ctrl+Shift+O")
        file_menu.add_separator()
        file_menu.add_command(label="Zapisz wynik...", command=self._save_result, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Wyjście", command=self._on_close)
        
        # Profile menu
        profile_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Profil", menu=profile_menu)
        
        profile_menu.add_command(label="Zapisz profil...", command=self._save_profile, accelerator="Ctrl+Shift+S")
        profile_menu.add_command(label="Wczytaj profil...", command=self._load_profile, accelerator="Ctrl+L")
        profile_menu.add_separator()
        
        # Recent profiles submenu
        self.recent_menu = tk.Menu(profile_menu, tearoff=0)
        profile_menu.add_cascade(label="Ostatnio używane", menu=self.recent_menu)
        self._update_recent_profiles_menu()
        
        # Tools menu
        tools_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Narzędzia", menu=tools_menu)
        
        tools_menu.add_command(label="Odśwież podgląd", command=self._execute_preview, accelerator="F5")
        tools_menu.add_command(label="Cofnij mapowanie", command=self._undo_mapping, accelerator="Ctrl+Z")
        tools_menu.add_separator()
        tools_menu.add_command(label="Filtr przetwarzania...", command=self._show_batch_filter)
        tools_menu.add_separator()
        tools_menu.add_command(label="Zapisz sesję", command=self._save_session)
        tools_menu.add_command(label="Wczytaj ostatnią sesję", command=self._load_last_session)
        tools_menu.add_command(label="Nowa sesja", command=self._new_session)
        
        # Settings submenu
        settings_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Ustawienia", menu=settings_menu)
        
        self.backup_var = tk.BooleanVar(value=self.config.create_backup)
        settings_menu.add_checkbutton(label="Twórz kopię zapasową", variable=self.backup_var)
        
        self.case_insensitive_var = tk.BooleanVar(value=self.config.case_insensitive)
        settings_menu.add_checkbutton(
            label="Ignoruj wielkość liter", 
            variable=self.case_insensitive_var,
            command=self._on_settings_changed
        )
        
        self.strip_zeros_var = tk.BooleanVar(value=self.config.strip_leading_zeros)
        settings_menu.add_checkbutton(
            label="Usuń zera wiodące", 
            variable=self.strip_zeros_var,
            command=self._on_settings_changed
        )
        
        self.strip_decimal_var = tk.BooleanVar(value=True)  # Default ON - common issue
        settings_menu.add_checkbutton(
            label="Normalizuj do liczby całkowitej (usuń .0)", 
            variable=self.strip_decimal_var,
            command=self._on_settings_changed
        )
        
        settings_menu.add_separator()
        
        self.normalize_paths_var = tk.BooleanVar(value=False)  # Default OFF - specialized use
        settings_menu.add_checkbutton(
            label="🗂️ Tryb struktur/kategorii (normalizuj ścieżki)", 
            variable=self.normalize_paths_var,
            command=self._on_settings_changed
        )
        
        settings_menu.add_separator()
        
        # FUZZY MATCHING - Better than VLOOKUP!
        self.fuzzy_matching_var = tk.BooleanVar(value=False)  # Default OFF
        settings_menu.add_checkbutton(
            label="🔍 Dopasowanie przybliżone (fuzzy matching)", 
            variable=self.fuzzy_matching_var,
            command=self._on_settings_changed
        )
        
        # Fuzzy threshold slider would be nice but for now use 0.85 default
        
        # Theme submenu (if ttkbootstrap available)
        if HAS_TTKBOOTSTRAP:
            theme_menu = tk.Menu(tools_menu, tearoff=0)
            tools_menu.add_cascade(label="Motyw", menu=theme_menu)
            
            themes = ['cosmo', 'flatly', 'journal', 'litera', 'lumen', 'minty', 
                      'pulse', 'sandstone', 'united', 'yeti', 'darkly', 'cyborg', 
                      'superhero', 'solar', 'vapor']
            
            for theme in themes:
                theme_menu.add_command(
                    label=theme.capitalize(),
                    command=lambda t=theme: self._change_theme(t)
                )
        
        # Help menu
        help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Pomoc", menu=help_menu)
        
        help_menu.add_command(label="O programie...", command=self._show_about)
    
    def _create_main_layout(self):
        """Create main layout with panels."""
        # Main container
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Top section (base file + sources) - fixed height
        top_frame = ttk.Frame(self.main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Base file panel (left)
        self.base_panel = BaseFilePanel(
            top_frame,
            on_file_loaded=self._on_base_loaded,
            on_key_changed=self._on_base_key_changed
        )
        self.base_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Sources panel (right)
        self.sources_panel = SourcesPanel(
            top_frame,
            on_source_added=self._on_source_added,
            on_source_removed=self._on_source_removed,
            on_source_key_changed=self._on_source_key_changed
        )
        self.sources_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # === RESIZABLE PANED WINDOW for mappings and preview ===
        self.paned = ttk.PanedWindow(self.main_frame, orient=tk.VERTICAL)
        self.paned.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Middle section (mappings) - in paned window
        self.mappings_panel = MappingsPanel(
            self.paned,
            on_mapping_changed=self._on_mapping_changed
        )
        self.paned.add(self.mappings_panel, weight=1)
        
        # Bottom section (preview) - in paned window, gets more weight
        self.preview_panel = PreviewPanel(self.paned)
        self.paned.add(self.preview_panel, weight=3)
        self.preview_panel.set_refresh_callback(self._execute_preview)
        
        # Action buttons
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            btn_frame, text="📋 Eksport raportu",
            command=self._export_report,
            width=20
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            btn_frame, text="❌ Nowa sesja",
            command=self._new_session,
            width=15
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        # Save button (initially disabled)
        if HAS_TTKBOOTSTRAP:
            self.save_btn = ttk.Button(
                btn_frame, text="💾 ZAPISZ WYNIK",
                command=self._save_result,
                width=20,
                bootstyle="success",
                state='disabled'
            )
        else:
            self.save_btn = ttk.Button(
                btn_frame, text="💾 ZAPISZ WYNIK",
                command=self._save_result,
                width=20,
                state='disabled'
            )
        self.save_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # Execute button
        if HAS_TTKBOOTSTRAP:
            self.execute_btn = ttk.Button(
                btn_frame, text="▶ WYKONAJ (PODGLĄD)",
                command=self._execute_preview,
                width=25,
                bootstyle="primary"
            )
        else:
            self.execute_btn = ttk.Button(
                btn_frame, text="▶ WYKONAJ (PODGLĄD)",
                command=self._execute_preview,
                width=25
            )
        self.execute_btn.pack(side=tk.RIGHT)
    
    def _create_status_bar(self):
        """Create status bar at bottom."""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.status_label = ttk.Label(
            self.status_frame, 
            text="Gotowy",
            padding=(10, 5)
        )
        self.status_label.pack(side=tk.LEFT)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.status_frame,
            variable=self.progress_var,
            maximum=100,
            length=200
        )
        self.progress_bar.pack(side=tk.RIGHT, padx=10, pady=5)
    
    def _bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        self.root.bind('<Control-o>', lambda e: self._load_base_file())
        self.root.bind('<Control-O>', lambda e: self._add_source())
        self.root.bind('<Control-s>', lambda e: self._save_result())
        self.root.bind('<Control-S>', lambda e: self._save_profile())
        self.root.bind('<Control-l>', lambda e: self._load_profile())
        self.root.bind('<Control-z>', lambda e: self._undo_mapping())
        self.root.bind('<F5>', lambda e: self._execute_preview())
    
    def _set_status(self, message: str):
        """Update status bar message."""
        self.status_label.config(text=message)
        self.root.update_idletasks()
    
    def _set_progress(self, value: float):
        """Update progress bar."""
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    # Event handlers
    def _on_base_loaded(self, source: DataSource):
        """Handle base file loaded."""
        self.matcher.set_base_source(source)
        self._update_mappings_options()
        self._set_status(f"Wczytano: {source.filename}")
        self.config.add_recent_base_file(source.filepath)
        
        # Check for profile match
        self._check_profile_match(source.filename)
    
    def _check_profile_match(self, filename: str):
        """Check if a profile matches the filename and suggest loading it."""
        profile_path = self.config.match_profile(filename)
        if profile_path:
            if messagebox.askyesno(
                "Wykryto profil",
                f"Wykryto pasujący profil dla pliku '{filename}'.\n"
                f"Czy chcesz wczytać profil '{Path(profile_path).stem}'?"
            ):
                self._load_profile_from_path(profile_path)
    
    def _on_base_key_changed(self, source: DataSource):
        """Handle base key column changed."""
        self._update_match_stats()
        self._set_status("Zmieniono klucz - kliknij 'Sugestie' lub 'Generuj podgląd'")
    
    def _on_source_added(self, source: DataSource):
        """Handle source added."""
        self.matcher.add_source(source)
        self._update_mappings_options()
        self._update_match_stats()
        self._set_status(f"Dodano źródło: {source.filename} - Kliknij 'Sugestie' aby dodać mapowania")
        self.config.add_recent_source_file(source.filepath)
        # User will click "Sugestie" manually when ready
    
    def _auto_suggest_mappings(self, source: DataSource):
        """Automatically suggest mappings for new source."""
        target_cols = self.matcher.base_source.get_columns()
        source_cols = source.get_columns()
        
        suggestions = get_all_column_suggestions(source_cols, target_cols)
        
        # Count high confidence matches
        high_conf = sum(1 for s in suggestions if s['confidence'] == 'high')
        
        if high_conf > 0:
            # Show dialog
            dialog = SmartMappingSuggestionDialog(
                self.root,
                source_name=source.filename,
                source_columns=source_cols,
                target_columns=target_cols
            )
            
            if dialog.result:
                for sug in dialog.result:
                    mapping = ColumnMapping(
                        source_id=source.id,
                        source_name=source.filename,
                        source_column=sug['source_column'],
                        target_column=sug['target_column'],
                        target_is_new=sug['target_is_new'],
                        write_mode=WriteMode.OVERWRITE
                    )
                    self.matcher.mapping_manager.add(mapping)
                
                self.mappings_panel._refresh_tree()
                self._execute_preview()
    
    def _on_source_removed(self, source: DataSource):
        """Handle source removed."""
        self.matcher.remove_source(source.id)
        self._update_mappings_options()
        self._set_status(f"Usunięto źródło: {source.filename}")
    
    def _on_source_key_changed(self, source: DataSource):
        """Handle source key changed."""
        self._update_match_stats()
        self._execute_preview()
    
    def _on_mapping_changed(self, mapping_manager):
        """Handle mapping changed - sync to DataMatcher."""
        # Sync mappings from panel to matcher
        self.matcher.mapping_manager = mapping_manager
        # Don't auto-execute preview to prevent lag
        self._set_status("Mapowania zmienione - kliknij 'Podgląd danych' aby odświeżyć wyniki")
    
    def _update_mappings_options(self):
        """Update available options in mappings panel."""
        sources = {s.id: s.filename for s in self.matcher.data_sources.values()}
        source_columns = {s.id: s.get_columns() for s in self.matcher.data_sources.values()}
        
        self.mappings_panel.set_sources(sources, source_columns)
        
        if self.matcher.base_source:
            self.mappings_panel.set_target_columns(self.matcher.base_source.get_columns())
    
    def _on_settings_changed(self):
        """Handle settings change (checkboxes)."""
        self._set_status("Aktualizowanie ustawień...")
        self.root.update_idletasks()
        
        # Update stats immediately
        self._update_match_stats()
        
        # If we have mappings, we might want to invalidate preview or auto-refresh?
        # For now, just update stats as that's what the user sees first.
        self._set_status("Zaktualizowano ustawienia. Odśwież podgląd (F5).")
    
    def _update_match_stats(self):
        """Update match statistics for all sources."""
        if not self.matcher.base_source or not self.matcher.base_source.key_column:
            return
        
        # Get current key_options from UI and propagate to sources
        key_options = {
            'case_insensitive': self.case_insensitive_var.get(),
            'strip_leading_zeros': self.strip_zeros_var.get(),
            'strip_decimal': self.strip_decimal_var.get(),
            'normalize_paths': self.normalize_paths_var.get()
        }
        
        # Update each source with current options and rebuild key_lookup
        for source in self.sources_panel.get_sources().values():
            source.key_options = key_options.copy()
            source.build_key_lookup(force=True)
        
        base_keys = list(self.matcher.base_source.dataframe[
            self.matcher.base_source.key_column
        ].dropna().astype(str))
        
        self.sources_panel.update_match_stats(base_keys)
    
    def _execute_preview(self):
        """Execute mappings and update preview (without saving)."""
        try:
            if not self._validate_ready():
                return
            
            # Disable buttons and show loading state
            self.execute_btn.config(state='disabled', text="⏳ Przetwarzanie...")
            self.save_btn.config(state='disabled')
            self.preview_panel.refresh_btn.config(state='disabled', text="⏳ Przetwarzanie...")
            
            self._set_status("Przetwarzanie... Proszę czekać")
            self._set_progress(0)
            self.root.update_idletasks()  # Force immediate UI update
            
            # Apply current key options
            self.matcher.key_options = {
                'case_insensitive': self.case_insensitive_var.get(),
                'strip_leading_zeros': self.strip_zeros_var.get(),
                'strip_decimal': self.strip_decimal_var.get(),
                'normalize_paths': self.normalize_paths_var.get(),
                'fuzzy_threshold': 0.85 if self.fuzzy_matching_var.get() else 1.0  # Better than VLOOKUP!
            }
            
            # Apply batch filter if set
            batch_filter = getattr(self, 'batch_filter', None)
            self.matcher.batch_filter = batch_filter
            
            # Set up progress callback
            def progress_callback(current, total, message):
                percent = (current / total * 100) if total > 0 else 0
                
                def update_ui():
                    self._set_progress(percent)
                    self._set_status(f"Przetwarzanie: {current:,}/{total:,} wierszy ({percent:.0f}%)")
                
                # Schedule UI update on main thread
                self.root.after(0, update_ui)
            
            self.matcher.set_progress_callback(progress_callback)
            
            # Run in thread to prevent freezing
            def execute_thread():
                try:
                    result = self.matcher.execute()
                    
                    # Schedule UI update on main thread
                    self.root.after(0, lambda: self._on_execute_complete(result, batch_filter))
                    
                except Exception as e:
                    self.root.after(0, lambda: self._on_execute_error(str(e)))
            
            import threading
            thread = threading.Thread(target=execute_thread, daemon=True)
            thread.start()
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Błąd krytyczny", f"Nie można uruchomić podglądu:\n{e}")
            self._reset_buttons()
            self._set_status("Błąd uruchamiania")

    def _reset_buttons(self):
        """Reset buttons to normal state."""
        self.execute_btn.config(state='normal', text="▶ WYKONAJ (PODGLĄD)")
        self.save_btn.config(state='normal')
        self.preview_panel.refresh_btn.config(state='normal', text="▶ GENERUJ PODGLĄD (F5)")

    def _on_execute_complete(self, result, batch_filter):
        """Called when execution completes successfully."""
        self.current_result = result
        
        # Check for duplicate conflicts - SMART RESOLVER
        if hasattr(self.matcher, '_duplicate_conflicts') and self.matcher._duplicate_conflicts:
            from gui.dialogs.conflict_resolver import ConflictResolverDialog
            dialog = ConflictResolverDialog(self.root, self.matcher._duplicate_conflicts, result.result_df)
            self.root.wait_window(dialog)
            # After dialog, the result.result_df is updated
        
        self.preview_panel.set_preview_data(result.result_df, result.changes)
        self.preview_panel.update_stats(result.stats)
        
        # Build status message
        filter_info = ""
        if batch_filter and batch_filter.enabled:
            filter_info = f" [Filtr: {batch_filter.get_description()}]"
        
        # Show conflict info in status if any were resolved
        conflict_info = ""
        if hasattr(self.matcher, '_duplicate_conflicts') and self.matcher._duplicate_conflicts:
            conflict_info = f" ({len(self.matcher._duplicate_conflicts)} konfliktów rozwiązano)"
        
        self._set_status(f"Podgląd gotowy - sprawdź wyniki i zapisz{filter_info}{conflict_info}")
        self._set_progress(100)
        self._reset_buttons()
    
    def _on_execute_error(self, error_message):
        """Called when execution fails."""
        self._set_status(f"Błąd: {error_message}")
        self._set_progress(0)
        self._reset_buttons()
        messagebox.showerror("Błąd", f"Nie można wygenerować podglądu:\n{error_message}")
    
    def _save_result(self):
        """Save the current result to file."""
        if not self.current_result:
            messagebox.showwarning("Brak danych", "Najpierw wykonaj podgląd.")
            return
        
        # Ask for output file
        default_name = Path(self.matcher.base_source.filepath).stem + self.config.output_suffix + ".xlsx"
        
        filepath = filedialog.asksaveasfilename(
            title="Zapisz wynik jako",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=[
                ("Pliki Excel", "*.xlsx"),
                ("Wszystkie pliki", "*.*")
            ]
        )
        
        if not filepath:
            return
        
        try:
            self._set_status("Zapisywanie...")
            self._set_progress(0)
            
            # Create backup if enabled
            if self.backup_var.get() and Path(self.matcher.base_source.filepath).exists():
                backup_path = create_backup(self.matcher.base_source.filepath)
                self._set_status(f"Utworzono backup: {Path(backup_path).name}")
            
            # Save
            save_excel(self.current_result.result_df, filepath)
            
            self._set_progress(100)
            self._set_status(f"Zapisano: {Path(filepath).name}")
            
            # Show report
            self._show_execution_report(self.current_result, filepath)
            
        except Exception as e:
            self._set_status(f"Błąd zapisu: {e}")
            messagebox.showerror("Błąd", f"Nie można zapisać:\n{e}")
    
    def _validate_ready(self) -> bool:
        """Check if ready to execute."""
        if not self.matcher.base_source:
            messagebox.showwarning("Brak pliku bazowego", "Wczytaj najpierw plik bazowy.")
            return False
            
        if not self.matcher.base_source.key_column:
            messagebox.showwarning("Brak klucza", "Wybierz kolumnę klucza dla pliku bazowego.")
            return False
            
        if not self.matcher.data_sources:
            messagebox.showwarning("Brak źródeł", "Dodaj przynajmniej jedno źródło danych.")
            return False
            
        if not self.matcher.mapping_manager.mappings:
            messagebox.showwarning("Brak mapowań", "Zdefiniuj przynajmniej jedno mapowanie kolumn.")
            return False
            
        return True
    
    # Menu actions
    def _load_base_file(self):
        """Trigger base file load."""
        self.base_panel._load_file()
    
    def _add_source(self):
        """Trigger add source."""
        self.sources_panel._add_source()
    
    def _show_execution_report(self, result, output_filepath: str):
        """Show execution report dialog."""
        reporter = Reporter(result)
        
        # Gather info
        sources_info = []
        for s in self.matcher.data_sources.values():
            sources_info.append({
                'filename': s.filename,
                'key_column': s.key_column,
                'matched': s.match_stats.get('matched', 0),
                'total_base': s.match_stats.get('total_base', 0)
            })
        
        mappings_info = []
        for m in self.matcher.mapping_manager.mappings:
            # Count changes for this mapping
            changes = sum(1 for c in result.changes 
                          if c.mapping_id == m.id and 
                          c.change_type.value in ('new', 'changed'))
            mappings_info.append({
                'source_column': m.source_column,
                'target_column': m.target_column,
                'write_mode': m.write_mode.value,
                'cells_changed': changes
            })
        
        report_text = reporter.generate_summary(
            self.matcher.base_source.filename,
            self.matcher.base_source.key_column,
            sources_info,
            mappings_info
        )
        
        report_text += f"\n\nPLIK WYNIKOWY: {output_filepath}"
        
        ReportViewerDialog(self.root, report_text)
    
    def _export_report(self):
        """Export current report."""
        if not self.current_result:
            messagebox.showwarning("Brak danych", "Najpierw wygeneruj podgląd.")
            return
        
        # Generate and show report
        self._show_execution_report(self.current_result, "(podgląd)")
    
    def _save_profile(self):
        """Save current configuration as profile."""
        if not self.matcher.base_source:
            messagebox.showwarning("Brak danych", "Wczytaj plik bazowy przed zapisem profilu.")
            return
        
        # Ask for profile name
        from tkinter import simpledialog
        name = simpledialog.askstring(
            "Zapisz profil",
            "Nazwa profilu:",
            parent=self.root
        )
        
        if not name:
            return
        
        # Create profile
        profile = Profile(
            profile_name=name,
            base_key_column=self.matcher.base_source.key_column,
            base_key_options=self.matcher.key_options,
            sources=[s.to_dict() for s in self.matcher.data_sources.values()],
            mappings=self.matcher.mapping_manager.to_list()
        )
        
        # Save
        profiles_dir = self.config.get_profiles_directory()
        filepath = profiles_dir / f"{name.replace(' ', '_')}.json"
        
        profile.save(str(filepath))
        self.config.add_recent_profile(str(filepath))
        self._update_recent_profiles_menu()
        
        messagebox.showinfo("Zapisano", f"Profil zapisany:\n{filepath}")
    
    def _load_profile(self):
        """Load profile from file."""
        filetypes = [("Profile JSON", "*.json"), ("Wszystkie", "*.*")]
        
        # Start in profiles directory
        initial_dir = self.config.get_profiles_directory()
        
        filepath = filedialog.askopenfilename(
            title="Wczytaj profil",
            initialdir=initial_dir,
            filetypes=filetypes
        )
        
        if not filepath:
            return
        
        self._load_profile_from_path(filepath)
    
    def _load_profile_from_path(self, filepath: str):
        """Load profile from specified path."""
        try:
            profile = Profile.load(filepath)
            
            # Apply profile
            # Note: Files need to be loaded manually - profile stores patterns/columns
            self.matcher.key_options = profile.base_key_options
            self.case_insensitive_var.set(profile.base_key_options.get('case_insensitive', False))
            self.strip_zeros_var.set(profile.base_key_options.get('strip_leading_zeros', False))
            
            # Load mappings
            self.mappings_panel.load_mappings(profile.mappings)
            
            self.config.add_recent_profile(filepath)
            self._update_recent_profiles_menu()
            
            self._set_status(f"Wczytano profil: {profile.profile_name}")
            
            messagebox.showinfo(
                "Profil wczytany",
                f"Wczytano profil: {profile.profile_name}\n\n"
                "Uwaga: Wczytaj pliki źródłowe ręcznie."
            )
            
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można wczytać profilu:\n{e}")
    
    def _update_recent_profiles_menu(self):
        """Update recent profiles submenu."""
        self.recent_menu.delete(0, tk.END)
        
        for filepath in self.config.recent_profiles[:10]:
            name = Path(filepath).stem
            self.recent_menu.add_command(
                label=name,
                command=lambda p=filepath: self._load_profile_from_path(p)
            )
    
    def _undo_mapping(self):
        """Undo last mapping change."""
        self.mappings_panel._undo()
    
    def _new_session(self):
        """Start a new session."""
        if messagebox.askyesno(
            "Nowa sesja",
            "Czy na pewno chcesz rozpocząć nową sesję?\nWszystkie niezapisane zmiany zostaną utracone."
        ):
            self.matcher.clear()
            self.base_panel.reset()
            self.sources_panel.reset()
            self.mappings_panel.reset()
            self.preview_panel.clear()
            self.current_result = None
            self.save_btn.config(state='disabled')
            self._set_status("Nowa sesja")
    
    def _change_theme(self, theme: str):
        """Change application theme."""
        if HAS_TTKBOOTSTRAP:
            self.root.style.theme_use(theme)
            self.config.theme = theme
            self.config.save()
    
    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "O programie",
            "DataMatcher Pro\n\n"
            "Zaawansowane narzędzie do łączenia danych\n"
            "z plików Excel na podstawie kluczy.\n\n"
            "Wersja: 1.1.0\n"
            "© 2025"
        )
    
    def _save_session(self, silent: bool = False):
        """Save current session state."""
        if not self.matcher.base_source:
            if not silent:
                messagebox.showinfo("Brak danych", "Brak danych do zapisania.")
            return
        
        session_data = {
            'base_file': self.matcher.base_source.filepath,
            'base_key_column': self.matcher.base_source.key_column,
            'sources': [
                {
                    'filepath': s.filepath,
                    'key_column': s.key_column
                } for s in self.matcher.data_sources.values()
            ],
            'mappings': self.matcher.mapping_manager.to_list(),
            'key_options': self.matcher.key_options
        }
        
        if SessionManager.save_session(session_data):
            if not silent:
                messagebox.showinfo("Zapisano", "Sesja została zapisana.")
        else:
            if not silent:
                messagebox.showerror("Błąd", "Nie udało się zapisać sesji.")
    
    def _load_last_session(self):
        """Load last saved session."""
        session = SessionManager.load_session()
        
        if not session:
            messagebox.showinfo("Brak sesji", "Nie znaleziono zapisanej sesji.")
            return
        
        try:
            # Load base file
            base_path = session.get('base_file')
            if base_path and Path(base_path).exists():
                base_source = DataSource.from_file(
                    base_path,
                    key_column=session.get('base_key_column', '')
                )
                self.base_panel.set_source(base_source)
                self._on_base_loaded(base_source)
            
            # Load sources
            for src_data in session.get('sources', []):
                src_path = src_data.get('filepath')
                if src_path and Path(src_path).exists():
                    source = DataSource.from_file(
                        src_path,
                        key_column=src_data.get('key_column', '')
                    )
                    self.sources_panel.add_source(source)
                    self._on_source_added(source)
            
            # Load mappings
            self.mappings_panel.load_mappings(session.get('mappings', []))
            
            # Load key options
            self.matcher.key_options = session.get('key_options', {})
            
            self._set_status("Sesja wczytana")
            
        except Exception as e:
            messagebox.showerror("Błąd", f"Nie można wczytać sesji:\n{e}")
    
    def _show_batch_filter(self):
        """Show batch filter dialog."""
        from gui.dialogs.batch_filter import BatchFilterDialog
        
        # Get current filter or create new
        current_filter = getattr(self, 'batch_filter', None) or BatchFilter()
        
        dialog = BatchFilterDialog(self.root, current_filter)
        
        if dialog.result:
            self.batch_filter = dialog.result
            self._set_status(f"Filtr: {self.batch_filter.get_description()}")
    
    def _check_startup_session(self):
        """Check for saved session on startup."""
        info = SessionManager.get_session_info()
        if info:
            from gui.dialogs.batch_filter import LastSessionDialog
            dialog = LastSessionDialog(self.root, info)
            if dialog.result == "load":
                self._load_last_session()
    
    def _on_close(self):
        """Handle window close."""
        # Auto-save session
        self._save_session(silent=True)
        
        # Save window position
        self.config.window_width = self.root.winfo_width()
        self.config.window_height = self.root.winfo_height()
        self.config.window_x = self.root.winfo_x()
        self.config.window_y = self.root.winfo_y()
        self.config.create_backup = self.backup_var.get()
        self.config.case_insensitive = self.case_insensitive_var.get()
        self.config.strip_leading_zeros = self.strip_zeros_var.get()
        self.config.save()
        
        self.root.destroy()
    
    def run(self):
        """Start the application."""
        self.root.mainloop()
