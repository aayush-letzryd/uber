import os
from dotenv import load_dotenv

load_dotenv()

# Uber API Configuration (read exclusively from environment variables / Secret Manager)
UBER_CLIENT_ID = os.getenv("UBER_CLIENT_ID")
UBER_CLIENT_SECRET = os.getenv("UBER_CLIENT_SECRET")
UBER_ACCESS_TOKEN = os.getenv("UBER_ACCESS_TOKEN")
BASE_API_URL = os.getenv("UBER_BASE_API_URL", "https://api.uber.com/v1/vehicle-suppliers").rstrip("/")

# Dynamic Fleet Discovery Mode:
AUTO_DISCOVER_ALL_FLEETS = os.getenv("AUTO_DISCOVER_ALL_FLEETS", "false").lower() in ("true", "1", "yes")

# Default Target Fleets (Configurable via env var DEFAULT_FLEETS as comma-separated list)
_raw_default_fleets = os.getenv("DEFAULT_FLEETS")
if _raw_default_fleets:
    DEFAULT_FLEETS = [f.strip() for f in _raw_default_fleets.split(",") if f.strip()]
else:
    DEFAULT_FLEETS = [
        "SAMVREEDDHI MOBILITY Pvt. Ltd. BLR P",
        "Samvreeddhi Mobility Pvt Ltd HYD P",
        "Samvreeddhi Mobility Pvt. Ltd. MUM P",
    ]

# Database Configuration (read exclusively from environment variables / Secret Manager)
DB_CONFIG = {
    "host": os.getenv("PGHOST", "35.200.196.113"),
    "port": os.getenv("PGPORT", "5432"),
    "dbname": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", ""),
}

# Table Names
TABLE_TRIPS = "uber_pipeline_trips"
TABLE_TRANSACTIONS = "uber_pipeline_order_transactions"
TABLE_DRIVER_PAYMENTS = "uber_pipeline_driver_payments"
TABLE_ORG_PAYMENTS = "uber_pipeline_org_payments"
TABLE_LOGS = "uber_pipeline_execution_logs"
TABLE_STATE = "uber_pipeline_sync_state"

# SMTP Email Notification Configuration (read exclusively from environment variables / Secret Manager)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "vendor_aayush@letzryd.com")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "vendor_aayush@letzryd.com")
