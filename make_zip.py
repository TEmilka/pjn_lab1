#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pack LAB deliverable zip:
LAB1 <Nazwisko1> <Imie1> <Nazwisko2> <Imie2>.zip
It includes:
- source code (scraper.py, parse_utils.py, requirements.txt, README.md)
- dataset files from ./data (CSV/XLSX), if present
"""
import argparse
import os
import zipfile

FILES = ["scraper.py", "parse_utils.py", "requirements.txt", "README.md"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--first", required=True, help="Imię 1")
    ap.add_argument("--last", required=True, help="Nazwisko 1")
    ap.add_argument("--first2", default="", help="Imię 2 (opcjonalnie)")
    ap.add_argument("--last2", default="", help="Nazwisko 2 (opcjonalnie)")
    ap.add_argument("--out", default=".", help="Katalog wyjściowy (domyślnie bieżący)")
    args = ap.parse_args()

    parts = ["LAB1", args.last, args.first]
    if args.last2 or args.first2:
        parts += [args.last2, args.first2]
    zip_name = " ".join([p for p in parts if p]).strip() + ".zip"
    zip_path = os.path.join(args.out, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in FILES:
            if os.path.exists(fn):
                z.write(fn, arcname=fn)
        # include dataset if present
        if os.path.isdir("data"):
            for root, _, files in os.walk("data"):
                for f in files:
                    if f.lower().endswith((".csv",".xlsx")):
                        full = os.path.join(root, f)
                        arc = os.path.relpath(full, ".")
                        z.write(full, arcname=arc)

    print(f"Created: {zip_path}")

if __name__ == "__main__":
    main()
