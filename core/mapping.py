"""
Mapping module - defines column mappings, write modes, and conditional rules.
"""
import uuid
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class WriteMode(Enum):
    """Defines how values should be written to the target column."""
    
    OVERWRITE = "overwrite"                 # Zawsze nadpisz
    FILL_EMPTY = "fill_empty"               # Tylko jeśli docelowa jest pusta
    APPEND = "append"                       # Dopisz do istniejącej wartości
    OVERWRITE_IF_DIFFERENT = "diff"         # Nadpisz tylko jeśli się różni
    OVERWRITE_IF_LONGER = "longer"          # Nadpisz jeśli nowa jest dłuższa
    OVERWRITE_IF_NOT_EMPTY = "not_empty"    # Nadpisz tylko jeśli źródło nie jest puste
    
    @classmethod
    def get_display_name(cls, mode: 'WriteMode') -> str:
        """Get human-readable name for display."""
        names = {
            cls.OVERWRITE: "Nadpisz zawsze",
            cls.FILL_EMPTY: "Uzupełnij puste",
            cls.APPEND: "Dopisz",
            cls.OVERWRITE_IF_DIFFERENT: "Nadpisz jeśli inne",
            cls.OVERWRITE_IF_LONGER: "Nadpisz jeśli dłuższe",
            cls.OVERWRITE_IF_NOT_EMPTY: "Nadpisz jeśli niepuste",
        }
        return names.get(mode, mode.value)
    
    @classmethod
    def get_all_display_names(cls) -> Dict['WriteMode', str]:
        """Get all modes with their display names."""
        return {mode: cls.get_display_name(mode) for mode in cls}


class RuleOperator(Enum):
    """Operators for rule conditions."""
    EQUALS = "equals"               # ==
    NOT_EQUALS = "not_equals"       # !=
    CONTAINS = "contains"           # in
    NOT_CONTAINS = "not_contains"   # not in
    STARTS_WITH = "starts_with"     # startswith
    ENDS_WITH = "ends_with"         # endswith
    IS_EMPTY = "is_empty"           # is None or ''
    IS_NOT_EMPTY = "is_not_empty"   # is not None and != ''
    GREATER_THAN = "gt"             # >
    LESS_THAN = "lt"                # <
    REGEX_MATCH = "regex"           # re.match
    
    @classmethod
    def get_display_name(cls, op: 'RuleOperator') -> str:
        names = {
            cls.EQUALS: "równe",
            cls.NOT_EQUALS: "różne od",
            cls.CONTAINS: "zawiera",
            cls.NOT_CONTAINS: "nie zawiera",
            cls.STARTS_WITH: "zaczyna się od",
            cls.ENDS_WITH: "kończy się na",
            cls.IS_EMPTY: "jest puste",
            cls.IS_NOT_EMPTY: "nie jest puste",
            cls.GREATER_THAN: "większe niż",
            cls.LESS_THAN: "mniejsze niż",
            cls.REGEX_MATCH: "pasuje do regex",
        }
        return names.get(op, op.value)


