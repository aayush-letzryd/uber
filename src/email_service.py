import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
import datetime
from config.settings import SMTP_HOST, SMTP_PORT, SENDER_EMAIL, APP_PASSWORD, RECIPIENT_EMAIL

def send_execution_email(run_id, run_type, target_window, status, stats, duration_seconds, error_msg=None):
    """
    Dispatches an HTML execution summary email styled identically to the LetzRyd Ola Automation template.
    """
    now_dt = datetime.datetime.now()
    now_str = now_dt.strftime("%d %b %Y, %I:%M %p IST")
    
    # Subject & Badges
    if status == "SUCCESS":
        subject_icon = "✅ [SUCCESS]"
        status_text = "STATUS: SUCCESSFUL"
        status_bg = "#22c55e"
        db_status_text = "ACTIVE & COMMITTED"
        db_status_bg = "#dcfce7"
        db_status_color = "#15803d"
    elif status == "PARTIAL":
        subject_icon = "⚠️ [PARTIAL]"
        status_text = "STATUS: PARTIAL SUCCESS"
        status_bg = "#eab308"
        db_status_text = "PARTIAL INGESTION"
        db_status_bg = "#fef9c3"
        db_status_color = "#854d0e"
    else:
        subject_icon = "❌ [FAILED]"
        status_text = "STATUS: FAILED"
        status_bg = "#ef4444"
        db_status_text = "INGESTION ERROR"
        db_status_bg = "#fee2e2"
        db_status_color = "#991b1b"

    subject = f"{subject_icon} LetzRyd Uber Statement Ingested ({target_window})"

    trips_count = f"{stats.get('trips', 0):,} rides"
    txns_count = f"{stats.get('transactions', 0):,} rows"
    drivers_count = f"{stats.get('drivers', 0):,} drivers"
    orgs_count = f"{stats.get('orgs', 0):,} statements"
    duration_str = f"{duration_seconds:.1f} seconds"

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LetzRyd Uber Statement</title>
</head>
<body style="margin: 0; padding: 30px 15px; background-color: #f1f5f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased;">
    <div style="max-width: 580px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -2px rgba(0, 0, 0, 0.05); border: 1px solid #e2e8f0;">
        
        <!-- Header / Logo -->
        <div style="padding: 32px 24px 16px 24px; text-align: center;">
            <div style="display: inline-flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 8px;">
                <svg width="36" height="36" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg" style="vertical-align: middle;">
                    <circle cx="50" cy="50" r="45" stroke="#15803d" stroke-width="8" fill="#f0fdf4"/>
                    <path d="M30 65 L45 35 L55 35 L70 65" stroke="#047857" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
                    <circle cx="50" cy="50" r="10" fill="#eab308"/>
                </svg>
                <span style="font-size: 22px; font-weight: 900; letter-spacing: 1.5px; color: #0f172a; vertical-align: middle;">LETZ<span style="color: #16a34a;">RYD</span></span>
            </div>
            <div style="font-size: 11px; font-weight: 700; letter-spacing: 1.5px; color: #64748b; text-transform: uppercase; margin-top: 6px;">
                FLEET FINANCIAL OPERATIONS • UBER PIPELINE
            </div>
        </div>

        <div style="height: 1px; background-color: #f1f5f9; margin: 0 24px;"></div>

        <!-- Main Content Body -->
        <div style="padding: 28px 32px;">
            
            <!-- Status Badge -->
            <div style="margin-bottom: 14px;">
                <span style="background-color: {status_bg}; color: #ffffff; font-size: 11px; font-weight: 800; letter-spacing: 0.5px; padding: 5px 14px; border-radius: 9999px; display: inline-block; text-transform: uppercase;">
                    {status_text}
                </span>
            </div>

            <!-- Title & Subtitle -->
            <h1 style="font-size: 22px; font-weight: 800; color: #0f172a; margin: 0 0 6px 0; line-height: 1.3;">
                Uber Statement Ingestion Completed
            </h1>
            <p style="font-size: 14px; color: #64748b; margin: 0 0 24px 0; line-height: 1.5;">
                All ride and financial ledger records successfully loaded into PostgreSQL.
            </p>

            <!-- Metrics Highlight Box -->
            <div style="background-color: #f0fdf4; border-left: 4px solid #22c55e; border-radius: 8px; padding: 20px 22px; margin-bottom: 26px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <tr>
                        <td style="padding: 6px 0; color: #475569; width: 45%; font-weight: 500;">Target Date Window:</td>
                        <td style="padding: 6px 0; color: #0f172a; font-weight: 700;">{target_window}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #475569; font-weight: 500;">Trips Ingested:</td>
                        <td style="padding: 6px 0; color: #16a34a; font-weight: 800;">{trips_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #475569; font-weight: 500;">Financial Ledger Rows:</td>
                        <td style="padding: 6px 0; color: #16a34a; font-weight: 800;">{txns_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #475569; font-weight: 500;">Driver Settlements:</td>
                        <td style="padding: 6px 0; color: #16a34a; font-weight: 800;">{drivers_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #475569; font-weight: 500;">Org Balance Rows:</td>
                        <td style="padding: 6px 0; color: #16a34a; font-weight: 800;">{orgs_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #475569; font-weight: 500;">Execution Duration:</td>
                        <td style="padding: 6px 0; color: #0f172a; font-weight: 600;">{duration_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 6px 0; color: #475569; font-weight: 500;">Database Status:</td>
                        <td style="padding: 6px 0;">
                            <span style="background-color: {db_status_bg}; color: {db_status_color}; font-size: 11px; font-weight: 800; padding: 3px 8px; border-radius: 4px; display: inline-block; letter-spacing: 0.5px;">
                                {db_status_text}
                            </span>
                        </td>
                    </tr>
                </table>
            </div>

            {"<div style='background-color: #fef2f2; border-left: 4px solid #ef4444; border-radius: 6px; padding: 12px 16px; margin-bottom: 24px; color: #991b1b; font-size: 13px;'><strong>Error Diagnostics:</strong><br/>" + str(error_msg) + "</div>" if error_msg else ""}

            <!-- CTA Button -->
            <div style="text-align: center; margin: 28px 0 10px 0;">
                <a href="https://console.cloud.google.com/run/jobs?project=letzryd-prod" target="_blank" style="background-color: #15803d; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 700; padding: 12px 28px; border-radius: 6px; display: inline-block; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    📥 Download Statement (.xlsx)
                </a>
            </div>

        </div>

        <!-- Footer -->
        <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 20px; text-align: center;">
            <div style="font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 4px;">
                LetzRyd Mobility Private Limited
            </div>
            <div style="font-size: 11px; color: #64748b; margin-bottom: 4px;">
                Automated Cloud Pipeline • Serverless Microservice (asia-south1)
            </div>
            <div style="font-size: 11px; color: #94a3b8;">
                Execution Timestamp: {now_str} • Confidential
            </div>
        </div>

    </div>
</body>
</html>
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr(("LetzRyd Uber Automation", SENDER_EMAIL))
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD.replace(" ", ""))
        server.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
        server.quit()
        print(f"[EMAIL SERVICE] Replicated Ola-style UI email delivered to {RECIPIENT_EMAIL}!")
        return True
    except Exception as e:
        print(f"[EMAIL SERVICE ERROR] Email delivery failed: {e}")
        return False

if __name__ == "__main__":
    # Test send
    test_stats = {"trips": 12975, "transactions": 11679, "drivers": 710, "orgs": 10, "fleets": 3}
    send_execution_email("run_test_replica_001", "DAILY_SCHEDULED", "2026-08-24 → 2026-08-25", "SUCCESS", test_stats, 486.6)
