# LAB 1 — Parser danych (Komputronik)

Ten projekt zawiera gotowy skrypt scrapujący **Komputronik → Laptopy** i budujący zbiór danych: **≥100 rekordów** oraz **20 atrybutów** (w tym atrybut przewidywalny — `price_pln`).

> **Uwaga prawna i etyczna**
>
> - Sprawdź `robots.txt` i warunki usługi serwisu. Pozyskane dane mogą podlegać ograniczeniom licencyjnym i prawu autorskiemu. Używaj ich wyłącznie w dozwolony sposób.
> - Skrypt wprowadza opóźnienia (`sleep`) i retry, żeby ograniczyć obciążenie serwera.

## Wymogi zadania a implementacja

- **(a)** Zbiór danych oparty o sklep Komputronik — ✔️
- **(b)** Minimum **100 rekordów** — skrypt zbiera do uzyskania `--min-records 100` (domyślnie). ✔️
- **(c)** **Kategoria** zahardkodowana w kodzie:  
  `https://www.komputronik.pl/category/5022/laptopy.html` — ✔️
- **(d)** Parser wyszukuje linki produktów po wzorcu `/product/<id>/<slug>.html` — ✔️
- **(e)** Paginacja po `?p=<n>` — ✔️
- **(f)** Zbiór danych z **20 atrybutami** (w tym cena jako atrybut przewidywalny):  
  1. `product_id`  
  2. `name`  
  3. `brand`  
  4. `model`  
  5. `price_pln` *(target)*  
  6. `availability`  
  7. `rating`  
  8. `reviews_count`  
  9. `screen_size_inches`  
  10. `screen_resolution`  
  11. `panel_type`  
  12. `cpu`  
  13. `gpu`  
  14. `ram_gb`  
  15. `storage_type`  
  16. `storage_capacity_gb`  
  17. `os`  
  18. `color`  
  19. `keyboard_backlight`  
  20. `product_url`  
- **(g)** Język: **Python** + `requests`, `BeautifulSoup` — ✔️
- **(h)** Archiwum `.zip` — skrypt `make_zip.py` ułatwia spakowanie kodu i danych. ✔️

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
