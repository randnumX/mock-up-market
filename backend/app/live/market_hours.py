from datetime import datetime, time
from zoneinfo import ZoneInfo
from app.live.nse_holidays import NSE_HOLIDAYS

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def is_market_open(now=None):
    """NSE cash market hours: 9:15-15:30 IST, Monday-Friday, excluding
    published trading holidays (see nse_holidays.py)."""
    now = (now or datetime.now(IST)).astimezone(IST)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    if now.date().isoformat() in NSE_HOLIDAYS:
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE
