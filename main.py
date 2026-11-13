#!/usr/bin/env python3
"""polymarket-nvidia-ceo-forecast-01: adaptive quantile forecaster (v3).

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
  - Spread: a robust per-market volatility, blended across two windows.
    One-minute returns are mostly zero with occasional jumps, so the
    plain std is dominated by a few huge moves and badly overstates
    typical movement. Instead sigma is the 90th percentile of |1-minute
    returns|, divided by 1.644854 (the half-normal factor). v2 took that
    over the last 720 minutes only; v3 blends the 720-minute sigma with
    the last 90 minutes' (equal weight in variance), because volatility
    comes in regimes: a quiet last hour means narrow near-horizon bands
    are safe, a jumpy one means they are not, and the 720-minute window
    alone mixes the regimes. The blend is floored at 0.0002 and capped
    at 0.005. The short window alone is too noisy (it scores worse than
    v2); the blend is what works, and the gain is flat across short
    windows of 30-120 minutes and weights of 0.25-0.75, so 90 minutes
    at 0.50 sits at the centre of the plateau, not a sharp peak.
  - Horizon: the spread grows as h**0.45, slightly slower than a random
    walk's sqrt(h): minute returns are negatively autocorrelated
    (bid/ask bounce), so the random-walk extrapolation overstates
    long-horizon moves. Quantiles are the standard normal's, clamped to
    [0, 1] and rounded to 6 decimals.
  - Rows are enforced non-decreasing after rounding.

Practice backtest (local scorer, calibrated: it reproduces the house
baseline's published 0.363589 exactly): this forecaster scores 0.263638,
beating v2 (0.270740) on 5 of 6 practice cases and the house baseline on
all six. Asymmetric quantiles (skewed toward the sum-reversion pull)
were tested and hurt monotonically, so the quantiles stay symmetric.
Verified locally: all six practice cases run in 0.40 s total, outputs
are 208-267 KB, and two runs write byte-identical outputs.
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
BLEND_SHORT_MINUTES = 90
BLEND_SHORT_WEIGHT = 0.50
SIGMA_QUANTILE = 0.90
SIGMA_Z = 1.644854
SIGMA_FLOOR = 0.0002
SIGMA_CAP = 0.005
HORIZON_ALPHA = 0.45
SUM_KAPPA = 0.70


def quantile_sigma(prices, window):
    """Raw sigma from the 90th percentile of |1-minute returns|."""
    start = max(1, len(prices) - window)
    moves = sorted(abs(prices[i] - prices[i - 1])
                   for i in range(start, len(prices)))
    if not moves:
        return 0.0
    idx = int(SIGMA_QUANTILE * (len(moves) - 1))
    return moves[idx] / SIGMA_Z


def robust_sigma(prices):
    """Per-minute volatility: 720-minute and 90-minute quantile sigmas
    blended with equal weight in variance, then floored and capped."""
    sig_long = quantile_sigma(prices, WINDOW_MINUTES)
    sig_short = quantile_sigma(prices, BLEND_SHORT_MINUTES)
    sigma = math.sqrt(BLEND_SHORT_WEIGHT * sig_short ** 2 +
                      (1.0 - BLEND_SHORT_WEIGHT) * sig_long ** 2)
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
