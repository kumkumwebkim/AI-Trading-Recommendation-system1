import requests
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import sys
import os

# CONFIGURATION (shared with the alerts service)
sys.path.insert(0, os.path.dirname(__file__))
from email_config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_PROVIDER, BREVO_API_KEY, BREVO_SMTP_LOGIN

API_URL = "http://localhost:8000/api/v1/ml/signal/live"

def get_stock_details(ticker):
    print(f"Fetching live data for {ticker}...")
    try:
        response = requests.post(API_URL, json={"ticker": ticker}, timeout=15)
        if response.status_code == 200:
            return response.json()
        print(f"API Error: {response.text}")
        return None
    except Exception as e:
        print(f"Connection Error: {e}")
        return None

def send_instant_email(recipient, ticker, data):
    print(f"Sending email to {recipient}...")
    
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    signal = data.get('signal', 'N/A')
    price = data.get('current_price', 0.0)
    conf = data.get('confidence', 0.0)
    
    subject = f"⚡ INSTANT REPORT: {ticker} ({signal})"
    
    body = f"""
    Subject: {subject}

    INSTANT STOCK REPORT
    ============================
    Ticker:     {ticker}
    Time:       {current_time}
    ----------------------------
    Signal:     {signal}
    Price:      ₹{price}
    Confidence: {conf:.2f}%
    ----------------------------
    
    Expected Return (Model): {data.get('expected_return', 0):.4f}%
    
    This report was generated on demand.
    """

    try:
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = recipient

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
                    server.sendmail(EMAIL_SENDER, recipient, msg.as_string())
                print("Email sent successfully!")
                return True
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json={
                    "sender": {"name": "AI Signals Platform", "email": EMAIL_SENDER},
                    "to": [{"email": recipient}],
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
            server.sendmail(EMAIL_SENDER, recipient, msg.as_string())
        
        print("Email sent successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        return False

if __name__ == "__main__":
    print("--- INSTANT STOCK REPORTER ---")
    
    # Get inputs interactively if not passed as args
    if len(sys.argv) >= 3:
        ticker = sys.argv[1]
        email = sys.argv[2]
    else:
        ticker = input("Enter Ticker (e.g. RELIANCE.NS): ").strip().upper()
        email = input("Enter Recipient Email: ").strip()
        
    if ticker and email:
        data = get_stock_details(ticker)
        if data:
            send_instant_email(email, ticker, data)
    else:
        print("Invalid input.")
