#!/usr/bin/env python3
"""Fetch BTC-USD (or any product) hourly history from Coinbase Exchange's
public candles API into Apex's CSV format (ts,symbol,price).

No API key needed. Run this on your own machine (the Claude cloud sandbox
blocks external market-data hosts):

    python scripts/fetch_btc_data.py --days 730 --out data/btc_1h.csv
    apex backtest --csv data/btc_1h.csv --bars-per-day 24

Coinbase returns max 300 candles per request, so this paginates backwards
from now and sleeps between requests to respect rate limits.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

API = "https://api.exchange.coinbase.com/products/{product}/candles"


def fetch(product: str, granularity: int, days: int) -> list[tuple[float, float]]:
    end = datetime.now(timezone.utc)
    start_limit = end - timedelta(days=days)
    span = timedelta(seconds=granularity * 300)  # 300 candles per request
    rows: list[tuple[float, float]] = []
    while end > start_limit:
        start = max(end - span, start_limit)
        resp = requests.get(
            API.format(product=product),
            params={"granularity": granularity,
                    "start": start.isoformat(), "end": end.isoformat()},
            timeout=15)
        resp.raise_for_status()
        # each row: [time, low, high, open, close, volume]
        batch = [(float(c[0]), float(c[4])) for c in resp.json()]
        rows.extend(batch)
        print(f"  {start:%Y-%m-%d} -> {end:%Y-%m-%d}: {len(batch)} candles "
              f"({len(rows)} total)", file=sys.stderr)
        end = start
        time.sleep(0.4)  # public rate limit: ~10 req/s; stay far under it
    rows.sort(key=lambda r: r[0])
    # de-dup overlapping boundaries
    seen: set[float] = set()
    return [r for r in rows if not (r[0] in seen or seen.add(r[0]))]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product", default="BTC-USD")
    p.add_argument("--granularity", type=int, default=3600,
                   help="candle seconds: 60, 300, 900, 3600, 21600, 86400")
    p.add_argument("--days", type=int, default=730)
    p.add_argument("--out", default="data/btc_1h.csv")
    args = p.parse_args()

    rows = fetch(args.product, args.granularity, args.days)
    if not rows:
        print("No data returned", file=sys.stderr)
        return 1
    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts", "symbol", "price"])
        for ts, close in rows:
            w.writerow([int(ts), args.product, close])
    first = datetime.fromtimestamp(rows[0][0], timezone.utc)
    last = datetime.fromtimestamp(rows[-1][0], timezone.utc)
    print(f"Wrote {len(rows)} bars to {args.out} ({first:%Y-%m-%d} -> {last:%Y-%m-%d})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
