"""
Session Manager - Save and restore application sessions.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime


def get_session_path() -> Path:
    """Get path to session file."""
    import os
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    return Path(appdata) / 'DataMatcherPro' / 'last_session.json'


class SessionManager:
    """
    Manages saving and restoring application sessions.
    Stores: base file, sources, mappings, key columns, options.
    """
    
    @staticmethod
    def save_session(session_data: Dict[str, Any]) -> bool:
        """
        Save current session to file.
        
        session_data should contain:
        - base_file: str (path)
        - base_key_column: str
        - sources: List[Dict] (filepath, key_column)
        - mappings: List[Dict]
        - key_options: Dict
        - saved_at: str (auto-added)
        """
        try:
            session_path = get_session_path()
            session_path.parent.mkdir(parents=True, exist_ok=True)
            
            session_data['saved_at'] = datetime.now().isoformat()
            
            with open(session_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error saving session: {e}")
            return False
    
    @staticmethod
    def load_session() -> Optional[Dict[str, Any]]:
        """Load last session from file. Returns None if no session exists."""
        try:
            session_path = get_session_path()
            
            if not session_path.exists():
                return None
            
            with open(session_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading session: {e}")
            return None
    
    @staticmethod
    def has_session() -> bool:
        """Check if a saved session exists."""
        return get_session_path().exists()
    
    @staticmethod
    def get_session_info() -> Optional[Dict[str, str]]:
        """Get brief info about saved session (for display)."""
        session = SessionManager.load_session()
        if not session:
            return None
        
        base_file = session.get('base_file', '')
        sources_count = len(session.get('sources', []))
        mappings_count = len(session.get('mappings', []))
        saved_at = session.get('saved_at', '')
        
        return {
            'base_file': Path(base_file).name if base_file else 'Brak',
            'sources_count': str(sources_count),
            'mappings_count': str(mappings_count),
            'saved_at': saved_at[:16].replace('T', ' ') if saved_at else 'Nieznana'
        }
    
    @staticmethod
    def clear_session() -> bool:
        """Clear saved session."""
        try:
            session_path = get_session_path()
            if session_path.exists():
                session_path.unlink()
            return True
        except Exception:
            return False


class BatchFilter:
    """
    Filter for selecting which rows/keys to process.
    """
    
    def __init__(self):
        self.enabled = False
        self.mode = "all"  # "all", "range", "list", "limit"
        
        # Range mode
        self.start_index = 0
        self.end_index = -1  # -1 = all
        
        # List mode
        self.key_list: List[str] = []
        
        # Limit mode
        self.limit = 0  # 0 = no limit
        
        # Pattern mode
        self.key_pattern = ""  # regex pattern for keys
    
    def should_process_row(self, index: int, key: str) -> bool:
        """Check if a row should be processed."""
        if not self.enabled:
            return True
        
        if self.mode == "range":
            if self.start_index > 0 and index < self.start_index:
                return False
            if self.end_index > 0 and index > self.end_index:
                return False
            return True
        
        elif self.mode == "list":
            return str(key) in self.key_list
        
        elif self.mode == "limit":
            return index < self.limit
        
        elif self.mode == "pattern":
            import re
            try:
                return bool(re.search(self.key_pattern, str(key), re.IGNORECASE))
            except re.error:
                return True
        
        return True
    
    def get_description(self) -> str:
        """Get human-readable description of filter."""
        if not self.enabled:
            return "Wszystkie wiersze"
        
        if self.mode == "range":
            return f"Wiersze {self.start_index} - {self.end_index if self.end_index > 0 else 'koniec'}"
        elif self.mode == "list":
            return f"Lista {len(self.key_list)} kluczy"
        elif self.mode == "limit":
            return f"Pierwsze {self.limit} wierszy"
        elif self.mode == "pattern":
            return f"Wzorzec: {self.key_pattern}"
        
        return "Wszystkie"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'mode': self.mode,
            'start_index': self.start_index,
            'end_index': self.end_index,
            'key_list': self.key_list,
            'limit': self.limit,
            'key_pattern': self.key_pattern
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BatchFilter':
        bf = cls()
        bf.enabled = data.get('enabled', False)
        bf.mode = data.get('mode', 'all')
        bf.start_index = data.get('start_index', 0)
        bf.end_index = data.get('end_index', -1)
        bf.key_list = data.get('key_list', [])
        bf.limit = data.get('limit', 0)
        bf.key_pattern = data.get('key_pattern', '')
        return bf