@dataclass
class RuleCondition:
    """A single condition for conditional mapping."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    column: str = ""                        # Column to check (source or target)
    operator: RuleOperator = RuleOperator.EQUALS
    value: str = ""                         # Value to compare against
    is_source_column: bool = True           # Check source (True) or target (False)
    
    def evaluate(self, row_data: Dict[str, Any], source_data: Dict[str, Any]) -> bool:
        """Evaluate the condition against row data."""
        # Get the value to check
        if self.is_source_column:
            check_value = source_data.get(self.column)
        else:
            check_value = row_data.get(self.column)
        
        # Convert to string for comparison
        check_str = str(check_value) if check_value is not None else ""
        compare_value = self.value
        
        # Apply operator
        if self.operator == RuleOperator.EQUALS:
            return check_str.lower() == compare_value.lower()
        elif self.operator == RuleOperator.NOT_EQUALS:
            return check_str.lower() != compare_value.lower()
        elif self.operator == RuleOperator.CONTAINS:
            return compare_value.lower() in check_str.lower()
        elif self.operator == RuleOperator.NOT_CONTAINS:
            return compare_value.lower() not in check_str.lower()
        elif self.operator == RuleOperator.STARTS_WITH:
            return check_str.lower().startswith(compare_value.lower())
        elif self.operator == RuleOperator.ENDS_WITH:
            return check_str.lower().endswith(compare_value.lower())
        elif self.operator == RuleOperator.IS_EMPTY:
            return check_value is None or check_str.strip() == ""
        elif self.operator == RuleOperator.IS_NOT_EMPTY:
            return check_value is not None and check_str.strip() != ""
        elif self.operator == RuleOperator.GREATER_THAN:
            try:
                return float(check_str) > float(compare_value)
            except ValueError:
                return False
        elif self.operator == RuleOperator.LESS_THAN:
            try:
                return float(check_str) < float(compare_value)
            except ValueError:
                return False
        elif self.operator == RuleOperator.REGEX_MATCH:
            try:
                return bool(re.search(compare_value, check_str, re.IGNORECASE))
            except re.error:
                return False
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'column': self.column,
            'operator': self.operator.value,
            'value': self.value,
            'is_source_column': self.is_source_column
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RuleCondition':
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            column=data.get('column', ''),
            operator=RuleOperator(data.get('operator', 'equals')),
            value=data.get('value', ''),
            is_source_column=data.get('is_source_column', True)
        )


@dataclass
class ColumnMapping:
    """Represents a mapping from source column to target column."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str = ""                     # ID źródła danych (DataSource.id)
    source_name: str = ""                   # Display name for source
    source_column: str = ""                 # Nazwa kolumny w źródle
    target_column: str = ""                 # Nazwa kolumny docelowej
    target_is_new: bool = False             # Czy tworzymy nową kolumnę
    write_mode: WriteMode = WriteMode.OVERWRITE
    transform: Optional[str] = None         # ID transformacji
    append_separator: str = " | "           # Separator dla trybu APPEND
    priority: int = 0                       # Kolejność wykonania
    enabled: bool = True                    # Czy mapowanie jest aktywne
    output_name: str = ""                   # Custom output column name (if different from target_column)
    
    # Advanced: Template mode (combine multiple columns)
    source_template: str = ""               # e.g., "{Marka} - {Model}" (if set, overrides source_column)
    
    # Advanced: Conditional rules
    conditions: List[RuleCondition] = field(default_factory=list)
    condition_logic: str = "AND"            # "AND" or "OR"
    
    # Advanced: Custom Python script for transformation
    custom_script: str = ""                 # Python lambda expression, e.g., "lambda x: x.upper()"
    
    # Validation
    expected_type: str = ""                 # "string", "number", "date" - for validation warnings
    
    def evaluate_conditions(self, row_data: Dict[str, Any], source_data: Dict[str, Any]) -> bool:
        """
        Evaluate all conditions to determine if mapping should be applied.
        Returns True if mapping should be applied, False otherwise.
        """
        if not self.conditions:
            return True  # No conditions = always apply
        
        results = [c.evaluate(row_data, source_data) for c in self.conditions]
        
        if self.condition_logic == "OR":
            return any(results)
        else:  # AND
            return all(results)
    
    def render_template(self, source_data: Dict[str, Any]) -> Optional[str]:
        """
        Render the source_template using values from source_data.
        Returns the rendered string or None if template is empty.
        """
        if not self.source_template:
            return None
        
        result = self.source_template
        
        # Find all {column_name} patterns
        pattern = r'\{([^}]+)\}'
        matches = re.findall(pattern, self.source_template)
        
        for col_name in matches:
            value = source_data.get(col_name, '')
            value_str = str(value) if value is not None else ''
            result = result.replace(f'{{{col_name}}}', value_str)
        
        return result
    
    def get_output_column_name(self) -> str:
        """Get the actual output column name (uses output_name if set, else target_column)."""
        return self.output_name if self.output_name else self.target_column
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'id': self.id,
            'source_id': self.source_id,
            'source_name': self.source_name,
            'source_column': self.source_column,
            'target_column': self.target_column,
            'target_is_new': self.target_is_new,
            'write_mode': self.write_mode.value,
            'transform': self.transform,
            'append_separator': self.append_separator,
            'priority': self.priority,
            'enabled': self.enabled,
            'output_name': self.output_name,
            'source_template': self.source_template,
            'conditions': [c.to_dict() for c in self.conditions],
            'condition_logic': self.condition_logic,
            'custom_script': self.custom_script,
            'expected_type': self.expected_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColumnMapping':
        """Create from dictionary."""
        write_mode = data.get('write_mode', 'overwrite')
        if isinstance(write_mode, str):
            write_mode = WriteMode(write_mode)
        
        conditions = [RuleCondition.from_dict(c) for c in data.get('conditions', [])]
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            source_id=data.get('source_id', ''),
            source_name=data.get('source_name', ''),
            source_column=data.get('source_column', ''),
            target_column=data.get('target_column', ''),
            target_is_new=data.get('target_is_new', False),
            write_mode=write_mode,
            transform=data.get('transform'),
            append_separator=data.get('append_separator', ' | '),
            priority=data.get('priority', 0),
            enabled=data.get('enabled', True),
            output_name=data.get('output_name', ''),
            source_template=data.get('source_template', ''),
            conditions=conditions,
            condition_logic=data.get('condition_logic', 'AND'),
            custom_script=data.get('custom_script', ''),
            expected_type=data.get('expected_type', '')
        )
    
    def get_display_mode(self) -> str:
        """Get display name for write mode."""
        return WriteMode.get_display_name(self.write_mode)


