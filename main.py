#!/usr/bin/env python3
"""polymarket-nvidia-ceo-forecast-01: adaptive quantile forecaster (v2).

Forecasts each market's Yes price at every minute of the next 4 hours as
five quantiles (5%, 25%, 50%, 75%, 95%).

Method:
  - Median: the last price, pulled toward its sum-normalized share. The
    24 markets are mutually exclusive outcomes ("Next CEO of NVIDIA?"),
    so their Yes prices should sum to about 1. A market priced above its
    share of the sum (x / sum of all last prices) tends to fall back, and
    one below its share tends to rise: the pooled regression of the
    240-minute move on the deviation from share is -0.555 on the practice
    cases. The pull is median(h) = x + 0.70 * (x/sum - x) * sqrt(h/H),
    growing with the horizon. Own-history mean reversion (pull toward a
    recent mean, EMA, or lagged price) was tested over 157 configs and
    hurt on every anchor family; the cross-market pull is what works.
  - Spread: a robust per-market volatility. One-minute returns are mostly
    zero with occasional jumps, so the plain std is dominated by a few
    huge moves and badly overstates typical movement. Instead sigma is the
    90th percentile of |1-minute returns| over the last 720 minutes,
    divided by 1.644854 (the half-normal factor), floored at 0.0002 and
    capped at 0.005.
  - Horizon: the spread grows as h**0.45, slightly slower than a random
    walk's sqrt(h): minute returns are negatively autocorrelated
    (bid/ask bounce), so the random-walk extrapolation overstates
    long-horizon moves. Quantiles are the standard normal's, clamped to
    [0, 1] and rounded to 6 decimals.
  - Rows are enforced non-decreasing after rounding.

Practice backtest (local scorer, calibrated: it reproduces the house
baseline's published 0.363589 exactly): this forecaster scores 0.270740,
beating v1 (0.279164) on 5 of 6 practice cases and the house baseline on
all six. The pull strength is flat between 0.60 and 0.80 (all within
0.0002), so 0.70 sits at the centre of the plateau, not a sharp peak.
Verified locally: all six practice cases run in 0.41 s total, outputs
are 209-265 KB, and two runs write byte-identical outputs.
"""
import json
import math
import os
from pathlib import Path

INPUT_DIR = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
OUTPUT_DIR = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")

QUANTILES = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.644854, -0.674490, 0.0, 0.674490, 1.644854]

WINDOW_MINUTES = 720
SIGMA_QUANTILE = 0.90
SIGMA_Z = 1.644854
SIGMA_FLOOR = 0.0002
SIGMA_CAP = 0.005
HORIZON_ALPHA = 0.45
SUM_KAPPA = 0.70


def robust_sigma(prices):
    """Per-minute volatility from the 90th percentile of |returns|."""
    start = max(1, len(prices) - WINDOW_MINUTES)
    moves = sorted(abs(prices[i] - prices[i - 1])
                   for i in range(start, len(prices)))
    if not moves:
        return SIGMA_FLOOR
    idx = int(SIGMA_QUANTILE * (len(moves) - 1))
    sigma = moves[idx] / SIGMA_Z
    return min(SIGMA_CAP, max(SIGMA_FLOOR, sigma))


def price6(x):
    """x clamped to [0, 1] and rounded to 6 decimals (0, never -0)."""
    return round(min(1.0, max(0.0, x)), 6) + 0.0


def forecast(market, horizon, total):
    prices = market["prices"]
    if not prices:
        raise ValueError("market %s has no prices" % market["id"])
    x = prices[-1]
    sigma = robust_sigma(prices)
    share = x / total if total > 0 else x
    rows = []
    for h in range(1, horizon + 1):
        center = x + SUM_KAPPA * (share - x) * math.sqrt(h / horizon)
        scale = sigma * (h ** HORIZON_ALPHA)
        row = [price6(center + z * scale) for z in Z]
        for i in range(1, 5):
            if row[i] < row[i - 1]:
                row[i] = row[i - 1]
        rows.append(row)
    return rows


def main():
    in_dir = Path(INPUT_DIR)
    out_dir = Path(OUTPUT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(in_dir.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if case["quantiles"] != QUANTILES:
            raise ValueError("%s asks for quantiles %s, not %s" % (
                path.name, case["quantiles"], QUANTILES))
        total = sum(m["prices"][-1] for m in case["markets"] if m["prices"])
        forecasts = [{"id": m["id"],
                      "q": forecast(m, case["horizon_minutes"], total)}
                     for m in case["markets"]]
        out = json.dumps({"forecasts": forecasts}, separators=(",", ":")) + "\n"
        (out_dir / (path.stem + ".out")).write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
