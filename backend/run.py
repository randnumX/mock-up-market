import os
import sys

# Ensure the backend directory is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    print(f"\n🚀 Mock-Up Market API starting on http://localhost:{port}")
    print(f"📊 Dashboard: http://localhost:5173\n")
    # threaded=True is required, not cosmetic: /api/backtest/stream and
    # /api/stream hold their connection open for the life of a run. Without
    # threading, Werkzeug's dev server handles one request at a time - a
    # dropped SSE connection (e.g. the browser refreshing mid-backtest)
    # isn't noticed until its next write attempt, and until then every
    # other request (including the ones the reloaded page needs just to
    # boot) queues up behind it, making the whole UI look frozen.
    app.run(host='0.0.0.0', port=port, debug=debug, threaded=True)
