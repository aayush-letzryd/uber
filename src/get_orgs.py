import requests
from src.auth import get_access_token
from config.settings import BASE_API_URL, AUTO_DISCOVER_ALL_FLEETS, DEFAULT_FLEETS

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
    
    # Default to the 3 primary operating fleets
    matched = [o for o in all_orgs if o.get("name") in DEFAULT_FLEETS]
    return matched if matched else all_orgs

def get_operating_fleets(token=None):
    orgs = get_all_organizations(token)
    return sorted(orgs, key=lambda x: x.get("name", ""))

if __name__ == "__main__":
    fleets = get_operating_fleets()
    print(f"Operating Fleets: {len(fleets)}")
    for f in fleets:
        print(f" - {f.get('name')}")
