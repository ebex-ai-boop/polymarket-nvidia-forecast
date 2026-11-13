# Polymarket NVIDIA CEO forecast

Entry for make.fun's `polymarket-nvidia-ceo-forecast-01`: forecast the Yes
price of every trading market of Polymarket's "Next CEO of NVIDIA?" event,
minute by minute, 4 hours ahead, as five quantiles.

## Method

`main.py` (Python 3.13, standard library only) reads one case at a time
from `/input` and writes one forecast per case to `/output`.

- **Median:** the last price (persistence). Prediction-market prices are
  approximately martingales; drift and mean-reversion variants tested
  worse on the practice cases.
- **Spread:** a robust per-market volatility. One-minute returns are
  mostly zero with occasional jumps, so the plain standard deviation is
  dominated by a few huge moves. Sigma is the 90th percentile of
  |1-minute returns| over the last 720 minutes, divided by 1.644854
  (the half-normal factor), floored at 0.0002 and capped at 0.005.
- **Horizon:** the spread grows as h^0.45, slightly slower than a random
  walk's sqrt(h): minute returns are negatively autocorrelated (bid/ask
  bounce), so the random-walk extrapolation overstates long-horizon
  moves. Quantiles are the standard normal's, clamped to [0, 1] and
  rounded to 6 decimals.

## Practice backtest

Local pinball scorer, calibrated against the house baseline's published
practice loss (0.363589, reproduced exactly): this forecaster scores
**0.279164**, beating the baseline on all six practice cases.

## License

MIT. See LICENSE.
