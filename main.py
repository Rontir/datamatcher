#!/usr/bin/env python3
"""
DataMatcher Pro - Advanced Excel Data Matching Tool

Usage (GUI mode):
    python main.py [--profile PROFILE_PATH] [--base FILE]

Usage (CLI/Headless mode):
    python main.py --headless --config CONFIG.json --output OUTPUT.xlsx
"""
import sys
import argparse
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def run_headless(config_path: str, output_path: str, verbose: bool = False):
    """Run DataMatcher in headless/CLI mode."""
    from core.data_source import DataSource
    from core.matcher import DataMatcher
    from core.mapping import ColumnMapping
    from utils.file_handlers import save_excel
    from utils.config import Profile
    
    # Load config (can be a profile or a simple JSON)
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    matcher = DataMatcher()
    
    # Load base file
    base_path = config.get('base_file')
    base_key = config.get('base_key_column')
    
    if not base_path or not Path(base_path).exists():
        print(f"ERROR: Base file not found: {base_path}")
        sys.exit(1)
    
    if verbose:
        print(f"Loading base file: {base_path}")
    
    base_source = DataSource.from_file(base_path, key_column=base_key)
    matcher.set_base_source(base_source)
    
    # Load sources
    for src_config in config.get('sources', []):
        src_path = src_config.get('filepath')
        src_key = src_config.get('key_column')
        
        if not src_path or not Path(src_path).exists():
            print(f"WARNING: Source file not found: {src_path}, skipping")
            continue
        
        if verbose:
            print(f"Loading source: {src_path}")
        
        source = DataSource.from_file(src_path, key_column=src_key)
        matcher.add_source(source)
        
        # Store ID mapping for later use with mappings
        src_config['loaded_id'] = source.id
    
    # Load mappings
    for map_config in config.get('mappings', []):
        # Find the source ID
        source_id = map_config.get('source_id', '')
        
        # If source_id is a name, find the actual ID
        if not source_id:
            source_name = map_config.get('source_name', '')
            for src in matcher.data_sources.values():
                if src.filename == source_name:
                    source_id = src.id
                    break
        
        if not source_id:
            print(f"WARNING: Source not found for mapping: {map_config}")
            continue
        
        mapping = ColumnMapping.from_dict({**map_config, 'source_id': source_id})
        matcher.mapping_manager.add(mapping)
    
    if verbose:
        print(f"Loaded {len(matcher.mapping_manager)} mappings")
        print("Executing...")
    
    # Execute
    def progress_callback(cur, tot, msg):
        if verbose and cur % 1000 == 0:
            print(f"  {msg}")
    
    matcher.set_progress_callback(progress_callback)
    result = matcher.execute()
    
    # Save output
    if verbose:
        print(f"Saving result to: {output_path}")
    
    save_excel(result.result_df, output_path)
    
    # Print stats
    stats = result.stats
    print(f"\n=== DataMatcher Pro Results ===")
    print(f"Total rows:       {stats['total_rows']:,}")
    print(f"Rows changed:     {stats['rows_with_changes']:,}")
    print(f"Cells modified:   {stats['cells_total_modified']:,}")
    print(f"Match rate:       {stats['match_percent']:.1f}%")
    
    if result.validation_warnings:
        print(f"\nWarnings: {len(result.validation_warnings)}")
        for w in result.validation_warnings[:5]:
            print(f"  - {w}")
        if len(result.validation_warnings) > 5:
            print(f"  ... and {len(result.validation_warnings) - 5} more")
    
    print(f"\nOutput saved: {output_path}")


def run_gui(args):
    """Run DataMatcher in GUI mode."""
    from gui.main_window import MainApplication
    
    app = MainApplication()
    
    # Load profile if specified
    if args.profile:
        app._load_profile_from_path(args.profile)
    
    # Load base file if specified
    if args.base:
        app.base_panel.load_from_path(args.base)
    
    app.run()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DataMatcher Pro - Łączenie danych z plików Excel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Przykłady:
  GUI mode:       python main.py
  GUI + profile:  python main.py --profile config.json
  Headless mode:  python main.py --headless --config config.json --output result.xlsx
        """
    )
    
    # GUI mode arguments
    parser.add_argument(
        '--profile', '-p',
        type=str,
        help='Ścieżka do profilu mapowań (.json)'
    )
    parser.add_argument(
        '--base', '-b',
        type=str,
        help='Ścieżka do pliku bazowego'
    )
    
    # Headless mode arguments
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Uruchom w trybie CLI (bez GUI)'
    )
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Ścieżka do pliku konfiguracji JSON (tryb headless)'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Ścieżka do pliku wynikowego (tryb headless)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Pokazuj szczegółowe informacje'
    )
    
    args = parser.parse_args()
    
    if args.headless:
        if not args.config:
            print("ERROR: --config is required in headless mode")
            sys.exit(1)
        if not args.output:
            print("ERROR: --output is required in headless mode")
            sys.exit(1)
        
        run_headless(args.config, args.output, args.verbose)
    else:
        run_gui(args)


if __name__ == '__main__':
    main()
