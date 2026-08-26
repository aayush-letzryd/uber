import os
import io
import re
import zipfile
import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
from config.settings import (
    DB_CONFIG,
    TABLE_TRIPS,
    TABLE_TRANSACTIONS,
    TABLE_DRIVER_PAYMENTS,
    TABLE_ORG_PAYMENTS,
    TABLE_LOGS,
    TABLE_STATE
)

DRIVER_COL_MAP = {
    "Driver UUID": "driver_uuid", "Driver first name": "driver_first_name", "Driver surname": "driver_surname",
    "Total earnings": "total_earnings", "Total earnings:Net fare": "total_earnings_net_fare",
    "Total earnings : Net fare": "total_earnings_net_fare", "Total earnings:Promotions": "total_earnings_promotions",
    "Total earnings : Promotions": "total_earnings_promotions", "Total earnings:Tip": "total_earnings_tip",
    "Total earnings : Tip": "total_earnings_tip", "Total earnings:Taxes": "total_earnings_taxes",
    "Total earnings : Taxes": "total_earnings_taxes",
    "Total earnings:Other fees:Platform fee": "total_earnings_other_fees_platform_fee",
    "Total earnings : Other fees : Platform fee": "total_earnings_other_fees_platform_fee",
    "Total earnings:Other earnings": "total_earnings_other_earnings",
    "Total earnings:Other earnings:Other": "total_earnings_other_earnings_other",
    "Total earnings : Other earnings : Other": "total_earnings_other_earnings_other",
    "Total earnings:Other earnings:Adjustment": "total_earnings_other_earnings_adjustment",
    "Total earnings : Other earnings : Adjustment": "total_earnings_other_earnings_adjustment",
    "Refunds & Expenses": "refunds_expenses", "Refunds & Expenses:Taxes:Tax": "refunds_expenses_taxes_tax",
    "Refunds & Expenses : Taxes : Tax": "refunds_expenses_taxes_tax",
    "Refunds & Expenses:Expenses:Driver subscription charge": "refunds_expenses_expenses_driver_subscription_charge",
    "Refunds & Expenses : Expenses : Driver subscription charge": "refunds_expenses_expenses_driver_subscription_charge",
    "Refunds & Expenses:Refunds:Toll": "refunds_expenses_refunds_toll",
    "Refunds & Expenses : Refunds : Toll": "refunds_expenses_refunds_toll",
    "Payouts": "payouts", "Payouts:Transferred To Bank Account": "payouts_transferred_to_bank_account",
    "Payouts : Transferred To Bank Account": "payouts_transferred_to_bank_account",
    "Payouts:Cash collected": "payouts_cash_collected", "Payouts : Cash collected": "payouts_cash_collected",
    "Paid to third parties": "paid_to_third_parties",
    "Paid to third parties:Paid to airport": "paid_to_third_parties_paid_to_airport",
    "Paid to third parties : Paid to airport": "paid_to_third_parties_paid_to_airport",
    "Paid to third parties:Railway pick-up fee": "paid_to_third_parties_railway_pickup_fee",
    "Paid to third parties : Railway pick-up fee": "paid_to_third_parties_railway_pickup_fee",
    "Paid to Uber": "paid_to_uber", "Paid to Uber:Booking Fee": "paid_to_uber_booking_fee",
    "Paid to Uber:Booking fee": "paid_to_uber_booking_fee", "Paid to Uber : Booking fee": "paid_to_uber_booking_fee",
}

