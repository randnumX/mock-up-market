"""
Central logging setup. Without this, every logger in the app inherits
Python's default (last-resort) handler: WARNING and above, to stderr, with
no timestamps and nothing written to disk. That's how a strategy crashing
on every single tick stayed invisible for an entire trading session - the
tracebacks scrolled past in `docker compose` output and were never stored.

Two handlers:
  - a rotating file handler, so there's a durable record to go back to
  - a console handler, so `docker compose logs` / the terminal still work

Everything is namespaced under the `mockupmarket` logger tree (see
get_logger) so app logs can be filtered apart from library noise.
"""
import logging
import logging.handlers
import os
import sys

from app.config import Config

LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
BACKUP_COUNT = 5  # ~50 MB ceiling total, then oldest is dropped

_configured = False


def get_logger(name):
    """Every module should use this rather than logging.getLogger directly,
    so all app loggers share one configurable parent."""
    return logging.getLogger(f"mockupmarket.{name}")


def setup_logging():
    """Idempotent - create_app() may run more than once (tests, reloader)."""
    global _configured
    if _configured:
        return

    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger("mockupmarket")
    root.setLevel(level)
    root.propagate = False  # don't double-log through the real root logger

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    # File logging is best-effort: a read-only or missing volume mount
    # shouldn't take the whole app down at startup.
    try:
        os.makedirs(Config.LOG_DIR, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            os.path.join(Config.LOG_DIR, "mock-up-market.log"),
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        root.info("Logging to %s (level=%s)", Config.LOG_DIR, Config.LOG_LEVEL.upper())
    except OSError as e:
        root.warning("File logging disabled - could not write to %s: %s", Config.LOG_DIR, e)

    _configured = True
