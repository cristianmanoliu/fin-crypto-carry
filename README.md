# fin-crypto-carry

Delta-neutral crypto carry trade. Long spot + short perpetual futures on the
same asset. Collect funding rate payments (shorts receive when rate is positive,
which is ~88% of the time).

## Origin

Spike in `fin-trading-engine` (`results/spike_three_strategies_2026-08-21.md`).
6.4-year backtest using Binance historical funding CSVs as a proxy for Kraken.

| Symbol | Sharpe | Ann ret | Max DD | Monthly WR | t-stat | Tail |
|---|---|---|---|---|---|---|
| **BTC** | **2.40** | **+5.5%** | **0.4%** | **88.3%** | **+5.97** | **OK** |
| **ETH** | **2.25** | **+6.7%** | **0.9%** | **88.3%** | **+5.57** | **OK** |

Cost as % of gross: 10.5% (BTC), 8.8% (ETH). Both pass 3× cost screen.

## What the spike proved

- The structural carry is real: speculators pay to be long, carry traders
  collect the funding rate. 87-88% of days have positive funding.
- Highest Sharpe of any strategy tested across the entire fin-trading-engine
  project (85 perp trials + 3 strategy-class spikes).
- Max drawdown < 1% — the position is delta-neutral so price moves cancel.
- The trade is well-documented academically and run by multiple institutional
  quant funds.

## What the spike did NOT prove — CRITICAL CAUTION

- **Used Binance data as proxy.** Kraken's funding rate mechanism is similar but
  rates differ. Must validate with actual Kraken historical funding rates.
- **The carry is declining.** By-year trajectory:

  | Year | BTC | ETH |
  |---|---|---|
  | 2020 | +8.3% | +13.9% |
  | 2021 | +15.6% | +19.6% |
  | 2022 | +1.5% | -0.3% |
  | 2023 | +3.3% | +3.5% |
  | 2024 | +5.5% | +6.0% |
  | 2025 | +1.9% | +1.8% |
  | 2026 | -0.2% | -0.3% |

  The edge dropped from 15-20% annualized (2020-2021) to 2-3% (2024-2025)
  to near-zero (2026). This is consistent with more carry desks entering and
  arbitraging the premium away.

- **No exchange risk model.** Counterparty risk, liquidation cascades, basis
  collapse during extreme vol. 2022 showed ETH carry went slightly negative.
- **No Kraken-specific cost model.** Kraken taker fees, funding frequency,
  margin requirements, spot-to-perp basis at entry.
- **Worst negative-funding streak: 11-13 days.** Must model capital reserve
  for sustained negative periods.

## Operator context

- **Venue:** Kraken (full access confirmed). Kraken perps available to EU
  retail. Operator previously had Kraken futures blocked on Binance (region
  restriction) — Kraken is the confirmed accessible venue.
- **Capital:** $50k allocated ($25k spot + $25k perp margin).
- **Operator did NOT have Kraken MiFID quiz issues for spot** — the MiFID quiz
  failure was on Kraken futures specifically (memory: `project_kraken_mifid_fail`).
  Verify futures access status before proceeding.

## What to do next

### Phase 0: Venue access gate (do this FIRST)

1. **Verify Kraken futures access.** Operator failed MiFID appropriateness quiz
   2026-07-07, futures blocked 30 days. Retake was eligible ~2026-08-06. Check
   if futures are now accessible. If still blocked, this project is on hold.

### Phase 1: Real data validation (kill or confirm)

2. **Get Kraken historical funding rates.** Kraken API or historical data
   download. Compare to Binance rates — if Kraken rates are systematically
   lower, the edge may not clear costs.
3. **Model at 2025-2026 rate levels, not the 6-year average.** The spike's
   Sharpe 2.40 is dominated by 2020-2021. At 2025-2026 rates (1.8-2%
   annualized), does the carry clear Kraken's costs?
4. **Kraken fee structure.** Taker fee, maker fee, funding payment frequency,
   margin interest. Model entry/exit cost + ongoing carry revenue at current
   rate levels.
5. **Carry compression model.** Fit the declining trajectory. If extrapolation
   suggests < 1% annualized by 2027, the project is not viable long-term.
6. **Honesty check at current rates:** if 2025-2026 rates alone don't pass the
   3× cost screen on Kraken, KILL the project.

### Phase 2: Execution design (only if Phase 1 passes)

7. **Kraken API integration.** Spot buy + perp short simultaneously. Need
   atomic or near-atomic execution to avoid basis risk during entry.
8. **Monitoring.** Funding rate tracking, position delta check, margin health.
9. **Exit logic.** When to unwind: funding rate turns persistently negative,
   basis collapses, margin call risk.

### Phase 3: Paper/live

10. **Kraken paper account** (if available) or small-scale live test ($1k).
11. **Go/no-go criteria** (pre-register).

## Honesty method

Copy `scripts/quant_honesty.py` from `fin-trading-engine`. Key addition for
this strategy: the cost screen must use CURRENT (2025-2026) rate levels, not
the historical average. The average is inflated by 2020-2021.

## Key risk

**Edge decay.** This is a crowding risk, not a structural risk. The carry
exists because speculators overpay to be long. As more carry desks enter, the
funding rate compresses toward zero. The 2020→2026 trajectory is a straight
line down. At current rates ($50k capital, 2% annual, 10% cost), net annual
income is ~$900. That may not justify the operational complexity and exchange
counterparty risk.

This project has the HIGHEST Sharpe but the LOWEST conviction for future
viability. Proceed only if Phase 1 shows current rates clearing Kraken costs
with margin.