ORG_COL_MAP = {
    "Organization UUID": "organization_uuid", "Organisation name": "organisation_name", "Org alias": "org_alias",
    "Driver first name": "driver_first_name", "Driver surname": "driver_surname",
    "Start of period balance": "start_of_period_balance", "End of period balance": "end_of_period_balance",
    "Total earnings": "total_earnings", "Total earnings:Net fare": "total_earnings_net_fare",
    "Total earnings : Net fare": "total_earnings_net_fare", "Total earnings:Promotions": "total_earnings_promotions",
    "Total earnings : Promotions": "total_earnings_promotions", "Total earnings:Tip": "total_earnings_tip",
    "Total earnings : Tip": "total_earnings_tip", "Total earnings:Taxes": "total_earnings_taxes",
    "Total earnings : Taxes": "total_earnings_taxes",
    "Total earnings:Other fees:Platform fee": "total_earnings_other_fees_platform_fee",
    "Total earnings : Other fees : Platform fee": "total_earnings_other_fees_platform_fee",
    "Total earnings:Other earnings:Other": "total_earnings_other_earnings_other",
    "Total earnings : Other earnings : Other": "total_earnings_other_earnings_other",
    "Total earnings:Other earnings:Adjustment": "total_earnings_other_earnings_adjustment",
    "Total earnings : Other earnings : Adjustment": "total_earnings_other_earnings_adjustment",
    "Refunds & Expenses": "refunds_expenses", "Refunds & Expenses:Taxes:Tax": "refunds_expenses_taxes_tax",
    "Refunds & Expenses : Taxes : Tax": "refunds_expenses_taxes_tax",
    "Refunds & Expenses:Expenses:Driver subscription charge": "refunds_expenses_expenses_driver_subscription_charge",
    "Refunds & Expenses : Expenses : Driver subscription charge": "refunds_expenses_expenses_driver_subscription_charge",
    "Refunds & Expenses:Refunds:Toll": "refunds_expenses_refunds_toll",
    "Refunds & Expenses : Refunds : Toll": "refunds_expenses_refunds_toll",
    "Payouts": "payouts", "Payouts:Cash collected": "payouts_cash_collected",
    "Payouts : Cash collected": "payouts_cash_collected",
    "Payouts:Transferred To Bank Account": "payouts_transferred_to_bank_account",
    "Payouts : Transferred To Bank Account": "payouts_transferred_to_bank_account",
    "Paid to third parties": "paid_to_third_parties",
    "Paid to third parties:Paid to airport": "paid_to_third_parties_paid_to_airport",
    "Paid to third parties : Paid to airport": "paid_to_third_parties_paid_to_airport",
    "Paid to third parties:Railway pick-up fee": "paid_to_third_parties_railway_pickup_fee",
    "Paid to third parties : Railway pick-up fee": "paid_to_third_parties_railway_pickup_fee",
    "Paid to Uber": "paid_to_uber", "Paid to Uber:Booking fee": "paid_to_uber_booking_fee",
    "Paid to Uber : Booking fee": "paid_to_uber_booking_fee",
}

ORDER_COL_MAP = {
    "transaction UUID": "transaction_uuid", "Driver UUID": "driver_uuid",
    "Driver first name": "driver_first_name", "Driver surname": "driver_surname",
    "Trip UUID": "trip_uuid", "Description": "description",
    "Organisation name": "organisation_name", "Org alias": "org_alias",
    "vs reporting": "reporting_time", "Reporting Time": "reporting_time",
    "Paid to you": "paid_to_you", "Actual earnings": "actual_earnings",
    "Paid to you : Your earnings": "actual_earnings",
    "Paid to you : Trip balance : Payouts : Cash collected": "cash_collected",
    "Paid to you:Trip balance:Payouts:Transferred To Bank Account": "bank_payout",
    "Paid to you:Trip balance:Refunds:Toll": "refunds_toll",
    "Paid to you : Trip balance : Refunds : Toll": "refunds_toll",
    "Car No": "vehicle_number", "Vehicle": "vehicle_number", "Vehicle Number": "vehicle_number",
}

def get_row_val(row, col):
    val = row.get(col)
    if isinstance(val, pd.Series):
        s = val.dropna()
        return s.iloc[0] if not s.empty else None
    return val

def safe_float(val):
    if val is None or pd.isna(val):
        return None
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).replace(",", "").strip()
        if s == "" or s == "-" or s.lower() in ("nan", "none", "null", "nat"):
            return None
        return float(s)
    except (TypeError, ValueError):
        return None

def safe_str(val):
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if s == "" or s.lower() in ("nan", "none", "null", "nat"):
        return None
    return s

def safe_ts(val):
    if val is None or pd.isna(val):
        return None
    try:
        ts = pd.to_datetime(val)
        if pd.isna(ts):
            return None
        return ts.to_pydatetime()
    except Exception:
        return None

