"""
Thin wrapper around Zerodha's Kite Connect API.

Kite access tokens are valid for a single trading day, so the token returned
by generate_session() is cached to a local JSON file (KITE_SESSION_FILE) and
reused until it stops working, at which point the user reconnects via the
"Connect Zerodha" flow (GET /api/kite/login-url -> Zerodha login -> redirected
to GET /api/kite/callback which exchanges the request_token for a fresh
access_token and re-saves it here).
"""
import json
import os
from app.config import Config

try:
    from kiteconnect import KiteConnect
except ImportError:
    KiteConnect = None

_kite = None
_profile = None


def is_configured():
    """True if KITE_API_KEY / KITE_API_SECRET are set and the SDK is installed."""
    return bool(KiteConnect and Config.KITE_API_KEY and Config.KITE_API_SECRET)


def _load_session():
    if not os.path.exists(Config.KITE_SESSION_FILE):
        return None
    try:
        with open(Config.KITE_SESSION_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_session(access_token, profile=None):
    with open(Config.KITE_SESSION_FILE, 'w') as f:
        json.dump({"access_token": access_token, "profile": profile}, f)


def get_login_url():
    """Return the Zerodha hosted login page URL to redirect the user to."""
    if not is_configured():
        return None
    kite = KiteConnect(api_key=Config.KITE_API_KEY)
    return kite.login_url()


def complete_login(request_token):
    """
    Exchange a one-time request_token (received on the callback redirect)
    for a day-valid access_token, and persist it.
    """
    if not is_configured():
        raise RuntimeError("Kite Connect is not configured (missing KITE_API_KEY/KITE_API_SECRET)")

    global _kite, _profile
    kite = KiteConnect(api_key=Config.KITE_API_KEY)
    session = kite.generate_session(request_token, api_secret=Config.KITE_API_SECRET)
    access_token = session["access_token"]
    kite.set_access_token(access_token)

    profile = None
    try:
        profile = kite.profile()
    except Exception:
        pass

    _save_session(access_token, profile)
    _kite = kite
    _profile = profile
    return kite


def get_kite():
    """
    Return a ready-to-use, authenticated KiteConnect instance, or None if
    not configured / not yet connected / the cached token has expired.
    """
    global _kite, _profile
    if not is_configured():
        return None

    if _kite is not None:
        return _kite

    session = _load_session()
    if not session or not session.get("access_token"):
        return None

    kite = KiteConnect(api_key=Config.KITE_API_KEY)
    kite.set_access_token(session["access_token"])

    try:
        kite.margins()  # cheap call to verify the token still works
    except Exception:
        return None

    _kite = kite
    _profile = session.get("profile")
    return _kite


def is_connected():
    return get_kite() is not None


def get_profile():
    global _profile
    if _profile is None:
        session = _load_session()
        _profile = (session or {}).get("profile")
    return _profile


def disconnect():
    """Forget the cached session (does not revoke it on Zerodha's side)."""
    global _kite, _profile
    _kite = None
    _profile = None
    if os.path.exists(Config.KITE_SESSION_FILE):
        os.remove(Config.KITE_SESSION_FILE)
