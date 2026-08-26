import os
from dotenv import load_dotenv

load_dotenv()

# Uber API Configuration
UBER_CLIENT_ID = os.getenv("UBER_CLIENT_ID")
UBER_CLIENT_SECRET = os.getenv("UBER_CLIENT_SECRET")
UBER_ACCESS_TOKEN = os.getenv("UBER_ACCESS_TOKEN", "IA.AQAAAAdDXrzL0DywPZz876sBoFENZcHr18P9VEtw3JvhfqQEXpWlsLF4G3We3YAOpWePo-Nfuj69e_ERZYxTXtWmKBZnn1Kl_gATsn20lG9wldEQHepuUTwrtVe0sXyoI3Fp79dv1IP6Lx0KCikfs-COmJSur7D5-xuQFCOr7xnxrw")
BASE_API_URL = "https://api.uber.com/v1/vehicle-suppliers"

# Dynamic Fleet Discovery Mode:
# When set to True or empty list, the pipeline automatically fetches ALL organizations/cities
# associated with the account via the Uber API.
AUTO_DISCOVER_ALL_FLEETS = os.getenv("AUTO_DISCOVER_ALL_FLEETS", "true").lower() in ("true", "1", "yes")

# Optional whitelist (if filtering is specifically desired, otherwise empty to discover all)
FLEET_NAME_WHITELIST = [
    # "SAMVREEDDHI MOBILITY Pvt. Ltd. BLR P",
    # "Samvreeddhi Mobility Pvt Ltd HYD P",
    # "Samvreeddhi Mobility Pvt. Ltd. MUM P",
]

# Database Configuration
DB_CONFIG = {
    "host": os.getenv("PGHOST", "35.200.196.113"),
    "port": os.getenv("PGPORT", "5432"),
    "dbname": os.getenv("PGDATABASE", "postgres"),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", r"8S5]U3@L^Xz)\FH}"),
}

# Table Names
TABLE_TRIPS = "uber_pipeline_trips"
TABLE_TRANSACTIONS = "uber_pipeline_order_transactions"
TABLE_DRIVER_PAYMENTS = "uber_pipeline_driver_payments"
TABLE_ORG_PAYMENTS = "uber_pipeline_org_payments"
TABLE_LOGS = "uber_pipeline_execution_logs"
TABLE_STATE = "uber_pipeline_sync_state"

# SMTP Email Notification Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "vendor_aayush@letzryd.com")
APP_PASSWORD = os.getenv("APP_PASSWORD", "gqnk qlhy rdcl rwrn")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "vendor_aayush@letzryd.com")
