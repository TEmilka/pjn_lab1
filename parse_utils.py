# -*- coding: utf-8 -*-
import os, re, time, random
from typing import Dict, Optional
from bs4 import BeautifulSoup

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def normalize_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def clean_price_pln(text: str):
    """
    Extract a price in PLN (float) from messy text, accepting formats like:
    "3 499,00 zł", "3499 zł", "3.499,00 PLN", etc.
    """
    if not text:
        return None
    t = text.lower()
    # remove currency words/symbols
    t = t.replace("pln", "").replace("zł", "").replace("z\u0142", "")
    # keep digits, separators
    t = re.sub(r"[^0-9,.\s]", "", t)
    # remove spaces used as thousands sep
    t = t.replace(" ", "").replace("\u00a0","")
    # prefer comma as decimal
    if "," in t and "." in t:
        # assume dot as thousands sep; remove dots
        t = t.replace(".", "")
        t = t.replace(",", ".")
    elif "," in t and "." not in t:
        t = t.replace(",", ".")
    try:
        return float(t)
    except:
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

def guess_brand_model_from_name(name: Optional[str]):
    if not name:
        return (None, None)
    # heuristic: brand is first token (letter group), model is rest with digits/letters
    tokens = name.split()
    brand = tokens[0] if tokens else None
    # model: find token(s) with letters+digits like "15-eh1000nw", "i5-13420H", etc.
    model = None
    m = re.search(r"([A-Za-z]{1,}[A-Za-z0-9\-]+)", name)
    if m:
        model = m.group(1)
    return (brand, model)

def extract_specs_from_title(title: str) -> Dict[str, str]:
    """
    Parse common specs embedded in product title (as seen in Komputronik listing):
    e.g. "Lenovo Ideapad Slim 3-15 - Core i5-13420H | 15,3’’-WUXGA | 16GB | 512GB | Podśw. klawiatura | Win11Home | Niebieski"
    """
    out: Dict[str, str] = {}
    t = title.replace("’’", "\"").replace("’", "'")
    # screen size
    m = re.search(r"(\d{1,2}[,.]\d)\s*['\"”]?", t)
    if m:
        out["screen_size_inches"] = m.group(1).replace(",", ".")
    # resolution or panel
    if "WUXGA" in t.upper():
        out["screen_resolution"] = "WUXGA"
    if "FHD" in t.upper():
        out["screen_resolution"] = "FHD"
    if "OLED" in t.upper():
        out["panel_type"] = "OLED"
    if "IPS" in t.upper():
        out["panel_type"] = "IPS"
    # RAM
    m = re.search(r"(\d+)\s*GB", t, flags=re.I)
    if m:
        out["ram_gb"] = m.group(1)
    # storage capacity
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
    # keyboard backlight
    if re.search(r"pod[\w\.]*\s*klawiatura|podśw", t, flags=re.I):
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

def extract_from_spec_table(soup: BeautifulSoup) -> Dict[str, str]:
    """
    Try to parse key-value pairs from a spec table common on product pages.
    Works with both <table> and <dl> based blocks.
    """
    spec: Dict[str, str] = {}
    # DL pairs
    for spec_block in soup.select("dl, .specification, .product-parameters, .product-specs"):
        dts = spec_block.find_all("dt")
        dds = spec_block.find_all("dd")
        if len(dts) == len(dds) and len(dts) > 0:
            for dt, dd in zip(dts, dds):
                key = normalize_whitespace(dt.get_text(" ", strip=True)).lower()
                val = normalize_whitespace(dd.get_text(" ", strip=True))
                map_into_spec(spec, key, val)
    # Table rows
    for row in soup.select("table tr"):
        th = row.find(["th", "td"])
        tds = row.find_all("td")
        if th and len(tds) >= 1:
            key = normalize_whitespace(th.get_text(" ", strip=True)).lower()
            val = normalize_whitespace(tds[-1].get_text(" ", strip=True))
            map_into_spec(spec, key, val)
    return spec

def map_into_spec(spec: Dict[str, str], key_lower: str, val: str):
    # Map various Polish labels to normalized fields
    mapping = [
        (["przekątna ekranu", "przekatna ekranu"], "screen_size_inches"),
        (["rozdzielczość", "rozdzielczosc", "rozdzielczo\u015b\u0107"], "screen_resolution"),
        (["matryca", "typ matrycy", "rodzaj matrycy", "panel"], "panel_type"),
        (["procesor", "cpu"], "cpu"),
        (["karta graficzna", "gpu", "układ graficzny"], "gpu"),
        (["pamięć ram", "pamieć ram", "ram", "pamięć", "pamiec"], "ram_gb"),
        (["dysk", "rodzaj dysku", "typ dysku"], "storage_type"),
        (["pojemność dysku", "pojemnosc dysku", "pojemność nośnika"], "storage_capacity_gb"),
        (["system operacyjny", "system"], "os"),
        (["kolor"], "color"),
        (["podświetlenie klawiatury", "podswietlenie klawiatury"], "keyboard_backlight"),
        (["dostępność", "dostepnosc"], "availability"),
        (["ocena", "średnia ocena", "srednia ocena"], "rating"),
        (["liczba opinii", "opinie", "recenzje"], "reviews_count"),
    ]
    for keys, target in mapping:
        if any(k in key_lower for k in keys):
            spec[target] = val
            return

