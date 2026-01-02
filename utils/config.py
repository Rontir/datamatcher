"""
Config module - application configuration and settings.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime


def get_appdata_path() -> Path:
    """Get path to application data directory."""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    return Path(appdata) / 'DataMatcherPro'


def get_local_path() -> Path:
    """Get path to local application directory."""
    return Path(__file__).parent.parent


@dataclass
class Config:
    """Application configuration settings."""
    
    # Window settings
    window_width: int = 1400
    window_height: int = 900
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    
    # Theme
    theme: str = "cosmo"  # ttkbootstrap theme
    dark_mode: bool = False
    
    # Key normalization defaults
    case_insensitive: bool = False
    strip_leading_zeros: bool = False
    treat_empty_as_null: bool = True
    
    # Duplicate handling
    duplicate_strategy: str = "first"  # first, last, skip
    base_duplicate_fill_all: bool = True
    
    # Recent files
    recent_base_files: List[str] = field(default_factory=list)
    recent_source_files: List[str] = field(default_factory=list)
    recent_profiles: List[str] = field(default_factory=list)
    max_recent: int = 10
    
    # Profile storage
    profile_location: str = "both"  # appdata, local, both
    
    # Output defaults
    create_backup: bool = True
    preserve_formatting: bool = False
    output_suffix: str = "_matched"
    
    # Preview settings
    preview_rows: int = 100
    
    # Paths
    last_directory: str = ""
    
    @classmethod
    def load(cls) -> 'Config':
        """Load configuration from file."""
        config_path = get_appdata_path() / 'config.json'
        
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except Exception as e:
                print(f"Error loading config: {e}")
        
        return cls()
    
    def save(self) -> None:
        """Save configuration to file."""
        config_dir = get_appdata_path()
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_path = config_dir / 'config.json'
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
    
    def add_recent_base_file(self, filepath: str) -> None:
        """Add a file to recent base files."""
        if filepath in self.recent_base_files:
            self.recent_base_files.remove(filepath)
        self.recent_base_files.insert(0, filepath)
        self.recent_base_files = self.recent_base_files[:self.max_recent]
        self.save()
    
    def add_recent_source_file(self, filepath: str) -> None:
        """Add a file to recent source files."""
        if filepath in self.recent_source_files:
            self.recent_source_files.remove(filepath)
        self.recent_source_files.insert(0, filepath)
        self.recent_source_files = self.recent_source_files[:self.max_recent]
        self.save()
    
    def add_recent_profile(self, filepath: str) -> None:
        """Add a profile to recent profiles."""
        if filepath in self.recent_profiles:
            self.recent_profiles.remove(filepath)
        self.recent_profiles.insert(0, filepath)
        self.recent_profiles = self.recent_profiles[:self.max_recent]
        self.save()
    
    def get_profiles_directory(self) -> Path:
        """Get the directory for storing profiles."""
        if self.profile_location == "local":
            path = get_local_path() / 'profiles'
        else:
            path = get_appdata_path() / 'profiles'
        
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def get_all_profiles_directories(self) -> List[Path]:
        """Get all directories that may contain profiles."""
        dirs = []
        
        if self.profile_location in ["appdata", "both"]:
            appdata_profiles = get_appdata_path() / 'profiles'
            if appdata_profiles.exists():
                dirs.append(appdata_profiles)
        
        if self.profile_location in ["local", "both"]:
            local_profiles = get_local_path() / 'profiles'
            if local_profiles.exists():
                dirs.append(local_profiles)
        
        return dirs
    
    def get_key_options(self) -> Dict[str, Any]:
        """Get current key normalization options."""
        return {
            'case_insensitive': self.case_insensitive,
            'strip_leading_zeros': self.strip_leading_zeros,
            'treat_empty_as_null': self.treat_empty_as_null,
            'duplicate_strategy': self.duplicate_strategy
        }


@dataclass
class Profile:
    """Mapping profile for saving/loading configurations."""
    
    profile_name: str = ""
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    # Base file pattern
    base_file_pattern: str = ""
    base_sheet_pattern: str = ""
    base_key_column: str = ""
    base_key_options: Dict[str, Any] = field(default_factory=dict)
    
    # Sources
    sources: List[Dict[str, Any]] = field(default_factory=list)
    
    # Mappings
    mappings: List[Dict[str, Any]] = field(default_factory=list)
    
    # Output settings
    output_filename_pattern: str = ""
    preserve_formatting: bool = False
    create_backup: bool = True
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def save(self, filepath: str) -> None:
        """Save profile to file."""
        self.updated_at = datetime.now().isoformat()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load(cls, filepath: str) -> 'Profile':
        """Load profile from file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


def list_profiles(config: Config) -> List[Dict[str, Any]]:
    """List all available profiles."""
    profiles = []
    
    for directory in config.get_all_profiles_directories():
        for file in directory.glob('*.json'):
            try:
                profile = Profile.load(str(file))
                profiles.append({
                    'path': str(file),
                    'name': profile.profile_name,
                    'description': profile.description,
                    'updated_at': profile.updated_at,
                    'location': 'AppData' if 'AppData' in str(directory) else 'Local'
                })
            except Exception as e:
                print(f"Error loading profile {file}: {e}")
    
    # Sort by updated date
    profiles.sort(key=lambda p: p['updated_at'], reverse=True)
    
    return profiles