class MappingManager:
    """Manages a collection of column mappings."""
    
    def __init__(self):
        self.mappings: List[ColumnMapping] = []
        self._undo_stack: List[List[ColumnMapping]] = []
    
    def add(self, mapping: ColumnMapping) -> None:
        """Add a new mapping."""
        self._save_undo_state()
        mapping.priority = len(self.mappings)
        self.mappings.append(mapping)
    
    def remove(self, mapping_id: str) -> bool:
        """Remove a mapping by ID."""
        for i, m in enumerate(self.mappings):
            if m.id == mapping_id:
                self._save_undo_state()
                self.mappings.pop(i)
                self._update_priorities()
                return True
        return False
    
    def update(self, mapping: ColumnMapping) -> bool:
        """Update an existing mapping."""
        for i, m in enumerate(self.mappings):
            if m.id == mapping.id:
                self._save_undo_state()
                self.mappings[i] = mapping
                return True
        return False
    
    def get(self, mapping_id: str) -> Optional[ColumnMapping]:
        """Get a mapping by ID."""
        for m in self.mappings:
            if m.id == mapping_id:
                return m
        return None
    
    def get_by_source(self, source_id: str) -> List[ColumnMapping]:
        """Get all mappings for a specific source."""
        return [m for m in self.mappings if m.source_id == source_id]
    
    def get_enabled(self) -> List[ColumnMapping]:
        """Get all enabled mappings sorted by priority."""
        return sorted(
            [m for m in self.mappings if m.enabled],
            key=lambda m: m.priority
        )
    
    def move_up(self, mapping_id: str) -> bool:
        """Move a mapping up in priority."""
        for i, m in enumerate(self.mappings):
            if m.id == mapping_id and i > 0:
                self._save_undo_state()
                self.mappings[i], self.mappings[i-1] = self.mappings[i-1], self.mappings[i]
                self._update_priorities()
                return True
        return False
    
    def move_down(self, mapping_id: str) -> bool:
        """Move a mapping down in priority."""
        for i, m in enumerate(self.mappings):
            if m.id == mapping_id and i < len(self.mappings) - 1:
                self._save_undo_state()
                self.mappings[i], self.mappings[i+1] = self.mappings[i+1], self.mappings[i]
                self._update_priorities()
                return True
        return False
    
    def clear(self) -> None:
        """Remove all mappings."""
        self._save_undo_state()
        self.mappings.clear()
    
    def undo(self) -> bool:
        """Undo last change."""
        if self._undo_stack:
            self.mappings = self._undo_stack.pop()
            return True
        return False
    
    def _save_undo_state(self) -> None:
        """Save current state for undo."""
        # Keep max 50 undo states
        if len(self._undo_stack) >= 50:
            self._undo_stack.pop(0)
        self._undo_stack.append([
            ColumnMapping.from_dict(m.to_dict()) for m in self.mappings
        ])
    
    def _update_priorities(self) -> None:
        """Update priority values to match list order."""
        for i, m in enumerate(self.mappings):
            m.priority = i
    
    def to_list(self) -> List[Dict[str, Any]]:
        """Convert all mappings to list of dicts."""
        return [m.to_dict() for m in self.mappings]
    
    def from_list(self, data: List[Dict[str, Any]]) -> None:
        """Load mappings from list of dicts."""
        self.mappings = [ColumnMapping.from_dict(d) for d in data]
        self._update_priorities()
    
    def __len__(self) -> int:
        return len(self.mappings)
    
    def __iter__(self):
        return iter(self.mappings)
