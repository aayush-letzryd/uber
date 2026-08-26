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

MAX_CHUNK_HOURS = 72

def run_backfill(start_date, end_date):
    if start_date > end_date:
        raise ValueError(f"start_date ({start_date}) cannot be greater than end_date ({end_date})")

    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    start_wall_time = time.time()
    now_ist = datetime.datetime.now(ist_tz)
    run_id = f"backfill_{now_ist.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=ist_tz)
    end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=ist_tz)

    total_start_ms = int(start_dt.timestamp() * 1000)
    total_end_ms = int(end_dt.timestamp() * 1000)
    chunk_ms = MAX_CHUNK_HOURS * 3600 * 1000

    window_str = f"{start_date} -> {end_date} (Historical Backfill)"

    print("=" * 80)
    print(f"[UBER BACKFILL ENGINE] RUN ID: {run_id}")
    print(f"Target Range: {window_str}")
    print("=" * 80)

    stats = {"trips": 0, "transactions": 0, "drivers": 0, "orgs": 0, "fleets": 0}
    status = "SUCCESS"
    error_log = []
    conn = None

    try:
        conn = get_connection()
        log_execution_start(conn, run_id, "HISTORICAL_BACKFILL", start_dt, end_dt)
    except Exception as e:
        print(f"[ERROR] Could not initialize audit log in DB: {e}")
        error_log.append(f"DB Init Error: {e}")

    try:
        token = get_access_token()
        orgs = get_operating_fleets(token)
        print(f"Found {len(orgs)} active supplier fleet(s) across all cities.")

        fleets_processed_count = 0
        for i, org in enumerate(orgs, 1):
            org_uuid = org["id"]
            org_name = org.get("name")
            print(f"\n========================================================")
            print(f"[{i}/{len(orgs)}] BACKFILLING FLEET: {org_name}")
            print(f"========================================================")
            fleet_has_error = False

            for report_type in REPORT_TYPES:
                curr_start = total_start_ms
                while curr_start < total_end_ms:
                    curr_end = min(curr_start + chunk_ms, total_end_ms)
                    w_start_dt = datetime.datetime.fromtimestamp(curr_start / 1000, tz=ist_tz)
                    w_end_dt = datetime.datetime.fromtimestamp(curr_end / 1000, tz=ist_tz)

                    print(f"  Requesting chunk [{w_start_dt.strftime('%Y-%m-%d %H:%M')} -> {w_end_dt.strftime('%Y-%m-%d %H:%M')}]...")
                    try:
                        report_id = get_or_generate_report(token, org_uuid, report_type, curr_start, curr_end)
                        wait_for_report(token, org_uuid, report_id)
                        path = download_report(token, org_uuid, report_id, report_type, org_name)

                        if report_type == "REPORT_TYPE_TRIP_ACTIVITY":
                            cnt = load_trips_csv(conn, path, org_name, run_id, report_id, w_start_dt, w_end_dt)
                            stats["trips"] += cnt
                        elif report_type == "REPORT_TYPE_PAYMENTS_ORDER":
                            cnt = load_order_transactions_csv(conn, path, org_name, run_id, report_id, w_start_dt, w_end_dt)
                            stats["transactions"] += cnt
                        elif report_type == "REPORT_TYPE_PAYMENTS_DRIVER":
                            cnt = load_driver_csv(conn, path, w_start_dt, w_end_dt, org_name, run_id, report_id)
                            stats["drivers"] += cnt
                        elif report_type == "REPORT_TYPE_PAYMENTS_ORGANIZATION":
                            cnt = load_org_csv(conn, path, w_start_dt, w_end_dt, run_id, report_id)
                            stats["orgs"] += cnt

                        curr_start = curr_end

                    except Exception as e:
                        fleet_has_error = True
                        err_msg = f"{org_name} [{report_type} chunk {w_start_dt.strftime('%m-%d')}]: {e}"
                        print(f"    [ERROR] {err_msg}")
                        error_log.append(err_msg)
                        status = "PARTIAL"
                        break

                    time.sleep(2)

            if not fleet_has_error:
                fleets_processed_count += 1

        stats["fleets"] = fleets_processed_count

    except Exception as e:
        status = "FAILED"
        error_log.append(f"Fatal backfill error: {e}")

    duration = time.time() - start_wall_time
    err_str = "; ".join(error_log) if error_log else None

    email_sent = False
    try:
        email_sent = send_execution_email(run_id, "HISTORICAL_BACKFILL", window_str, status, stats, duration, err_str)
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
    print(f"[UBER BACKFILL ENGINE] FINISHED WITH STATUS: {status} in {duration:.1f}s")
    print("=" * 80)
    return status == "SUCCESS"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LetzRyd Uber Historical Data Backfill CLI")
    parser.add_argument("--days", type=int, help="Number of past days to backfill ending yesterday (e.g. --days 7)")
    parser.add_argument("--start", type=str, help="Start Date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End Date (YYYY-MM-DD)")

    args = parser.parse_args()
    ist_tz = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    now_ist = datetime.datetime.now(ist_tz)
    yesterday = now_ist.date() - datetime.timedelta(days=1)

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
    elif args.days is not None:
        if args.days <= 0:
            parser.error(f"--days must be a positive integer >= 1 (received: {args.days}).")
        s_date = yesterday - datetime.timedelta(days=args.days - 1)
        e_date = yesterday
    else:
        s_date = yesterday - datetime.timedelta(days=6)
        e_date = yesterday

    success = run_backfill(s_date, e_date)
    if not success:
        sys.exit(1)
