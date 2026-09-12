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
    app.run(host='0.0.0.0', port=port, debug=debug)
