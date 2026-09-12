from datetime import datetime, time
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)


def is_market_open(now=None):
    """NSE cash market hours: 9:15-15:30 IST, Monday-Friday. No holiday calendar."""
    now = (now or datetime.now(IST)).astimezone(IST)
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE
