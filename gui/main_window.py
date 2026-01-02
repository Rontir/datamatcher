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

from core.data_source import DataSource
from core.matcher import DataMatcher
from core.reporter import Reporter
from utils.config import Config, Profile, list_profiles
from utils.file_handlers import save_excel, create_backup


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
        file_menu.add_command(label="Wykonaj i zapisz...", command=self._execute_and_save, accelerator="Ctrl+S")
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
        
        tools_menu.add_command(label="Odśwież podgląd", command=self._refresh_preview, accelerator="F5")
        tools_menu.add_command(label="Cofnij mapowanie", command=self._undo_mapping, accelerator="Ctrl+Z")
        tools_menu.add_separator()
        tools_menu.add_command(label="Nowa sesja", command=self._new_session)
        
        # Settings submenu
        settings_menu = tk.Menu(tools_menu, tearoff=0)
        tools_menu.add_cascade(label="Ustawienia", menu=settings_menu)
        
        self.backup_var = tk.BooleanVar(value=self.config.create_backup)
        settings_menu.add_checkbutton(label="Twórz kopię zapasową", variable=self.backup_var)
        
        self.case_insensitive_var = tk.BooleanVar(value=self.config.case_insensitive)
        settings_menu.add_checkbutton(label="Ignoruj wielkość liter", variable=self.case_insensitive_var)
        
        self.strip_zeros_var = tk.BooleanVar(value=self.config.strip_leading_zeros)
        settings_menu.add_checkbutton(label="Usuń zera wiodące", variable=self.strip_zeros_var)
        
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
        
        # Top section (base file + sources)
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
        
        # Middle section (mappings)
        self.mappings_panel = MappingsPanel(
            self.main_frame,
            on_mapping_changed=self._on_mapping_changed
        )
        self.mappings_panel.pack(fill=tk.X, pady=(0, 10))
        
        # Bottom section (preview)
        self.preview_panel = PreviewPanel(self.main_frame)
        self.preview_panel.pack(fill=tk.BOTH, expand=True)
        self.preview_panel.set_refresh_callback(self._refresh_preview)
        
        # Action buttons
        btn_frame = ttk.Frame(self.main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(
            btn_frame, text="📋 Eksport raportu",
            command=self._export_report,
            width=20
        ).pack(side=tk.LEFT)
        
        ttk.Button(
            btn_frame, text="❌ Anuluj",
            command=self._new_session,
            width=15
        ).pack(side=tk.RIGHT, padx=(10, 0))
        
        if HAS_TTKBOOTSTRAP:
            self.execute_btn = ttk.Button(
                btn_frame, text="✅ WYKONAJ I ZAPISZ",
                command=self._execute_and_save,
                width=25,
                bootstyle="success"
            )
        else:
            self.execute_btn = ttk.Button(
                btn_frame, text="✅ WYKONAJ I ZAPISZ",
                command=self._execute_and_save,
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
        self.root.bind('<Control-s>', lambda e: self._execute_and_save())
        self.root.bind('<Control-S>', lambda e: self._save_profile())
        self.root.bind('<Control-l>', lambda e: self._load_profile())
        self.root.bind('<Control-z>', lambda e: self._undo_mapping())
        self.root.bind('<F5>', lambda e: self._refresh_preview())
    
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
    
    def _on_base_key_changed(self, source: DataSource):
        """Handle base key column changed."""
        self._update_match_stats()
        self._refresh_preview()
    
    def _on_source_added(self, source: DataSource):
        """Handle source added."""
        self.matcher.add_source(source)
        self._update_mappings_options()
        self._update_match_stats()
        self._set_status(f"Dodano źródło: {source.filename}")
        self.config.add_recent_source_file(source.filepath)
    
    def _on_source_removed(self, source: DataSource):
        """Handle source removed."""
        self.matcher.remove_source(source.id)
        self._update_mappings_options()
        self._set_status(f"Usunięto źródło: {source.filename}")
    
    def _on_source_key_changed(self, source: DataSource):
        """Handle source key changed."""
        self._update_match_stats()
        self._refresh_preview()
    
    def _on_mapping_changed(self, mapping_manager):
        """Handle mapping changed - sync to DataMatcher."""
        # Sync mappings from panel to matcher
        self.matcher.mapping_manager = mapping_manager
        self._refresh_preview()

    
    def _update_mappings_options(self):
        """Update available options in mappings panel."""
        sources = {s.id: s.filename for s in self.matcher.data_sources.values()}
        source_columns = {s.id: s.get_columns() for s in self.matcher.data_sources.values()}
        
        self.mappings_panel.set_sources(sources, source_columns)
        
        if self.matcher.base_source:
            self.mappings_panel.set_target_columns(self.matcher.base_source.get_columns())
    
    def _update_match_stats(self):
        """Update match statistics for all sources."""
        if not self.matcher.base_source or not self.matcher.base_source.key_column:
            return
        
        base_keys = list(self.matcher.base_source.dataframe[
            self.matcher.base_source.key_column
        ].dropna().astype(str))
        
        self.sources_panel.update_match_stats(base_keys)
    
    def _refresh_preview(self):
        """Refresh the preview panel."""
        if not self._validate_ready():
            return
        
        try:
            self._set_status("Generowanie podglądu...")
            
            # Apply current key options
            self.matcher.key_options = {
                'case_insensitive': self.case_insensitive_var.get(),
                'strip_leading_zeros': self.strip_zeros_var.get()
            }
            
            result = self.matcher.execute()
            self.current_result = result
            
            self.preview_panel.set_preview_data(result.result_df, result.changes)
            self.preview_panel.update_stats(result.stats)
            
            self._set_status("Podgląd gotowy")
            
        except Exception as e:
            self._set_status(f"Błąd: {e}")
            messagebox.showerror("Błąd", f"Nie można wygenerować podglądu:\n{e}")
    
    def _validate_ready(self) -> bool:
        """Check if ready to execute."""
        if not self.matcher.base_source:
            return False
        if not self.matcher.base_source.key_column:
            return False
        if not self.matcher.data_sources:
            return False
        if not self.matcher.mapping_manager.mappings:
            return False
        return True
    
    # Menu actions
    def _load_base_file(self):
        """Trigger base file load."""
        self.base_panel._load_file()
    
    def _add_source(self):
        """Trigger add source."""
        self.sources_panel._add_source()
    
    def _execute_and_save(self):
        """Execute mappings and save result."""
        if not self._validate_ready():
            messagebox.showwarning(
                "Brak danych",
                "Wczytaj plik bazowy, dodaj źródła i zdefiniuj mapowania."
            )
            return
        
        # Ask for output file
        default_name = Path(self.matcher.base_source.filepath).stem + "_matched.xlsx"
        
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
            self._set_status("Wykonywanie...")
            self._set_progress(0)
            
            # Create backup if enabled
            if self.backup_var.get() and Path(self.matcher.base_source.filepath).exists():
                backup_path = create_backup(self.matcher.base_source.filepath)
                self._set_status(f"Utworzono backup: {Path(backup_path).name}")
            
            # Execute
            self.matcher.set_progress_callback(
                lambda cur, tot, msg: (
                    self._set_status(msg),
                    self._set_progress(cur / tot * 100 if tot > 0 else 0)
                )
            )
            
            result = self.matcher.execute()
            self.current_result = result
            
            # Save
            save_excel(result.result_df, filepath)
            
            self._set_progress(100)
            self._set_status(f"Zapisano: {Path(filepath).name}")
            
            # Show report
            self._show_execution_report(result, filepath)
            
        except Exception as e:
            self._set_status(f"Błąd: {e}")
            messagebox.showerror("Błąd", f"Nie można wykonać:\n{e}")
    
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
            "Wersja: 1.0.0\n"
            "© 2025"
        )
    
    def _on_close(self):
        """Handle window close."""
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
