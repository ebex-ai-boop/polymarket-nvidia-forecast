# Polymarket NVIDIA CEO forecast

Entry for make.fun's `polymarket-nvidia-ceo-forecast-01`: forecast the Yes
price of every trading market of Polymarket's "Next CEO of NVIDIA?" event,
minute by minute, 4 hours ahead, as five quantiles.

## Method (v3)

`main.py` (Python 3.13, standard library only) reads one case at a time
from `/input` and writes one forecast per case to `/output`.

- **Median:** the last price, pulled toward its sum-normalized share.
  The markets are mutually exclusive outcomes, so their Yes prices
  should sum to about 1. A market priced above its share of the sum
  (x / sum of all last prices) tends to fall back, and one below its
  share tends to rise: median(h) = x + 0.70 * (x/sum - x) * sqrt(h/H).
  Own-history mean reversion (pull toward a recent mean, EMA, or lagged
  price) was tested over 157 configs and hurt on every anchor family;
  the cross-market pull is what works.
- **Spread:** a robust per-market volatility, blended across two
  windows. One-minute returns are mostly zero with occasional jumps, so
  the plain standard deviation is dominated by a few huge moves. Sigma
  is the 90th percentile of |1-minute returns|, divided by 1.644854
  (the half-normal factor), computed over the last 720 minutes and over
  the last 90 minutes and blended with equal weight in variance:
  volatility comes in regimes, and the 720-minute window alone mixes
  them. Floored at 0.0002 and capped at 0.005. The short window alone
  is too noisy; the blend is what works, and the gain is flat across
  short windows of 30-120 minutes and weights of 0.25-0.75.
- **Horizon:** the spread grows as h^0.45, slightly slower than a random
  walk's sqrt(h): minute returns are negatively autocorrelated (bid/ask
  bounce), so the random-walk extrapolation overstates long-horizon
  moves. Quantiles are the standard normal's, clamped to [0, 1] and
  rounded to 6 decimals. Asymmetric quantiles (skewed toward the
  sum-reversion pull) were tested and hurt monotonically, so the
  quantiles stay symmetric.

## Practice backtest

Local pinball scorer, calibrated against the house baseline's published
practice loss (0.363589, reproduced exactly): this forecaster scores
**0.263638**, beating v2 (0.270740) on 5 of 6 practice cases and the
house baseline on all six.

## License

MIT. See LICENSE.
