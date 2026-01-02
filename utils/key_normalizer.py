"""
Key normalizer module - normalizes keys for matching.
"""
from typing import Any, Dict, Optional
import pandas as pd


# Values considered as empty
EMPTY_VALUES = [None, '', 'NULL', 'N/A', '#N/A', '-', 'brak', 'BRAK', 'nan', 'NaN', 'NAN', 'none', 'None', 'NONE']


def normalize_key(value: Any, options: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Normalize a key value for matching.
    
    Args:
        value: The key value to normalize
        options: Dictionary of normalization options:
            - case_insensitive: Convert to lowercase
            - strip_leading_zeros: Remove leading zeros
            - treat_empty_as_null: Return None for empty values
            
    Returns:
        Normalized string key or None if empty
    """
    options = options or {}
    
    # Handle pandas NA/NaN
    if pd.isna(value):
        return None
    
    # Convert to string
    s = str(value).strip()
    
    # Check if empty
    if not s or s.upper() in [v.upper() if isinstance(v, str) else str(v) for v in EMPTY_VALUES if v]:
        if options.get('treat_empty_as_null', True):
            return None
        return s
    
    # Remove .0 from floats (Excel often converts int to float)
    if s.endswith('.0') and s[:-2].replace('-', '').isdigit():
        s = s[:-2]
    
    # Remove double spaces
    while '  ' in s:
        s = s.replace('  ', ' ')
    
    # Apply options
    if options.get('case_insensitive', False):
        s = s.lower()
    
    if options.get('strip_leading_zeros', False):
        # Preserve at least one zero
        stripped = s.lstrip('0')
        s = stripped if stripped else '0'
    
    return s


def is_empty(value: Any) -> bool:
    """
    Check if a value is considered empty.
    
    Args:
        value: The value to check
        
    Returns:
        True if the value is empty/null
    """
    if pd.isna(value):
        return True
    
    if value is None:
        return True
    
    s = str(value).strip()
    
    if not s:
        return True
    
    return s.upper() in [v.upper() if isinstance(v, str) else str(v) for v in EMPTY_VALUES if v]


def compare_keys(key1: Any, key2: Any, options: Optional[Dict[str, Any]] = None) -> bool:
    """
    Compare two keys after normalization.
    
    Args:
        key1: First key
        key2: Second key
        options: Normalization options
        
    Returns:
        True if keys match
    """
    norm1 = normalize_key(key1, options)
    norm2 = normalize_key(key2, options)
    
    if norm1 is None or norm2 is None:
        return False
    
    return norm1 == norm2


def detect_key_column(columns: list, df: Optional[pd.DataFrame] = None) -> Optional[str]:
    """
    Try to auto-detect the key column based on common names.
    
    Args:
        columns: List of column names
        df: Optional DataFrame to check for uniqueness
        
    Returns:
        Best guess for key column or None
    """
    # Common key column names (case-insensitive)
    key_patterns = [
        'mdm', 'index', 'indeks', 'ean', 'sku', 'kod', 'code', 
        'id', 'product_id', 'productid', 'item_id', 'itemid',
        'barcode', 'upc', 'gtin', 'asin'
    ]
    
    columns_lower = {c.lower(): c for c in columns}
    
    # First pass: exact matches
    for pattern in key_patterns:
        if pattern in columns_lower:
            return columns_lower[pattern]
    
    # Second pass: contains
    for pattern in key_patterns:
        for col_lower, col_orig in columns_lower.items():
            if pattern in col_lower:
                return col_orig
    
    # If DataFrame provided, find column with highest uniqueness ratio
    if df is not None and len(df) > 0:
        best_col = None
        best_ratio = 0
        
        for col in columns:
            try:
                unique_count = df[col].nunique()
                total_count = len(df[col].dropna())
                if total_count > 0:
                    ratio = unique_count / total_count
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_col = col
            except:
                continue
        
        if best_ratio > 0.9:  # At least 90% unique
            return best_col
    
    return None


def get_key_stats(df: pd.DataFrame, key_column: str, 
                  options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Get statistics about keys in a DataFrame.
    
    Args:
        df: The DataFrame
        key_column: Name of the key column
        options: Normalization options
        
    Returns:
        Dictionary with key statistics
    """
    if key_column not in df.columns:
        return {
            'total': 0,
            'unique': 0,
            'duplicates': 0,
            'empty': 0,
            'duplicate_keys': []
        }
    
    # Normalize all keys
    normalized = df[key_column].apply(lambda x: normalize_key(x, options))
    
    total = len(df)
    empty_count = normalized.isna().sum()
    
    # Count without empty
    non_empty = normalized.dropna()
    value_counts = non_empty.value_counts()
    
    unique_count = len(value_counts)
    duplicate_count = sum(1 for count in value_counts if count > 1)
    
    # Get actual duplicate keys (first 100)
    duplicate_keys = [key for key, count in value_counts.items() if count > 1][:100]
    
    return {
        'total': total,
        'unique': unique_count,
        'duplicates': duplicate_count,
        'empty': int(empty_count),
        'duplicate_keys': duplicate_keys
    }
