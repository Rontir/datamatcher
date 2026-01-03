import pandas as pd
import tkinter as tk
from tkinter import filedialog
import re
import sys

def normalize_path(path):
    """
    Normalizuje ścieżkę kategorii do postaci kanonicznej:
    - małe litery
    - bez spacji
    - bez cudzysłowów
    - separator / zamiast >
    """
    if pd.isna(path):
        return ""
    
    path = str(path).lower()
    path = path.replace('"', '').replace("'", '')
    path = path.replace(' ', '')
    path = path.replace('>', '/')
    # Opcjonalnie: usuń wielokrotne slashe
    path = re.sub(r'/+', '/', path)
    path = path.strip('/')
    
    return path


def load_base_file(file_path):
    """
    Wczytuje plik bazowy CSV z obsługą różnych kodowań i problematycznych cudzysłowów.
    Format: KOD | ŚCIEŻKA
    """
    encodings = ['utf-8', 'cp1250', 'latin1', 'iso-8859-2']
    
    for encoding in encodings:
        try:
            print(f"Próba wczytania pliku bazowego z kodowaniem: {encoding}")
            
            # quoting=3 to csv.QUOTE_NONE - ignoruje cudzysłowy
            df = pd.read_csv(
                file_path,
                sep='|',
                encoding=encoding,
                quoting=3,  # QUOTE_NONE
                engine='python',
                on_bad_lines='skip'  # Pomija wadliwe linie
            )
            
            # Oczyszczenie nazw kolumn (usunięcie spacji)
            df.columns = df.columns.str.strip()
            
            print(f"✓ Sukces! Wczytano {len(df)} wierszy z kodowaniem {encoding}")
            print(f"Kolumny w pliku bazowym: {list(df.columns)}")
            
            return df, encoding
            
        except Exception as e:
            print(f"✗ Błąd z kodowaniem {encoding}: {str(e)}")
            continue
    
    raise ValueError("Nie udało się wczytać pliku bazowego z żadnym z dostępnych kodowań!")


def load_batch_file(file_path):
    """
    Wczytuje plik wsadowy (Excel lub CSV).
    """
    try:
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            df = pd.read_excel(file_path)
            print(f"✓ Wczytano plik Excel: {len(df)} wierszy")
        else:
            # Próba CSV
            encodings = ['utf-8', 'cp1250', 'latin1']
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    print(f"✓ Wczytano plik CSV ({encoding}): {len(df)} wierszy")
                    break
                except:
                    continue
        
        return df
    
    except Exception as e:
        raise ValueError(f"Błąd wczytywania pliku wsadowego: {str(e)}")


def select_file(title, filetypes):
    """Okienko wyboru pliku."""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title=title, filetypes=filetypes)
    root.destroy()
    return file_path


def select_save_location(default_name="wynik_mapowanie.xlsx"):
    """Okienko wyboru miejsca zapisu."""
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.asksaveasfilename(
        title="Zapisz wynik jako",
        defaultextension=".xlsx",
        initialfile=default_name,
        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
    )
    root.destroy()
    return file_path


