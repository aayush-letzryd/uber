import re
import requests
from src.auth import get_access_token
from config.settings import BASE_API_URL, AUTO_DISCOVER_ALL_FLEETS, DEFAULT_FLEETS

def _normalize_name(name):
    if not name:
        return ""
    # Normalize multiple whitespace characters and non-breaking spaces (\xa0)
    return " ".join(re.split(r"\s+", str(name).strip()))

def get_all_organizations(token=None):
    """
    Dynamically fetches operating cities/supplier organizations from the Uber API.
    """
    if not token:
        token = get_access_token()
    url = f"{BASE_API_URL}/orgs"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    all_orgs = resp.json().get("organizations", [])
    
    if AUTO_DISCOVER_ALL_FLEETS:
        return all_orgs
    
    normalized_defaults = {_normalize_name(f) for f in DEFAULT_FLEETS}
    matched = [o for o in all_orgs if _normalize_name(o.get("name")) in normalized_defaults]
    
    if not matched and all_orgs:
        print(f"    [Warning] None of the target DEFAULT_FLEETS matched active orgs. Falling back to all {len(all_orgs)} discovered fleet(s).")
        return all_orgs
        
    return matched

def get_operating_fleets(token=None):
    orgs = get_all_organizations(token)
    return sorted(orgs, key=lambda x: _normalize_name(x.get("name")))

if __name__ == "__main__":
    fleets = get_operating_fleets()
    print(f"Operating Fleets: {len(fleets)}")
    for f in fleets:
        print(f" - {f.get('name')} (ID: {f.get('id')})")
