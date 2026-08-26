import argparse
import datetime
import time
import uuid
import sys
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
    now_ist = datetime.datetime.now(ist_tz)
    run_id = f"run_{now_ist.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    if not target_date:
        target_date = now_ist.date() - datetime.timedelta(days=1)

    start_dt = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=ist_tz)
    end_dt = datetime.datetime.combine(target_date, datetime.time.max, tzinfo=ist_tz)

    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)

    date_display = target_date.strftime("%d %b %Y (%Y-%m-%d)")

    print("=" * 80)
    print(f"[UBER PIPELINE RUNNER] RUN ID: {run_id} | TYPE: {run_type}")
    print(f"Target Date: {date_display} [{start_dt.strftime('%Y-%m-%d %H:%M:%S')} -> {end_dt.strftime('%Y-%m-%d %H:%M:%S')} IST]")
    print("=" * 80)

    stats = {"trips": 0, "transactions": 0, "drivers": 0, "orgs": 0, "fleets": 0}
    status = "SUCCESS"
    error_log = []
    conn = None

    try:
        conn = get_connection()
        log_execution_start(conn, run_id, run_type, start_dt, end_dt)
    except Exception as e:
        print(f"[ERROR] Could not initialize audit log in DB: {e}")
        error_log.append(f"DB Init Error: {e}")

    try:
        token = get_access_token()
        orgs = get_operating_fleets(token)

        print(f"Dynamically discovered {len(orgs)} active fleet organization(s) across all cities.")

        fleets_processed_count = 0
        for i, org in enumerate(orgs, 1):
            org_uuid = org["id"]
            org_name = org.get("name")
            print(f"\n[{i}/{len(orgs)}] Operating Fleet: {org_name}")
            fleet_has_error = False

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
                    fleet_has_error = True
                    err_msg = f"{org_name} [{report_type}]: {e}"
                    print(f"    [ERROR] {err_msg}")
                    error_log.append(err_msg)
                    status = "PARTIAL"

                time.sleep(2)

            if not fleet_has_error:
                fleets_processed_count += 1

        stats["fleets"] = fleets_processed_count

    except Exception as e:
        status = "FAILED"
        error_log.append(f"Fatal execution error: {e}")
        print(f"[FATAL ERROR] {e}")

    duration = time.time() - start_wall_time
    err_str = "; ".join(error_log) if error_log else None

    email_sent = False
    try:
        email_sent = send_execution_email(run_id, run_type, target_date, status, stats, duration, err_str)
    except Exception as e:
        print(f"[EMAIL DISPATCH ERROR] {e}")

    try:
        if not conn or conn.closed:
            conn = get_connection()
        log_execution_finish(
            conn, run_id, status, stats["fleets"], stats["trips"],
            stats["transactions"], stats["drivers"], stats["orgs"],
            err_str, email_sent
        )
    except Exception as e:
        print(f"[AUDIT LOG UPDATE ERROR] {e}")
    finally:
        if conn and not conn.closed:
            conn.close()

    print("\n" + "=" * 80)
    print(f"[UBER PIPELINE RUNNER] FINISHED WITH STATUS: {status} in {duration:.1f}s")
    print("=" * 80)
    return status == "SUCCESS"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LetzRyd Uber Data Pipeline Runner")
    parser.add_argument("--date", type=str, help="Target Date to sync (YYYY-MM-DD). Defaults to yesterday.")
    args = parser.parse_args()

    t_date = None
    if args.date:
        try:
            t_date = datetime.datetime.strptime(args.date.strip(), "%Y-%m-%d").date()
        except ValueError:
            parser.error(f"Invalid date format for --date: '{args.date}'. Expected YYYY-MM-DD.")

    success = run_pipeline(target_date=t_date, run_type="MANUAL_CLI" if args.date else "DAILY_SCHEDULED")
    if not success:
        sys.exit(1)
