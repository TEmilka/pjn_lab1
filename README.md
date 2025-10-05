## Szybki start

1. **Zainstaluj zależności** (najlepiej w wirtualnym środowisku):
   ```bash
   pip install -r requirements.txt
   ```

2. **Uruchom scraper** (zbierze co najmniej 100 rekordów i zapisze CSV/XLSX do `./data/`):
   ```bash
   python scraper.py --min-records 100 --outdir data
   ```

3. **Spakuj pliki do archiwum LAB** (podaj swoje dane zamiast przykładu):
   ```bash
   python make_zip.py --first "Jan" --last "Kowalski" --first2 "Anna" --last2 "Nowak"
   ```
   Wygeneruje plik:
   `LAB1 Kowalski Jan Nowak Anna.zip`  
   zawierający **kod źródłowy** i **pozyskane dane** (`.csv` i `.xlsx`).

## Jak to działa (w skrócie)

- Parser pobiera kolejne strony kategorii (`?p=2`, `?p=3`, ...), z każdej wyciąga linki produktów po selektorze `a[href^="/product/"]`.
- Dla każdego produktu pobiera stronę i:
  - odczytuje **nazwę** i **cenę** (kilka selektorów + heurystyki),
  - próbuje wydobyć **specyfikację** z tabel/`<dl>` (mapowanie polskich etykiet → ujednolicone pola),
  - wspiera heurystyki z **tytułu** (np. RAM, rozdzielczość, podświetlenie klawiatury).
- Dane są normalizowane i zapisywane do CSV/XLSX.

## Dobre praktyki

- Nie zwiększaj agresywnie szybkości — możesz zmienić zakres `SLEEP_MIN` / `SLEEP_MAX` w `scraper.py`, ale z wyczuciem.
- Jeśli struktura HTML się zmieni, dostosuj selektory w `discover_product_links()` i `parse_product_page()`.
- Dobrym zwyczajem jest cache'owanie odpowiedzi podczas developmentu (tu pominięto dla prostoty).

Powodzenia! ✨
