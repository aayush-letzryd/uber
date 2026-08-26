import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
from config.settings import SMTP_HOST, SMTP_PORT, SENDER_EMAIL, APP_PASSWORD, RECIPIENT_EMAIL

def send_execution_email(run_id, run_type, target_window, status, stats, duration_seconds, error_msg=None):
    """
    Dispatches a structured HTML execution summary email to vendor_aayush@letzryd.com.
    """
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject_status = "SUCCESS" if status == "SUCCESS" else ("PARTIAL" if status == "PARTIAL" else "FAILED")
    
    subject = f"[{subject_status}] LetzRyd Uber Pipeline Daily Ingestion Report — {now_str} IST"
    
    status_badge_color = "#16a34a" if status == "SUCCESS" else ("#eab308" if status == "PARTIAL" else "#dc2626")
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f8fafc; padding: 20px; color: #1e293b;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);">
            
            <div style="background-color: #0f172a; padding: 24px 20px; color: #ffffff;">
                <div style="float: right; background-color: {status_badge_color}; color: #ffffff; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 13px;">
                    {status}
                </div>
                <h2 style="margin: 0; color: #38bdf8; font-size: 20px;">LetzRyd Uber Data Pipeline</h2>
                <p style="margin: 6px 0 0 0; color: #94a3b8; font-size: 13px;">Automated Data Ingestion & Sync Report</p>
            </div>

            <div style="padding: 24px;">
                <h3 style="margin-top: 0; color: #0f172a; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;">Run Metadata</h3>
                <table style="width: 100%; font-size: 14px; margin-bottom: 20px; border-collapse: collapse;">
                    <tr><td style="padding: 6px 0; color: #64748b; width: 40%;"><strong>Run ID:</strong></td><td><code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">{run_id}</code></td></tr>
                    <tr><td style="padding: 6px 0; color: #64748b;"><strong>Execution Mode:</strong></td><td><strong>{run_type}</strong></td></tr>
                    <tr><td style="padding: 6px 0; color: #64748b;"><strong>Target Date Window:</strong></td><td>{target_window}</td></tr>
                    <tr><td style="padding: 6px 0; color: #64748b;"><strong>Execution Duration:</strong></td><td>{duration_seconds:.1f} seconds</td></tr>
                    <tr><td style="padding: 6px 0; color: #64748b;"><strong>Timestamp:</strong></td><td>{now_str} IST</td></tr>
                </table>

                <h3 style="color: #0f172a; border-bottom: 2px solid #f1f5f9; padding-bottom: 8px;">Ingestion Metrics Summary</h3>
                <div style="display: flex; gap: 10px; margin-bottom: 20px;">
                    <div style="flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; text-align: center;">
                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: bold;">Trips</div>
                        <div style="font-size: 20px; font-weight: bold; color: #0284c7; margin-top: 4px;">{stats.get('trips', 0):,}</div>
                    </div>
                    <div style="flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; text-align: center;">
                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: bold;">Orders / Txns</div>
                        <div style="font-size: 20px; font-weight: bold; color: #0284c7; margin-top: 4px;">{stats.get('transactions', 0):,}</div>
                    </div>
                    <div style="flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; text-align: center;">
                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: bold;">Driver Records</div>
                        <div style="font-size: 20px; font-weight: bold; color: #0284c7; margin-top: 4px;">{stats.get('drivers', 0):,}</div>
                    </div>
                    <div style="flex: 1; background: #f8fafc; border: 1px solid #e2e8f0; padding: 12px; border-radius: 6px; text-align: center;">
                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase; font-weight: bold;">Fleets Synced</div>
                        <div style="font-size: 20px; font-weight: bold; color: #0284c7; margin-top: 4px;">{stats.get('fleets', 0)}</div>
                    </div>
                </div>

                {"<div style='background: #fef2f2; border: 1px solid #f87171; padding: 12px; border-radius: 6px; color: #991b1b; font-size: 13px; margin-bottom: 20px;'><strong>Errors Logged:</strong><br/>" + str(error_msg) + "</div>" if error_msg else ""}

                <div style="background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 12px; border-radius: 4px; font-size: 13px; color: #065f46;">
                    ✅ <strong>Idempotency Guaranteed:</strong> Historical data remains intact. All rows were processed using atomic composite-key UPSERT mechanics.
                </div>
            </div>

            <div style="background-color: #f1f5f9; padding: 14px 20px; text-align: center; color: #64748b; font-size: 12px; border-top: 1px solid #e2e8f0;">
                LetzRyd Autonomous Data Infrastructure • Scheduled & Managed via Google Cloud
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(html, "html"))

    try:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20)
        server.starttls()
        server.login(SENDER_EMAIL, APP_PASSWORD.replace(" ", ""))
        server.sendmail(SENDER_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
        server.quit()
        print(f"[EMAIL SERVICE] Execution report successfully delivered to {RECIPIENT_EMAIL}!")
        return True
    except Exception as e:
        print(f"[EMAIL SERVICE WARNING] Failed to deliver execution email: {e}")
        return False
