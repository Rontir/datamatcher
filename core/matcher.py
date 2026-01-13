"""
Matcher module - the main matching logic engine.
Supports conditional rules, templates, and custom script transformations.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

from .data_source import DataSource
from .mapping import ColumnMapping, WriteMode, MappingManager
from .transformer import apply_transform
from utils.key_normalizer import normalize_key, is_empty


class ChangeType(Enum):
    """Type of change for a cell."""
    UNCHANGED = "unchanged"
    NEW = "new"           # Value added where empty
    CHANGED = "changed"   # Value modified
    NO_MATCH = "no_match" # Key not found in any source
    CONFLICT = "conflict" # Multiple sources with different values
    SKIPPED = "skipped"   # Skipped due to condition not met


@dataclass
class CellChange:
    """Represents a change to a single cell."""
    row_index: int
    column: str
    key: str
    old_value: Any
    new_value: Any
    change_type: ChangeType
    source_id: str
    source_name: str
    mapping_id: str
    write_mode: WriteMode
    transform: Optional[str] = None
    validation_warning: Optional[str] = None  # Type mismatch warning


@dataclass
class MatchResult:
    """Result of matching operation."""
    result_df: pd.DataFrame
    changes: List[CellChange] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    unmatched_keys: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)


class DataMatcher:
    """Main engine for matching and merging data."""
    
    def __init__(self):
        self.base_source: Optional[DataSource] = None
        self.data_sources: Dict[str, DataSource] = {}
        self.mapping_manager = MappingManager()
        self.key_options: Dict[str, Any] = {}
        
        # Batch filter for limiting which rows to process
        self.batch_filter = None  # Optional[BatchFilter]
        
        # Callbacks for progress updates
        self._progress_callback: Optional[Callable[[int, int, str], None]] = None
    
    def set_base_source(self, source: DataSource) -> None:
        """Set the base file source."""
        self.base_source = source
        # Recalculate matches for all sources
        if source.key_column:
            base_keys = self._get_base_keys()
            for ds in self.data_sources.values():
                ds.calculate_match_stats(base_keys)
    
    def add_source(self, source: DataSource) -> None:
        """Add a data source."""
        self.data_sources[source.id] = source
        # Calculate match stats
        if self.base_source and self.base_source.key_column:
            base_keys = self._get_base_keys()
            source.calculate_match_stats(base_keys)
    
    def remove_source(self, source_id: str) -> bool:
        """Remove a data source."""
        if source_id in self.data_sources:
            del self.data_sources[source_id]
            # Remove associated mappings
            for m in list(self.mapping_manager.mappings):
                if m.source_id == source_id:
                    self.mapping_manager.remove(m.id)
            return True
        return False
    
    def get_source(self, source_id: str) -> Optional[DataSource]:
        """Get a data source by ID."""
        return self.data_sources.get(source_id)
    
    def _get_base_keys(self) -> List[str]:
        """Get list of all keys from base source."""
        if not self.base_source or not self.base_source.key_column:
            return []
        
        return list(self.base_source.dataframe[self.base_source.key_column].dropna().astype(str))
    
    def set_progress_callback(self, callback: Callable[[int, int, str], None]) -> None:
        """Set callback for progress updates: (current, total, message)."""
        self._progress_callback = callback
    
    def _report_progress(self, current: int, total: int, message: str) -> None:
        """Report progress to callback if set."""
        if self._progress_callback:
            self._progress_callback(current, total, message)
    
    def _execute_custom_script(self, value: Any, script: str) -> Any:
        """Safely execute a custom Python script/lambda on a value."""
        if not script or not script.strip():
            return value
        
        try:
            # Create a safe namespace
            safe_globals = {
                '__builtins__': {
                    'str': str, 'int': int, 'float': float, 'bool': bool,
                    'len': len, 'abs': abs, 'round': round, 'min': min, 'max': max,
                    'sum': sum, 'sorted': sorted, 'list': list, 'dict': dict,
                    'upper': str.upper, 'lower': str.lower, 'strip': str.strip,
                    'replace': str.replace, 'split': str.split,
                    'None': None, 'True': True, 'False': False,
                }
            }
            
            # Execute the script
            if script.strip().startswith('lambda'):
                func = eval(script.strip(), safe_globals)
                return func(value)
            else:
                # Assume it's an expression using 'x' as the variable
                safe_globals['x'] = value
                return eval(script.strip(), safe_globals)
                
        except Exception as e:
            # On error, return original value
            return value
    
    def _validate_type(self, value: Any, expected_type: str) -> Optional[str]:
        """Validate value against expected type. Returns warning message or None."""
        if not expected_type or value is None or is_empty(value):
            return None
        
        value_str = str(value)
        
        if expected_type == "number":
            try:
                float(value_str.replace(',', '.'))
                return None
            except ValueError:
                return f"Oczekiwano liczby, otrzymano: '{value_str[:20]}'"
        
        elif expected_type == "date":
            import re
            date_patterns = [
                r'\d{4}-\d{2}-\d{2}',
                r'\d{2}/\d{2}/\d{4}',
                r'\d{2}\.\d{2}\.\d{4}'
            ]
            for pattern in date_patterns:
                if re.match(pattern, value_str):
                    return None
            return f"Oczekiwano daty, otrzymano: '{value_str[:20]}'"
        
        return None  # String type or unknown
    
    def execute(self) -> MatchResult:
        """Execute all mappings and return the result."""
        if not self.base_source or self.base_source.dataframe is None:
            raise ValueError("No base source loaded")
        
        if not self.mapping_manager.mappings:
            raise ValueError("No mappings defined")
        
        result_df = self.base_source.dataframe.copy()
        changes: List[CellChange] = []
        unmatched_keys: set = set()
        validation_warnings: List[str] = []
        self._duplicate_conflicts = []  # Clear conflicts at start

        
        base_key_col = self.base_source.key_column
        total_rows = len(result_df)
        enabled_mappings = self.mapping_manager.get_enabled()
        
        # IMPORTANT: Propagate current key_options to all sources and rebuild their key_lookup
        # This ensures normalization settings (strip_decimal, normalize_paths, etc.) are applied
        for source in self.data_sources.values():
            source.key_options = self.key_options.copy()
            source.build_key_lookup(force=True)  # Force rebuild with new options
        
        # CRITICAL: Also propagate to base_source for consistent key normalization
        self.base_source.key_options = self.key_options.copy()

        
        # Check which keys can be matched to any source
        all_matched_keys: set = set()
        for source in self.data_sources.values():
            all_matched_keys.update(source.get_key_lookup().keys())
        
        # Process each row
        for idx, (row_idx, row) in enumerate(result_df.iterrows()):
            if idx % 2000 == 0:  # Report progress every 2000 rows to reduce UI lag
                self._report_progress(idx, total_rows, f"Przetwarzanie wiersza {idx}/{total_rows}")
            
            raw_key = row[base_key_col]
            normalized_key = normalize_key(raw_key, self.key_options)
            
            if normalized_key is None:
                continue  # Skip empty keys
            
            # Check batch filter
            if self.batch_filter and self.batch_filter.enabled:
                if not self.batch_filter.should_process_row(idx, str(raw_key)):
                    continue  # Skip this row due to filter
            
            key_matched_somewhere = normalized_key in all_matched_keys
            
            if not key_matched_somewhere:
                unmatched_keys.add(str(raw_key))
            
            # Apply each mapping
            for mapping in enabled_mappings:
                source = self.data_sources.get(mapping.source_id)
                if not source:
                    continue
                
                # Create new column if needed
                if mapping.target_is_new and mapping.target_column not in result_df.columns:
                    result_df[mapping.target_column] = np.nan
                
                # Get source row data for this key
                # SMART DUPLICATE HANDLING: Use get_best_row_for_key to find row with data
                fuzzy_threshold = self.key_options.get('fuzzy_threshold', 1.0)  # 1.0 = exact only
                num_conflicts = 0
                
                if fuzzy_threshold < 1.0:
                    # Use fuzzy matching
                    source_row_data, match_score, matched_key = source.get_row_for_key_fuzzy(
                        str(raw_key), 
                        threshold=fuzzy_threshold
                    )
                    source_row_data = source_row_data or {}
                else:
                    # IMPROVED: Use smart duplicate handling
                    # Get the best row that has data for the target column we're mapping
                    source_row_data, num_conflicts = source.get_best_row_for_key(
                        str(raw_key), 
                        mapping.source_column
                    )
                    source_row_data = source_row_data or {}
                    
                    # Track conflicts for reporting
                    if num_conflicts > 0:
                        if not hasattr(self, '_duplicate_conflicts'):
                            self._duplicate_conflicts = []
                        
                        # Get all rows with data for this key
                        all_rows = source.get_all_rows_for_key(str(raw_key))
                        rows_with_data = [
                            r for r in all_rows 
                            if r.get(mapping.source_column) is not None 
                            and str(r.get(mapping.source_column)).strip() 
                            and str(r.get(mapping.source_column)).lower() != 'nan'
                        ]
                        
                        self._duplicate_conflicts.append({
                            'key': str(raw_key),
                            'column': mapping.source_column,
                            'target_column': mapping.target_column,
                            'row_index': row_idx,
                            'rows': rows_with_data
                        })
                
                if not source_row_data:
                    # No match in this source
                    if not key_matched_somewhere:
                        changes.append(CellChange(
                            row_index=row_idx,
                            column=mapping.target_column,
                            key=str(raw_key),
                            old_value=row.get(mapping.target_column),
                            new_value=None,
                            change_type=ChangeType.NO_MATCH,
                            source_id=mapping.source_id,
                            source_name=mapping.source_name,
                            mapping_id=mapping.id,
                            write_mode=mapping.write_mode
                        ))
                    continue
                
                # Evaluate conditional rules
                row_dict = row.to_dict()
                if not mapping.evaluate_conditions(row_dict, source_row_data):
                    # Condition not met, skip this mapping for this row
                    changes.append(CellChange(
                        row_index=row_idx,
                        column=mapping.target_column,
                        key=str(raw_key),
                        old_value=row.get(mapping.target_column),
                        new_value=None,
                        change_type=ChangeType.SKIPPED,
                        source_id=mapping.source_id,
                        source_name=mapping.source_name,
                        mapping_id=mapping.id,
                        write_mode=mapping.write_mode
                    ))
                    continue
                
                # Get source value (from template or column)
                if mapping.source_template:
                    source_value = mapping.render_template(source_row_data)
                else:
                    source_value = source_row_data.get(mapping.source_column)
                
                if source_value is None:
                    continue
                
                # Apply built-in transformation
                if mapping.transform:
                    source_value = apply_transform(source_value, mapping.transform)
                
                # Apply custom script transformation
                if mapping.custom_script:
                    source_value = self._execute_custom_script(source_value, mapping.custom_script)
                
                # Validate type
                validation_warning = None
                if mapping.expected_type:
                    validation_warning = self._validate_type(source_value, mapping.expected_type)
                    if validation_warning:
                        validation_warnings.append(f"Wiersz {row_idx}, {mapping.target_column}: {validation_warning}")
                
                # Get current value
                current_value = row.get(mapping.target_column) if mapping.target_column in row.index else None
                
                # Determine if we should write
                should_write, change_type = self._should_write(
                    current_value, source_value, mapping.write_mode
                )
                
                if should_write:
                    # Handle append mode
                    if mapping.write_mode == WriteMode.APPEND and not is_empty(current_value):
                        new_value = f"{current_value}{mapping.append_separator}{source_value}"
                    else:
                        new_value = source_value
                    
                    result_df.at[row_idx, mapping.target_column] = new_value
                    
                    changes.append(CellChange(
                        row_index=row_idx,
                        column=mapping.target_column,
                        key=str(raw_key),
                        old_value=current_value,
                        new_value=new_value,
                        change_type=change_type,
                        source_id=mapping.source_id,
                        source_name=mapping.source_name,
                        mapping_id=mapping.id,
                        write_mode=mapping.write_mode,
                        transform=mapping.transform,
                        validation_warning=validation_warning
                    ))
                else:
                    # Record unchanged
                    changes.append(CellChange(
                        row_index=row_idx,
                        column=mapping.target_column,
                        key=str(raw_key),
                        old_value=current_value,
                        new_value=current_value,
                        change_type=ChangeType.UNCHANGED,
                        source_id=mapping.source_id,
                        source_name=mapping.source_name,
                        mapping_id=mapping.id,
                        write_mode=mapping.write_mode
                    ))
        
        self._report_progress(total_rows, total_rows, "Zakończono")
        
        # --- Smart Column Reordering ---
        # 1. Identify all target columns defined in mappings (in order)
        mapped_targets = []
        seen_targets = set()
        for m in self.mapping_manager.mappings:
            if m.target_column not in seen_targets:
                mapped_targets.append(m.target_column)
                seen_targets.add(m.target_column)
        
        # 2. Identify base columns that are NOT mapped (preserve original order)
        unmapped_base_cols = []
        if self.base_source:
            for col in self.base_source.get_columns():
                if col in result_df.columns and col not in seen_targets:
                    unmapped_base_cols.append(col)
        
        # 3. Combine: Unmapped Base Cols + Mapped Targets (in mapping order)
        # This ensures that if user maps an existing column, it moves to the mapped section
        final_cols = unmapped_base_cols + [c for c in mapped_targets if c in result_df.columns]
        
        # 4. Add any remaining columns (safety check)
        existing_set = set(final_cols)
        for c in result_df.columns:
            if c not in existing_set:
                final_cols.append(c)
        
        result_df = result_df[final_cols]
        
        # --- Column Renaming (output_name alias) ---
        rename_map = {}
        for m in self.mapping_manager.mappings:
            if m.output_name and m.output_name != m.target_column:
                if m.target_column in result_df.columns:
                    rename_map[m.target_column] = m.output_name
        
        if rename_map:
            result_df = result_df.rename(columns=rename_map)
        # -------------------------------
        
        # Calculate stats
        stats = self._calculate_stats(changes, total_rows, validation_warnings)
        
        return MatchResult(
            result_df=result_df,
            changes=changes,
            stats=stats,
            unmatched_keys=list(unmatched_keys),
            validation_warnings=validation_warnings
        )
    
    def _should_write(self, current: Any, new: Any, mode: WriteMode) -> Tuple[bool, ChangeType]:
        """Determine if a value should be written based on mode."""
        current_empty = is_empty(current)
        new_empty = is_empty(new)
        
        if mode == WriteMode.OVERWRITE:
            if current_empty:
                return True, ChangeType.NEW
            elif str(current) != str(new):
                return True, ChangeType.CHANGED
            return False, ChangeType.UNCHANGED
        
        elif mode == WriteMode.FILL_EMPTY:
            if current_empty and not new_empty:
                return True, ChangeType.NEW
            return False, ChangeType.UNCHANGED
        
        elif mode == WriteMode.APPEND:
            if not new_empty:
                if current_empty:
                    return True, ChangeType.NEW
                return True, ChangeType.CHANGED
            return False, ChangeType.UNCHANGED
        
        elif mode == WriteMode.OVERWRITE_IF_DIFFERENT:
            if str(current) != str(new):
                if current_empty:
                    return True, ChangeType.NEW
                return True, ChangeType.CHANGED
            return False, ChangeType.UNCHANGED
        
        elif mode == WriteMode.OVERWRITE_IF_LONGER:
            if len(str(new) if new else "") > len(str(current) if current else ""):
                if current_empty:
                    return True, ChangeType.NEW
                return True, ChangeType.CHANGED
            return False, ChangeType.UNCHANGED
        
        elif mode == WriteMode.OVERWRITE_IF_NOT_EMPTY:
            if not new_empty:
                if current_empty:
                    return True, ChangeType.NEW
                elif str(current) != str(new):
                    return True, ChangeType.CHANGED
            return False, ChangeType.UNCHANGED
        
        return False, ChangeType.UNCHANGED
    
    def _calculate_stats(self, changes: List[CellChange], total_rows: int, 
                         validation_warnings: List[str]) -> Dict[str, Any]:
        """Calculate statistics from changes."""
        new_count = sum(1 for c in changes if c.change_type == ChangeType.NEW)
        changed_count = sum(1 for c in changes if c.change_type == ChangeType.CHANGED)
        skipped_count = sum(1 for c in changes if c.change_type == ChangeType.SKIPPED)
        no_match_count = len(set(c.key for c in changes if c.change_type == ChangeType.NO_MATCH))
        
        rows_with_changes = len(set(c.row_index for c in changes 
                                     if c.change_type in (ChangeType.NEW, ChangeType.CHANGED)))
        
        return {
            'total_rows': total_rows,
            'rows_with_changes': rows_with_changes,
            'rows_no_match': no_match_count,
            'cells_new': new_count,
            'cells_changed': changed_count,
            'cells_skipped': skipped_count,
            'cells_total_modified': new_count + changed_count,
            'validation_warnings_count': len(validation_warnings),
            'match_percent': ((total_rows - no_match_count) / total_rows * 100) if total_rows > 0 else 0
        }
    
    def get_preview(self, max_rows: int = 100, filter_type: str = "all") -> pd.DataFrame:
        """Get a preview of changes without modifying the original data."""
        result = self.execute()
        
        if filter_type == "changed":
            changed_rows = set(c.row_index for c in result.changes 
                               if c.change_type in (ChangeType.NEW, ChangeType.CHANGED))
            return result.result_df.loc[list(changed_rows)[:max_rows]]
        
        elif filter_type == "unmatched":
            unmatched_rows = set(c.row_index for c in result.changes 
                                  if c.change_type == ChangeType.NO_MATCH)
            return result.result_df.loc[list(unmatched_rows)[:max_rows]]
        
        return result.result_df.head(max_rows)
    
    def clear(self) -> None:
        """Clear all data."""
        self.base_source = None
        self.data_sources.clear()
        self.mapping_manager.clear()
