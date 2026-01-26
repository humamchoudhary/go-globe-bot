import os
import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env (user sets full path)
env_path = "/var/www/gobot_go_glo_usr47/data/go-globe-bot/.env"
load_dotenv(dotenv_path=env_path)

HEALTHCHECK_URL = os.environ.get("BACKEND_URL", "").rstrip("/") + "/healthcheck"
# in config ALERT_EMAILS=admin1@example.com,admin2@example.com
EMAILS = os.environ.get("ALERT_EMAILS", "").split(",")  # Comma-separated in .env
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
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = ", ".join(recipients)

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(FROM_EMAIL, recipients, msg.as_string())

def check_health():
    try:
        print(f"Checking healthcheck URL: {HEALTHCHECK_URL}")
        resp = requests.get(HEALTHCHECK_URL, timeout=10)
        if resp.status_code == 200 and resp.text.strip() == "OK":
            print("Healthcheck OK")
            return True
        else:
            return False
    except Exception as e:
        print(f"Healthcheck failed with exception: {e}")
        return False

if __name__ == "__main__":
    if not check_health():
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = f"[ALERT] Healthcheck Failed at {now}"
        body = f"The healthcheck endpoint {HEALTHCHECK_URL} did not return OK at {now}."
        if EMAILS and EMAILS[0]:
            send_email(subject, body, EMAILS)
    print("Healthcheck completed.")