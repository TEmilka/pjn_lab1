#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Komputronik category scraper (hardcoded URL) for LAB 1.
- Builds a dataset (>=100 records, 20 attributes incl. price as target).
- Respects polite crawling: random sleep between requests, retry logic, and small concurrency (none by default).
- Output: CSV and XLSX in ./data/
"""
import os
import re
import time
import math
import random
import argparse
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter, Retry

from parse_utils import (
    clean_price_pln, normalize_whitespace, guess_brand_model_from_name,
    extract_specs_from_title, extract_from_spec_table, ensure_dir, parse_float, parse_int
)

# === Hardcoded category URL as required by the assignment ===
KOMPUTRONIK_CATEGORY_URL = "https://www.komputronik.pl/category/5022/laptopy.html"

# Polite crawling settings
REQUEST_TIMEOUT = (8, 20)  # (connect, read) timeouts
SLEEP_MIN = 20.00
SLEEP_MAX = 30.00
MAX_PAGES = 999  # we'll stop after collecting >=100, but cap just in case
TARGET_MIN_RECORDS = 3

HEADERS_POOL = [
    # rotate a few realistic desktop UAs
    {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15"},
    {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"},
]

def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.8,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    return s

def polite_get(session: requests.Session, url: str) -> requests.Response:
    headers = random.choice(HEADERS_POOL)
    # optional: accept-language for Polish site
    headers["Accept-Language"] = "pl-PL,pl;q=0.9,en;q=0.8"
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))
    r = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r

def discover_product_links(listing_html: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(listing_html, "lxml")
    links = []
    # product anchors usually inside cards; look for href starting with /product/
    for a in soup.select('a[href^="/product/"]'):
        href = a.get("href", "")
        # ignore non-product anchors that might also start with /product/preview etc.
        if re.match(r"^/product/\d+/.+\.html$", href):
            links.append(urljoin(base_url, href))
    # de-duplicate preserving order
    seen = set()
    uniq = []
    for u in links:
        if u not in seen:
            uniq.append(u)
            seen.add(u)
    return uniq

def next_page_url(current_url: str, page_index: int) -> str:
    # Komputronik supports ?p=N for pagination
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
    pr = urlparse(current_url)
    qs = dict(parse_qsl(pr.query))
    qs["p"] = str(page_index)
    new_pr = pr._replace(query=urlencode(qs))
    return urlunparse(new_pr)

@dataclass
class ProductRow:
    product_id: Optional[str]
    name: Optional[str]
    brand: Optional[str]
    model: Optional[str]
    price_pln: Optional[float]          # <- target attribute example
    availability: Optional[str]
    rating: Optional[float]
    reviews_count: Optional[int]
    screen_size_inches: Optional[float]
    screen_resolution: Optional[str]
    panel_type: Optional[str]
    cpu: Optional[str]
    gpu: Optional[str]
    ram_gb: Optional[int]
    storage_type: Optional[str]
    storage_capacity_gb: Optional[int]
    os: Optional[str]
    color: Optional[str]
    keyboard_backlight: Optional[bool]
    product_url: Optional[str]

def extract_product_id_from_url(url: str) -> Optional[str]:
    m = re.search(r"/product/(\d+)/", url)
    return m.group(1) if m else None

def parse_product_page(html: str, url: str) -> ProductRow:
    soup = BeautifulSoup(html, "lxml")

    # --- name/title ---
    # Try common title selectors
    name_el = soup.select_one("h1, h1.product-name, h1[data-testid='product-name']")
    name = normalize_whitespace(name_el.get_text(strip=True)) if name_el else None

    # --- price ---
    price_text_candidates = []
    for sel in [
        "[data-price-type='final']",      # nowy selektor dla Komputronika
        "[data-testid='product-price']",
        ".price, .price-final, .product-price",
        "[class*='price']"
    ]:
        el = soup.select_one(sel)
        if el:
            price_text_candidates.append(el.get_text(" ", strip=True))
    price_pln = None
    for t in price_text_candidates:
        price_pln = clean_price_pln(t)
        if price_pln is not None:
            break

    # --- availability ---
    availability = None
    avail_el = soup.find(lambda tag: tag.name in ["div","span","p"] and ("dostęp" in tag.get_text(strip=True).lower() or "magazyn" in tag.get_text(strip=True).lower()))
    if avail_el:
        availability = normalize_whitespace(avail_el.get_text(" ", strip=True))

    # --- rating / reviews ---
    rating = None
    reviews_count = None
    rating_el = soup.find(lambda tag: tag.name in ["div","span"] and ("gwiaz" in tag.get_text(strip=True).lower() or "ocen" in tag.get_text(strip=True).lower()))
    if rating_el:
        txt = rating_el.get_text(" ", strip=True)
        # try to capture "4,7/5" or "4.7"
        m = re.search(r"(\d+[.,]\d+)", txt)
        if m:
            rating = parse_float(m.group(1))
        m2 = re.search(r"(\d+)\s*(opini|recenz|ocen)", txt.lower())
        if m2:
            reviews_count = parse_int(m2.group(1))

    # --- specification table ---
    spec_map = extract_from_spec_table(soup)

    # derived attributes with fallbacks from title
    brand, model = guess_brand_model_from_name(name) if name else (None, None)

    from_title = extract_specs_from_title(name or "")
    for k, v in from_title.items():
        spec_map.setdefault(k, v)

    # Normalize/assign fields
    screen_size_inches = parse_float(spec_map.get("screen_size_inches"))
    screen_resolution = spec_map.get("screen_resolution")
    panel_type = spec_map.get("panel_type")
    cpu = spec_map.get("cpu")
    gpu = spec_map.get("gpu")
    ram_gb = parse_int(spec_map.get("ram_gb"))
    storage_type = spec_map.get("storage_type")
    storage_capacity_gb = parse_int(spec_map.get("storage_capacity_gb"))
    os = spec_map.get("os")
    color = spec_map.get("color")
    keyboard_backlight = None
    kb = (spec_map.get("keyboard_backlight") or "").lower()
    if kb:
        keyboard_backlight = "tak" in kb or "podś" in kb or "podsw" in kb or kb in ("yes", "true", "1")

    return ProductRow(
        product_id = extract_product_id_from_url(url),
        name = name,
        brand = brand,
        model = model,
        price_pln = price_pln,
        availability = availability,
        rating = rating,
        reviews_count = reviews_count,
        screen_size_inches = screen_size_inches,
        screen_resolution = screen_resolution,
        panel_type = panel_type,
        cpu = cpu,
        gpu = gpu,
        ram_gb = ram_gb,
        storage_type = storage_type,
        storage_capacity_gb = storage_capacity_gb,
        os = os,
        color = color,
        keyboard_backlight = keyboard_backlight,
        product_url = url
    )

def scrape_category(output_dir: str, min_records: int = TARGET_MIN_RECORDS) -> pd.DataFrame:
    ensure_dir(output_dir)
    session = make_session()

    collected: List[Dict] = []
    product_seen = set()

    base_url = "{uri.scheme}://{uri.netloc}/".format(uri=urlparse(KOMPUTRONIK_CATEGORY_URL))

    page = 1
    while len(collected) < min_records and page <= MAX_PAGES:
        page_url = KOMPUTRONIK_CATEGORY_URL if page == 1 else next_page_url(KOMPUTRONIK_CATEGORY_URL, page)
        print(f"[Category] Fetch page {page}: {page_url}")
        try:
            r = polite_get(session, page_url)
        except Exception as e:
            print(f"  ! Failed listing page {page}: {e}")
            break

        links = discover_product_links(r.text, base_url)
        print(f"  - Found {len(links)} product links")

        if not links and page > 1:
            print("  - No more links; stopping pagination.")
            break

        for prod_url in links:
            if prod_url in product_seen:
                continue
            product_seen.add(prod_url)
            try:
                pr = polite_get(session, prod_url)
            except Exception as e:
                print(f"    ! Failed product: {prod_url} -> {e}")
                continue

            row = parse_product_page(pr.text, prod_url)
            collected.append(asdict(row))

            print(f"    + {row.name or '[no name]'} | price={row.price_pln} | url={prod_url}")
            if len(collected) >= min_records:
                break

        page += 1

    df = pd.DataFrame(collected)
    return df

def save_outputs(df: pd.DataFrame, output_dir: str) -> Tuple[str, str]:
    ensure_dir(output_dir)
    csv_path = os.path.join(output_dir, "komputronik_laptops.csv")
    xlsx_path = os.path.join(output_dir, "komputronik_laptops.xlsx")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="data")
    return csv_path, xlsx_path

def main():
    parser = argparse.ArgumentParser(description="Komputronik category scraper (hardcoded URL).")
    parser.add_argument("--outdir", default="data", help="Output directory for CSV/XLSX (default: ./data)")
    parser.add_argument("--min-records", type=int, default=TARGET_MIN_RECORDS, help="Minimum number of records to collect (default: 100)")
    args = parser.parse_args()

    df = scrape_category(args.outdir, min_records=args.min_records)

    # Ensure 20 attributes even if some missing
    cols = [
        "product_id","name","brand","model","price_pln","availability","rating","reviews_count",
        "screen_size_inches","screen_resolution","panel_type","cpu","gpu","ram_gb",
        "storage_type","storage_capacity_gb","os","color","keyboard_backlight","product_url"
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols]

    csv_path, xlsx_path = save_outputs(df, args.outdir)

    print(f"\nSaved:\n - {csv_path}\n - {xlsx_path}\n")
    print(f"Rows: {len(df)} | Columns: {len(df.columns)}")
    if len(df) < TARGET_MIN_RECORDS:
        print("WARNING: Collected fewer than the target records. Consider increasing pages or checking site structure/selectors.")

if __name__ == "__main__":
    main()
