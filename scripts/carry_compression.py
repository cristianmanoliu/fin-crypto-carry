#!/usr/bin/env python3
"""Model carry compression trajectory and extrapolate.

Uses Binance historical data (2020-2026) for the long-term trend, overlaid
with Kraken data (2025-2026) for venue-specific validation.

Key question: if the declining trajectory continues, when does carry
drop below 1% annualized? Below cost breakeven?

Usage: python3 scripts/carry_compression.py
"""
import csv
import os
from datetime import datetime, timezone

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BINANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fin-trading-engine", "data", "funding")

ENTRY_EXIT_BPS = 30
BREAKEVEN_PCT = ENTRY_EXIT_BPS / 100


def load_binance_full(symbol):
    path = os.path.join(BINANCE_DIR, f"{symbol}.csv")
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            ts = datetime.fromtimestamp(int(r["funding_time_ms"]) / 1000, tz=timezone.utc)
            rows.append({"timestamp": ts, "rate": float(r["funding_rate"])})
    return rows


def load_kraken(symbol):
    path = os.path.join(DATA_DIR, f"kraken_funding_{symbol}.csv")
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            rows.append({"timestamp": ts, "rate": float(r["relative_funding_rate"])})
    return rows


def yearly_annualized(rates):
    by_year = {}
    for r in rates:
        yr = r["timestamp"].year
        by_year.setdefault(yr, [])
        by_year[yr].append(r)

    result = {}
    for yr, entries in sorted(by_year.items()):
        n_days = len(set(e["timestamp"].date() for e in entries))
        if n_days < 30:
            continue
        total_rate = sum(e["rate"] for e in entries)
        ann = total_rate / (n_days / 365.25)
        result[yr] = ann * 100
    return result


def fit_trend(years_data):
    years = np.array(list(years_data.keys()), dtype=float)
    rates = np.array(list(years_data.values()))
    coeffs = np.polyfit(years, rates, 1)
    return coeffs[0], coeffs[1]


def main():
    print("=" * 60)
    print("  CARRY COMPRESSION MODEL")
    print("=" * 60)

    for name, binance_sym, kraken_sym in [("BTC", "BTCUSDT", "PF_XBTUSD"),
                                           ("ETH", "ETHUSDT", "PF_ETHUSD")]:
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

        binance = load_binance_full(binance_sym)
        b_yearly = yearly_annualized(binance)
        print(f"\n  Binance annual carry (historical):")
        for yr, rate in sorted(b_yearly.items()):
            marker = " <-- below breakeven" if rate < BREAKEVEN_PCT else ""
            print(f"    {yr}: {rate:+.2f}%{marker}")

        try:
            kraken = load_kraken(kraken_sym)
            k_yearly = yearly_annualized(kraken)
            print(f"\n  Kraken annual carry (venue-specific):")
            for yr, rate in sorted(k_yearly.items()):
                marker = " <-- below breakeven" if rate < BREAKEVEN_PCT else ""
                print(f"    {yr}: {rate:+.2f}%{marker}")
        except FileNotFoundError:
            print(f"\n  Kraken data not found — run fetch_kraken_funding.py first")
            k_yearly = {}

        slope, intercept = fit_trend(b_yearly)
        print(f"\n  Linear trend (Binance): slope = {slope:+.3f}%/year")
        print(f"  Carry declining by ~{abs(slope):.1f}% per year")

        for target_yr in [2027, 2028, 2029]:
            projected = slope * target_yr + intercept
            print(f"    {target_yr} projected: {projected:+.2f}%")

        if slope < 0:
            breakeven_year = (BREAKEVEN_PCT - intercept) / slope
            zero_year = -intercept / slope
            print(f"\n  Breakeven ({BREAKEVEN_PCT:.2f}%) crossing: ~{breakeven_year:.1f}")
            print(f"  Zero crossing: ~{zero_year:.1f}")
        else:
            print(f"\n  Trend is flat or rising — no compression detected")

        current_rate = list(k_yearly.values())[-1] if k_yearly else list(b_yearly.values())[-1]

        print(f"\n  Current-era rate: {current_rate:+.2f}%")
        if current_rate < BREAKEVEN_PCT:
            print(f"  ** BELOW BREAKEVEN — carry does not clear entry/exit costs **")
        elif current_rate < 1.0:
            print(f"  ** MARGINAL — carry < 1%, operational complexity may not justify **")
        else:
            print(f"  ** VIABLE — carry clears costs **")

    print(f"\n{'='*60}")
    print("  GO / NO-GO DECISION")
    print(f"{'='*60}")
    print("""
  KILL if:
  - Current-era carry (2025-2026) is below breakeven (0.30%)
  - Linear extrapolation shows < 1% by 2027
  - Carry went negative in 2026

  PROCEED if:
  - Current-era carry > 1% on Kraken data
  - 3x cost screen passes
  - Trajectory suggests > 1 year of viable carry remaining
  """)


if __name__ == "__main__":
    main()
