# fin-crypto-carry

This project is a delta-neutral crypto carry trade. You hold long spot assets and short perpetual futures on the same asset. You collect funding rate payments. Shorts receive funding when the rate is positive. The rate is positive about 88% of the time.

## Source

This project started as a spike in `fin-trading-engine` (`results/spike_three_strategies_2026-08-21.md`). A 6.4-year backtest used Binance historical funding CSVs as a proxy for Kraken rates.

| Symbol | Sharpe | Ann ret | Max DD | Monthly WR | t-stat | Tail |
|---|---|---|---|---|---|---|
| **BTC** | **2.40** | **+5.5%** | **0.4%** | **88.3%** | **+5.97** | **OK** |
| **ETH** | **2.25** | **+6.7%** | **0.9%** | **88.3%** | **+5.57** | **OK** |

Cost as % of gross: 10.5% (BTC), 8.8% (ETH). The two assets pass the 3x cost screen.

## What the spike proved

The carry is structural. Speculators pay to be long, and carry traders collect the funding rate. Positive funding occurred on 87-88% of days in the backtest. This is the highest Sharpe of one strategy tested in `fin-trading-engine` across 85 perp trials and 3 strategy-class spikes. Max drawdown was less than 1%. The position is delta-neutral, so price moves cancel. Multiple institutional quant funds operate this trade. Academic literature holds that this trade is sound.

## What the spike did not prove

The backtest used Binance data as a proxy for Kraken. Kraken's funding mechanism is almost the same, but rates differ. You must validate with actual Kraken historical funding rates.

The carry is declining. The table below shows annual results by year.

  | Year | BTC | ETH |
  |---|---|---|
  | 2020 | +8.3% | +13.9% |
  | 2021 | +15.6% | +19.6% |
  | 2022 | +1.5% | -0.3% |
  | 2023 | +3.3% | +3.5% |
  | 2024 | +5.5% | +6.0% |
  | 2025 | +1.9% | +1.8% |
  | 2026 | -0.2% | -0.3% |

The edge fell from 15-20% annualized (2020-2021) to 2-3% (2024-2025) to near-zero in 2026. More carry desks that go into the trade is the likely cause.

The backtest has no exchange-risk model. Counterparty risk, liquidation cascades, and basis collapse during very high volatility are not modeled. ETH carry went a small quantity negative in 2022. There is no Kraken-specific cost model. Taker fees, funding frequency, margin requirements, and spot-to-perp basis at entry are not included. The worst negative-funding streak in the data was 11-13 days. You must model a capital reserve for sustained negative periods.

## What to do next

### Phase 0: Venue access gate (do this first)

1. Make sure that Kraken futures access is active. If Kraken does not let you access futures, stop this project.

### Phase 1: Data validation (kill or confirm)

2. Get Kraken historical funding rates from the API or a historical data download. Compare the rates to Binance rates. If Kraken rates are systematically lower, the edge may not be more than the costs.
3. Model at 2025-2026 rate levels only. Do not use the 6-year average. The backtest Sharpe of 2.40 comes mostly from 2020-2021. At 2025-2026 rates (1.8-2% annualized), make sure that the carry is more than Kraken costs.
4. Model the Kraken fee structure: taker fee, maker fee, funding payment frequency, and margin interest.
5. Model the declining trajectory. If the extrapolation gives less than 1% annualized by 2027, the project is not viable long-term.
6. Honesty check: if 2025-2026 rates alone are not more than the costs at the 3x screen on Kraken, kill the project.

### Phase 2: Execution design (only if Phase 1 passes)

7. Assemble the Kraken API integration. The spot buy and perp short must operate at the same time, or almost the same time. This prevents basis risk at entry.
8. Monitor the funding rate, position delta, and margin health.
9. Set the exit logic: when funding turns persistently negative, when basis collapses, or when margin call risk increases.

### Phase 3: Paper or live

10. Operate a Kraken paper account (if available) or a small-scale live test ($1k).
11. Pre-register go/no-go criteria before you see results.

## Honesty method

Write `scripts/quant_honesty.py` from `fin-trading-engine` into this project. The cost screen must use current (2025-2026) rate levels. Do not use the historical average. The historical average is too high because of 2020-2021.

## Primary risk

Edge decay is the primary risk. This is a crowding risk, not a structural one. The carry exists because speculators overpay to be long. When more carry desks go into the trade, the funding rate goes to 0%. The 2020-2026 trajectory is near a straight line down. At current rates, net annual income on a $50k position (2% annual, 10% cost) is about $900. That may not justify the complexity and the crypto-exchange counterparty risk.

This project has the highest Sharpe in the backtest set. It also has the lowest conviction for future viability. Proceed only if Phase 1 shows that current rates are more than Kraken costs with margin.
