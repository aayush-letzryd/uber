import time
import datetime
import os
import io
import zipfile
import random
import requests
import pandas as pd
from src.auth import get_access_token
from config.settings import BASE_API_URL

POLL_INTERVAL_SECONDS = 20
POLL_TIMEOUT_SECONDS = 15 * 60

def list_existing_reports(token, org_uuid):
    url = f"{BASE_API_URL}/suppliers/{org_uuid}/reports"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 200:
            return resp.json().get("reports", [])
    except Exception as e:
        print(f"    Warning: Could not fetch active report list from Uber: {e}")
    return []

def find_matching_existing_report(existing_reports, report_type, start_ms, end_ms):
    for r in existing_reports:
        if r.get("reportType") != report_type:
            continue
        status = r.get("status")
        if status in ("REPORT_STATUS_FAILED", "REPORT_STATUS_CANCELLED"):
            continue
        filters = r.get("filters", [])
        for f in filters:
            if f.get("field") == "dateRange" and f.get("value") == [str(start_ms), str(end_ms)]:
                return r
    return None

def get_or_generate_report(token, org_uuid, report_type, start_ms, end_ms, max_retries=3):
    existing = list_existing_reports(token, org_uuid)
    matched = find_matching_existing_report(existing, report_type, start_ms, end_ms)
    if matched:
        print(f"    [Queue Check] Adopting existing Uber report (ID: {matched['id']}, Status: {matched.get('status')})")
        return matched["id"]

    url = f"{BASE_API_URL}/suppliers/{org_uuid}/reports"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "reportType": report_type,
        "filters": [
            {"field": "dateRange", "operator": "OPERATOR_IN_RANGE", "value": [str(start_ms), str(end_ms)]}
        ]
    }
    for attempt in range(max_retries):
        resp = requests.post(url, headers=headers, json=body, timeout=30)
        if resp.status_code == 429:
            wait = (2 ** attempt) * 30 + random.randint(1, 10)
            print(f"    Rate limited (429). Waiting {wait}s ({attempt+1}/{max_retries})...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["report"]["id"]
    raise RuntimeError("Failed after max retries due to repeated 429 rate limiting.")

def wait_for_report(token, org_uuid, report_id):
    url = f"{BASE_API_URL}/suppliers/{org_uuid}/reports/{report_id}"
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code == 429:
            time.sleep(30)
            continue
        resp.raise_for_status()
        report = resp.json()["report"]
        if report["status"] == "REPORT_STATUS_COMPLETED":
            return report
        if report["status"] == "REPORT_STATUS_FAILED":
            raise RuntimeError(f"Report Failed: {report.get('failedReason')}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError("Report generation timed out.")

def download_report(token, org_uuid, report_id, report_type, org_name, dest_dir="./uber_reports"):
    link_url = f"{BASE_API_URL}/suppliers/{org_uuid}/reports/{report_id}/link"
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(link_url, headers=headers, timeout=20)
    resp.raise_for_status()
    signed_url = resp.json()["signedUrl"]["value"]

    raw_resp = requests.get(signed_url, timeout=60)
    raw_resp.raise_for_status()
    raw_bytes = raw_resp.content

    os.makedirs(dest_dir, exist_ok=True)
    safe_org_name = org_name.replace(" ", "_").replace(".", "")
    timestamp_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if raw_bytes.startswith(b"PK\x03\x04"):
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            csv_files = [f for f in z.namelist() if f.endswith(".csv")]
            dfs = [pd.read_csv(z.open(f), encoding="utf-8", encoding_errors="replace", low_memory=False) for f in csv_files]
            df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        path = os.path.join(dest_dir, f"{safe_org_name}_{report_type}_{timestamp_tag}.csv")
        df.to_csv(path, index=False)
    else:
        path = os.path.join(dest_dir, f"{safe_org_name}_{report_type}_{timestamp_tag}.csv")
        with open(path, "wb") as f:
            f.write(raw_bytes)

    return path
