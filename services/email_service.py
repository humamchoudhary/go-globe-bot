import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# Replace with your custom SMTP server settings
SMTP_SERVER = os.environ.get('SMTP_SERVER')
SMTP_PORT = os.environ.get('SMTP_PORT')  # Usually 587 for TLS, 465 for SSL
SMTP_USERNAME = os.environ.get('SMTP_USERNAME')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD')
FROM_EMAIL = SMTP_USERNAME


def send_email(to_email, subject, message):

    if not all([to_email, subject, message]):
        return 'Provide all values'

    # Construct email
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(message, 'plain'))
    print(msg)

    # Connect to custom SMTP server
    try:
        print(SMTP_SERVER)
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        print(server)
        server.set_debuglevel(1)  # Optional: show debug output
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

    return 'SEND'


if __name__ == "__main__":
    print(send_email('humamchoudhary@gmail.com', 'test', 'test'))
