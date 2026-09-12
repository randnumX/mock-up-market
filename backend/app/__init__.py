from flask import Flask
from flask_cors import CORS
from app.config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enable CORS for frontend dev server
    CORS(app, origins=Config.CORS_ORIGINS)

    # Register blueprints
    from app.routes.health import health_bp
    from app.routes.tickers import tickers_bp
    from app.routes.backtest import backtest_bp
    from app.routes.kite import kite_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(tickers_bp)
    app.register_blueprint(backtest_bp)
    app.register_blueprint(kite_bp)

    return app
