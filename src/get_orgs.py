import requests
from src.auth import get_access_token
from config.settings import BASE_API_URL

def get_all_organizations(token=None):
    if not token:
        token = get_access_token()
    url = f"{BASE_API_URL}/orgs"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return resp.json().get("organizations", [])

if __name__ == "__main__":
    orgs = get_all_organizations()
    print(f"Discovered {len(orgs)} organization(s):\n")
    for o in orgs:
        print(f" - {o.get('name')}: {o.get('id')[:30]}...")
