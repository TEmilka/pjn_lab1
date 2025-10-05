# -*- coding: utf-8 -*-
import os, re, time, random
from typing import Dict, Optional
from bs4 import BeautifulSoup

# ========== I/O / util ==========

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def normalize_whitespace(s: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()

def clean_price_pln(text: Optional[str]):
    """
    Zamienia zabałaganiony tekst ceny na float PLN.
    Obsługuje: "3 499,00 zł", "3499 zł", "3.499,00 PLN" itd.
    """
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
    "LENOVO": "Lenovo", "HP": "HP", "HEWLETT-PACKARD": "HP", "APPLE": "Apple", "DELL": "Dell",
    "ASUS": "ASUS", "ACER": "Acer", "MSI": "MSI", "HUAWEI": "Huawei", "LG": "LG",
    "MICROSOFT": "Microsoft", "SAMSUNG": "Samsung", "TOSHIBA": "Toshiba", "RAZER": "Razer",
    "GIGABYTE": "Gigabyte", "CHUWI": "Chuwi", "MEDION": "Medion", "XIAOMI": "Xiaomi",
}

def guess_brand_model_from_name(name: Optional[str]):
    """
    Poprawione: model ≠ marka.
    - znajduje markę z listy znanych (najwcześniejsze wystąpienie),
    - usuwa markę i słowa typu 'Laptop/Notebook' z początku,
    - jako model bierze część przed separatorami ('-', '|', ',', '('),
    - filtruje CPU/RAM/rozdzielczość/OS.
    """
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
    CPU = re.compile(r"^(i[3579](?:-\d{4,5}[A-Za-z]*)?|ryzen|core|celeron|pentium|m\d|m-?series)$", re.I)
    RAM = re.compile(r"^\d+\s*(gb|gib)$", re.I)
    RES = re.compile(r"^(fhd|uhd|wqhd|qhd|wuxga|wxga|retina|4k|3k|2\.?8k|\d{3,4}x\d{3,4})$", re.I)
    OS  = re.compile(r"^(windows|win\d+|linux|dos|freedos)$", re.I)
    BAD = re.compile(r"^(gaming|business|home|student)$", re.I)

    model_tokens = [tok for tok in tokens if not (CPU.match(tok) or RAM.match(tok) or RES.match(tok) or OS.match(tok) or BAD.match(tok))]
    model = " ".join(model_tokens[:4]).strip() or None

    if not model or (brand and model.lower() == brand.lower()):
        m = re.search(r"([A-Za-z]{2,}[A-Za-z0-9\-_/]+)", rest)
        model = m.group(1) if m else None

    return (brand, model)

def extract_specs_from_title(title: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    t = title.replace("’’", "\"").replace("’", "'")

    # przekątna
    m = re.search(r"(\d{1,2}[,.]\d)\s*['\"”]?", t)
    if m:
        out["screen_size_inches"] = m.group(1).replace(",", ".")

    U = t.upper()
    # rozdzielczości
    for key in ["WUXGA","QHD","WQHD","UHD","4K","FHD","WXGA","3K","2.8K","2880X1800","1920X1080"]:
        if key in U:
            out["screen_resolution"] = key
            break
    # panele
    for key in ["OLED","IPS","VA","TN","LTPS","MINI LED","RETINA"]:
        if key in U:
            out["panel_type"] = key.title()
            break

    # RAM
    m = re.search(r"(\d+)\s*GB", t, flags=re.I)
    if m:
        out["ram_gb"] = m.group(1)

    # pojemność dysku
    m = re.search(r"(\d{3,4})\s*GB", t, flags=re.I)
    if m:
        out["storage_capacity_gb"] = m.group(1)

    # OS
    if re.search(r"win\s*11|win11|windows\s*11", t, flags=re.I):
        out["os"] = "Windows 11"
    elif re.search(r"win\s*10|win10|windows\s*10", t, flags=re.I):
        out["os"] = "Windows 10"
    elif re.search(r"linux", t, flags=re.I):
        out["os"] = "Linux"

    # podświetlenie klawiatury
    if re.search(r"pod[\w\.]*\s*klaw|podśw|backlit|backlight", t, flags=re.I):
        out["keyboard_backlight"] = "tak"

    # color (very rough)
    color_map = {
        "niebiesk": "Niebieski",
        "szary": "Szary",
        "srebrn": "Srebrny",
        "czarn": "Czarny",
        "bial": "Biały",
        "zielon": "Zielony",
        "złoty": "Złoty",
    }
    for k, v in color_map.items():
        if re.search(k, t, flags=re.I):
            out["color"] = v
            break
    return out

# ========== Tabela/specyfikacja ==========

def extract_from_spec_table(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Parsuje pary klucz-wartość z typowych bloków specyfikacji (DL, TABLE, prosty grid).
    """
    spec: Dict[str, str] = {}

    # DL
    for spec_block in soup.select("dl, .specification, .product-parameters, .product-specs"):
        dts = spec_block.find_all("dt")
        dds = spec_block.find_all("dd")
        if len(dts) == len(dds) and len(dts) > 0:
            for dt, dd in zip(dts, dds):
                key = normalize_whitespace(dt.get_text(" ", strip=True)).lower()
                val = normalize_whitespace(dd.get_text(" ", strip=True))
                map_into_spec(spec, key, val)

    # TABLE
    for row in soup.select("table tr"):
        th = row.find(["th", "td"])
        tds = row.find_all("td")
        if th and len(tds) >= 1:
            key = normalize_whitespace(th.get_text(" ", strip=True)).lower()
            val = normalize_whitespace(tds[-1].get_text(" ", strip=True))
            map_into_spec(spec, key, val)

    # Prosty 2-kolumnowy grid (często używany w nowym front-endzie)
    for grid in soup.select("div.grid.grid-cols-2.text-sm"):
        divs = grid.find_all("div", recursive=False)
        if len(divs) == 2:
            key = normalize_whitespace(divs[0].get_text(" ", strip=True)).lower()
            val = normalize_whitespace(divs[1].get_text(" ", strip=True))
            map_into_spec(spec, key, val)

    return spec

def map_into_spec(spec: Dict[str, str], key_lower: str, val: str):
    mapping = [
        (["przekątna ekranu","przekatna ekranu","przekątna","przekatna"], "screen_size_inches"),
        (["rozdzielczość","rozdzielczosc","rozdzielczo\u015b\u0107"], "screen_resolution"),
        (["matryca","typ matrycy","rodzaj matrycy","panel"], "panel_type"),
        (["procesor","cpu"], "cpu"),
        (["karta graficzna","gpu","układ graficzny","uklad graficzny"], "gpu"),
        (["pamięć ram","pamieć ram","ram","pamięć","pamiec"], "ram_gb"),
        (["dysk","rodzaj dysku","typ dysku","nośnik danych","nosnik danych"], "storage_type"),
        (["pojemność dysku","pojemnosc dysku","pojemność nośnika","pojemnosc nosnika"], "storage_capacity_gb"),
        (["system operacyjny","system"], "os"),
        (["kolor","color"], "color"),
        (["podświetlenie klawiatury","podswietlenie klawiatury","backlight"], "keyboard_backlight"),
        (["dostępność","dostepnosc","availability"], "availability"),
        (["ocena","średnia ocena","srednia ocena","rating"], "rating"),
        (["liczba opinii","opinie","recenzje","review count"], "reviews_count"),
    ]
    for keys, target in mapping:
        if any(k in key_lower for k in keys):
            spec[target] = val
            return
