"""
Generates realistic synthetic stock price data using Geometric Brownian Motion.
Used as a fallback when MongoDB is unavailable, so the app is fully functional
out of the box without any database setup.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Pre-defined stock profiles for realistic simulation
STOCK_PROFILES = {
    "SBIN": {"base_price": 620, "volatility": 0.018, "drift": 0.0003},
    "RELIANCE": {"base_price": 2450, "volatility": 0.015, "drift": 0.0004},
    "HDFCBANK": {"base_price": 1680, "volatility": 0.012, "drift": 0.0003},
    "INFY": {"base_price": 1520, "volatility": 0.020, "drift": 0.0002},
    "TCS": {"base_price": 3800, "volatility": 0.014, "drift": 0.0003},
    "ICICIBANK": {"base_price": 1100, "volatility": 0.016, "drift": 0.0003},
    "TATAMOTORS": {"base_price": 950, "volatility": 0.025, "drift": 0.0005},
    "WIPRO": {"base_price": 480, "volatility": 0.019, "drift": 0.0001},
    "BAJFINANCE": {"base_price": 7200, "volatility": 0.022, "drift": 0.0004},
    "MARUTI": {"base_price": 12500, "volatility": 0.016, "drift": 0.0003},
}


def get_dummy_tickers():
    """Return list of available dummy ticker symbols."""
    return sorted(STOCK_PROFILES.keys())


def generate_stock_data(ticker="SBIN", days=365, seed=None, end_date=None):
    """
    Generate realistic historical stock price data using Geometric Brownian Motion.

    Args:
        ticker: Stock symbol (used to look up base price / volatility profile)
        days: Number of trading days to generate
        seed: Random seed for reproducibility
        end_date: datetime the generated series should end on (defaults to now) -
            lets a caller-selected date range line up with what's plotted,
            even though the underlying prices are still synthetic

    Returns:
        pandas DataFrame with columns: scripName, priceDate, Value, Volume
    """
    if seed is not None:
        np.random.seed(seed)
    else:
        # Use ticker name as seed for consistent results per ticker
        np.random.seed(sum(ord(c) for c in ticker))

    profile = STOCK_PROFILES.get(ticker, {"base_price": 500, "volatility": 0.02, "drift": 0.0002})
    base_price = profile["base_price"]
    volatility = profile["volatility"]
    drift = profile["drift"]

    # Generate price series using GBM
    dt = 1  # 1 day
    prices = [base_price]

    for _ in range(days - 1):
        shock = np.random.normal(0, 1)
        price_change = prices[-1] * (drift * dt + volatility * shock * np.sqrt(dt))
        new_price = max(prices[-1] + price_change, prices[-1] * 0.92)  # Floor at -8% daily
        prices.append(round(new_price, 2))

    # Generate volume (correlated with price movement magnitude)
    base_volume = np.random.randint(500000, 2000000)
    volumes = []
    for i in range(len(prices)):
        if i == 0:
            vol = base_volume
        else:
            price_change_pct = abs(prices[i] - prices[i - 1]) / prices[i - 1]
            # Higher price changes → higher volume
            vol = int(base_volume * (1 + price_change_pct * 20) * np.random.uniform(0.7, 1.3))
        volumes.append(vol)

    # Generate dates (skip weekends), walking backward from end_date so the
    # series lands exactly on it instead of the old forward-scan's "roughly
    # near end_date" approximation (which drifted depending on how weekends
    # happened to fall within its calendar-day lookback window).
    end_date = end_date or datetime.now()
    dates = []
    current = end_date
    while len(dates) < days:
        if current.weekday() < 5:  # Monday to Friday
            dates.append(current)
        current -= timedelta(days=1)
    dates.reverse()

    df = pd.DataFrame({
        "scripName": ticker,
        "priceDate": [d.strftime("%Y-%m-%d") for d in dates[:days]],
        "Value": prices[:days],
        "Volume": volumes[:days],
    })

    return df
