"""Helpers for getting pandas/numpy output into a BSON/JSON-safe shape."""
import numpy as np


def to_native(value):
    """Recursively convert numpy scalars (np.int64, np.float64, ...) to
    native Python types. Needed anywhere a value that started life as a
    pandas DataFrame cell - a bar's OHLCV field, or a strategy attribute
    accumulated from one (e.g. VWAP's `self.cum_vol += row["Volume"]`,
    which silently becomes np.int64) - ends up in a dict that gets
    persisted to Mongo or returned as JSON. Neither pymongo's BSON encoder
    nor (for most numpy types) Python's json encoder can serialize them."""
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {k: to_native(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_native(v) for v in value]
    return value


def records_to_native(records):
    """pandas aggregation (e.g. `.resample().agg({"Volume": "sum"})`)
    produces numpy scalar types that pymongo's BSON encoder can't
    serialize. Convert every value in a list of dict records (as from
    `df.to_dict(orient="records")`) to native Python types before
    persisting or returning it."""
    return [to_native(row) for row in records]
