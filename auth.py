# auth.py
import os, time, base64, requests

_TOKEN_CACHE = {"access_token": None, "expires_at": 0}

def _refresh_oauth_token() -> str:
    client_id = os.getenv("EBAY_CLIENT_ID")
    client_secret = os.getenv("EBAY_CLIENT_SECRET")
    refresh_token = os.getenv("EBAY_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError("Missing EBAY_CLIENT_ID/EBAY_CLIENT_SECRET/EBAY_REFRESH_TOKEN in .env")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {basic}",
    }
    # Inventory scope covers what this app needs; add others if you later expand
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "https://api.ebay.com/oauth/api_scope/sell.inventory"
    }
    r = requests.post("https://api.ebay.com/identity/v1/oauth2/token", headers=headers, data=data, timeout=30)
    r.raise_for_status()
    payload = r.json()
    token = payload["access_token"]
    # conservative expiry buffer
    _TOKEN_CACHE["access_token"] = token
    _TOKEN_CACHE["expires_at"] = time.time() + int(payload.get("expires_in", 7200)) - 120
    return token

def get_oauth_token() -> str:
    if _TOKEN_CACHE["access_token"] and time.time() < _TOKEN_CACHE["expires_at"]:
        return _TOKEN_CACHE["access_token"]
    # allow bootstrapping from env once, then prefer refresh flow
    env_token = os.getenv("EBAY_ACCESS_TOKEN")
    if env_token and not _TOKEN_CACHE["access_token"]:
        _TOKEN_CACHE["access_token"] = env_token
        _TOKEN_CACHE["expires_at"] = time.time() + 300  # short leash; will refresh next call
        return env_token
    return _refresh_oauth_token()
