from app.logging_config import get_logger
import time
import threading
from queue import Queue
from app.config import Config
from app.data.kite_client import get_kite, is_configured

logger = get_logger("live.ticker")

# Global in-memory cache of latest prices: {instrument_token: last_price}
PRICE_CACHE = {}
# Kite reports volume_traded as the day's CUMULATIVE volume, not per-tick.
# Cached raw here; callers difference successive readings to get the volume
# actually traded during an interval. {instrument_token: cumulative_volume}
VOLUME_CACHE = {}
# Map of tradingsymbol to instrument_token to allow symbol-based lookups
SYMBOL_MAP = {}

# PubSub for Server-Sent Events (SSE)
# List of queue.Queue objects for active client connections
_clients = []
_ticker_thread = None
_kws = None


def add_client(q: Queue):
    _clients.append(q)


def remove_client(q: Queue):
    if q in _clients:
        _clients.remove(q)


def _broadcast(message: dict):
    """Push a dict message to all listening SSE clients."""
    for q in _clients:
        # Non-blocking put to avoid stuck clients delaying others
        try:
            q.put_nowait(message)
        except Exception:
            pass


def get_latest_price(symbol: str):
    """Retrieve the latest price from the WebSocket cache if available."""
    token = SYMBOL_MAP.get(symbol)
    if token and token in PRICE_CACHE:
        return PRICE_CACHE[token]
    return None


def get_cumulative_volume(symbol: str):
    """Day-cumulative traded volume from the WebSocket feed, or None.

    Cumulative, not per-tick - VWAP needs the volume traded *during* each
    bar, so callers difference consecutive readings (and reset at the day
    boundary, where Kite's counter restarts)."""
    token = SYMBOL_MAP.get(symbol)
    if token is not None:
        return VOLUME_CACHE.get(token)
    return None


def update_symbol_map(kite):
    """Fetch all NSE instruments and build a mapping to allow symbol lookups."""
    try:
        instruments = kite.instruments("NSE")
        for inst in instruments:
            SYMBOL_MAP[inst["tradingsymbol"]] = inst["instrument_token"]
            # Also store the reverse mapping so we can broadcast symbols instead of tokens
            SYMBOL_MAP[inst["instrument_token"]] = inst["tradingsymbol"]
        logger.info("Fetched %d NSE instruments for ticker mapping.", len(instruments))
    except Exception as e:
        logger.error("Failed to fetch instruments for ticker: %s", e)


def subscribe_symbols(symbols: list):
    """Subscribe the WebSocket to a list of symbols."""
    global _kws
    if not _kws or not _kws.is_connected():
        return

    tokens_to_subscribe = []
    for sym in symbols:
        token = SYMBOL_MAP.get(sym)
        if token:
            tokens_to_subscribe.append(token)

    if tokens_to_subscribe:
        # Kite API has a hard limit of 3000 tokens per WebSocket connection
        if len(tokens_to_subscribe) > 3000:
            logger.warning("Capping subscription to 3000 tokens (Kite API limit). Requested: %s", len(tokens_to_subscribe))
            tokens_to_subscribe = tokens_to_subscribe[:3000]
            
        logger.info("Subscribing ticker to %s tokens", len(tokens_to_subscribe))
        _kws.subscribe(tokens_to_subscribe)
        _kws.set_mode(_kws.MODE_FULL, tokens_to_subscribe)


def _run_ticker():
    global _kws
    logger.info("Starting Kite Ticker thread...")

    # Exponential backoff state: starts at 5s, doubles on each failure, caps at 5 min.
    # Resets to base on a successful connection.
    _BASE_DELAY = 5
    _MAX_DELAY  = 300
    reconnect_delay = _BASE_DELAY

    while True:
        if not is_configured() or not Config.KITE_ALLOW:
            time.sleep(5)
            continue

        kite = get_kite()
        if not kite:
            time.sleep(5)
            continue

        # Build symbol map if empty
        if not SYMBOL_MAP:
            update_symbol_map(kite)

        from kiteconnect import KiteTicker

        try:
            _kws = KiteTicker(
                Config.KITE_API_KEY,
                kite.access_token,
                reconnect=False,   # We control reconnects ourselves with backoff.
                                   # SDK's built-in reconnect has no backoff and
                                   # causes the 429 storm we saw.
            )

            connected_once = threading.Event()
            got_429 = threading.Event()

            def on_connect(ws, response):
                nonlocal reconnect_delay
                reconnect_delay = _BASE_DELAY   # reset backoff on success
                connected_once.set()
                logger.info("Kite WebSocket Connected.")

            def on_ticks(ws, ticks):
                for tick in ticks:
                    token = tick.get('instrument_token')
                    price = tick.get('last_price')
                    if token and price:
                        PRICE_CACHE[token] = price
                        vol = tick.get('volume_traded')
                        if vol is not None:
                            VOLUME_CACHE[token] = vol

                        sym = SYMBOL_MAP.get(token)
                        if sym:
                            _broadcast({
                                "symbol": sym,
                                "price": price,
                                "volume": tick.get('volume_traded', 0)
                            })

            def on_error(ws, code, reason):
                reason_str = str(reason or "")
                if "429" in reason_str or "TooManyRequests" in reason_str:
                    got_429.set()
                logger.error("Kite WebSocket Error: %s - %s", code, reason)

            def on_close(ws, code, reason):
                logger.warning("Kite WebSocket Closed: %s - %s", code, reason)

            _kws.on_connect = on_connect
            _kws.on_ticks   = on_ticks
            _kws.on_error   = on_error
            _kws.on_close   = on_close

            logger.info("Connecting KiteTicker... (next retry delay=%ss)", reconnect_delay)
            _kws.connect(threaded=True)

            # Wait until actually connected or until it's clearly failed (2s grace)
            connected_once.wait(timeout=2)
            while _kws.is_connected():
                time.sleep(1)

        except Exception as e:
            logger.exception("Ticker thread crashed: %s", e)

        # If we hit a 429, back off harder
        if got_429.is_set():
            reconnect_delay = min(reconnect_delay * 2, _MAX_DELAY)
            logger.warning(
                "Kite WebSocket rate-limited (429). Backing off %ss before reconnect.", reconnect_delay
            )
        else:
            # Regular disconnect — mild backoff
            reconnect_delay = min(reconnect_delay * 1.5, _MAX_DELAY)

        time.sleep(reconnect_delay)


def start_ticker_thread():
    """Start the background WebSocket thread if not already running."""
    global _ticker_thread
    if _ticker_thread is None or not _ticker_thread.is_alive():
        _ticker_thread = threading.Thread(target=_run_ticker, daemon=True)
        _ticker_thread.start()