def main():
    print("=" * 60)
    print("SKRYPT MAPOWANIA STRUKTUR TOWAROWYCH (Fuzzy Merge)")
    print("=" * 60)
    print()
    
    # 1. Wybór pliku wsadowego
    print("KROK 1: Wybierz plik WSADOWY (produkty bez kodów)")
    batch_file = select_file(
        "Wybierz plik wsadowy",
        [("Excel/CSV", "*.xlsx *.xls *.csv"), ("All files", "*.*")]
    )
    
    if not batch_file:
        print("Anulowano wybór pliku wsadowego.")
        return
    
    print(f"Wybrany plik wsadowy: {batch_file}")
    print()
    
    # 2. Wczytanie pliku wsadowego
    try:
        df_batch = load_batch_file(batch_file)
    except Exception as e:
        print(f"BŁĄD: {e}")
        return
    
    # 3. Wybór kolumny ze ścieżkami
    print("\n" + "=" * 60)
    print("KOLUMNY W PLIKU WSADOWYM:")
    print("=" * 60)
    for idx, col in enumerate(df_batch.columns):
        print(f"{idx}: {col}")
    print()
    
    while True:
        try:
            col_idx = int(input("Podaj NUMER kolumny ze ścieżkami kategorii: "))
            if 0 <= col_idx < len(df_batch.columns):
                path_column = df_batch.columns[col_idx]
                print(f"✓ Wybrano kolumnę: '{path_column}'")
                break
            else:
                print(f"Błąd: Podaj liczbę od 0 do {len(df_batch.columns)-1}")
        except ValueError:
            print("Błąd: Podaj poprawną liczbę!")
    
    print()
    
    # 4. Wybór pliku bazowego
    print("KROK 2: Wybierz plik BAZOWY (struktura KOD | ŚCIEŻKA)")
    base_file = select_file(
        "Wybierz plik bazowy CSV",
        [("CSV files", "*.csv"), ("All files", "*.*")]
    )
    
    if not base_file:
        print("Anulowano wybór pliku bazowego.")
        return
    
    print(f"Wybrany plik bazowy: {base_file}")
    print()
    
    # 5. Wczytanie pliku bazowego
    try:
        df_base, encoding = load_base_file(base_file)
    except Exception as e:
        print(f"BŁĄD: {e}")
        return
    
    # 6. Walidacja struktury pliku bazowego
    if 'KOD' not in df_base.columns and 'ŚCIEŻKA' not in df_base.columns:
        print("\nOSTRZEŻENIE: Nie znaleziono kolumn 'KOD' i 'ŚCIEŻKA'")
        print(f"Dostępne kolumny: {list(df_base.columns)}")
        print("\nPróba automatycznego przypisania...")
        
        if len(df_base.columns) >= 2:
            df_base.columns = ['KOD', 'ŚCIEŻKA'] + list(df_base.columns[2:])
            print(f"✓ Przypisano: {list(df_base.columns[:2])}")
        else:
            print("BŁĄD: Za mało kolumn w pliku bazowym!")
            return
    
    # 7. Normalizacja ścieżek
    print("\n" + "=" * 60)
    print("NORMALIZACJA DANYCH")
    print("=" * 60)
    
    print("Tworzenie kluczy dopasowania...")
    df_base['_klucz'] = df_base['ŚCIEŻKA'].apply(normalize_path)
    df_batch['_klucz'] = df_batch[path_column].apply(normalize_path)
    
    print(f"✓ Znormalizowano {len(df_base)} ścieżek w bazie")
    print(f"✓ Znormalizowano {len(df_batch)} ścieżek w pliku wsadowym")
    print()
    
    # Przykłady normalizacji (pierwsze 3)
    print("Przykłady normalizacji (baza):")
    for i in range(min(3, len(df_base))):
        original = df_base['ŚCIEŻKA'].iloc[i]
        normalized = df_base['_klucz'].iloc[i]
        print(f"  '{original}' → '{normalized}'")
    print()
    
    # 8. Merge (LEFT JOIN)
    print("=" * 60)
    print("ŁĄCZENIE DANYCH")
    print("=" * 60)
    
    df_result = df_batch.merge(
        df_base[['KOD', '_klucz']],
        on='_klucz',
        how='left'
    )
    
    # Usuń tymczasowy klucz
    df_result = df_result.drop('_klucz', axis=1)
    
    # Przenieś kolumnę KOD na początek
    cols = ['KOD'] + [col for col in df_result.columns if col != 'KOD']
    df_result = df_result[cols]
    
    # Statystyki
    matched = df_result['KOD'].notna().sum()
    total = len(df_result)
    match_rate = (matched / total * 100) if total > 0 else 0
    
    print(f"✓ Dopasowano: {matched} / {total} ({match_rate:.1f}%)")
    print(f"✗ Bez dopasowania: {total - matched}")
    print()
    
    # 9. Zapis wyniku
    print("KROK 3: Wybierz miejsce zapisu wyniku")
    output_file = select_save_location()
    
    if not output_file:
        print("Anulowano zapis.")
        return
    
    try:
        df_result.to_excel(output_file, index=False)
        print(f"\n✓ SUKCES! Wynik zapisano do: {output_file}")
    except Exception as e:
        print(f"\n✗ BŁĄD zapisu: {e}")
        return
    
    # 10. Podsumowanie
    print("\n" + "=" * 60)
    print("PODSUMOWANIE")
    print("=" * 60)
    print(f"Plik wsadowy:    {batch_file}")
    print(f"Plik bazowy:     {base_file}")
    print(f"Kodowanie bazy:  {encoding}")
    print(f"Kolumna ścieżek: {path_column}")
    print(f"Wynik:           {output_file}")
    print(f"Dopasowania:     {matched}/{total} ({match_rate:.1f}%)")
    print("=" * 60)
    
    # Opcjonalnie: pokaż przykłady niedopasowanych
    if total - matched > 0:
        print("\nPierwsze 5 niedopasowanych ścieżek:")
        unmached_paths = df_result[df_result['KOD'].isna()][path_column].head()
        for idx, path in enumerate(unmached_paths, 1):
            print(f"  {idx}. {path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nPrzerwano przez użytkownika.")
    except Exception as e:
        print(f"\n\nNIEOCZEKIWANY BŁĄD: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n\nNaciśnij ENTER aby zakończyć...")