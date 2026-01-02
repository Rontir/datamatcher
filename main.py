#!/usr/bin/env python3
"""
DataMatcher Pro - Advanced Excel Data Matching Tool

Usage:
    python main.py [--profile PROFILE_PATH]
"""
import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="DataMatcher Pro - Łączenie danych z plików Excel"
    )
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
    
    args = parser.parse_args()
    
    # Import after path setup
    from gui.main_window import MainApplication
    
    # Create and run application
    app = MainApplication()
    
    # Load profile if specified
    if args.profile:
        app._load_profile_from_path(args.profile)
    
    # Load base file if specified
    if args.base:
        app.base_panel.load_from_path(args.base)
    
    app.run()


if __name__ == '__main__':
    main()
