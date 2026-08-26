-- ==============================================================================
-- LetzRyd Uber Data Pipeline Production Schema DDL
-- Non-colliding standalone schema dedicated to automated Uber data ingestion
-- ==============================================================================

-- 1. TRIPS ACTIVITY TABLE (Detailed Ride Telemetry & GPS)
CREATE TABLE IF NOT EXISTS uber_pipeline_trips (
    id                                      BIGSERIAL PRIMARY KEY,
    trip_date                               DATE NOT NULL,
    trip_uuid                               VARCHAR(100) UNIQUE NOT NULL,
    driver_uuid                             VARCHAR(100),
    driver_name                             VARCHAR(255),
    vehicle_uuid                            VARCHAR(100),
    car_no                                  VARCHAR(50),
    service_type                            VARCHAR(100),
    trip_request_time                       TIMESTAMP,
    trip_drop_off_time                      TIMESTAMP,
    pick_up_address                         TEXT,
    drop_off_address                        TEXT,
    trip_distance                           NUMERIC(10,2),
    trip_status                             VARCHAR(50),
    product_type                            VARCHAR(100),
    final_rider_fare                        NUMERIC(10,2),
    payment_type                            VARCHAR(50),
    rider_name                              VARCHAR(255),
    org_name                                VARCHAR(150),
    source_report_id                        VARCHAR(100),
    run_id                                  VARCHAR(100),
    report_fetch_window_start               TIMESTAMP,
    report_fetch_window_end                 TIMESTAMP,
    ingested_at                             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_date ON uber_pipeline_trips (trip_date);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_car ON uber_pipeline_trips (car_no);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_driver ON uber_pipeline_trips (driver_uuid);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_org ON uber_pipeline_trips (org_name);

-- 2. ORDER TRANSACTIONS & FINANCIAL LEDGER
CREATE TABLE IF NOT EXISTS uber_pipeline_order_transactions (
    id                                      BIGSERIAL PRIMARY KEY,
    trx_date                                DATE,
    transaction_uuid                        VARCHAR(100) UNIQUE NOT NULL,
    driver_uuid                             VARCHAR(100),
    driver_first_name                       VARCHAR(100),
    driver_surname                          VARCHAR(100),
    trip_uuid                               VARCHAR(100),
    description                             TEXT,
    organisation_name                       VARCHAR(150),
    org_alias                               VARCHAR(150),
    reporting_time                          TIMESTAMP,
    paid_to_you                             NUMERIC(12,2) DEFAULT 0,
    actual_earnings                         NUMERIC(12,2) DEFAULT 0,
    cash_collected                          NUMERIC(12,2) DEFAULT 0,
    refunds_toll                            NUMERIC(12,2) DEFAULT 0,
    vehicle_number                          VARCHAR(50),
    org_name                                VARCHAR(150),
    source_report_id                        VARCHAR(100),
    run_id                                  VARCHAR(100),
    report_fetch_window_start               TIMESTAMP,
    report_fetch_window_end                 TIMESTAMP,
    ingested_at                             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uber_pipe_txns_date ON uber_pipeline_order_transactions (trx_date);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_txns_driver ON uber_pipeline_order_transactions (driver_uuid);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_txns_trip ON uber_pipeline_order_transactions (trip_uuid);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_txns_car ON uber_pipeline_order_transactions (vehicle_number);

-- 3. DRIVER PAYMENTS (Aggregated Driver Settlements)
CREATE TABLE IF NOT EXISTS uber_pipeline_driver_payments (
    id                                                      BIGSERIAL PRIMARY KEY,
    driver_uuid                                             VARCHAR(100) NOT NULL,
    driver_first_name                                       VARCHAR(100),
    driver_surname                                          VARCHAR(100),
    total_earnings                                          NUMERIC(12,2),
    total_earnings_net_fare                                 NUMERIC(12,2),
    total_earnings_promotions                               NUMERIC(12,2),
    total_earnings_tip                                      NUMERIC(12,2),
    total_earnings_taxes                                    NUMERIC(12,2),
    total_earnings_other_fees_platform_fee                  NUMERIC(12,2),
    total_earnings_other_earnings                           NUMERIC(12,2),
    total_earnings_other_earnings_other                     NUMERIC(12,2),
    total_earnings_other_earnings_adjustment                NUMERIC(12,2),
    refunds_expenses                                        NUMERIC(12,2),
    refunds_expenses_taxes_tax                              NUMERIC(12,2),
    refunds_expenses_expenses_driver_subscription_charge    NUMERIC(12,2),
    refunds_expenses_refunds_toll                           NUMERIC(12,2),
    payouts                                                 NUMERIC(12,2),
    payouts_transferred_to_bank_account                     NUMERIC(12,2),
    payouts_cash_collected                                  NUMERIC(12,2),
    paid_to_third_parties                                   NUMERIC(12,2),
    paid_to_third_parties_paid_to_airport                   NUMERIC(12,2),
    paid_to_third_parties_railway_pickup_fee                NUMERIC(12,2),
    paid_to_uber                                            NUMERIC(12,2),
    paid_to_uber_booking_fee                                NUMERIC(12,2),
    org_name                                                VARCHAR(150),
    source_report_id                                        VARCHAR(100),
    run_id                                                  VARCHAR(100),
    report_fetch_window_start                               TIMESTAMP,
    report_fetch_window_end                                 TIMESTAMP,
    ingested_at                                             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (driver_uuid, org_name, report_fetch_window_start, report_fetch_window_end)
);

CREATE INDEX IF NOT EXISTS idx_uber_pipe_driver_uuid ON uber_pipeline_driver_payments (driver_uuid);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_driver_window ON uber_pipeline_driver_payments (report_fetch_window_start, report_fetch_window_end);

-- 4. ORGANIZATION PAYMENTS (Master Fleet Balance Sheet)
CREATE TABLE IF NOT EXISTS uber_pipeline_org_payments (
    id                                                      BIGSERIAL PRIMARY KEY,
    organization_uuid                                       VARCHAR(100) NOT NULL,
    organisation_name                                       VARCHAR(150),
    org_alias                                               VARCHAR(150),
    driver_first_name                                       VARCHAR(100),
    driver_surname                                          VARCHAR(100),
    start_of_period_balance                                 NUMERIC(14,2),
    end_of_period_balance                                   NUMERIC(14,2),
    total_earnings                                          NUMERIC(14,2),
    total_earnings_net_fare                                 NUMERIC(14,2),
    total_earnings_promotions                               NUMERIC(14,2),
    total_earnings_tip                                      NUMERIC(14,2),
    total_earnings_taxes                                    NUMERIC(14,2),
    total_earnings_other_fees_platform_fee                  NUMERIC(14,2),
    total_earnings_other_earnings                           NUMERIC(14,2),
    total_earnings_other_earnings_other                     NUMERIC(14,2),
    total_earnings_other_earnings_adjustment                NUMERIC(14,2),
    refunds_expenses                                        NUMERIC(14,2),
    refunds_expenses_taxes_tax                              NUMERIC(14,2),
    refunds_expenses_expenses_driver_subscription_charge    NUMERIC(14,2),
    refunds_expenses_refunds_toll                           NUMERIC(14,2),
    payouts                                                 NUMERIC(14,2),
    payouts_cash_collected                                  NUMERIC(14,2),
    payouts_transferred_to_bank_account                     NUMERIC(14,2),
    paid_to_third_parties                                   NUMERIC(14,2),
    paid_to_third_parties_paid_to_airport                   NUMERIC(14,2),
    paid_to_third_parties_railway_pickup_fee                NUMERIC(14,2),
    paid_to_uber                                            NUMERIC(14,2),
    paid_to_uber_booking_fee                                NUMERIC(14,2),
    source_report_id                                        VARCHAR(100),
    run_id                                                  VARCHAR(100),
    report_fetch_window_start                               TIMESTAMP,
    report_fetch_window_end                                 TIMESTAMP,
    ingested_at                                             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_uuid, report_fetch_window_start, report_fetch_window_end)
);

-- 5. PIPELINE EXECUTION AUDIT LOGS
CREATE TABLE IF NOT EXISTS uber_pipeline_execution_logs (
    id                                      BIGSERIAL PRIMARY KEY,
    run_id                                  VARCHAR(100) UNIQUE NOT NULL,
    run_type                                VARCHAR(50) NOT NULL,
    target_window_start                     TIMESTAMP,
    target_window_end                       TIMESTAMP,
    start_time                              TIMESTAMP NOT NULL,
    end_time                                TIMESTAMP,
    status                                  VARCHAR(20) NOT NULL,
    fleets_processed                        INT DEFAULT 0,
    trips_inserted                          INT DEFAULT 0,
    transactions_inserted                   INT DEFAULT 0,
    drivers_inserted                        INT DEFAULT 0,
    orgs_inserted                           INT DEFAULT 0,
    error_message                           TEXT,
    email_sent                              BOOLEAN DEFAULT FALSE,
    created_at                              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uber_pipe_logs_status ON uber_pipeline_execution_logs (status);

-- 6. INCREMENTAL SYNC STATE TRACKER
CREATE TABLE IF NOT EXISTS uber_pipeline_sync_state (
    id                                      BIGSERIAL PRIMARY KEY,
    fleet_id                                VARCHAR(100) NOT NULL,
    stream_name                             VARCHAR(100) NOT NULL,
    last_synced_timestamp                   TIMESTAMP NOT NULL,
    last_run_id                             VARCHAR(100),
    updated_at                              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (fleet_id, stream_name)
);
