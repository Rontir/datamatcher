"""
Data Source module - handles loading and managing source data files.
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

import pandas as pd

from utils.key_normalizer import normalize_key


@dataclass
class DataSource:
    """Represents a data source file with its key column and data."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    filepath: str = ""
    filename: str = ""
    sheet: Optional[str] = None
    key_column: str = ""
    dataframe: Optional[pd.DataFrame] = None
    key_options: Dict[str, Any] = field(default_factory=dict)
    
    # Computed after loading
    match_stats: Dict[str, int] = field(default_factory=dict)
    _key_lookup: Dict[str, Dict[str, Any]] = field(default_factory=dict, repr=False)
    
    def __post_init__(self):
        if self.filepath and not self.filename:
            self.filename = Path(self.filepath).name
    
    @classmethod
    def from_file(cls, filepath: str, sheet: Optional[str] = None, 
                  key_column: str = "", key_options: Optional[Dict] = None) -> 'DataSource':
        """Create a DataSource from a file path."""
        from utils.file_handlers import load_file
        
        source = cls(
            filepath=filepath,
            filename=Path(filepath).name,
            sheet=sheet,
            key_column=key_column,
            key_options=key_options or {}
        )
        
        df, sheets = load_file(filepath, sheet)
        source.dataframe = df
        
        if key_column:
            source.build_key_lookup()
        
        return source
    
    def load(self, sheet: Optional[str] = None) -> List[str]:
        """Load data from file, returns list of available sheets."""
        from utils.file_handlers import load_file
        
        df, sheets = load_file(self.filepath, sheet or self.sheet)
        self.dataframe = df
        if sheet:
            self.sheet = sheet
        
        return sheets
    
    def get_columns(self) -> List[str]:
        """Get list of column names."""
        if self.dataframe is None:
            return []
        return list(self.dataframe.columns)
    
    def get_row_count(self) -> int:
        """Get number of rows."""
        if self.dataframe is None:
            return 0
        return len(self.dataframe)
    
    def set_key_column(self, column: str):
        """Set the key column and rebuild lookup."""
        if column != self.key_column:  # Only rebuild if changed
            self.key_column = column
            self._auto_clean_key_column()
            self._key_lookup_built = False
            self.build_key_lookup()
    
    def _auto_clean_key_column(self):
        """Automatically clean key column if it contains .0 suffixes."""
        if self.dataframe is None or not self.key_column:
            return
            
        # Check if column is object/string type and has .0
        # We sample first 100 non-null values to be fast
        col_data = self.dataframe[self.key_column]
        sample = col_data.dropna().head(100).astype(str)
        
        if any(s.endswith('.0') for s in sample):
            # Apply fix to whole column
            # Convert to string and strip .0
            # This modifies the dataframe in place!
            self.dataframe[self.key_column] = col_data.astype(str).str.replace(r'\.0$', '', regex=True)
    
    def build_key_lookup(self, force: bool = False):
        """Build a dictionary mapping normalized keys to row data.
        Uses caching to avoid rebuilding if not needed.
        """
        if self.dataframe is None or not self.key_column:
            self._key_lookup = {}
            return
        
        # Check cache
        if hasattr(self, '_key_lookup_built') and self._key_lookup_built and not force:
            return
        
        self._key_lookup = {}
        duplicate_strategy = self.key_options.get('duplicate_strategy', 'first')
        
        # Optimized: use apply for faster key normalization
        key_series = self.dataframe[self.key_column]
        
        for idx, row in self.dataframe.iterrows():
            raw_key = row.get(self.key_column)
            normalized = normalize_key(raw_key, self.key_options)
            
            if normalized is None:
                continue  # Skip empty keys
            
            if normalized in self._key_lookup:
                if duplicate_strategy == 'first':
                    continue  # Keep first
                elif duplicate_strategy == 'last':
                    pass  # Will overwrite
                elif duplicate_strategy == 'skip':
                    self._key_lookup[normalized] = None  # Mark as conflict
                    continue
            
            self._key_lookup[normalized] = row.to_dict()
        
        self._key_lookup_built = True
    
    def get_key_lookup(self) -> Dict[str, Dict[str, Any]]:
        """Get the key lookup dictionary. Builds if not built yet."""
        if not self._key_lookup and self.key_column:
            self.build_key_lookup()
        return self._key_lookup
    
    def get_value_for_key(self, key: str, column: str) -> Any:
        """Get a specific column value for a given key."""
        normalized = normalize_key(key, self.key_options)
        if normalized in self._key_lookup:
            row_data = self._key_lookup[normalized]
            if row_data is not None:
                return row_data.get(column)
        return None
    
    def calculate_match_stats(self, base_keys: List[str]) -> Dict[str, Any]:
        """Calculate how many base keys match this source."""
        matched = 0
        unmatched = 0
        unmatched_keys = []
        
        for key in base_keys:
            normalized = normalize_key(key, self.key_options)
            if normalized in self._key_lookup and self._key_lookup[normalized] is not None:
                matched += 1
            else:
                unmatched += 1
                unmatched_keys.append(key)
        
        self.match_stats = {
            'matched': matched,
            'unmatched': unmatched,
            'unmatched_keys': unmatched_keys,
            'total_base': len(base_keys),
            'match_percent': (matched / len(base_keys) * 100) if base_keys else 0
        }
        return self.match_stats
    
    def get_unique_keys_count(self) -> int:
        """Get count of unique keys (excluding conflicts)."""
        return sum(1 for v in self._key_lookup.values() if v is not None)
    
    def get_duplicate_keys_count(self) -> int:
        """Get count of keys that appear more than once."""
        if self.dataframe is None or not self.key_column:
            return 0
        
        key_counts = self.dataframe[self.key_column].apply(
            lambda x: normalize_key(x, self.key_options)
        ).value_counts()
        
        return sum(1 for count in key_counts if count > 1)
    
    def get_empty_keys_count(self) -> int:
        """Get count of empty/null keys."""
        if self.dataframe is None or not self.key_column:
            return 0
        
        from utils.key_normalizer import is_empty
        return sum(1 for val in self.dataframe[self.key_column] if is_empty(val))
    
    def get_preview_data(self, rows: int = 100) -> pd.DataFrame:
        """Get first N rows for preview."""
        if self.dataframe is None:
            return pd.DataFrame()
        return self.dataframe.head(rows)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'filepath': self.filepath,
            'filename': self.filename,
            'sheet': self.sheet,
            'key_column': self.key_column,
            'key_options': self.key_options
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataSource':
        """Create from dictionary."""
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            filepath=data.get('filepath', ''),
            filename=data.get('filename', ''),
            sheet=data.get('sheet'),
            key_column=data.get('key_column', ''),
            key_options=data.get('key_options', {})
        )
