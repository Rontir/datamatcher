"""
File handlers module - loading various file formats.
"""
import os
from typing import Tuple, List, Optional, Dict, Any
from pathlib import Path

import pandas as pd
import chardet


def detect_encoding(filepath: str, sample_size: int = 10000) -> str:
    """
    Detect the encoding of a text file.
    
    Args:
        filepath: Path to the file
        sample_size: Number of bytes to sample
        
    Returns:
        Detected encoding name
    """
    with open(filepath, 'rb') as f:
        raw = f.read(sample_size)
    
    result = chardet.detect(raw)
    encoding = result.get('encoding', 'utf-8')
    
    # Map common variations
    encoding_map = {
        'ascii': 'utf-8',
        'ISO-8859-1': 'cp1250',  # Common for Polish
        'ISO-8859-2': 'cp1250',
        'windows-1250': 'cp1250',
        'windows-1252': 'cp1252',
    }
    
    return encoding_map.get(encoding, encoding or 'utf-8')


def detect_separator(filepath: str, encoding: str = 'utf-8') -> str:
    """
    Detect the separator used in a CSV/TSV file.
    
    Args:
        filepath: Path to the file
        encoding: File encoding
        
    Returns:
        Detected separator character
    """
    separators = [',', ';', '\t', '|']
    
    try:
        with open(filepath, 'r', encoding=encoding, errors='replace') as f:
            # Read first few lines
            lines = [f.readline() for _ in range(5)]
    except:
        return ','
    
    # Count occurrences of each separator
    counts = {}
    for sep in separators:
        counts[sep] = sum(line.count(sep) for line in lines)
    
    # Return the most common one
    best_sep = max(counts, key=counts.get)
    return best_sep if counts[best_sep] > 0 else ','


def load_excel(filepath: str, sheet: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Load an Excel file.
    
    Args:
        filepath: Path to the Excel file
        sheet: Optional sheet name to load
        
    Returns:
        Tuple of (DataFrame, list of sheet names)
    """
    ext = Path(filepath).suffix.lower()
    
    # Determine engine
    if ext == '.xls':
        engine = 'xlrd'
    elif ext == '.xlsb':
        engine = 'pyxlsb'
    else:
        engine = 'openpyxl'
    
    # Get sheet names
    try:
        xl = pd.ExcelFile(filepath, engine=engine)
        sheet_names = xl.sheet_names
    except Exception as e:
        raise ValueError(f"Nie można otworzyć pliku Excel: {e}")
    
    # Load specified sheet or first one
    target_sheet = sheet if sheet else sheet_names[0]
    
    if target_sheet not in sheet_names:
        raise ValueError(f"Arkusz '{target_sheet}' nie istnieje. Dostępne: {sheet_names}")
    
    df = pd.read_excel(filepath, sheet_name=target_sheet, engine=engine)
    
    return df, sheet_names


def load_csv(filepath: str, encoding: Optional[str] = None, 
             separator: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Load a CSV/TSV file.
    
    Args:
        filepath: Path to the file
        encoding: Optional encoding (auto-detected if not provided)
        separator: Optional separator (auto-detected if not provided)
        
    Returns:
        Tuple of (DataFrame, empty list for sheets)
    """
    # Auto-detect encoding if not provided
    if not encoding:
        encoding = detect_encoding(filepath)
    
    # Auto-detect separator if not provided
    if not separator:
        separator = detect_separator(filepath, encoding)
    
    try:
        df = pd.read_csv(
            filepath, 
            encoding=encoding, 
            sep=separator,
            on_bad_lines='warn',
            low_memory=False
        )
    except UnicodeDecodeError:
        # Try with different encoding
        for fallback_enc in ['utf-8', 'cp1250', 'cp1252', 'latin1']:
            try:
                df = pd.read_csv(
                    filepath,
                    encoding=fallback_enc,
                    sep=separator,
                    on_bad_lines='warn',
                    low_memory=False
                )
                break
            except:
                continue
        else:
            raise ValueError(f"Nie można odczytać pliku z żadnym kodowaniem")
    
    return df, []


def load_file(filepath: str, sheet: Optional[str] = None) -> Tuple[pd.DataFrame, List[str]]:
    """
    Load a file (Excel or CSV) based on extension.
    
    Args:
        filepath: Path to the file
        sheet: Optional sheet name for Excel files
        
    Returns:
        Tuple of (DataFrame, list of sheet names)
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Plik nie istnieje: {filepath}")
    
    ext = Path(filepath).suffix.lower()
    
    if ext in ['.xlsx', '.xls', '.xlsm', '.xlsb']:
        return load_excel(filepath, sheet)
    elif ext in ['.csv', '.tsv', '.txt']:
        return load_csv(filepath)
    else:
        raise ValueError(f"Nieobsługiwany format pliku: {ext}")


def get_file_info(filepath: str) -> Dict[str, Any]:
    """
    Get basic file information.
    
    Args:
        filepath: Path to the file
        
    Returns:
        Dictionary with file info
    """
    path = Path(filepath)
    
    return {
        'name': path.name,
        'extension': path.suffix.lower(),
        'size_bytes': path.stat().st_size,
        'size_mb': path.stat().st_size / (1024 * 1024),
        'is_excel': path.suffix.lower() in ['.xlsx', '.xls', '.xlsm', '.xlsb'],
        'is_csv': path.suffix.lower() in ['.csv', '.tsv', '.txt']
    }


def save_excel(df: pd.DataFrame, filepath: str, 
               preserve_formatting: bool = False,
               sheet_name: str = 'Dane') -> None:
    """
    Save DataFrame to Excel file.
    
    Args:
        df: DataFrame to save
        filepath: Output file path
        preserve_formatting: Whether to try to preserve original formatting
        sheet_name: Name of the sheet
    """
    with pd.ExcelWriter(filepath, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Auto-adjust column widths
        worksheet = writer.sheets[sheet_name]
        for i, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            ) + 2
            max_len = min(max_len, 50)  # Cap at 50
            worksheet.set_column(i, i, max_len)


def create_backup(filepath: str) -> str:
    """
    Create a backup copy of a file.
    
    Args:
        filepath: Path to the file to backup
        
    Returns:
        Path to the backup file
    """
    from datetime import datetime
    import shutil
    
    path = Path(filepath)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"{path.stem}_BACKUP_{timestamp}{path.suffix}"
    backup_path = path.parent / backup_name
    
    shutil.copy2(filepath, backup_path)
    
    return str(backup_path)
