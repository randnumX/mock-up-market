import os
import sys
import json
import time
from dotenv import load_dotenv, find_dotenv
from kiteconnect import KiteConnect, KiteTicker

# 1. Load environment variables
load_dotenv(find_dotenv())

API_KEY = os.getenv("KITE_API_KEY")
API_SECRET = os.getenv("KITE_API_SECRET")
# Point to the session file managed by the backend
SESSION_FILE = os.path.join(os.path.dirname(__file__), ".kite_session.json")

kite = KiteConnect(api_key=API_KEY)
ACCESS_TOKEN = None

# Check if we already have a saved session file from today
if os.path.exists(SESSION_FILE):
    try:
        with open(SESSION_FILE, "r") as f:
            saved = json.load(f)
            ACCESS_TOKEN = saved.get("access_token")
            kite.set_access_token(ACCESS_TOKEN)
            profile = kite.profile()
            print(f"✅ Found existing active session! Logged in as: {profile.get('user_name')}")
    except Exception as e:
        print(f"⚠️ Cached session expired or invalid: {e}. Fresh login needed.")
        ACCESS_TOKEN = None

# If no active token, generate login link
if not ACCESS_TOKEN:
    print("\n👉 Click this URL to log in:")
    print(kite.login_url())
    print("\nAfter login, copy the 'request_token' from the redirected browser URL")
    request_token = input("Paste your request_token here: ").strip()
    
    if request_token:
        # Exchange for access_token
        session_data = kite.generate_session(request_token, api_secret=API_SECRET)
        ACCESS_TOKEN = session_data["access_token"]
        kite.set_access_token(ACCESS_TOKEN)

        # Save to .kite_session.json so the rest of your backend & notebook can reuse it
        profile = kite.profile()
        with open(SESSION_FILE, "w") as f:
            json.dump({"access_token": ACCESS_TOKEN, "profile": profile}, f)

        print(f"✅ Login successful! Logged in as: {profile.get('user_name')}")
        print(f"Token saved to {SESSION_FILE}")
    else:
        print("❌ No request_token provided. Exiting.")
        sys.exit(1)


# ---------------------------------------------------------
# Web Socket Connection
# ---------------------------------------------------------

# Fetch NSE instrument master list
print("\nFetching instrument list...")
instruments = kite.instruments("NSE")

def get_token(symbol):
    for inst in instruments:
        if inst["tradingsymbol"] == symbol:
            return inst["instrument_token"]
    return None

# Find tokens for stocks you want
symbols = ["TCS", "HDFCBANK", "INFY", "RELIANCE"]
token_map = {sym: get_token(sym) for sym in symbols}
tokens_to_track = [t for t in token_map.values() if t]

print("\nResolved Tokens:")
for sym, tok in token_map.items():
    print(f"  {sym}: {tok}")

# 1. Initialize KiteTicker
kws = KiteTicker(API_KEY, ACCESS_TOKEN)

def on_connect(ws, response):
    print("\n🚀 [CONNECTED] Successfully connected to Kite WebSocket!")
    print(f"Subscribing to {len(tokens_to_track)} tokens: {tokens_to_track}")
    ws.subscribe(tokens_to_track)
    ws.set_mode(ws.MODE_FULL, tokens_to_track)

def on_ticks(ws, ticks):
    for tick in ticks:
        print(f"📈 Token: {tick.get('instrument_token')} | LTP: ₹{tick.get('last_price')} | Vol: {tick.get('volume_traded')}")

def on_error(ws, code, reason):
    print(f"❌ [ERROR] {code} - {reason}")

def on_close(ws, code, reason):
    print(f"⚠️ [CLOSED] {code} - {reason}")

# 2. Attach callbacks
kws.on_connect = on_connect
kws.on_ticks = on_ticks
kws.on_error = on_error
kws.on_close = on_close

# 3. Connect in background thread
kws.connect(threaded=True)

# 4. Wait up to 5 seconds to confirm connection
for _ in range(10):
    if kws.is_connected():
        break
    time.sleep(0.5)

print("\nConnection Status:", "🟢 Connected!" if kws.is_connected() else "🔴 Waiting/Failed")

try:
    print("\nListening for ticks... Press Ctrl+C to stop.")
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nStopping...")
    kws.close()
    print("🛑 WebSocket disconnected.")
