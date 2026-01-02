"""
Reporter module - generates execution reports.
"""
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

import pandas as pd

from .matcher import MatchResult, CellChange, ChangeType
from .mapping import WriteMode


class Reporter:
    """Generates reports after matching execution."""
    
    def __init__(self, result: MatchResult):
        self.result = result
        self.timestamp = datetime.now()
    
    def generate_summary(self, 
                         base_filename: str,
                         base_key_column: str,
                         sources_info: List[Dict[str, Any]],
                         mappings_info: List[Dict[str, Any]]) -> str:
        """Generate a text summary report."""
        
        lines = [
            "═" * 70,
            "                    RAPORT DATAMATCHER PRO",
            f"                    {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "═" * 70,
            "",
            f"PLIK BAZOWY: {base_filename}",
            f"KLUCZ: {base_key_column}",
            f"WIERSZY: {self.result.stats.get('total_rows', 0):,}",
            "",
            "ŹRÓDŁA DANYCH:",
        ]
        
        for i, src in enumerate(sources_info, 1):
            matched = src.get('matched', 0)
            total = src.get('total_base', 0)
            pct = (matched / total * 100) if total > 0 else 0
            lines.append(f"  {i}. {src['filename']} (klucz: {src['key_column']})")
            lines.append(f"     Dopasowano: {matched:,} / {total:,} ({pct:.1f}%)")
            lines.append("")
        
        lines.append("WYKONANE MAPOWANIA:")
        lines.append("  ┌────┬─────────────────────┬─────────────────┬────────────────┬──────────┐")
        lines.append("  │ Nr │ Źródło → Cel        │ Tryb            │ Zmienionych    │ Status   │")
        lines.append("  ├────┼─────────────────────┼─────────────────┼────────────────┼──────────┤")
        
        for i, m in enumerate(mappings_info, 1):
            source_target = f"{m['source_column'][:8]} → {m['target_column'][:8]}"
            mode_name = WriteMode.get_display_name(WriteMode(m['write_mode']))[:15]
            changed = m.get('cells_changed', 0)
            lines.append(f"  │ {i:<2} │ {source_target:<19} │ {mode_name:<15} │ {changed:>14,} │ ✓ OK     │")
        
        lines.append("  └────┴─────────────────────┴─────────────────┴────────────────┴──────────┘")
        lines.append("")
        lines.append("PODSUMOWANIE:")
        
        stats = self.result.stats
        total = stats.get('total_rows', 0)
        with_changes = stats.get('rows_with_changes', 0)
        no_match = stats.get('rows_no_match', 0)
        cells_mod = stats.get('cells_total_modified', 0)
        
        pct_changed = (with_changes / total * 100) if total > 0 else 0
        pct_no_match = (no_match / total * 100) if total > 0 else 0
        
        lines.append(f"  • Wierszy przetworzonych: {total:,}")
        lines.append(f"  • Wierszy ze zmianami: {with_changes:,} ({pct_changed:.1f}%)")
        lines.append(f"  • Komórek zmodyfikowanych: {cells_mod:,}")
        lines.append(f"  • Wierszy bez dopasowania: {no_match:,} ({pct_no_match:.1f}%)")
        
        if self.result.unmatched_keys:
            lines.append("")
            lines.append(f"NIEDOPASOWANE KLUCZE (pierwsze 50):")
            keys_preview = self.result.unmatched_keys[:50]
            lines.append(f"  {', '.join(keys_preview)}")
            if len(self.result.unmatched_keys) > 50:
                lines.append(f"  (i {len(self.result.unmatched_keys) - 50} więcej...)")
        
        lines.append("")
        lines.append("═" * 70)
        
        return "\n".join(lines)
    
    def export_unmatched(self, filepath: str) -> None:
        """Export unmatched keys to CSV file."""
        if not self.result.unmatched_keys:
            return
        
        # Find row indices for unmatched keys
        unmatched_data = []
        for change in self.result.changes:
            if change.change_type == ChangeType.NO_MATCH:
                unmatched_data.append({
                    'klucz_bazowy': change.key,
                    'wiersz_w_pliku': change.row_index + 2  # +2 for header and 0-index
                })
        
        # Remove duplicates
        seen = set()
        unique_data = []
        for item in unmatched_data:
            key = item['klucz_bazowy']
            if key not in seen:
                seen.add(key)
                unique_data.append(item)
        
        df = pd.DataFrame(unique_data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
    
    def export_change_log(self, filepath: str) -> None:
        """Export detailed change log to CSV."""
        log_data = []
        
        for change in self.result.changes:
            if change.change_type in (ChangeType.NEW, ChangeType.CHANGED):
                log_data.append({
                    'wiersz': change.row_index + 2,
                    'kolumna': change.column,
                    'klucz': change.key,
                    'wartosc_przed': change.old_value,
                    'wartosc_po': change.new_value,
                    'zrodlo': change.source_name,
                    'tryb': WriteMode.get_display_name(change.write_mode),
                    'typ_zmiany': 'nowa' if change.change_type == ChangeType.NEW else 'zmieniona'
                })
        
        df = pd.DataFrame(log_data)
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
    
    def save_report(self, filepath: str,
                    base_filename: str,
                    base_key_column: str,
                    sources_info: List[Dict[str, Any]],
                    mappings_info: List[Dict[str, Any]]) -> None:
        """Save the full text report to a file."""
        summary = self.generate_summary(
            base_filename, base_key_column, sources_info, mappings_info
        )
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(summary)
    
    def get_stats_for_display(self) -> Dict[str, str]:
        """Get formatted statistics for GUI display."""
        stats = self.result.stats
        total = stats.get('total_rows', 0)
        with_changes = stats.get('rows_with_changes', 0)
        no_match = stats.get('rows_no_match', 0)
        cells_mod = stats.get('cells_total_modified', 0)
        match_pct = stats.get('match_percent', 0)
        
        return {
            'total_rows': f"{total:,}",
            'rows_with_changes': f"{with_changes:,}",
            'rows_no_match': f"{no_match:,}",
            'cells_modified': f"{cells_mod:,}",
            'match_percent': f"{match_pct:.1f}%",
            'summary': f"Dopasowano {total - no_match:,}/{total:,} ({match_pct:.1f}%) │ Komórek do zmiany: {cells_mod:,}"
        }
