import datetime
import time
import uuid
from src.auth import get_access_token
from src.get_orgs import get_operating_fleets
from src.fetch_reports import get_or_generate_report, wait_for_report, download_report
from src.db_loader import (
    get_connection,
    log_execution_start,
    log_execution_finish,
    load_trips_csv,
    load_order_transactions_csv,
    load_driver_csv,
    load_org_csv
)
from src.email_service import send_execution_email

REPORT_TYPES = [
    "REPORT_TYPE_TRIP_ACTIVITY",
    "REPORT_TYPE_PAYMENTS_ORDER",
    "REPORT_TYPE_PAYMENTS_DRIVER",
    "REPORT_TYPE_PAYMENTS_ORGANIZATION",
]

def run_pipeline(target_date=None, run_type="DAILY_SCHEDULED"):
    """
    Executes an idempotent ingestion run for target_date (defaults to yesterday in IST).
    Dynamically discovers all operating cities/fleets so new cities work automatically.
    Safe to trigger randomly at any hour (force run) without breaking data.
    """
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    start_wall_time = time.time()
    run_id = f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    if not target_date:
        target_date = datetime.date.today() - datetime.timedelta(days=1)

    start_dt = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=ist_tz)
    end_dt = datetime.datetime.combine(target_date, datetime.time.max, tzinfo=ist_tz)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    window_str = f"{target_date} [{start_dt.strftime('%Y-%m-%d %H:%M:%S')} -> {end_dt.strftime('%Y-%m-%d %H:%M:%S')}]"

    print("="*80)
    print(f"[UBER PIPELINE RUNNER] RUN ID: {run_id} | TYPE: {run_type}")
    print(f"Target Window: {window_str}")
    print("="*80)

    conn = get_connection()
    log_execution_start(conn, run_id, run_type, start_dt, end_dt)

    stats = {"trips": 0, "transactions": 0, "drivers": 0, "orgs": 0, "fleets": 0}
    status = "SUCCESS"
    error_log = []

    try:
        token = get_access_token()
        # DYNAMIC DISCOVERY: Automatically finds all cities/organizations
        orgs = get_operating_fleets(token)
        stats["fleets"] = len(orgs)

        print(f"Dynamically discovered {len(orgs)} active fleet organizations across all cities.")

        for i, org in enumerate(orgs, 1):
            org_uuid = org["id"]
            org_name = org.get("name")
            print(f"\n[{i}/{len(orgs)}] Operating Fleet: {org_name}")

            for report_type in REPORT_TYPES:
                print(f"  * Fetching {report_type}...")
                try:
                    report_id = get_or_generate_report(token, org_uuid, report_type, start_ms, end_ms)
                    wait_for_report(token, org_uuid, report_id)
                    path = download_report(token, org_uuid, report_id, report_type, org_name)

                    if report_type == "REPORT_TYPE_TRIP_ACTIVITY":
                        cnt = load_trips_csv(conn, path, org_name, run_id, report_id, start_dt, end_dt)
                        stats["trips"] += cnt
                    elif report_type == "REPORT_TYPE_PAYMENTS_ORDER":
                        cnt = load_order_transactions_csv(conn, path, org_name, run_id, report_id, start_dt, end_dt)
                        stats["transactions"] += cnt
                    elif report_type == "REPORT_TYPE_PAYMENTS_DRIVER":
                        cnt = load_driver_csv(conn, path, start_dt, end_dt, org_name, run_id, report_id)
                        stats["drivers"] += cnt
                    elif report_type == "REPORT_TYPE_PAYMENTS_ORGANIZATION":
                        cnt = load_org_csv(conn, path, start_dt, end_dt, run_id, report_id)
                        stats["orgs"] += cnt

                except Exception as e:
                    err_msg = f"{org_name} [{report_type}]: {e}"
                    print(f"    [ERROR] {err_msg}")
                    error_log.append(err_msg)
                    status = "PARTIAL"

                time.sleep(2)

    except Exception as e:
        status = "FAILED"
        error_log.append(f"Fatal execution error: {e}")
        print(f"[FATAL ERROR] {e}")

    duration = time.time() - start_wall_time
    err_str = "; ".join(error_log) if error_log else None

    # Dispatch email (styled identically to Ola template)
    email_sent = send_execution_email(run_id, run_type, f"{target_date}", status, stats, duration, err_str)

    # Log to DB
    log_execution_finish(
        conn, run_id, status, stats["fleets"], stats["trips"],
        stats["transactions"], stats["drivers"], stats["orgs"],
        err_str, email_sent
    )

    conn.close()
    print("\n" + "="*80)
    print(f"[UBER PIPELINE RUNNER] FINISHED WITH STATUS: {status} in {duration:.1f}s")
    print("="*80)

if __name__ == "__main__":
    run_pipeline()
