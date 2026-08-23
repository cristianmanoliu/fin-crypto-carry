#!/usr/bin/env python3
"""Fetch historical funding rates from Kraken Futures API (v4).

Kraken provides ~1 year of hourly funding data. No auth required.
Saves to data/kraken_funding_{symbol}.csv.

Usage: python3 scripts/fetch_kraken_funding.py
"""
import csv
import os
import requests

API_URL = "https://futures.kraken.com/derivatives/api/v4/historicalfundingrates"
SYMBOLS = ["PF_XBTUSD", "PF_ETHUSD"]
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def fetch_funding(symbol):
    resp = requests.get(API_URL, params={"symbol": symbol}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data["result"] != "success":
        raise RuntimeError(f"API error for {symbol}: {data}")
    return data["rates"]


def save_csv(rates, symbol):
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"kraken_funding_{symbol}.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "funding_rate", "relative_funding_rate"])
        for r in rates:
            w.writerow([r["timestamp"], r["fundingRate"], r["relativeFundingRate"]])
    return path


def main():
    for sym in SYMBOLS:
        print(f"Fetching {sym}...")
        rates = fetch_funding(sym)
        path = save_csv(rates, sym)
        print(f"  {len(rates)} hourly rates -> {path}")
        print(f"  Range: {rates[0]['timestamp']} to {rates[-1]['timestamp']}")


if __name__ == "__main__":
    main()
