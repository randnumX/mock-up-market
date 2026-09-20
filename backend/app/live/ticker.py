import logging
import time
import threading
from queue import Queue
from app.config import Config
from app.data.kite_client import get_kite, is_configured

logger = logging.getLogger("live_ticker")

# Global in-memory cache of latest prices: {instrument_token: last_price}
PRICE_CACHE = {}
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

        # Initialize KiteTicker
        # The KiteConnect SDK unfortunately doesn't expose the underlying ACCESS_TOKEN easily 
        # from a KiteConnect instance, but we can read it from the session file or reconstruct.
        # Actually kite.access_token is accessible.
        from kiteconnect import KiteTicker
        
        try:
            _kws = KiteTicker(Config.KITE_API_KEY, kite.access_token)
            
            def on_connect(ws, response):
                logger.info("Kite WebSocket Connected.")
                # By default, we could subscribe to some default tokens, or wait for the engine
                # to call subscribe_symbols().

            def on_ticks(ws, ticks):
                for tick in ticks:
                    token = tick.get('instrument_token')
                    price = tick.get('last_price')
                    if token and price:
                        PRICE_CACHE[token] = price
                        
                        sym = SYMBOL_MAP.get(token)
                        if sym:
                            _broadcast({
                                "symbol": sym,
                                "price": price,
                                "volume": tick.get('volume_traded', 0)
                            })

            def on_error(ws, code, reason):
                logger.error("Kite WebSocket Error: %s - %s", code, reason)

            def on_close(ws, code, reason):
                logger.warning("Kite WebSocket Closed: %s - %s", code, reason)

            _kws.on_connect = on_connect
            _kws.on_ticks = on_ticks
            _kws.on_error = on_error
            _kws.on_close = on_close

            logger.info("Connecting KiteTicker...")
            # This is a blocking call, it will keep running until disconnected
            _kws.connect(threaded=False)
            
        except Exception as e:
            logger.exception("Ticker thread crashed: %s", e)
            
        # If connect() returns/crashes, wait a bit and reconnect
        time.sleep(5)


def start_ticker_thread():
    """Start the background WebSocket thread if not already running."""
    global _ticker_thread
    if _ticker_thread is None or not _ticker_thread.is_alive():
        _ticker_thread = threading.Thread(target=_run_ticker, daemon=True)
        _ticker_thread.start()
