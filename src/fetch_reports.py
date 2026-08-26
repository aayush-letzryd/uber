import time
import datetime
import os
import io
import gzip
import zipfile
import random
import re
import requests
import pandas as pd
from src.auth import get_access_token
from config.settings import BASE_API_URL

POLL_INTERVAL_SECONDS = 20
POLL_TIMEOUT_SECONDS = 15 * 60

def _get_retry_wait(attempt, base_wait=30, resp=None):
    if resp is not None:
        retry_header = resp.headers.get("Retry-After")
        if retry_header and retry_header.isdigit():
            return int(retry_header)
    return (2 ** attempt) * base_wait + random.randint(1, 10)

def list_existing_reports(token=None, org_uuid=None):
    if not token:
        token = get_access_token()
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
    target_range = [str(start_ms), str(end_ms)]
    for r in (existing_reports or []):
        if r.get("reportType") != report_type:
            continue
        status = r.get("status")
        if status in ("REPORT_STATUS_FAILED", "REPORT_STATUS_CANCELLED"):
            continue
        filters = r.get("filters") or []
        for f in filters:
            if f.get("field") == "dateRange":
                raw_val = f.get("value") or []
                norm_val = [str(v) for v in raw_val]
                if norm_val == target_range:
                    return r
    return None

def get_or_generate_report(token, org_uuid, report_type, start_ms, end_ms, max_retries=4):
    if not token:
        token = get_access_token()
        
    existing = list_existing_reports(token, org_uuid)
    matched = find_matching_existing_report(existing, report_type, start_ms, end_ms)
    if matched and matched.get("id"):
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
            wait = _get_retry_wait(attempt, base_wait=30, resp=resp)
            print(f"    Rate limited (429). Waiting {wait}s ({attempt+1}/{max_retries})...")
            time.sleep(wait)
            continue
        if resp.status_code == 401:
            print("    [Auth] 401 Unauthorized encountered. Refreshing OAuth token...")
            token = get_access_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            continue
        if resp.status_code in (500, 502, 503, 504) and attempt < max_retries - 1:
            wait = _get_retry_wait(attempt, base_wait=10)
            print(f"    Server error ({resp.status_code}). Retrying in {wait}s ({attempt+1}/{max_retries})...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()["report"]["id"]
    raise RuntimeError("Failed after max retries due to repeated rate limiting or server errors.")

def wait_for_report(token, org_uuid, report_id):
    if not token:
        token = get_access_token()
    url = f"{BASE_API_URL}/suppliers/{org_uuid}/reports/{report_id}"
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    consecutive_errors = 0
    
    while time.time() < deadline:
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if resp.status_code == 429:
                wait = _get_retry_wait(0, base_wait=30, resp=resp)
                time.sleep(wait)
                continue
            if resp.status_code == 401:
                token = get_access_token(force_refresh=True)
                headers["Authorization"] = f"Bearer {token}"
                continue
            if resp.status_code in (500, 502, 503, 504):
                consecutive_errors += 1
                if consecutive_errors > 5:
                    resp.raise_for_status()
                time.sleep(POLL_INTERVAL_SECONDS)
                continue
                
            resp.raise_for_status()
            consecutive_errors = 0
            report = resp.json().get("report", {})
            status = report.get("status")
            
            if status == "REPORT_STATUS_COMPLETED":
                return report
            if status == "REPORT_STATUS_FAILED":
                raise RuntimeError(f"Report Failed: {report.get('failedReason')}")
            if status == "REPORT_STATUS_CANCELLED":
                raise RuntimeError(f"Report Cancelled by Uber platform: {report}")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            consecutive_errors += 1
            if consecutive_errors > 5:
                raise e
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
            
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Report generation timed out after {POLL_TIMEOUT_SECONDS}s (Report ID: {report_id}).")

def _extract_signed_url(resp_json):
    if not isinstance(resp_json, dict):
        return None
    val = resp_json.get("signedUrl") or resp_json.get("signed_url") or resp_json.get("url")
    if isinstance(val, dict):
        return val.get("value") or val.get("url")
    if isinstance(val, str):
        return val
    return None

def download_report(token, org_uuid, report_id, report_type, org_name, dest_dir="./uber_reports", max_retries=4):
    if not token:
        token = get_access_token()
    link_url = f"{BASE_API_URL}/suppliers/{org_uuid}/reports/{report_id}/link"
    headers = {"Authorization": f"Bearer {token}"}
    
    signed_url = None
    for attempt in range(max_retries):
        resp = requests.post(link_url, headers=headers, timeout=25)
        if resp.status_code == 429:
            wait = _get_retry_wait(attempt, base_wait=20, resp=resp)
            print(f"    Link generation 429 limited. Waiting {wait}s ({attempt+1}/{max_retries})...")
            time.sleep(wait)
            continue
        if resp.status_code == 401:
            token = get_access_token(force_refresh=True)
            headers["Authorization"] = f"Bearer {token}"
            continue
        if resp.status_code in (500, 502, 503, 504) and attempt < max_retries - 1:
            time.sleep(10)
            continue
        resp.raise_for_status()
        signed_url = _extract_signed_url(resp.json())
        if signed_url:
            break
        time.sleep(5)
        
    if not signed_url:
        raise ValueError(f"Could not extract valid signed download URL from Uber response: {resp.text}")

    raw_bytes = None
    for attempt in range(max_retries):
        try:
            raw_resp = requests.get(signed_url, timeout=(15, 120))
            if raw_resp.status_code == 429:
                wait = _get_retry_wait(attempt, base_wait=20, resp=raw_resp)
                time.sleep(wait)
                continue
            raw_resp.raise_for_status()
            raw_bytes = raw_resp.content
            break
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            if attempt == max_retries - 1:
                raise e
            wait = (attempt + 1) * 10
            print(f"    S3 download error ({e}). Retrying in {wait}s ({attempt+1}/{max_retries})...")
            time.sleep(wait)

    if raw_bytes is None:
        raise RuntimeError(f"Failed to download report payload for report {report_id}")

    os.makedirs(dest_dir, exist_ok=True)
    safe_org_name = re.sub(r"[^\w\-]", "_", org_name.strip())
    timestamp_tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(dest_dir, f"{safe_org_name}_{report_type}_{timestamp_tag}.csv")

    if zipfile.is_zipfile(io.BytesIO(raw_bytes)):
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
            csv_files = sorted([
                f for f in z.namelist() 
                if f.lower().endswith(".csv") and not os.path.basename(f).startswith(".")
            ])
            dfs = []
            for f in csv_files:
                try:
                    chunk_df = pd.read_csv(
                        z.open(f),
                        encoding="utf-8",
                        encoding_errors="replace",
                        low_memory=False,
                        dtype=str
                    )
                    if not chunk_df.empty:
                        dfs.append(chunk_df)
                except pd.errors.EmptyDataError:
                    continue
            df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        df.to_csv(path, index=False)
    elif raw_bytes.startswith(b"\x1f\x8b"):
        decompressed = gzip.decompress(raw_bytes)
        with open(path, "wb") as f:
            f.write(decompressed)
    else:
        with open(path, "wb") as f:
            f.write(raw_bytes)

    return path
