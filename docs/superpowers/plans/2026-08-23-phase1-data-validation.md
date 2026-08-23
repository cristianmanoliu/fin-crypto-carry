# Phase 1: Data Validation — Kill or Confirm

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fetch Kraken historical funding rates, compare to Binance, run honesty checks at 2025-2026 rate levels, model carry compression, and produce a go/no-go decision.

**Architecture:** Three scripts + one shared utility. `fetch_kraken_funding.py` pulls data from the Kraken v4 API and saves CSV. `analyze_carry.py` computes carry P&L at current rate levels with Kraken's fee structure and runs `quant_honesty.py`. `carry_compression.py` fits the declining funding rate trajectory and extrapolates. All three feed `scripts/go_nogo.py` which prints the final verdict.

**Tech Stack:** Python 3, numpy, requests (for API calls). `quant_honesty.py` copied from `fin-trading-engine`.

**Spec:** `README.md` Phase 1, lines 76-88.

## Global Constraints

- No package manager beyond pip. Only deps: `numpy`, `requests`.
- All scripts runnable standalone: `python3 scripts/<name>.py`
- Data stored in `data/` directory as CSV.
- Binance comparison data read from `../fin-trading-engine/data/funding/BTCUSDT.csv` and `ETHUSDT.csv`.
- Copy `quant_honesty.py` from `../fin-trading-engine/scripts/quant_honesty.py` into `scripts/`.

---

### Task 1: Project scaffolding + fetch Kraken funding rates

**Files:**
- Create: `requirements.txt`
- Create: `scripts/fetch_kraken_funding.py`
- Create: `data/` (directory)
- Copy: `scripts/quant_honesty.py` (from `../fin-trading-engine/scripts/quant_honesty.py`)

**Interfaces:**
- Produces: `data/kraken_funding_PF_XBTUSD.csv` and `data/kraken_funding_PF_ETHUSD.csv`
  - Columns: `timestamp,funding_rate,relative_funding_rate`
  - `timestamp`: ISO 8601 UTC string
  - `relative_funding_rate`: per-hour fractional rate (e.g. 5e-06)

- [ ] **Step 1: Create `requirements.txt`**

```
numpy
requests
```

- [ ] **Step 2: Copy `quant_honesty.py`**

```bash
cp ../fin-trading-engine/scripts/quant_honesty.py scripts/quant_honesty.py
```

Verify selftest:
```bash
python3 scripts/quant_honesty.py --selftest
```
Expected: `selftest OK`

- [ ] **Step 3: Write `scripts/fetch_kraken_funding.py`**

```python
#!/usr/bin/env python3
"""Fetch historical funding rates from Kraken Futures API (v4).

Kraken provides ~1 year of hourly funding data. No auth required.
Saves to data/kraken_funding_{symbol}.csv.

Usage: python3 scripts/fetch_kraken_funding.py
"""
import csv
import os
import sys
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
```

- [ ] **Step 4: Run fetch and verify**

```bash
python3 scripts/fetch_kraken_funding.py
```

Expected: two CSV files in `data/`, each with ~8800 rows spanning Aug 2025 - Aug 2026.

Verify:
```bash
head -3 data/kraken_funding_PF_XBTUSD.csv
wc -l data/kraken_funding_PF_XBTUSD.csv
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt scripts/fetch_kraken_funding.py scripts/quant_honesty.py
git commit -m "feat: add Kraken funding rate fetcher and quant_honesty"
```

Note: do NOT commit `data/` — add to `.gitignore` in next step.

---

### Task 2: Analyze carry at current rate levels

**Files:**
- Create: `.gitignore`
- Create: `scripts/analyze_carry.py`

**Interfaces:**
- Consumes: `data/kraken_funding_PF_XBTUSD.csv`, `data/kraken_funding_PF_ETHUSD.csv` (from Task 1)
- Consumes: `quant_honesty.screen()` and `quant_honesty.honesty()` (from Task 1 copy)
- Produces: printed report with go/no-go metrics

**Kraken fee model (Tier 1 retail, confirmed from API):**
- Taker fee: 0.05% (5 bps)
- Maker fee: 0.02% (2 bps)
- Funding: hourly (24 payments/day, not 3 like Binance)
- Entry cost: spot buy (taker ~10 bps on Kraken spot) + perp short (5 bps futures taker) = 15 bps
- Exit cost: same = 15 bps
- Round-trip entry/exit: 30 bps
- Capital: $50k ($25k spot + $25k perp margin), so the carry applies to $25k notional

**Binance comparison data:**
- Path: `../fin-trading-engine/data/funding/BTCUSDT.csv` and `ETHUSDT.csv`
- Format: `funding_time_ms,funding_rate` (8-hourly, rate as fraction e.g. 0.0001 = 1 bp)

- [ ] **Step 1: Create `.gitignore`**

```
data/
__pycache__/
*.pyc
```

- [ ] **Step 2: Write `scripts/analyze_carry.py`**

