import psycopg2

conn = psycopg2.connect(
    host="35.200.196.113",
    port=5432,
    dbname="postgres",
    user="postgres",
    password=r"8S5]U3@L^Xz)\FH}"
)
cur = conn.cursor()

sql = """
CREATE OR REPLACE FUNCTION fn_sync_core_uber()
RETURNS TRIGGER 
LANGUAGE plpgsql
AS $$
BEGIN
    -- 1. Refresh core_uber_daily for active 30-day window
    WITH trips_agg AS (
        SELECT 
            t.trip_date AS op_date,
            UPPER(REPLACE(t.car_no, ' ', '')) AS veh_no,
            t.driver_uuid,
            COUNT(*) FILTER (WHERE t.trip_status = 'COMPLETED') AS trips,
            COALESCE(SUM(t.trip_distance), 0.0) AS dist_km
        FROM uber_pipeline_trips t
        WHERE t.trip_date >= (CURRENT_DATE - INTERVAL '30 days')
          AND t.car_no IS NOT NULL AND TRIM(t.car_no) <> ''
        GROUP BY 1, 2, 3
    ),
    txns_agg AS (
        SELECT 
            COALESCE(ot.trx_date, ot.reporting_time::date, t.trip_date) AS op_date,
            UPPER(REPLACE(COALESCE(ot.vehicle_number, t.car_no), ' ', '')) AS veh_no,
            COALESCE(ot.driver_uuid, t.driver_uuid) AS driver_uuid,
            SUM(COALESCE(ot.actual_earnings, 0.0)) AS earnings,
            SUM(COALESCE(ot.cash_collected, 0.0)) AS cash,
            SUM(COALESCE(ot.refunds_toll, 0.0)) AS toll,
            0.0 AS sub_fee
        FROM uber_pipeline_order_transactions ot
        FULL OUTER JOIN uber_pipeline_trips t ON ot.trip_uuid = t.trip_uuid
        WHERE (ot.trx_date >= (CURRENT_DATE - INTERVAL '30 days') 
            OR ot.reporting_time >= (CURRENT_DATE - INTERVAL '30 days') 
            OR t.trip_date >= (CURRENT_DATE - INTERVAL '30 days'))
        GROUP BY 1, 2, 3
    ),
    combined AS (
        SELECT 
            COALESCE(t.op_date, x.op_date) AS operational_date,
            COALESCE(t.veh_no, x.veh_no) AS vehicle_number,
            COALESCE(t.driver_uuid, x.driver_uuid) AS driver_uuid,
            COALESCE(t.trips, 0) AS completed_trips,
            COALESCE(t.dist_km, 0) AS total_trip_distance_km,
            COALESCE(x.earnings, 0) AS net_fare_earnings,
            COALESCE(x.cash, 0) AS cash_collected,
            COALESCE(x.toll, 0) AS tolls_refunded,
            COALESCE(x.sub_fee, 0) AS driver_subscription_charge,
            (COALESCE(x.earnings, 0) - COALESCE(x.cash, 0) + COALESCE(x.toll, 0) - COALESCE(x.sub_fee, 0)) AS net_driver_day_balance
        FROM trips_agg t
        FULL OUTER JOIN txns_agg x 
          ON t.op_date = x.op_date 
         AND t.veh_no = x.veh_no 
         AND COALESCE(t.driver_uuid, '') = COALESCE(x.driver_uuid, '')
        WHERE COALESCE(t.veh_no, x.veh_no) IS NOT NULL
    )
    INSERT INTO core_uber_daily (
        operational_date, vehicle_number, driver_uuid, vendor_code, city,
        completed_trips, total_trip_distance_km, net_fare_earnings, cash_collected,
        tolls_refunded, driver_subscription_charge, net_driver_day_balance
    )
    SELECT 
        c.operational_date, c.vehicle_number, c.driver_uuid, dvs.partner_id AS vendor_code,
        COALESCE(dvs.city, 'Hyderabad') AS city, c.completed_trips, c.total_trip_distance_km,
        c.net_fare_earnings, c.cash_collected, c.tolls_refunded, c.driver_subscription_charge,
        c.net_driver_day_balance
    FROM combined c
    LEFT JOIN core_daily_vehicle_status dvs 
      ON c.vehicle_number = dvs.vehicle_number AND c.operational_date = dvs.status_date
    ON CONFLICT (operational_date, vehicle_number, driver_uuid) DO UPDATE SET
        vendor_code = EXCLUDED.vendor_code,
        city = EXCLUDED.city,
        completed_trips = EXCLUDED.completed_trips,
        total_trip_distance_km = EXCLUDED.total_trip_distance_km,
        net_fare_earnings = EXCLUDED.net_fare_earnings,
        cash_collected = EXCLUDED.cash_collected,
        tolls_refunded = EXCLUDED.tolls_refunded,
        driver_subscription_charge = EXCLUDED.driver_subscription_charge,
        net_driver_day_balance = EXCLUDED.net_driver_day_balance,
        updated_at = NOW();

    -- 2. Refresh core_uber_weekly for active 30-day window
    WITH weekly_cal AS (
        SELECT 
            d.operational_date, d.vehicle_number, d.vendor_code, d.city,
            d.completed_trips, d.total_trip_distance_km, d.net_fare_earnings,
            d.cash_collected, d.tolls_refunded, d.driver_subscription_charge,
            DATE_TRUNC('week', d.operational_date)::date AS week_start,
            (DATE_TRUNC('week', d.operational_date) + INTERVAL '6 days')::date AS week_end,
            EXTRACT(ISOYEAR FROM d.operational_date)::int AS settlement_year,
            EXTRACT(WEEK FROM d.operational_date)::int AS settlement_week,
            'CY' || SUBSTRING(EXTRACT(ISOYEAR FROM d.operational_date)::text FROM 3 FOR 2) || 'WK' || LPAD(EXTRACT(WEEK FROM d.operational_date)::text, 2, '0') AS week_id
        FROM core_uber_daily d
        WHERE d.operational_date >= (CURRENT_DATE - INTERVAL '30 days')
    ),
    weekly_agg AS (
        SELECT 
            settlement_year, settlement_week, week_id, week_start, week_end, vehicle_number,
            COALESCE(vendor_code, 'UNASSIGNED') AS vendor_code, MAX(city) AS city,
            COUNT(DISTINCT operational_date) FILTER (WHERE completed_trips > 0) AS active_days,
            SUM(completed_trips) AS completed_trips, SUM(total_trip_distance_km) AS total_trip_km,
            SUM(net_fare_earnings) AS uber_total_earnings, SUM(cash_collected) AS uber_cash_collection,
            SUM(tolls_refunded) AS uber_toll, SUM(driver_subscription_charge) AS uber_driver_sub_charge
        FROM weekly_cal
        GROUP BY settlement_year, settlement_week, week_id, week_start, week_end, vehicle_number, COALESCE(vendor_code, 'UNASSIGNED')
    ),
    raw_inc_agg AS (
        SELECT 
            UPPER(REPLACE(number_plate, ' ', '')) AS veh_no,
            start_date::date AS week_start,
            SUM(total_payout) AS total_payout
        FROM uber_vehicle_incentives_raw
        WHERE number_plate IS NOT NULL AND TRIM(number_plate) <> '' AND number_plate <> 'nan'
          AND start_date::date >= (CURRENT_DATE - INTERVAL '30 days')
        GROUP BY 1, 2
    )
    INSERT INTO core_uber_weekly (
        settlement_year, settlement_week, week_id, week_start, week_end, vehicle_number,
        vendor_code, city, active_days, completed_trips, total_trip_km, uber_total_earnings,
        uber_cash_collection, uber_toll, uber_driver_sub_charge, uber_vehicle_incentive,
        uber_pass_on_incentive, uber_letzryd_incentive, uber_week_balance
    )
    SELECT 
        w.settlement_year, w.settlement_week, w.week_id, w.week_start, w.week_end, w.vehicle_number,
        w.vendor_code, w.city, w.active_days, w.completed_trips, w.total_trip_km,
        w.uber_total_earnings, w.uber_cash_collection, w.uber_toll, w.uber_driver_sub_charge,
        COALESCE(inc.total_payout, 0.00) AS uber_vehicle_incentive, 0.00 AS uber_pass_on_incentive,
        COALESCE(inc.total_payout, 0.00) AS uber_letzryd_incentive,
        (w.uber_total_earnings - w.uber_cash_collection + w.uber_toll - w.uber_driver_sub_charge + COALESCE(inc.total_payout, 0.00)) AS uber_week_balance
    FROM weekly_agg w
    LEFT JOIN raw_inc_agg inc 
      ON w.vehicle_number = inc.veh_no AND inc.week_start = w.week_start
    ON CONFLICT (settlement_year, settlement_week, vehicle_number, vendor_code) DO UPDATE SET
        active_days = EXCLUDED.active_days,
        completed_trips = EXCLUDED.completed_trips,
        total_trip_km = EXCLUDED.total_trip_km,
        uber_total_earnings = EXCLUDED.uber_total_earnings,
        uber_cash_collection = EXCLUDED.uber_cash_collection,
        uber_toll = EXCLUDED.uber_toll,
        uber_driver_sub_charge = EXCLUDED.uber_driver_sub_charge,
        uber_vehicle_incentive = EXCLUDED.uber_vehicle_incentive,
        uber_pass_on_incentive = EXCLUDED.uber_pass_on_incentive,
        uber_letzryd_incentive = EXCLUDED.uber_letzryd_incentive,
        uber_week_balance = EXCLUDED.uber_week_balance,
        updated_at = NOW();

    RETURN NULL;
EXCEPTION WHEN OTHERS THEN
    RAISE WARNING 'fn_sync_core_uber downstream warning: %', SQLERRM;
    RETURN NULL;
END;
$$;
"""

cur.execute(sql)
conn.commit()
print("SUCCESS: fn_sync_core_uber is now protected with EXCEPTION handling!")
conn.close()
