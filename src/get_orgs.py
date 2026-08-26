import requests
from src.auth import get_access_token
from config.settings import BASE_API_URL, AUTO_DISCOVER_ALL_FLEETS, FLEET_NAME_WHITELIST

def get_all_organizations(token=None, filter_primary_fleets=True):
    """
    Dynamically fetches all operating cities/supplier organizations from the Uber API.
    If new cities/fleets are added to the Uber Supplier Account in the future,
    this endpoint discovers them automatically without code changes.
    """
    if not token:
        token = get_access_token()
    url = f"{BASE_API_URL}/orgs"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, timeout=25)
    resp.raise_for_status()
    all_orgs = resp.json().get("organizations", [])
    
    if not filter_primary_fleets or AUTO_DISCOVER_ALL_FLEETS:
        # Return all discovered active organizations across all cities
        # Exclude only if explicitly whitelisted and list is non-empty
        if FLEET_NAME_WHITELIST:
            return [o for o in all_orgs if o.get("name") in FLEET_NAME_WHITELIST]
        return all_orgs
    
    return all_orgs

def get_operating_fleets(token=None):
    """
    Returns active supplier fleet organizations grouped and sorted by city/name.
    """
    orgs = get_all_organizations(token)
    # Sort by organization name
    return sorted(orgs, key=lambda x: x.get("name", ""))

if __name__ == "__main__":
    fleets = get_operating_fleets()
    print(f"================================================================================")
    print(f"DYNAMIC FLEET DISCOVERY: Found {len(fleets)} Organization(s) Across All Cities")
    print(f"================================================================================\n")
    for i, f in enumerate(fleets, 1):
        print(f"  {i:2d}. {f.get('name'):<45} [ID: {f.get('id')[:25]}...]")
