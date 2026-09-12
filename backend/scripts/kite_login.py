#!/usr/bin/env python3
"""
One-time (well, once-a-day - Kite tokens expire daily) CLI login flow for
Zerodha Kite Connect. Equivalent to the in-app "Connect Zerodha" button,
for headless use (servers, cron jobs) where there's no browser session
to click through.

Usage:
    cd backend && python scripts/kite_login.py
"""
import os
import sys
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

from app.data import kite_client  # noqa: E402


def main():
    if not kite_client.is_configured():
        print("KITE_API_KEY / KITE_API_SECRET are not set (check backend/.env).")
        sys.exit(1)

    login_url = kite_client.get_login_url()
    print("1. Open this URL, log in with your Zerodha credentials:\n")
    print(f"   {login_url}\n")
    print("2. After login you'll be redirected to a URL containing 'request_token=...'.")
    print("   Paste that full redirect URL (or just the token) below.\n")

    raw = input("Redirect URL or request_token: ").strip()
    match = re.search(r"request_token=([^&]+)", raw)
    request_token = match.group(1) if match else raw

    kite_client.complete_login(request_token)
    print("\nConnected. Access token cached for today's session.")


if __name__ == "__main__":
    main()
