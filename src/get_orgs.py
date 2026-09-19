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
    Includes fallback to DB / default orgs if API fails.
    """
    if not token:
        try:
            token = get_access_token()
        except Exception as e:
            print(f"    [Auth Warning] Token fetch failed: {e}")
            token = None

    if token:
        url = f"{BASE_API_URL}/orgs"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            resp = requests.get(url, headers=headers, timeout=25)
            if resp.status_code == 401:
                print("    [Auth] 401 Unauthorized for /orgs. Refreshing OAuth token...")
                token = get_access_token(force_refresh=True)
                headers["Authorization"] = f"Bearer {token}"
                resp = requests.get(url, headers=headers, timeout=25)
            resp.raise_for_status()
            all_orgs = resp.json().get("organizations", [])
            if all_orgs:
                if AUTO_DISCOVER_ALL_FLEETS:
                    return all_orgs
                normalized_defaults = {_normalize_name(f) for f in DEFAULT_FLEETS}
                matched = [o for o in all_orgs if _normalize_name(o.get("name")) in normalized_defaults]
                if matched:
                    return matched
                print(f"    [Warning] None of the target DEFAULT_FLEETS matched active orgs. Returning all {len(all_orgs)} discovered fleet(s).")
                return all_orgs
        except Exception as e:
            print(f"    [Warning] API /orgs endpoint call failed ({e}). Attempting database fallback for fleet orgs...")

    # Fallback: Query known active fleet orgs from DB
    try:
        from src.db_loader import get_connection
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT organization_uuid, organisation_name FROM uber_pipeline_org_payments WHERE organization_uuid IS NOT NULL;")
        rows = cur.fetchall()
        conn.close()
        if rows:
            fallback_orgs = [{"id": r[0], "name": r[1]} for r in rows if r[0] and r[1]]
            if fallback_orgs:
                print(f"    [Fallback] Loaded {len(fallback_orgs)} active orgs from database.")
                return fallback_orgs
    except Exception as db_err:
        print(f"    [Fallback Warning] DB org fallback query failed: {db_err}")

    # Final static fallback if API and DB are unreachable
    static_defaults = [
        {"id": "ebb10afb-c08b-463e-a4fa-33b64674adfd", "name": "SAMVREEDDHI MOBILITY Pvt. Ltd. BLR P"},
        {"id": "44cb587c-a690-44b5-94c2-37539500c7d5", "name": "Samvreeddhi Mobility Pvt. Ltd. MUM P"},
        {"id": "f7d7968b-43fe-4c15-bfc8-30a82c8ad5b9", "name": "Samvreeddhi Mobility Pvt Ltd HYD P"}
    ]
    print(f"    [Fallback] Returning default {len(static_defaults)} static fleet orgs.")
    return static_defaults

def get_operating_fleets(token=None):
    orgs = get_all_organizations(token)
    return sorted(orgs, key=lambda x: _normalize_name(x.get("name")))

if __name__ == "__main__":
    fleets = get_operating_fleets()
    print(f"Operating Fleets: {len(fleets)}")
    for f in fleets:
        print(f" - {f.get('name')} (ID: {f.get('id')})")
