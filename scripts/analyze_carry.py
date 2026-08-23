#!/usr/bin/env python3
"""Analyze crypto carry at 2025-2026 Kraken rate levels.

Loads Kraken hourly funding data, computes carry P&L net of fees,
compares to Binance rates over the same period, runs quant_honesty checks.

Usage: python3 scripts/analyze_carry.py
"""
import csv
import os
import sys
from datetime import datetime, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from quant_honesty import honesty, format_report

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BINANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fin-trading-engine", "data", "funding")

KRAKEN_SYMBOLS = {"PF_XBTUSD": "BTC", "PF_ETHUSD": "ETH"}
BINANCE_SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}

CAPITAL = 50_000
NOTIONAL = 25_000
ENTRY_EXIT_BPS = 30


def load_kraken(symbol):
    path = os.path.join(DATA_DIR, f"kraken_funding_{symbol}.csv")
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
            rows.append({"timestamp": ts, "rate": float(r["relative_funding_rate"])})
    return rows


def load_binance(binance_symbol, start_dt, end_dt):
    path = os.path.join(BINANCE_DIR, f"{binance_symbol}.csv")
    if not os.path.exists(path):
        return []
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            ts = datetime.fromtimestamp(int(r["funding_time_ms"]) / 1000, tz=timezone.utc)
            if start_dt <= ts <= end_dt:
                rows.append({"timestamp": ts, "rate": float(r["funding_rate"])})
    return rows


def daily_returns(hourly_rates):
    by_day = {}
    for r in hourly_rates:
        day = r["timestamp"].date()
        by_day.setdefault(day, 0.0)
        by_day[day] += r["rate"]
    days = sorted(by_day.keys())
    return days, np.array([by_day[d] for d in days])


def monthly_returns(days, daily_ret):
    by_month = {}
    for d, r in zip(days, daily_ret):
        key = (d.year, d.month)
        by_month.setdefault(key, 0.0)
        by_month[key] += r
    months = sorted(by_month.keys())
    return months, np.array([by_month[m] for m in months])


def by_year_returns(days, daily_ret):
    by_year = {}
    for d, r in zip(days, daily_ret):
        by_year.setdefault(d.year, [])
        by_year[d.year].append(r)
    return by_year


def analyze_symbol(kraken_symbol):
    name = KRAKEN_SYMBOLS[kraken_symbol]
    print(f"\n{'='*60}")
    print(f"  {name} ({kraken_symbol}) — Kraken funding carry analysis")
    print(f"{'='*60}")

    rates = load_kraken(kraken_symbol)
    days, daily_ret = daily_returns(rates)
    months, monthly_ret = monthly_returns(days, daily_ret)

    ann_gross = float(np.sum(daily_ret)) / (len(days) / 365.25)
    ann_gross_pct = ann_gross * 100

    pct_positive_days = float(np.mean(daily_ret > 0)) * 100
    worst_neg_streak = 0
    current_streak = 0
    for r in daily_ret:
        if r < 0:
            current_streak += 1
            worst_neg_streak = max(worst_neg_streak, current_streak)
        else:
            current_streak = 0

    print(f"\n  Period: {days[0]} to {days[-1]} ({len(days)} days)")
    print(f"  Hourly data points: {len(rates)}")
    print(f"  Annualized gross carry: {ann_gross_pct:+.2f}%")
    print(f"  Days with positive funding: {pct_positive_days:.1f}%")
    print(f"  Worst negative-funding streak: {worst_neg_streak} days")

    entry_exit_cost_pct = ENTRY_EXIT_BPS / 100
    ann_net = ann_gross_pct - entry_exit_cost_pct
    net_dollar = NOTIONAL * ann_net / 100

    print(f"\n  Kraken costs:")
    print(f"    Entry+exit (round-trip): {ENTRY_EXIT_BPS} bps = {entry_exit_cost_pct:.2f}%")
    print(f"    Annualized net carry: {ann_net:+.2f}%")
    print(f"    Net annual $ on ${NOTIONAL:,} notional: ${net_dollar:+,.0f}")
    print(f"    Net annual $ on ${CAPITAL:,} capital: ${net_dollar:+,.0f}")

    ratio = ann_gross_pct / entry_exit_cost_pct if entry_exit_cost_pct > 0 else float("inf")
    passes_3x = ratio >= 3.0
    print(f"\n  Cost screen: gross/cost = {ratio:.1f}x {'PASS' if passes_3x else 'FAIL'} (need >= 3.0x)")

    monthly_bps = monthly_ret * 10000
    yr_groups = {}
    for m, r in zip(months, monthly_bps):
        yr_groups.setdefault(m[0], [])
        yr_groups[m[0]].append(r)

    h = honesty(monthly_bps, by_year=yr_groups, min_n=6)
    print(f"\n  Honesty check (monthly returns, bps):")
    print(format_report(h, unit="bp"))

    yr_data = by_year_returns(days, daily_ret)
    print(f"\n  By-year annualized carry:")
    for yr in sorted(yr_data.keys()):
        yr_arr = np.array(yr_data[yr])
        yr_ann = float(np.sum(yr_arr)) / (len(yr_arr) / 365.25) * 100
        print(f"    {yr}: {yr_ann:+.2f}%")

    binance_sym = BINANCE_SYMBOLS[name]
    start_dt = rates[0]["timestamp"]
    end_dt = rates[-1]["timestamp"]
    binance = load_binance(binance_sym, start_dt, end_dt)
    if binance:
        b_days, b_daily = daily_returns(binance)
        b_ann = float(np.sum(b_daily)) / (len(b_days) / 365.25) * 100
        print(f"\n  Binance comparison (same period):")
        print(f"    Binance {binance_sym} annualized: {b_ann:+.2f}%")
        print(f"    Kraken {kraken_symbol} annualized:  {ann_gross_pct:+.2f}%")
        diff = ann_gross_pct - b_ann
        print(f"    Difference: {diff:+.2f}% ({'Kraken higher' if diff > 0 else 'Kraken lower'})")
    else:
        print(f"\n  Binance comparison: no data found for {binance_sym}")

    return {
        "symbol": name,
        "ann_gross_pct": ann_gross_pct,
        "ann_net_pct": ann_net,
        "net_dollar": net_dollar,
        "passes_3x": passes_3x,
        "cost_ratio": ratio,
        "pct_positive_days": pct_positive_days,
        "tail_carried": h["tail_carried"],
        "honesty": h,
    }


def main():
    print("=" * 60)
    print("  CRYPTO CARRY PHASE 1: KRAKEN DATA VALIDATION")
    print("  Capital: ${:,}  |  Date: {}".format(CAPITAL, datetime.now(timezone.utc).strftime("%Y-%m-%d")))
    print("=" * 60)

    results = {}
    for sym in KRAKEN_SYMBOLS:
        results[sym] = analyze_symbol(sym)

    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    all_pass = True
    for sym, r in results.items():
        status = "PASS" if r["passes_3x"] and not r["tail_carried"] else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"  {r['symbol']}: gross={r['ann_gross_pct']:+.2f}% net={r['ann_net_pct']:+.2f}% "
              f"${r['net_dollar']:+,.0f}/yr  3x={r['passes_3x']}  tail={r['tail_carried']}  -> {status}")

    print(f"\n  Phase 1 verdict: {'PROCEED to Phase 2' if all_pass else 'REVIEW REQUIRED — see carry_compression.py'}")
    return results


if __name__ == "__main__":
    main()
