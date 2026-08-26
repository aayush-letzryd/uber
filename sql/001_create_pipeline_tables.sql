-- ==============================================================================
-- LetzRyd Uber Data Pipeline — Dedicated Production Tables & Audit Schemas
-- ==============================================================================

-- 1. EXECUTION AUDIT LOG TABLE (Tracks every scheduled run & manual force run)
CREATE TABLE IF NOT EXISTS uber_pipeline_execution_logs (
    id                      BIGSERIAL PRIMARY KEY,
    run_id                  VARCHAR(100) UNIQUE NOT NULL,
    run_type                VARCHAR(50) NOT NULL, -- 'DAILY_SCHEDULED', 'MANUAL_FORCE_RUN', 'HISTORICAL_BACKFILL'
    target_window_start     TIMESTAMP,
    target_window_end       TIMESTAMP,
    start_time              TIMESTAMP NOT NULL,
    end_time                TIMESTAMP,
    status                  VARCHAR(20) NOT NULL, -- 'RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED'
    fleets_processed        INT DEFAULT 0,
    trips_inserted          INT DEFAULT 0,
    transactions_inserted   INT DEFAULT 0,
    drivers_inserted        INT DEFAULT 0,
    orgs_inserted           INT DEFAULT 0,
    error_message           TEXT,
    email_sent              BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uber_log_status ON uber_pipeline_execution_logs(status);
CREATE INDEX IF NOT EXISTS idx_uber_log_start ON uber_pipeline_execution_logs(start_time DESC);

-- 2. TRIPS ACTIVITY TABLE (Stream 1: REPORT_TYPE_TRIP_ACTIVITY)
CREATE TABLE IF NOT EXISTS uber_pipeline_trips (
    id                          BIGSERIAL PRIMARY KEY,
    trip_date                   DATE NOT NULL,
    trip_uuid                   VARCHAR(100) UNIQUE NOT NULL,
    driver_uuid                 VARCHAR(100),
    driver_name                 VARCHAR(255),
    vehicle_uuid                VARCHAR(100),
    car_no                      VARCHAR(50),
    service_type                VARCHAR(100),
    trip_request_time           TIMESTAMP,
    trip_drop_off_time          TIMESTAMP,
    pick_up_address             TEXT,
    drop_off_address            TEXT,
    trip_distance               NUMERIC(10,2),
    trip_status                 VARCHAR(50),
    product_type                VARCHAR(100),
    final_rider_fare            NUMERIC(10,2),
    payment_type                VARCHAR(50),
    rider_name                  VARCHAR(255),
    org_name                    VARCHAR(150),
    source_report_id            VARCHAR(100),
    run_id                      VARCHAR(100),
    report_fetch_window_start   TIMESTAMP,
    report_fetch_window_end     TIMESTAMP,
    ingested_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_date ON uber_pipeline_trips(trip_date);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_carno ON uber_pipeline_trips(car_no);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_driver ON uber_pipeline_trips(driver_uuid);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_trips_org ON uber_pipeline_trips(org_name);

-- 3. TRANSACTION ACTIVITY LEDGER (Stream 2: REPORT_TYPE_PAYMENTS_ORDER)
CREATE TABLE IF NOT EXISTS uber_pipeline_order_transactions (
    id                          BIGSERIAL PRIMARY KEY,
    trx_date                    DATE,
    transaction_uuid            VARCHAR(100) UNIQUE NOT NULL,
    driver_uuid                 VARCHAR(100),
    driver_first_name           VARCHAR(100),
    driver_surname              VARCHAR(100),
    trip_uuid                   VARCHAR(100),
    description                 TEXT,
    organisation_name           VARCHAR(150),
    org_alias                   VARCHAR(150),
    reporting_time              TIMESTAMP,
    paid_to_you                 NUMERIC(12,2) DEFAULT 0,
    actual_earnings             NUMERIC(12,2) DEFAULT 0,
    cash_collected              NUMERIC(12,2) DEFAULT 0,
    refunds_toll                NUMERIC(12,2) DEFAULT 0,
    vehicle_number              VARCHAR(50),
    org_name                    VARCHAR(150),
    source_report_id            VARCHAR(100),
    run_id                      VARCHAR(100),
    report_fetch_window_start   TIMESTAMP,
    report_fetch_window_end     TIMESTAMP,
    ingested_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_uber_pipe_txn_date ON uber_pipeline_order_transactions(trx_date);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_txn_trip ON uber_pipeline_order_transactions(trip_uuid);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_txn_driver ON uber_pipeline_order_transactions(driver_uuid);
CREATE INDEX IF NOT EXISTS idx_uber_pipe_txn_org ON uber_pipeline_order_transactions(org_name);

-- 4. DRIVER PAYMENTS TABLE (Stream 3: REPORT_TYPE_PAYMENTS_DRIVER)
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
    report_fetch_window_start                               TIMESTAMP NOT NULL,
    report_fetch_window_end                                 TIMESTAMP NOT NULL,
    ingested_at                                             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (driver_uuid, org_name, report_fetch_window_start, report_fetch_window_end)
);

CREATE INDEX IF NOT EXISTS idx_uber_pipe_drv_window ON uber_pipeline_driver_payments(report_fetch_window_start, report_fetch_window_end);

-- 5. ORGANIZATION PAYMENTS TABLE (Stream 4: REPORT_TYPE_PAYMENTS_ORGANIZATION)
CREATE TABLE IF NOT EXISTS uber_pipeline_org_payments (
    id                                                      BIGSERIAL PRIMARY KEY,
    organization_uuid                                       VARCHAR(100) NOT NULL,
    organisation_name                                       VARCHAR(150),
    org_alias                                               VARCHAR(100),
    driver_first_name                                       VARCHAR(100),
    driver_surname                                          VARCHAR(100),
    start_of_period_balance                                 NUMERIC(12,2),
    end_of_period_balance                                   NUMERIC(12,2),
    total_earnings                                          NUMERIC(12,2),
    total_earnings_net_fare                                 NUMERIC(12,2),
    total_earnings_promotions                               NUMERIC(12,2),
    total_earnings_tip                                      NUMERIC(12,2),
    total_earnings_taxes                                    NUMERIC(12,2),
    total_earnings_other_fees_platform_fee                  NUMERIC(12,2),
    total_earnings_other_earnings_other                     NUMERIC(12,2),
    total_earnings_other_earnings_adjustment                NUMERIC(12,2),
    refunds_expenses                                        NUMERIC(12,2),
    refunds_expenses_taxes_tax                              NUMERIC(12,2),
    refunds_expenses_expenses_driver_subscription_charge    NUMERIC(12,2),
    refunds_expenses_refunds_toll                           NUMERIC(12,2),
    payouts                                                 NUMERIC(12,2),
    payouts_cash_collected                                  NUMERIC(12,2),
    payouts_transferred_to_bank_account                     NUMERIC(12,2),
    paid_to_third_parties                                   NUMERIC(12,2),
    paid_to_third_parties_paid_to_airport                   NUMERIC(12,2),
    paid_to_third_parties_railway_pickup_fee                NUMERIC(12,2),
    paid_to_uber                                            NUMERIC(12,2),
    paid_to_uber_booking_fee                                NUMERIC(12,2),
    source_report_id                                        VARCHAR(100),
    run_id                                                  VARCHAR(100),
    report_fetch_window_start                               TIMESTAMP NOT NULL,
    report_fetch_window_end                                 TIMESTAMP NOT NULL,
    ingested_at                                             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (organization_uuid, report_fetch_window_start, report_fetch_window_end)
);

-- 6. INCREMENTAL ETL STATE TABLE
CREATE TABLE IF NOT EXISTS uber_pipeline_sync_state (
    org_uuid VARCHAR(255),
    report_type VARCHAR(255),
    last_end_ms BIGINT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (org_uuid, report_type)
);
