"""
One definition of the bar intervals the app supports, instead of the
freq_map being duplicated in live/engine.py and live/scanner.py and the
selectable options being hardcoded a third time in three frontend files.

`freq` is the pandas offset alias used for resampling ticks into bars
(note "min", not the "T" alias pandas dropped). `kite_max_days` mirrors
Kite Connect's per-request history limits for intraday data.
"""

INTERVALS = [
    {"id": "day",      "label": "Daily",      "freq": None,    "minutes": 375, "kite_max_days": 2000},
    {"id": "minute",   "label": "1 Minute",   "freq": "1min",  "minutes": 1,   "kite_max_days": 60},
    {"id": "3minute",  "label": "3 Minute",   "freq": "3min",  "minutes": 3,   "kite_max_days": 100},
    {"id": "5minute",  "label": "5 Minute",   "freq": "5min",  "minutes": 5,   "kite_max_days": 100},
    {"id": "10minute", "label": "10 Minute",  "freq": "10min", "minutes": 10,  "kite_max_days": 100},
    {"id": "15minute", "label": "15 Minute",  "freq": "15min", "minutes": 15,  "kite_max_days": 100},
    {"id": "30minute", "label": "30 Minute",  "freq": "30min", "minutes": 30,  "kite_max_days": 100},
    {"id": "60minute", "label": "60 Minute",  "freq": "60min", "minutes": 60,  "kite_max_days": 100},
]

_BY_ID = {i["id"]: i for i in INTERVALS}

# Pandas offset alias per interval, for resampling raw ticks into bars.
FREQ_MAP = {i["id"]: i["freq"] for i in INTERVALS if i["freq"]}

INTRADAY_IDS = [i["id"] for i in INTERVALS if i["id"] != "day"]

# NSE continuous session is 9:15-15:30 = 375 minutes.
TRADING_MINUTES_PER_DAY = 375


def is_valid(interval):
    return interval in _BY_ID


def kite_max_days(interval):
    """Kite refuses (or silently truncates) intraday history requests that
    reach back further than this."""
    return _BY_ID.get(interval, _BY_ID["day"])["kite_max_days"]


def days_for_bars(interval, n_bars):
    """Calendar days of history to request to end up with roughly `n_bars`
    bars of this size. Deliberately generous - weekends/holidays produce no
    bars, so asking for the exact arithmetic minimum reliably comes up
    short. Always capped to what Kite will actually serve."""
    meta = _BY_ID.get(interval)
    if not meta:
        return 30
    if interval == "day":
        days = int(n_bars * 1.6)  # ~5 trading days per 7 calendar days
    else:
        bars_per_day = max(1, TRADING_MINUTES_PER_DAY // meta["minutes"])
        days = int((n_bars / bars_per_day) * 2) + 2  # x2 for non-trading days
    return max(1, min(days, meta["kite_max_days"]))
