import os
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv
# setup guide in README.md
# Load environment variables from .env (user sets full path)
env_path = "/var/www/gobot_go/data/go-globe-bot/.env"
load_dotenv(dotenv_path=env_path)

HEALTHCHECK_URL = os.environ.get("BACKEND_URL", "").rstrip("/") + "/healthcheck"
# in config ALERT_EMAILS=admin1@example.com,admin2@example.com
EMAILS = [e.strip() for e in os.environ.get("ALERT_EMAILS", "").split(",") if e.strip()]  # Comma-separated in .env
SMTP_SERVER = os.environ.get("SMTP_SERVER")
SMTP_PORT = int(os.environ.get("SMTP_PORT", 465))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
FROM_EMAIL = os.environ.get("SMTP_USERNAME")

print(f"HEALTHCHECK_URL: {HEALTHCHECK_URL}")
print(f"EMAILS: {EMAILS}")
print(f"SMTP_SERVER: {SMTP_SERVER}")
print(f"SMTP_PORT: {SMTP_PORT}")
print(f"SMTP_USERNAME: {SMTP_USERNAME}")
print(f"SMTP_PASSWORD: {'***' if SMTP_PASSWORD else None}")
print(f"FROM_EMAIL: {FROM_EMAIL}")

def send_email(subject, body, recipients):
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        print("No valid recipients to send email to.")
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(recipients)

    # Try SMTP over SSL first, if auth fails try STARTTLS on port 587
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
            print("Alert email sent via SMTP_SSL.")
            return
    except smtplib.SMTPAuthenticationError as e:
        print(f"SMTP_SSL auth failed: {e}. Trying STARTTLS (port 587).")
    except Exception as e:
        print(f"SMTP_SSL send failed: {e}. Trying STARTTLS (port 587).")

    # Fallback to STARTTLS
    try:
        with smtplib.SMTP(SMTP_SERVER, 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
            print("Alert email sent via STARTTLS.")
            return
    except Exception as e:
        print(f"Failed to send alert email via STARTTLS: {e}")
        raise

def check_health():
    try:
        print(f"Checking healthcheck URL: {HEALTHCHECK_URL}")
        resp = requests.get(HEALTHCHECK_URL, timeout=10)
        if resp.status_code in (200,) and resp.text.strip().upper() == "OK":
            print("Healthcheck OK")
            return True
        else:
            print(f"Unexpected healthcheck response: status={resp.status_code} body={resp.text!r}")
            return False
    except Exception as e:
        print(f"Healthcheck failed with exception: {e}")
        return False

if __name__ == "__main__":
    if not check_health():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"[ALERT] Healthcheck Failed at {now}"
        body = f"The healthcheck endpoint {HEALTHCHECK_URL} did not return OK at {now}."
        if EMAILS:
            send_email(subject, body, EMAILS)
        else:
            print("No ALERT_EMAILS configured; skipping email alert.")
    print("Healthcheck completed.")