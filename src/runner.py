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
from src.backfill import run_backfill

REPORT_TYPES = [
    "REPORT_TYPE_TRIP_ACTIVITY",
    "REPORT_TYPE_PAYMENTS_ORDER",
    "REPORT_TYPE_PAYMENTS_DRIVER",
    "REPORT_TYPE_PAYMENTS_ORGANIZATION",
]

def ensure_connection(conn):
    if not conn or conn.closed != 0:
        return get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        return conn
    except Exception:
        return get_connection()

def is_another_execution_running(conn, current_run_id):
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT run_id, created_at 
                FROM uber_pipeline_execution_logs 
                WHERE status = 'RUNNING' 
                  AND created_at > (NOW() - INTERVAL '115 minutes')
                  AND run_id != %s;
            """, (current_run_id,))
            row = cur.fetchone()
            if row:
                return row
    except Exception as e:
        print(f"    [Warning] Concurrency check query failed: {e}")
    return None

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

    # 29-Hour Safety Window: target_date 00:00:00 IST -> (target_date + 1 day) 05:00:00 IST
    # Captures full calendar day PLUS data right up to the 5:00 AM execution time
    start_dt = datetime.datetime.combine(target_date, datetime.time.min, tzinfo=ist_tz)
    next_day = target_date + datetime.timedelta(days=1)
    end_dt = datetime.datetime.combine(next_day, datetime.time(hour=5, minute=0, second=0), tzinfo=ist_tz)

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
        active_run = is_another_execution_running(conn, run_id)
        if active_run:
            print(f"\n[CONCURRENCY LOCK] Another execution (Run ID: {active_run[0]}, started at {active_run[1]}) is currently running.")
            print("[CONCURRENCY LOCK] Exiting cleanly to prevent overlapping runs.")
            conn.close()
            return True

        log_execution_start(conn, run_id, run_type, start_dt, end_dt)
    except Exception as e:
        print(f"[ERROR] Could not initialize audit log in DB: {e}")
        error_log.append(f"DB Init Error: {e}")

    try:
        token = None
        try:
            token = get_access_token()
        except Exception as auth_err:
            print(f"[AUTH WARNING] OAuth token fetch encountered an issue: {auth_err}")
            error_log.append(f"Auth Token Warning: {auth_err}")

        orgs = get_operating_fleets(token)
        print(f"Targeting {len(orgs)} active fleet organization(s) across operating cities.")

        fleets_processed_count = 0
        for i, org in enumerate(orgs, 1):
            org_uuid = org["id"]
            org_name = org.get("name", "Unknown Fleet")
            print(f"\n[{i}/{len(orgs)}] Operating Fleet: {org_name} (ID: {org_uuid})")
            fleet_has_error = False
            for report_type in REPORT_TYPES:
                print(f"  * Fetching {report_type}...")
                try:
                    active_token = get_access_token()
                    report_id = get_or_generate_report(active_token, org_uuid, report_type, start_ms, end_ms)
                    wait_for_report(active_token, org_uuid, report_id)
                    path = download_report(active_token, org_uuid, report_id, report_type, org_name)

                    conn = ensure_connection(conn)

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
                    if status != "FAILED":
                        status = "PARTIAL"

                time.sleep(1.5)

            if not fleet_has_error:
                fleets_processed_count += 1

        stats["fleets"] = fleets_processed_count

        # Post-ingestion sync: Decoupled single-shot refresh of core_uber summary tables
        if conn and not conn.closed and (stats["trips"] + stats["transactions"]) > 0:
            try:
                print("\n[CORE SYNC] Triggering post-ingestion summary sync for core_uber...")
                with conn.cursor() as sync_cur:
                    sync_cur.execute("CALL sp_sync_core_uber();")
                conn.commit()
                print("[CORE SYNC] core_uber aggregation completed successfully.")
            except Exception as sync_err:
                print(f"[CORE SYNC WARNING] Non-fatal downstream sync warning: {sync_err}")

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
    parser = argparse.ArgumentParser(description="LetzRyd Uber Data Pipeline Runner & Backfill CLI")
    parser.add_argument("--date", type=str, help="Target Date to sync (YYYY-MM-DD). Defaults to yesterday.")
    parser.add_argument("--days", type=int, help="Backfill past N days ending yesterday.")
    parser.add_argument("--start", type=str, help="Backfill start date (YYYY-MM-DD).")
    parser.add_argument("--end", type=str, help="Backfill end date (YYYY-MM-DD).")
    args = parser.parse_args()

    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = datetime.datetime.now(ist_tz)
    yesterday = now_ist.date() - datetime.timedelta(days=1)

    # 1. Date Range Backfill Mode (--start and --end)
    if args.start or args.end:
        if not (args.start and args.end):
            parser.error("Both --start and --end must be provided together when specifying a custom date range.")
        try:
            s_date = datetime.datetime.strptime(args.start.strip(), "%Y-%m-%d").date()
            e_date = datetime.datetime.strptime(args.end.strip(), "%Y-%m-%d").date()
        except ValueError as ve:
            parser.error(f"Invalid date format: {ve}. Expected YYYY-MM-DD.")
        if s_date > e_date:
            parser.error(f"--start date ({s_date}) cannot be after --end date ({e_date}).")
        
        success = run_backfill(s_date, e_date)
        if not success:
            sys.exit(1)
        sys.exit(0)

    # 2. Past N Days Backfill Mode (--days N)
    if args.days is not None:
        if args.days <= 0:
            parser.error(f"--days must be a positive integer >= 1 (received: {args.days}).")
        s_date = yesterday - datetime.timedelta(days=args.days - 1)
        e_date = yesterday
        success = run_backfill(s_date, e_date)
        if not success:
            sys.exit(1)
        sys.exit(0)

    # 3. Single Date or Scheduled Yesterday Mode (--date YYYY-MM-DD or default)
    t_date = None
    if args.date:
        try:
            t_date = datetime.datetime.strptime(args.date.strip(), "%Y-%m-%d").date()
        except ValueError:
            parser.error(f"Invalid date format for --date: '{args.date}'. Expected YYYY-MM-DD.")

    success = run_pipeline(target_date=t_date, run_type="MANUAL_CLI" if args.date else "DAILY_SCHEDULED")
    if not success:
        sys.exit(1)
