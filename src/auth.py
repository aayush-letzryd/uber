import os
import time
import requests
from config.settings import UBER_CLIENT_ID, UBER_CLIENT_SECRET, UBER_ACCESS_TOKEN

AUTH_URL = "https://auth.uber.com/oauth/v2/token"
SCOPE = (
    "solutions.suppliers.reports "
    "vehicle_suppliers.organizations.read "
    "solutions.suppliers.metrics.read "
    "vehicle_suppliers.vehicles.read "
    "solutions.suppliers.drivers.status.read "
    "vehicle_suppliers.vehicles.assignment "
    "supplier.partner.payments"
)

_TOKEN_CACHE = {
    "token": None,
    "expires_at": 0
}

def get_access_token(force_refresh=False):
    """
    Acquires an OAuth 2.0 Bearer access token using client_credentials grant.
    Maintains an in-memory cache and automatically refreshes when within 300 seconds of expiration.
    """
    now = time.time()
    
    if not force_refresh and _TOKEN_CACHE["token"] and _TOKEN_CACHE["expires_at"] > (now + 300):
        return _TOKEN_CACHE["token"]

    if UBER_CLIENT_ID and UBER_CLIENT_SECRET:
        try:
            resp = requests.post(AUTH_URL, data={
                "client_id": UBER_CLIENT_ID,
                "client_secret": UBER_CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": SCOPE,
            }, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            token = data["access_token"]
            expires_in = data.get("expires_in", 2592000)
            
            _TOKEN_CACHE["token"] = token
            _TOKEN_CACHE["expires_at"] = now + expires_in
            return token
        except Exception as e:
            if UBER_ACCESS_TOKEN:
                print(f"Warning: OAuth token generation failed ({e}), falling back to static token.")
                return UBER_ACCESS_TOKEN
            raise e

    if UBER_ACCESS_TOKEN:
        return UBER_ACCESS_TOKEN

    raise ValueError("Missing credentials: Set UBER_CLIENT_ID & UBER_CLIENT_SECRET or UBER_ACCESS_TOKEN in environment.")

if __name__ == "__main__":
    token = get_access_token()
    print(f"Token acquired successfully: {token[:15]}... (Length: {len(token)})")
