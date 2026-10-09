import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import requests
import sys
import os

# CONFIGURATION (shared with the alerts service)
sys.path.insert(0, os.path.dirname(__file__))
from email_config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_PROVIDER, BREVO_API_KEY, BREVO_SMTP_LOGIN

TARGET_EMAIL = "alonewalker07827@gmail.com"
TICKER = "AMZN"

def fetch_live_signal(ticker):
    """Try to get real data from the running ML API"""
    try:
        print(f"Connecting to ML API for {ticker}...")
        url = "http://localhost:8000/api/v1/ml/signal/live"
        response = requests.post(url, json={"ticker": ticker}, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API returned status {response.status_code}")
    except Exception as e:
        print(f"Could not connect to ML API: {e}")
    return None

def send_alert(data):
    try:
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        signal = data.get('signal', 'TEST')
        price = data.get('current_price', 0.0)
        confidence = data.get('confidence', 0.0)
        
        # Format confidence
        if isinstance(confidence, (int, float)):
            conf_str = f"{confidence:.2f}%"
        else:
            conf_str = str(confidence)

        subject = f"🚨 TEST ALERT: {signal} {TICKER}"
        body = f"""
        Subject: {subject}

        TRADING ALERT SYSTEM (MANUAL TEST)
        ---------------------------------
        Time:       {current_time}
        Ticker:     {TICKER}
        Signal:     {signal}
        Price:      {price}
        Confidence: {conf_str}
        ---------------------------------
        This is a test alert requested manually.
        """

        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = TARGET_EMAIL

        print(f"Sending email to {TARGET_EMAIL}...")

        if EMAIL_PROVIDER == "brevo":
            if not BREVO_API_KEY or BREVO_API_KEY.startswith("PASTE_"):
                print("Brevo API key not configured. Edit scripts/email_config.py -> BREVO_API_KEY")
                return False
            if BREVO_API_KEY.startswith("xsmtpsib-"):
                if not BREVO_SMTP_LOGIN:
                    print("BREVO_SMTP_LOGIN is empty. Copy the 'SMTP login' value from https://app.brevo.com/settings/keys/smtp")
                    return False
                with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=45) as server:
                    server.ehlo(); server.starttls(); server.ehlo()
                    server.login(BREVO_SMTP_LOGIN, BREVO_API_KEY)
                    server.sendmail(EMAIL_SENDER, TARGET_EMAIL, msg.as_string())
                print("Email sent successfully!")
                return True
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json={
                    "sender": {"name": "AI Signals Platform", "email": EMAIL_SENDER},
                    "to": [{"email": TARGET_EMAIL}],
                    "subject": subject,
                    "textContent": body
                },
                timeout=30
            )
            if resp.status_code in (200, 201):
                print("Email sent successfully!")
                return True
            print(f"Brevo API returned {resp.status_code}: {resp.text}")
            return False

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, TARGET_EMAIL, msg.as_string())

        print("Email sent successfully!")
        return True

    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

def main():
    # 1. Try to fetch real data
    data = fetch_live_signal(TICKER)
    
    # 2. If no real data, use dummy data (since this is a requested 'test')
    if not data:
        print("Using dummy data for test...")
        data = {
            "signal": "TEST_BUY",
            "current_price": 185.50,
            "confidence": 99.9
        }
    
    # 3. Send the alert
    send_alert(data)

if __name__ == "__main__":
    main()
