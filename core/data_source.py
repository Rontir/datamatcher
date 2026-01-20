"""
Data Source module - handles loading and managing source data files.
"""
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
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
            
        col_data = self.dataframe[self.key_column]
        
        # If float, convert to nullable int then string (safest way to remove .0)
        import pandas as pd
        import numpy as np
        
        if pd.api.types.is_float_dtype(col_data):
            # Convert to Int64 (nullable int) to handle NaNs correctly
            # Then to string. This automatically removes .0
            try:
                # Round first to be safe? No, user wants integer matching.
                # But if it's 123.9, maybe they want 123 or 124? 
                # Usually it's 123.0.
                self.dataframe[self.key_column] = col_data.astype('Int64').astype(str).replace('<NA>', 'nan')
                return
            except Exception:
                # Fallback if conversion fails
                pass

        # If object/string, check for .0 suffix
        # Check entire column (vectorized is fast)
        s_data = col_data.astype(str)
        if s_data.str.endswith('.0').any():
            self.dataframe[self.key_column] = s_data.str.replace(r'\.0$', '', regex=True)
    
    def build_key_lookup(self, force: bool = False):
        """Build a dictionary mapping normalized keys to row data.
        
        SMART DUPLICATE HANDLING:
        - Stores ALL rows for each key (not just first/last)
        - During matching, the best row is selected based on target column availability
        - This is BETTER than VLOOKUP which only takes the first match
        """
        if self.dataframe is None or not self.key_column:
            self._key_lookup = {}
            return
        
        # Check cache
        if hasattr(self, '_key_lookup_built') and self._key_lookup_built and not force:
            return
        
        self._key_lookup = {}
        self._key_all_rows = {}  # NEW: Store ALL rows for each key
        self._key_stripped_fallback = {}  # NEW: Map stripped keys -> list of actual keys
        
        strip_zeros_enabled = self.key_options.get('strip_leading_zeros', False)
        
        for idx, row in self.dataframe.iterrows():
            raw_key = row.get(self.key_column)
            normalized = normalize_key(raw_key, self.key_options)
            
            if normalized is None:
                continue  # Skip empty keys
            
            row_dict = row.to_dict()
            
            # Store in all_rows list
            if normalized not in self._key_all_rows:
                self._key_all_rows[normalized] = []
            self._key_all_rows[normalized].append(row_dict)
            
            # For backward compatibility, _key_lookup stores first row
            if normalized not in self._key_lookup:
                self._key_lookup[normalized] = row_dict
            
            # Populate stripped fallback if needed
            # (If strip_zeros is already ON, we don't need this as normalized key is already stripped)
            if not strip_zeros_enabled and normalized:
                # Force strip zeros for the fallback key
                stripped_key = normalized.lstrip('0')
                if not stripped_key: stripped_key = '0'
                
                if stripped_key not in self._key_stripped_fallback:
                    self._key_stripped_fallback[stripped_key] = set()
                self._key_stripped_fallback[stripped_key].add(normalized)
        
        self._key_lookup_built = True
    
    def get_all_rows_for_key(self, key: str) -> List[Dict[str, Any]]:
        """Get ALL rows matching a key (for smart duplicate handling).
        
        Returns:
            List of row dictionaries, or empty list if no match
        """
        if not hasattr(self, '_key_all_rows'):
            return []
        normalized = normalize_key(key, self.key_options)
        
        # Try exact match first
        if normalized in self._key_all_rows:
            return self._key_all_rows[normalized]
            
        # Try fallback: matches differing only by leading zeros
        # Only if strict stripping is OFF (otherwise normalized is already stripped)
        if hasattr(self, '_key_stripped_fallback') and not self.key_options.get('strip_leading_zeros', False) and normalized:
            stripped = normalized.lstrip('0')
            if not stripped: stripped = '0'
            
            if stripped in self._key_stripped_fallback:
                # Found keys that match when stripped!
                matching_original_keys = self._key_stripped_fallback[stripped]
                all_combined_rows = []
                for orig_key in matching_original_keys:
                    rows = self._key_all_rows.get(orig_key)
                    if rows:
                        all_combined_rows.extend(rows)
                        all_combined_rows.extend(rows)
                return all_combined_rows
        
        # Try fallback: Explicit Stripping (Handle Base='0123' -> Source='123')
        # Even if strip_leading_zeros is False, if we fail to find '0123', try finding '123'
        if normalized and normalized.startswith('0'):
            stripped_lookup = normalized.lstrip('0')
            if not stripped_lookup: stripped_lookup = '0'
            
            # Check if this stripped key exists in the INDEX directly
            if stripped_lookup in self._key_all_rows:
                return self._key_all_rows[stripped_lookup]
                
            # Also check if the stripped key exists via the fallback map (Source='00123')
            # This handles Base='0123' -> Source='00123' via transitive stripping logic
            if hasattr(self, '_key_stripped_fallback') and stripped_lookup in self._key_stripped_fallback:
                matching_original_keys = self._key_stripped_fallback[stripped_lookup]
                all_combined_rows = []
                for orig_key in matching_original_keys:
                    rows = self._key_all_rows.get(orig_key)
                    if rows:
                        all_combined_rows.extend(rows)
                return all_combined_rows

        # Try fallback: Zero Padding (EAN-13 support)
        # If input is '12356' but source has '012356', and stripping didn't work (maybe source key is complex)
        # We try adding zeros explicitly.
        if normalized and normalized.isdigit() and len(normalized) < 14:
            # Try adding zeros up to typical identifier lengths (e.g. 13, 14, or just general padding)
            # We try padding up to 5 zeros deep or up to 14 chars total
            current_pad = "0" + normalized
            while len(current_pad) <= 14 and len(current_pad) <= len(normalized) + 5:
                if current_pad in self._key_all_rows:
                    return self._key_all_rows[current_pad]
                current_pad = "0" + current_pad
                
        return []
    
    def get_best_row_for_key(self, key: str, target_column: str) -> Tuple[Optional[Dict[str, Any]], int]:
        """Get the best row for a key based on target column availability.
        
        SMART DUPLICATE STRATEGY:
        1. If only one row has data for target_column, return that one
        2. If multiple rows have data, return first one and count of alternatives
        3. If no rows have data, return first row with empty value
        
        Args:
            key: The key to look up
            target_column: The column we want to get data from
            
        Returns:
            Tuple of (best_row_dict, num_alternatives_with_data)
            - If num_alternatives > 0, there are conflicting values
        """
        all_rows = self.get_all_rows_for_key(key)
        
        if not all_rows:
            return None, 0
        
        if len(all_rows) == 1:
            return all_rows[0], 0
        
        # Find rows that have non-null value for target column
        rows_with_data = []
        for row in all_rows:
            val = row.get(target_column)
            if val is not None and str(val).strip() and str(val).lower() != 'nan':
                rows_with_data.append(row)
        
        if len(rows_with_data) == 0:
            # No rows have data - return first one
            return all_rows[0], 0
        elif len(rows_with_data) == 1:
            # Exactly one row has data - perfect!
            return rows_with_data[0], 0
        else:
            # Multiple rows have data - return first, note conflict
            return rows_with_data[0], len(rows_with_data) - 1
    
    def get_key_lookup(self) -> Dict[str, Dict[str, Any]]:
        """Get the key lookup dictionary. Builds if not built yet."""
        # Use proper flag check instead of empty dict check
        if not getattr(self, '_key_lookup_built', False) and self.key_column:
            self.build_key_lookup()
        return self._key_lookup
    
    def get_value_for_key(self, key: str, column: str) -> Any:
        """Get a specific column value for a given key."""
        # Use get_all_rows_for_key to benefit from fallback logic
        rows = self.get_all_rows_for_key(key)
        if rows:
            return rows[0].get(column)
        return None
    
    def get_row_for_key_fuzzy(
        self, 
        key: str, 
        threshold: float = 0.85
    ) -> Tuple[Optional[Dict[str, Any]], float, Optional[str]]:
        """
        Get row data for a key with fuzzy matching fallback.
        This is BETTER than VLOOKUP as it can find approximate matches.
        
        Args:
            key: The key to search for
            threshold: Minimum similarity ratio (0.0-1.0) for fuzzy match
            
        Returns:
            Tuple of (row_data, similarity_score, matched_key)
            If exact match found: (data, 1.0, key)
            If fuzzy match found: (data, score, matched_key)
            If no match: (None, 0.0, None)
        """
        from utils.fuzzy_matcher import find_best_fuzzy_match
        
        normalized = normalize_key(key, self.key_options)
        
        # Try exact match first (fastest)
        if normalized and normalized in self._key_lookup:
            row_data = self._key_lookup[normalized]
            if row_data is not None:
                return row_data, 1.0, normalized
                
        # Try fallback: matches differing only by leading zeros (Fast "Fuzzy")
        if hasattr(self, '_key_stripped_fallback') and not self.key_options.get('strip_leading_zeros', False) and normalized:
            stripped = normalized.lstrip('0')
            if not stripped: stripped = '0'
            
            if stripped in self._key_stripped_fallback:
                # Found keys that match when stripped!
                # Pick any matching original key
                orig_key = next(iter(self._key_stripped_fallback[stripped]))
                row_data = self._key_lookup.get(orig_key)
                if row_data:
                    return row_data, 1.0, orig_key
        
                if row_data:
                    return row_data, 1.0, orig_key
        
        # Try fallback: Explicit Stripping (Handle Base='0123' -> Source='123')
        if normalized and normalized.startswith('0'):
            stripped_lookup = normalized.lstrip('0')
            if not stripped_lookup: stripped_lookup = '0'
            
            # Check direct match for trimmed key
            if stripped_lookup in self._key_lookup:
                 return self._key_lookup[stripped_lookup], 1.0, stripped_lookup
        
        # Try fallback: Zero Padding (EAN-13 support) - Explicit check
        if normalized and normalized.isdigit() and len(normalized) < 14:
            current_pad = "0" + normalized
            while len(current_pad) <= 14 and len(current_pad) <= len(normalized) + 5:
                if current_pad in self._key_lookup:
                     row_data = self._key_lookup[current_pad]
                     if row_data is not None:
                         return row_data, 1.0, current_pad
                current_pad = "0" + current_pad
        
        # Fallback to fuzzy matching
        if normalized and threshold < 1.0:
            matched_key, score, row_data = find_best_fuzzy_match(
                normalized, 
                self._key_lookup, 
                threshold=threshold
            )
            if matched_key and row_data:
                return row_data, score, matched_key
        
        return None, 0.0, None

    
    def calculate_match_stats(self, base_keys: List[str]) -> Dict[str, Any]:
        """Calculate how many base keys match this source."""
        matched = 0
        unmatched = 0
        unmatched_keys = []
        
        for key in base_keys:
            # Skip empty keys or 'nan' strings
            s_key = str(key)
            if not s_key or s_key.lower() == 'nan':
                continue
                
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