```python
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
from quant_honesty import screen, honesty, format_report

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BINANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fin-trading-engine", "data", "funding")

KRAKEN_SYMBOLS = {"PF_XBTUSD": "BTC", "PF_ETHUSD": "ETH"}
BINANCE_SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}

CAPITAL = 50_000
NOTIONAL = 25_000  # half in spot, half in perp margin
ENTRY_EXIT_BPS = 30  # round-trip: spot taker + perp taker, both sides


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
    """Aggregate hourly rates into daily returns (sum of hourly rates per day)."""
    by_day = {}
    for r in hourly_rates:
        day = r["timestamp"].date()
        by_day.setdefault(day, 0.0)
        by_day[day] += r["rate"]
    days = sorted(by_day.keys())
    return days, np.array([by_day[d] for d in days])


def monthly_returns(days, daily_ret):
    """Aggregate daily returns into monthly returns."""
    by_month = {}
    for d, r in zip(days, daily_ret):
        key = (d.year, d.month)
        by_month.setdefault(key, 0.0)
        by_month[key] += r
    months = sorted(by_month.keys())
    return months, np.array([by_month[m] for m in months])


def by_year_returns(days, daily_ret):
    """Group daily returns by year for honesty check."""
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

    # Short receives positive funding, pays negative funding
    # relative_funding_rate is already the fraction short receives per hour
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

    # Entry/exit cost
    entry_exit_cost_pct = ENTRY_EXIT_BPS / 100
    holding_period_months = len(months)
    ann_cost = entry_exit_cost_pct  # amortized over assumed 1 trade/year
    ann_net = ann_gross_pct - ann_cost
    net_dollar = NOTIONAL * ann_net / 100

    print(f"\n  Kraken costs:")
    print(f"    Entry+exit (round-trip): {ENTRY_EXIT_BPS} bps = {entry_exit_cost_pct:.2f}%")
    print(f"    No ongoing fees beyond funding (funding IS the P&L)")
    print(f"    Annualized net carry: {ann_net:+.2f}%")
    print(f"    Net annual $ on ${NOTIONAL:,} notional: ${net_dollar:+,.0f}")
    print(f"    Net annual $ on ${CAPITAL:,} capital: ${net_dollar:+,.0f}")

    # Cost screen: does gross >= 3x cost?
    # For carry, "gross" is annual rate, "cost" is entry/exit amortized
    ratio = ann_gross_pct / ann_cost if ann_cost > 0 else float("inf")
    passes_3x = ratio >= 3.0
    print(f"\n  Cost screen: gross/cost = {ratio:.1f}x {'PASS' if passes_3x else 'FAIL'} (need >= 3.0x)")

    # Honesty battery on monthly returns (in bps for readability)
    monthly_bps = monthly_ret * 10000
    yr_groups = {}
    for m, r in zip(months, monthly_bps):
        yr_groups.setdefault(m[0], [])
        yr_groups[m[0]].append(r)

    h = honesty(monthly_bps, by_year=yr_groups, min_n=6)
    print(f"\n  Honesty check (monthly returns, bps):")
    print(format_report(h, unit="bp"))

    # By-year breakdown
    yr_data = by_year_returns(days, daily_ret)
    print(f"\n  By-year annualized carry:")
    for yr in sorted(yr_data.keys()):
        yr_arr = np.array(yr_data[yr])
        yr_ann = float(np.sum(yr_arr)) / (len(yr_arr) / 365.25) * 100
        print(f"    {yr}: {yr_ann:+.2f}%")

    # Binance comparison over same period
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

    # Summary verdict
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
```

- [ ] **Step 3: Run analysis**

```bash
python3 scripts/analyze_carry.py
```

Review output. Key questions:
1. Does annualized gross carry at Kraken 2025-2026 rates exceed 3x entry/exit cost?
2. Does the honesty battery pass (no tail-carried flag)?
3. How does Kraken compare to Binance over the same period?

- [ ] **Step 4: Commit**

```bash
git add .gitignore scripts/analyze_carry.py
git commit -m "feat: add carry analysis at current Kraken rate levels"
```

---

### Task 3: Carry compression model + go/no-go

**Files:**
- Create: `scripts/carry_compression.py`

**Interfaces:**
- Consumes: `data/kraken_funding_PF_XBTUSD.csv`, `data/kraken_funding_PF_ETHUSD.csv` (from Task 1)
- Consumes: Binance CSVs from `../fin-trading-engine/data/funding/` (for long-term trajectory)
- Produces: printed report with trend fit, extrapolation, and final go/no-go

- [ ] **Step 1: Write `scripts/carry_compression.py`**

