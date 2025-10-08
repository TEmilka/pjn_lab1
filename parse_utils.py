# -*- coding: utf-8 -*-
import os, re
from typing import Dict, Optional
from bs4 import BeautifulSoup

# ========== I/O / util ==========

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def normalize_whitespace(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def clean_price_pln(text: Optional[str]):
    """Czyści i konwertuje tekst ceny na float PLN."""
    if not text:
        return None
    t = text.lower()
    t = t.replace("pln", "").replace("zł", "").replace("z\u0142", "")
    t = re.sub(r"[^0-9,.\s]", "", t)
    t = t.replace(" ", "").replace("\u00a0", "")
    if "," in t and "." in t:
        t = t.replace(".", "")
        t = t.replace(",", ".")
    elif "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except Exception:
        m = re.search(r"(\d+(?:[.,]\d+)?)", t)
        if m:
            return float(m.group(1).replace(",", "."))
    return None

def parse_float(s: Optional[str]):
    if s is None:
        return None
    s = s.replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else None

def parse_int(s: Optional[str]):
    if s is None:
        return None
    m = re.search(r"(\d+)", s)
    return int(m.group(1)) if m else None

# ========== Marka + model ==========

KNOWN_BRANDS = {
    "LENOVO": "Lenovo", "HP": "HP", "APPLE": "Apple", "DELL": "Dell",
    "ASUS": "ASUS", "ACER": "Acer", "MSI": "MSI", "HUAWEI": "Huawei", "LG": "LG",
    "MICROSOFT": "Microsoft", "SAMSUNG": "Samsung", "TOSHIBA": "Toshiba",
    "RAZER": "Razer", "GIGABYTE": "Gigabyte", "CHUWI": "Chuwi", "XIAOMI": "Xiaomi",
}

def guess_brand_model_from_name(name: Optional[str]):
    if not name:
        return (None, None)
    t = normalize_whitespace(name)
    brand = None
    first_pos = 10**9
    for raw, canon in KNOWN_BRANDS.items():
        m = re.search(rf"\b{re.escape(raw)}\b", t, flags=re.I)
        if m and m.start() < first_pos:
            brand, first_pos = canon, m.start()
    if not brand:
        brand = t.split()[0]
    rest = re.sub(rf"\b{re.escape(brand)}\b", "", t, flags=re.I, count=1).strip()
    rest = re.sub(r"^(Laptop|Notebook|Ultrabook)\s+", "", rest, flags=re.I)
    first_chunk = re.split(r"\s*[–—-]\s*|\s*\|\s*|,\s*|\(\s*", rest, maxsplit=1)[0].strip()
    tokens = re.findall(r"[A-Za-z0-9]+(?:[-_/][A-Za-z0-9]+)*", first_chunk)
    model = " ".join(tokens[:4]).strip() or None
    return (brand, model)

# ========== Tabela/specyfikacja ==========

def extract_from_spec_table(soup: BeautifulSoup) -> Dict[str, str]:
    """Obsługuje stary i nowy layout Komputronika."""
    spec: Dict[str, str] = {}

    # --- klasyczny DL/TABLE ---
    for spec_block in soup.select("dl, .specification, .product-parameters, .product-specs"):
        dts = spec_block.find_all("dt")
        dds = spec_block.find_all("dd")
        if len(dts) == len(dds) and len(dts) > 0:
            for dt, dd in zip(dts, dds):
                key = normalize_whitespace(dt.get_text(" ", strip=True)).lower()
                val = normalize_whitespace(dd.get_text(" ", strip=True))
                map_into_spec(spec, key, val)

    for row in soup.select("table tr"):
        th = row.find(["th", "td"])
        tds = row.find_all("td")
        if th and len(tds) >= 1:
            key = normalize_whitespace(th.get_text(" ", strip=True)).lower()
            val = normalize_whitespace(tds[-1].get_text(" ", strip=True))
            map_into_spec(spec, key, val)

    # --- nowy layout (div[data-name='specsGroup']) ---
    for group in soup.select('div[data-name="specsGroup"]'):
        for grid in group.select("div.grid.grid-cols-2"):
            divs = grid.find_all("div", recursive=False)
            if len(divs) >= 2:
                key = normalize_whitespace(divs[0].get_text(" ", strip=True)).lower()
                val_el = divs[1].select_one("span.block") or divs[1]
                val = normalize_whitespace(val_el.get_text(" ", strip=True))
                map_into_spec(spec, key, val)

    return spec

def map_into_spec(spec: Dict[str, str], key_lower: str, val: str):
    """Mapowanie nazw pól Komputronika -> nasze kolumny."""
    mapping = [
        (["przekątna ekranu","przekatna"], "screen_size_inches"),
        (["rozdzielczość","rozdzielczosc"], "screen_resolution"),
        (["matryca","panel"], "panel_type"),
        (["procesor","cpu"], "cpu"),
        (["karta graficzna","układ graficzny","gpu"], "gpu"),
        (["rodzaj dysku","typ dysku","dysk"], "storage_type"),
        (["częstotliwość odświeżania","czestotliwosc odswiezania","odświeżanie ekranu","refresh rate"], "screen_refresh_rate_hz"),
        (["system operacyjny","system"], "os"),

        # Nowe atrybuty:
        (["pojemność baterii","bateria","akumulator"], "battery_capacity_wh"),
        (["waga","masa"], "weight_kg"),
        (["typ pamięci ram","typ pamieci ram"], "ram_type"),
        (["materiał obudowy","material obudowy","obudowa"], "body_material"),
        (["gwarancja"], "warranty_months"),

        (["dostępność","dostepnosc"], "availability"),
    ]
    for keys, target in mapping:
        if any(k in key_lower for k in keys):
            spec[target] = val
            return
