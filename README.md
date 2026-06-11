# Apex

An adaptive trading engine for Robinhood that learns, in real time, which of its
strategies is making money — and moves capital toward it.

> **Reality check, up front:** no software can guarantee profits, and most retail
> algos lose money to costs and overfitting. What Apex *can* do is enforce the
> discipline that separates survivors from blowups: honest cost modeling,
> volatility-aware sizing, hard kill switches, and a measurable feedback loop.
> Maximizing money over time starts with not losing it.

## The workflow

```
            ┌─────────────────────────────────────────────────┐
            │                  SUPERVISOR                     │
            │   restarts on crash · never overrides the kill  │
            └───────────────────────┬─────────────────────────┘
                                    │
   ┌──────────┐   bars   ┌──────────▼──────────┐   orders   ┌──────────────┐
   │  FEEDS   ├─────────►│       ENGINE        ├───────────►│   BROKER     │
   │ live/csv │          │  per bar:           │            │ paper (sim)  │
   └──────────┘          │  1 ingest prices    │            │ RH crypto    │
                         │  2 attribute PnL ───┼──┐         │ (RH stocks*) │
   ┌──────────────┐ sig  │  3 combine signals  │  │ rewards └──────────────┘
   │ STRATEGIES   ├─────►│  4 size w/ risk     │  │
   │ momentum x2  │      │  5 execute          │  ▼
   │ mean-revert  │      └─────────┬───────────┘ ┌─────────────────┐
   │ breakout     │◄───────────────┼─────────────┤ BANDIT (learns) │
   └──────────────┘  capital wts   │             │ Thompson sampling│
                                   ▼             │ decayed memory   │
                         ┌─────────────────┐     └─────────────────┘
                         │ RISK MANAGER    │
                         │ vol targeting   │     ┌─────────────────┐
                         │ daily loss halt │     │ JOURNAL         │
                         │ drawdown KILL   │     │ every decision  │
                         └─────────────────┘     │ to disk (jsonl) │
                                                 └─────────────────┘
```

**How it "learns, adapts, and improves in real time":** every bar, each
strategy is credited with the PnL its previous signal would have earned. A
Thompson-sampling bandit with exponentially-decaying memory turns those rewards
into live capital weights. A strategy that stops working gets defunded within
hours — no nightly retrain, no human in the loop. If *nothing* has a positive
edge, the bandit stands down to flat rather than forcing trades.

## Quickstart

```bash
pip install -e ".[dev]"
pytest                                  # all green before anything else

apex backtest --synthetic --steps 5000  # prove the plumbing end to end
apex backtest --csv data/btc_15s.csv    # validate on real history (ts,symbol,price)
apex paper                              # live quotes, fake money  <- live here 30+ days
apex live --i-understand-the-risks      # real money, Robinhood crypto
```

Copy `config/config.example.yaml` to `config/config.yaml` (gitignored) and add
your Robinhood Crypto API credentials for live quotes/trading.

## Getting real history

A real backtest needs real data. Fetch two years of hourly BTC candles from
Coinbase's public API (no key required — run on your own machine, not in a
sandboxed environment):

```bash
python scripts/fetch_btc_data.py --days 730 --out data/btc_1h.csv
apex backtest --csv data/btc_1h.csv --bars-per-day 24
```

`--bars-per-day` tells the risk manager how to annualize volatility and when a
"day" rolls over for the daily loss halt (24 for hourly bars, 5760 for 15s).

A 50-bar sample of real BTC hourly closes lives in
`data/samples/btc_recent_1h.csv` to keep the replay path tested against real
market data — it is far too short to judge strategy performance.

## The promotion gate

Apex is built to earn its way to real money, not to be trusted on day one:

1. **Backtest** on real history. Same engine code that trades live — what you
   validate is what you deploy.
2. **Paper trade** with live quotes for 30+ days. The journal records every
   decision; the summary shows return, drawdown, and per-strategy attribution.
3. **Go live small.** Only after paper results hold up, and only with money you
   can lose. The kill switch file (`APEX_KILL_SWITCH`) makes every halt
   require a deliberate human re-arm.

## Why crypto first (the Robinhood constraint)

- **Robinhood has no official stock-trading API.** Stocks via `robin_stocks`
  drive Robinhood's *private* endpoints — that violates their ToS and risks
  your account. The adapter exists (`brokers/robinhood_stocks.py`) but is
  disabled unless you explicitly opt in after reading its warning.
- The **official Robinhood Crypto Trading API** is fully supported here
  (Ed25519-signed, key from the Robinhood app). BTC trades 24/7, fractional,
  no Pattern-Day-Trader rule.
- Costs are modeled honestly: Robinhood crypto's cost is the **spread**, not a
  commission line. The paper broker charges fees + slippage so backtests can't
  lie to you.

## What it would take to actually be "the best" (the honest roadmap)

Signals like momentum and mean reversion are table stakes — everyone has them.
Real, durable edge comes from things this scaffold is structured to grow into:

- **Better data** — order-book imbalance, funding rates, on-chain flows,
  cross-exchange basis. Edge lives in data others don't use well.
- **Execution quality** — limit orders inside the spread instead of market
  orders; on Robinhood crypto the spread IS the fee, so this is pure money.
- **Regime detection** — explicit bull/bear/chop classification feeding the
  bandit, not just decayed memory.
- **Walk-forward validation** — re-fit on window N, test on N+1, repeatedly,
  to kill overfit strategies before they trade.
- **A real stock venue** — if stocks matter, add an Alpaca or IBKR broker
  (one file, the `Broker` interface is 4 methods) rather than risking the
  Robinhood account on private APIs.
- **Taxes** — short-term gains are taxed as income in the US; high turnover
  must outperform by the tax drag just to break even with holding.

## Layout

```
src/apex/
  engine.py            the per-bar loop: ingest -> learn -> combine -> size -> execute
  main.py              CLI + crash supervisor (never restarts past the kill switch)
  journal.py           every decision to disk; you can't improve what you don't measure
  data/feed.py         replay (CSV), synthetic, and live feeds
  strategies/          momentum, mean reversion, breakout (conviction in [-1,1])
  learning/bandit.py   Thompson-sampling capital allocator — the real-time learning core
  risk/manager.py      vol targeting, daily halt, drawdown kill switch
  brokers/             paper simulator, Robinhood crypto (official), Robinhood stocks (opt-in)
  backtest/engine.py   same engine, replayed data
```