def is_valid_uuid(val):
    if val is None or pd.isna(val):
        return False
    return bool(re.match(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", str(val).strip().lower()))

def read_report_dataframe(filepath_or_bytes, encoding="utf-8"):
    if isinstance(filepath_or_bytes, str):
        if filepath_or_bytes.endswith(".zip") or zipfile.is_zipfile(filepath_or_bytes):
            with zipfile.ZipFile(filepath_or_bytes, "r") as z:
                csv_files = [f for f in z.namelist() if f.endswith(".csv")]
                dfs = [pd.read_csv(z.open(f), encoding=encoding, encoding_errors="replace", low_memory=False) for f in csv_files]
                return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        return pd.read_csv(filepath_or_bytes, encoding=encoding, encoding_errors="replace", low_memory=False)
    elif isinstance(filepath_or_bytes, (bytes, bytearray)):
        if filepath_or_bytes.startswith(b"PK\x03\x04"):
            with zipfile.ZipFile(io.BytesIO(filepath_or_bytes)) as z:
                csv_files = [f for f in z.namelist() if f.endswith(".csv")]
                dfs = [pd.read_csv(z.open(f), encoding=encoding, encoding_errors="replace", low_memory=False) for f in csv_files]
                return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        return pd.read_csv(io.BytesIO(filepath_or_bytes), encoding=encoding, encoding_errors="replace", low_memory=False)
    elif isinstance(filepath_or_bytes, pd.DataFrame):
        return filepath_or_bytes
    raise ValueError(f"Unsupported payload type: {type(filepath_or_bytes)}")

def get_connection():
    conn = psycopg2.connect(
        **DB_CONFIG,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5
    )
    return conn

def log_execution_start(conn, run_id, run_type, start_dt, end_dt):
    try:
        cur = conn.cursor()
        cur.execute(f"""
            INSERT INTO {TABLE_LOGS} (run_id, run_type, target_window_start, target_window_end, start_time, status)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, 'RUNNING');
        """, (run_id, run_type, start_dt, end_dt))
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()

def log_execution_finish(conn, run_id, status, fleets, trips, txns, drivers, orgs, error_msg, email_sent):
    try:
        cur = conn.cursor()
        cur.execute(f"""
            UPDATE {TABLE_LOGS}
            SET end_time = CURRENT_TIMESTAMP,
                status = %s,
                fleets_processed = %s,
                trips_inserted = %s,
                transactions_inserted = %s,
                drivers_inserted = %s,
                orgs_inserted = %s,
                error_message = %s,
                email_sent = %s
            WHERE run_id = %s;
        """, (status, fleets, trips, txns, drivers, orgs, error_msg, email_sent, run_id))
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()

def load_trips_csv(conn, filepath_or_df, org_name, run_id=None, report_id=None, w_start=None, w_end=None):
    df = read_report_dataframe(filepath_or_df)
    rows, skipped = [], 0
    for _, row in df.iterrows():
        trip_uuid = safe_str(get_row_val(row, "Trip UUID"))
        if not trip_uuid or not is_valid_uuid(trip_uuid):
            skipped += 1
            continue
        req_time = safe_ts(get_row_val(row, "Trip request time"))
        drop_time = safe_ts(get_row_val(row, "Trip drop-off time"))
        trip_date = req_time.date() if req_time else None
        driver_name = f"{safe_str(get_row_val(row, 'Driver first name')) or ''} {safe_str(get_row_val(row, 'Driver surname')) or ''}".strip()
        
        rows.append((
            trip_date, trip_uuid, safe_str(get_row_val(row, "Driver UUID")),
            driver_name if driver_name else None, safe_str(get_row_val(row, "Vehicle UUID")),
            safe_str(get_row_val(row, "Number plate")), safe_str(get_row_val(row, "Service type")),
            req_time, drop_time, safe_str(get_row_val(row, "Pick-up address")),
            safe_str(get_row_val(row, "Drop-off address")), safe_float(get_row_val(row, "Trip distance")),
            safe_str(get_row_val(row, "Trip status")), safe_str(get_row_val(row, "Product type")),
            safe_float(get_row_val(row, "Final rider fare")), safe_str(get_row_val(row, "Payment type")),
            safe_str(get_row_val(row, "Rider name")), org_name, report_id, run_id, w_start, w_end
        ))
    if rows:
        cur = conn.cursor()
        try:
            execute_values(cur, f"""
                INSERT INTO {TABLE_TRIPS} (
                    trip_date, trip_uuid, driver_uuid, driver_name, vehicle_uuid, car_no,
                    service_type, trip_request_time, trip_drop_off_time, pick_up_address,
                    drop_off_address, trip_distance, trip_status, product_type,
                    final_rider_fare, payment_type, rider_name, org_name,
                    source_report_id, run_id, report_fetch_window_start, report_fetch_window_end
                ) VALUES %s
                ON CONFLICT (trip_uuid) DO UPDATE SET
                    trip_date                  = EXCLUDED.trip_date,
                    driver_name                = EXCLUDED.driver_name,
                    car_no                     = EXCLUDED.car_no,
                    trip_distance              = EXCLUDED.trip_distance,
                    trip_status                = EXCLUDED.trip_status,
                    final_rider_fare           = EXCLUDED.final_rider_fare,
                    org_name                   = EXCLUDED.org_name,
                    source_report_id           = EXCLUDED.source_report_id,
                    run_id                     = EXCLUDED.run_id,
                    report_fetch_window_start  = EXCLUDED.report_fetch_window_start,
                    report_fetch_window_end    = EXCLUDED.report_fetch_window_end,
                    ingested_at                = CURRENT_TIMESTAMP;
            """, rows)
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            raise e
        cur.close()
    print(f"  {TABLE_TRIPS}: {len(rows)} trips upserted ({skipped} skipped)")
    return len(rows)

def load_order_transactions_csv(conn, filepath_or_df, org_name, run_id=None, report_id=None, w_start=None, w_end=None):
    df = read_report_dataframe(filepath_or_df)
    df = df.rename(columns=ORDER_COL_MAP)
    df = df.loc[:, ~df.columns.duplicated()]
    rows, skipped = [], 0
    for _, row in df.iterrows():
        txn_uuid = safe_str(get_row_val(row, "transaction_uuid"))
        if not txn_uuid or not is_valid_uuid(txn_uuid):
            skipped += 1
            continue
        rep_time = safe_ts(get_row_val(row, "reporting_time"))
        trx_date = rep_time.date() if rep_time else None
        
        rows.append((
            trx_date, txn_uuid, safe_str(get_row_val(row, "driver_uuid")),
            safe_str(get_row_val(row, "driver_first_name")), safe_str(get_row_val(row, "driver_surname")),
            safe_str(get_row_val(row, "trip_uuid")), safe_str(get_row_val(row, "description")),
            safe_str(get_row_val(row, "organisation_name")), safe_str(get_row_val(row, "org_alias")),
            rep_time, safe_float(get_row_val(row, "paid_to_you")), safe_float(get_row_val(row, "actual_earnings")),
            safe_float(get_row_val(row, "cash_collected")), safe_float(get_row_val(row, "refunds_toll")),
            safe_str(get_row_val(row, "vehicle_number")), org_name, report_id, run_id, w_start, w_end
        ))
    if rows:
        cur = conn.cursor()
        try:
            execute_values(cur, f"""
                INSERT INTO {TABLE_TRANSACTIONS} (
                    trx_date, transaction_uuid, driver_uuid, driver_first_name, driver_surname,
                    trip_uuid, description, organisation_name, org_alias, reporting_time,
                    paid_to_you, actual_earnings, cash_collected, refunds_toll,
                    vehicle_number, org_name, source_report_id, run_id,
                    report_fetch_window_start, report_fetch_window_end
                ) VALUES %s
                ON CONFLICT (transaction_uuid) DO UPDATE SET
                    description                = EXCLUDED.description,
                    paid_to_you                = EXCLUDED.paid_to_you,
                    actual_earnings            = EXCLUDED.actual_earnings,
                    cash_collected             = EXCLUDED.cash_collected,
                    refunds_toll               = EXCLUDED.refunds_toll,
                    vehicle_number             = EXCLUDED.vehicle_number,
                    source_report_id           = EXCLUDED.source_report_id,
                    run_id                     = EXCLUDED.run_id,
                    report_fetch_window_start  = EXCLUDED.report_fetch_window_start,
                    report_fetch_window_end    = EXCLUDED.report_fetch_window_end,
                    ingested_at                = CURRENT_TIMESTAMP;
            """, rows)
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            raise e
        cur.close()
    print(f"  {TABLE_TRANSACTIONS}: {len(rows)} transactions upserted ({skipped} skipped)")
    return len(rows)

def load_driver_csv(conn, filepath_or_df, window_start, window_end, org_name, run_id=None, report_id=None):
    df = read_report_dataframe(filepath_or_df)
    df = df.rename(columns=DRIVER_COL_MAP)
    df = df.loc[:, ~df.columns.duplicated()]
    rows, skipped = [], 0
    for _, row in df.iterrows():
        driver_uuid = safe_str(get_row_val(row, "driver_uuid"))
        if not driver_uuid or not is_valid_uuid(driver_uuid):
            skipped += 1
            continue
        rows.append((
            driver_uuid, safe_str(get_row_val(row, "driver_first_name")), safe_str(get_row_val(row, "driver_surname")),
            safe_float(get_row_val(row, "total_earnings")), safe_float(get_row_val(row, "total_earnings_net_fare")),
            safe_float(get_row_val(row, "total_earnings_promotions")), safe_float(get_row_val(row, "total_earnings_tip")),
            safe_float(get_row_val(row, "total_earnings_taxes")), safe_float(get_row_val(row, "total_earnings_other_fees_platform_fee")),
            safe_float(get_row_val(row, "total_earnings_other_earnings")), safe_float(get_row_val(row, "total_earnings_other_earnings_other")),
            safe_float(get_row_val(row, "total_earnings_other_earnings_adjustment")), safe_float(get_row_val(row, "refunds_expenses")),
            safe_float(get_row_val(row, "refunds_expenses_taxes_tax")), safe_float(get_row_val(row, "refunds_expenses_expenses_driver_subscription_charge")),
            safe_float(get_row_val(row, "refunds_expenses_refunds_toll")), safe_float(get_row_val(row, "payouts")),
            safe_float(get_row_val(row, "payouts_transferred_to_bank_account")), safe_float(get_row_val(row, "payouts_cash_collected")),
            safe_float(get_row_val(row, "paid_to_third_parties")), safe_float(get_row_val(row, "paid_to_third_parties_paid_to_airport")),
            safe_float(get_row_val(row, "paid_to_third_parties_railway_pickup_fee")), safe_float(get_row_val(row, "paid_to_uber")),
            safe_float(get_row_val(row, "paid_to_uber_booking_fee")), org_name, report_id, run_id, window_start, window_end
        ))
    if rows:
        cur = conn.cursor()
        try:
            execute_values(cur, f"""
                INSERT INTO {TABLE_DRIVER_PAYMENTS} (
                    driver_uuid, driver_first_name, driver_surname,
                    total_earnings, total_earnings_net_fare, total_earnings_promotions,
                    total_earnings_tip, total_earnings_taxes, total_earnings_other_fees_platform_fee,
                    total_earnings_other_earnings, total_earnings_other_earnings_other, total_earnings_other_earnings_adjustment,
                    refunds_expenses, refunds_expenses_taxes_tax,
                    refunds_expenses_expenses_driver_subscription_charge,
                    refunds_expenses_refunds_toll, payouts,
                    payouts_transferred_to_bank_account, payouts_cash_collected,
                    paid_to_third_parties, paid_to_third_parties_paid_to_airport,
                    paid_to_third_parties_railway_pickup_fee,
                    paid_to_uber, paid_to_uber_booking_fee,
                    org_name, source_report_id, run_id,
                    report_fetch_window_start, report_fetch_window_end
                ) VALUES %s
                ON CONFLICT (driver_uuid, org_name, report_fetch_window_start, report_fetch_window_end)
                DO UPDATE SET
                    total_earnings             = EXCLUDED.total_earnings,
                    total_earnings_net_fare    = EXCLUDED.total_earnings_net_fare,
                    payouts_cash_collected     = EXCLUDED.payouts_cash_collected,
                    source_report_id           = EXCLUDED.source_report_id,
                    run_id                     = EXCLUDED.run_id,
                    ingested_at                = CURRENT_TIMESTAMP;
            """, rows)
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            raise e
        cur.close()
    print(f"  {TABLE_DRIVER_PAYMENTS}: {len(rows)} drivers upserted ({skipped} skipped)")
    return len(rows)

def load_org_csv(conn, filepath_or_df, window_start, window_end, run_id=None, report_id=None):
    df = read_report_dataframe(filepath_or_df)
    df = df.rename(columns=ORG_COL_MAP)
    df = df.loc[:, ~df.columns.duplicated()]
    rows, skipped = [], 0
    for _, row in df.iterrows():
        org_uuid = safe_str(get_row_val(row, "organization_uuid"))
        if not org_uuid or not is_valid_uuid(org_uuid):
            skipped += 1
            continue
        rows.append((
            org_uuid, safe_str(get_row_val(row, "organisation_name")), safe_str(get_row_val(row, "org_alias")),
            safe_str(get_row_val(row, "driver_first_name")), safe_str(get_row_val(row, "driver_surname")),
            safe_float(get_row_val(row, "start_of_period_balance")), safe_float(get_row_val(row, "end_of_period_balance")),
            safe_float(get_row_val(row, "total_earnings")), safe_float(get_row_val(row, "total_earnings_net_fare")),
            safe_float(get_row_val(row, "total_earnings_promotions")), safe_float(get_row_val(row, "total_earnings_tip")),
            safe_float(get_row_val(row, "total_earnings_taxes")), safe_float(get_row_val(row, "total_earnings_other_fees_platform_fee")),
            safe_float(get_row_val(row, "total_earnings_other_earnings_other")), safe_float(get_row_val(row, "total_earnings_other_earnings_adjustment")),
            safe_float(get_row_val(row, "refunds_expenses")), safe_float(get_row_val(row, "refunds_expenses_taxes_tax")),
            safe_float(get_row_val(row, "refunds_expenses_expenses_driver_subscription_charge")),
            safe_float(get_row_val(row, "refunds_expenses_refunds_toll")), safe_float(get_row_val(row, "payouts")),
            safe_float(get_row_val(row, "payouts_cash_collected")), safe_float(get_row_val(row, "payouts_transferred_to_bank_account")),
            safe_float(get_row_val(row, "paid_to_third_parties")), safe_float(get_row_val(row, "paid_to_third_parties_paid_to_airport")),
            safe_float(get_row_val(row, "paid_to_third_parties_railway_pickup_fee")), safe_float(get_row_val(row, "paid_to_uber")),
            safe_float(get_row_val(row, "paid_to_uber_booking_fee")), report_id, run_id, window_start, window_end
        ))
    if rows:
        cur = conn.cursor()
        try:
            execute_values(cur, f"""
                INSERT INTO {TABLE_ORG_PAYMENTS} (
                    organization_uuid, organisation_name, org_alias,
                    driver_first_name, driver_surname,
                    start_of_period_balance, end_of_period_balance,
                    total_earnings, total_earnings_net_fare, total_earnings_promotions,
                    total_earnings_tip, total_earnings_taxes, total_earnings_other_fees_platform_fee,
                    total_earnings_other_earnings_other, total_earnings_other_earnings_adjustment,
                    refunds_expenses, refunds_expenses_taxes_tax,
                    refunds_expenses_expenses_driver_subscription_charge,
                    refunds_expenses_refunds_toll, payouts,
                    payouts_cash_collected, payouts_transferred_to_bank_account,
                    paid_to_third_parties, paid_to_third_parties_paid_to_airport,
                    paid_to_third_parties_railway_pickup_fee,
                    paid_to_uber, paid_to_uber_booking_fee,
                    source_report_id, run_id,
                    report_fetch_window_start, report_fetch_window_end
                ) VALUES %s
                ON CONFLICT (organization_uuid, report_fetch_window_start, report_fetch_window_end)
                DO UPDATE SET
                    total_earnings         = EXCLUDED.total_earnings,
                    total_earnings_net_fare= EXCLUDED.total_earnings_net_fare,
                    payouts_cash_collected = EXCLUDED.payouts_cash_collected,
                    source_report_id       = EXCLUDED.source_report_id,
                    run_id                 = EXCLUDED.run_id,
                    ingested_at            = CURRENT_TIMESTAMP;
            """, rows)
            conn.commit()
        except Exception as e:
            conn.rollback()
            cur.close()
            raise e
        cur.close()
    print(f"  {TABLE_ORG_PAYMENTS}: {len(rows)} org rows upserted ({skipped} skipped)")
    return len(rows)
