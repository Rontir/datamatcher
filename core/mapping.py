"""
Mapping module - defines column mappings and write modes.
"""
import uuid
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
            'enabled': self.enabled
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ColumnMapping':
        """Create from dictionary."""
        write_mode = data.get('write_mode', 'overwrite')
        if isinstance(write_mode, str):
            write_mode = WriteMode(write_mode)
        
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
            enabled=data.get('enabled', True)
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