```python
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
import sys
from datetime import datetime, timezone

import numpy as np

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BINANCE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fin-trading-engine", "data", "funding")

ENTRY_EXIT_BPS = 30
BREAKEVEN_PCT = ENTRY_EXIT_BPS / 100  # 0.30% annualized minimum to break even


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
    """Compute annualized carry per calendar year."""
    by_year = {}
    for r in rates:
        yr = r["timestamp"].year
        by_year.setdefault(yr, [])
        by_year[yr].append(r["rate"])

    result = {}
    for yr, vals in sorted(by_year.items()):
        arr = np.array(vals)
        # Annualize: sum of rates in year, scaled to 365.25 days
        n_days = len(set(r["timestamp"].date() for r in rates if r["timestamp"].year == yr))
        if n_days < 30:
            continue
        ann = float(np.sum(arr)) / (n_days / 365.25)
        result[yr] = ann * 100  # as percent
    return result


def fit_trend(years_data):
    """Linear regression on year vs annualized carry."""
    years = np.array(list(years_data.keys()), dtype=float)
    rates = np.array(list(years_data.values()))
    coeffs = np.polyfit(years, rates, 1)
    slope, intercept = coeffs
    return slope, intercept


def main():
    print("=" * 60)
    print("  CARRY COMPRESSION MODEL")
    print("=" * 60)

    for name, binance_sym, kraken_sym in [("BTC", "BTCUSDT", "PF_XBTUSD"),
                                           ("ETH", "ETHUSDT", "PF_ETHUSD")]:
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

        # Binance long-term trajectory
        binance = load_binance_full(binance_sym)
        b_yearly = yearly_annualized(binance)
        print(f"\n  Binance annual carry (historical):")
        for yr, rate in sorted(b_yearly.items()):
            marker = " <-- breakeven" if rate < BREAKEVEN_PCT else ""
            print(f"    {yr}: {rate:+.2f}%{marker}")

        # Kraken overlay
        try:
            kraken = load_kraken(kraken_sym)
            k_yearly = yearly_annualized(kraken)
            print(f"\n  Kraken annual carry (venue-specific):")
            for yr, rate in sorted(k_yearly.items()):
                marker = " <-- breakeven" if rate < BREAKEVEN_PCT else ""
                print(f"    {yr}: {rate:+.2f}%{marker}")
        except FileNotFoundError:
            print(f"\n  Kraken data not found — run fetch_kraken_funding.py first")
            k_yearly = {}

        # Trend fit on Binance (longer history)
        slope, intercept = fit_trend(b_yearly)
        print(f"\n  Linear trend (Binance): slope = {slope:+.3f}%/year")
        print(f"  Interpretation: carry declining by ~{abs(slope):.1f}% per year")

        # Extrapolation
        for target_yr in [2027, 2028, 2029]:
            projected = slope * target_yr + intercept
            print(f"    {target_yr} projected: {projected:+.2f}%")

        # When does it hit breakeven?
        if slope < 0:
            breakeven_year = (BREAKEVEN_PCT - intercept) / slope
            zero_year = -intercept / slope
            print(f"\n  Breakeven ({BREAKEVEN_PCT:.2f}%) crossing: ~{breakeven_year:.1f}")
            print(f"  Zero crossing: ~{zero_year:.1f}")
        else:
            print(f"\n  Trend is flat or rising — no compression detected")

        # Verdict for this symbol
        current_rate = list(b_yearly.values())[-1] if b_yearly else 0
        if k_yearly:
            current_rate = list(k_yearly.values())[-1] if k_yearly else current_rate

        print(f"\n  Current-era rate: {current_rate:+.2f}%")
        if current_rate < BREAKEVEN_PCT:
            print(f"  ** BELOW BREAKEVEN — carry does not clear entry/exit costs **")
        elif current_rate < 1.0:
            print(f"  ** MARGINAL — carry < 1%, operational complexity may not justify **")
        else:
            print(f"  ** VIABLE — carry clears costs **")

    # Final go/no-go
    print(f"\n{'='*60}")
    print("  GO / NO-GO DECISION")
    print(f"{'='*60}")
    print("""
  Run analyze_carry.py for the detailed Kraken-specific verdict.
  This model provides the trajectory context:

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
```

- [ ] **Step 2: Run compression model**

```bash
python3 scripts/carry_compression.py
```

- [ ] **Step 3: Commit**

```bash
git add scripts/carry_compression.py
git commit -m "feat: add carry compression model and go/no-go framework"
```

---

### Task 4: Run the full pipeline and record verdict

- [ ] **Step 1: Run all three scripts in sequence**

```bash
python3 scripts/fetch_kraken_funding.py
python3 scripts/analyze_carry.py
python3 scripts/carry_compression.py
```

- [ ] **Step 2: Save output to `results/`**

```bash
mkdir -p results
python3 scripts/analyze_carry.py > results/phase1_analysis_$(date +%Y-%m-%d).txt 2>&1
python3 scripts/carry_compression.py >> results/phase1_analysis_$(date +%Y-%m-%d).txt 2>&1
```

- [ ] **Step 3: Commit results**

```bash
git add results/
git commit -m "results: phase 1 data validation output"
```

- [ ] **Step 4: Review verdict and update README**

Based on the output, update the README's "What to do next" section with the Phase 1 finding. If the verdict is KILL, document why and close the project. If PROCEED, document the validated numbers and move to Phase 2 design.
