import os


class Config:
    MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
    DB_NAME = os.getenv('DB_NAME', 'AlgoTradingSource')
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')

    # Collection names
    COLLECTION_TICKERS = 'StockPricesData'
    COLLECTION_TIMESERIES = 'StockPriceDataTimeSeries'
    COLLECTION_HISTORICAL = 'LastOneYearStockData'

    # Zerodha Kite Connect (real market data ingestion)
    KITE_API_KEY = os.getenv('KITE_API_KEY', '')
    KITE_API_SECRET = os.getenv('KITE_API_SECRET', '')
    KITE_REDIRECT_URL = os.getenv('KITE_REDIRECT_URL', 'http://localhost:5000/api/kite/callback')
    KITE_FRONTEND_URL = os.getenv('KITE_FRONTEND_URL', 'http://localhost:5173')
    KITE_SESSION_FILE = os.getenv(
        'KITE_SESSION_FILE',
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.kite_session.json')
    )
