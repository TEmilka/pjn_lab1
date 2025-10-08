#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, time, random, argparse, json
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from parse_utils import (
    clean_price_pln, normalize_whitespace, guess_brand_model_from_name,
    extract_from_spec_table, ensure_dir, parse_float, parse_int
)

KOMPUTRONIK_CATEGORY_URL = "https://www.komputronik.pl/category/5022/laptopy.html"

REQUEST_TIMEOUT = (8, 20)  # (connect, read) timeouts
SLEEP_MIN = 20.00
SLEEP_MAX = 30.00
MAX_PAGES = 999
TARGET_MIN_RECORDS = 5

HEADERS_POOL = [
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
]

def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.8,
                    status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def polite_get(session: requests.Session, url: str) -> requests.Response:
    headers = random.choice(HEADERS_POOL)
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
    r = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r

def discover_product_links(html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    links = []
    for a in soup.select('a[href^="/product/"]'):
        href = a.get("href", "")
        if re.match(r"^/product/\d+/.+\.html$", href):
            links.append(urljoin(base_url, href))
    return list(dict.fromkeys(links))

def next_page_url(current_url: str, page_index: int) -> str:
    pr = urlparse(current_url)
    return f"{pr.scheme}://{pr.netloc}{pr.path}?p={page_index}"

# ====== Nowy zestaw kolumn ======

@dataclass
class ProductRow:
    product_id: Optional[str]
    name: Optional[str]
    brand: Optional[str]
    model: Optional[str]
    price_pln: Optional[float]
    availability: Optional[str]
    battery_capacity_wh: Optional[str]
    weight_kg: Optional[str]
    screen_size_inches: Optional[float]
    screen_resolution: Optional[str]
    panel_type: Optional[str]
    cpu: Optional[str]
    gpu: Optional[str]
    ram_type: Optional[str]
    storage_type: Optional[str]
    screen_refresh_rate_hz: Optional[str]
    os: Optional[str]
    body_material: Optional[str]
    warranty_months: Optional[str]
    product_url: Optional[str]

def extract_product_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"/product/(\d+)/", url)
    return m.group(1) if m else None

def parse_product_page(html: str, url: str) -> ProductRow:
    soup = BeautifulSoup(html, "lxml")

    # --- name/title ---
    name_el = soup.select_one("h1")
    name = normalize_whitespace(name_el.get_text(strip=True)) if name_el else None

    # --- price ---
    price_el = soup.select_one("[data-price-type='final'], .price, .product-price")
    price_pln = clean_price_pln(price_el.get_text(" ", strip=True)) if price_el else None

    # --- availability ---
    availability = None
    for s in soup.find_all(string=re.compile(r"(Dostępny|Niedostępny)", re.I)):
        cand = normalize_whitespace(s)
        if not availability or len(cand) < len(availability):
            availability = cand

    # --- specs ---
    spec_map = extract_from_spec_table(soup)

    brand, model = guess_brand_model_from_name(name) if name else (None, None)

    return ProductRow(
        product_id = extract_product_id_from_url(url),
        name = name,
        brand = brand,
        model = model,
        price_pln = price_pln,
        availability = spec_map.get("availability", availability),
        battery_capacity_wh = spec_map.get("battery_capacity_wh"),
        weight_kg = spec_map.get("weight_kg"),
        screen_size_inches = parse_float(spec_map.get("screen_size_inches")),
        screen_resolution = spec_map.get("screen_resolution"),
        panel_type = spec_map.get("panel_type"),
        cpu = spec_map.get("cpu"),
        gpu = spec_map.get("gpu"),
        ram_type = spec_map.get("ram_type"),
        storage_type = spec_map.get("storage_type"),
        screen_refresh_rate_hz = spec_map.get("screen_refresh_rate_hz"),
        os = spec_map.get("os"),
        body_material = spec_map.get("body_material"),
        warranty_months = spec_map.get("warranty_months"),
        product_url = url
    )

def scrape_category(output_dir: str, min_records: int = TARGET_MIN_RECORDS) -> pd.DataFrame:
    ensure_dir(output_dir)
    session = make_session()

    collected: List[Dict] = []
    seen = set()
    base_url = "https://www.komputronik.pl/"

    page = 1
    while len(collected) < min_records and page <= MAX_PAGES:
        page_url = KOMPUTRONIK_CATEGORY_URL if page == 1 else next_page_url(KOMPUTRONIK_CATEGORY_URL, page)
        print(f"[Page {page}] {page_url}")
        try:
            r = polite_get(session, page_url)
        except Exception as e:
            print("! Listing error:", e)
            break
        links = discover_product_links(r.text, base_url)
        if not links:
            break

        for link in links:
            if link in seen:
                continue
            seen.add(link)
            try:
                pr = polite_get(session, link)
            except Exception as e:
                print("  ! Product failed:", e)
                continue
            row = parse_product_page(pr.text, link)
            collected.append(asdict(row))
            print(f"  + {row.name} ({row.price_pln} zł)")
            if len(collected) >= min_records:
                break
        page += 1

    return pd.DataFrame(collected)

def save_outputs(df: pd.DataFrame, output_dir: str) -> Tuple[str, str]:
    ensure_dir(output_dir)
    csv_path = os.path.join(output_dir, "komputronik_laptops.csv")
    xlsx_path = os.path.join(output_dir, "komputronik_laptops.xlsx")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    return csv_path, xlsx_path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="data")
    parser.add_argument("--min-records", type=int, default=TARGET_MIN_RECORDS)
    args = parser.parse_args()

    df = scrape_category(args.outdir, args.min_records)
    cols = [
        "product_id","name","brand","model","price_pln","availability",
        "battery_capacity_wh","weight_kg",
        "screen_size_inches","screen_resolution","panel_type","cpu","gpu","ram_type",
        "storage_type","screen_refresh_rate_hz","os","body_material","warranty_months","product_url"
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]

    csv_path, xlsx_path = save_outputs(df, args.outdir)
    print(f"\nSaved to:\n - {csv_path}\n - {xlsx_path}\n")

if __name__ == "__main__":
    main()
