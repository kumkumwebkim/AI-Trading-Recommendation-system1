import re

with open("alerts/main.py", "r", encoding="utf-8") as f:
    code = f.read()

config_code = """import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'scripts')))
try:
    from email_config import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_PROVIDER, BREVO_API_KEY, BREVO_SMTP_LOGIN
except ImportError:
    EMAIL_SENDER = "kumkumgupta587@gmail.com"
    EMAIL_PASSWORD = os.getenv("ALERTS_EMAIL_PASSWORD", "")
    EMAIL_PROVIDER = "gmail"
    BREVO_API_KEY = ""
    BREVO_SMTP_LOGIN = ""
"""
code = code.replace(
    'EMAIL_SENDER = "kumkumgupta587@gmail.com"  # Your Email\nEMAIL_PASSWORD = os.getenv("ALERTS_EMAIL_PASSWORD", "")  # Your Gmail App Password (set as env var)',
    config_code
)

send_email_code = """        # Setup the email
        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = user_email

        if EMAIL_PROVIDER == "brevo":
            if not BREVO_API_KEY or BREVO_API_KEY.startswith("PASTE_"):
                print("❌ [Email Failed] Brevo API key not configured.")
                return False
            
            if BREVO_API_KEY.startswith("xsmtpsib-"):
                if not BREVO_SMTP_LOGIN:
                    print("❌ [Email Failed] BREVO_SMTP_LOGIN is empty.")
                    return False
                with smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=45) as server:
                    server.ehlo(); server.starttls(); server.ehlo()
                    server.login(BREVO_SMTP_LOGIN, BREVO_API_KEY)
                    server.sendmail(EMAIL_SENDER, user_email, msg.as_string())
                print(f"✅ [Success] Email sent via Brevo SMTP to {user_email} for {ticker}")
                return True
                
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"api-key": BREVO_API_KEY, "Content-Type": "application/json"},
                json={
                    "sender": {"name": "AI Signals Platform", "email": EMAIL_SENDER},
                    "to": [{"email": user_email}],
                    "subject": subject,
                    "htmlContent": body
                },
                timeout=30
            )
            if resp.status_code in (200, 201):
                print(f"✅ [Success] Email sent via Brevo API to {user_email} for {ticker}")
                return True
            print(f"❌ [Email Failed] Brevo API returned {resp.status_code}: {resp.text}")
            return False
        else:
            # Send via Gmail SSL
            password_clean = EMAIL_PASSWORD.replace(" ", "")
            if not password_clean:
                print("❌ [Email Failed] Gmail App Password not provided.")
                return False
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.ehlo()
                server.login(EMAIL_SENDER, password_clean)
                server.sendmail(EMAIL_SENDER, user_email, msg.as_string())
                print(f"✅ [Success] Email sent to {user_email} for {ticker}")
                return True"""

code = code.replace(
'''        # Setup the email
        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = EMAIL_SENDER
        msg['To'] = user_email

        # Send via Gmail SSL
        password_clean = EMAIL_PASSWORD.replace(" ", "")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.ehlo()
            server.login(EMAIL_SENDER, password_clean)
            server.sendmail(EMAIL_SENDER, user_email, msg.as_string())
            print(f"✅ [Success] Email sent to {user_email} for {ticker}")''',
    send_email_code
)

code = code.replace(
    'except Exception as e:\n        print(f"❌ [Email Failed] Could not send email: {e}")',
    'except Exception as e:\n        print(f"❌ [Email Failed] Could not send email: {e}")\n        return False'
)

code = code.replace(
'''        # 3️⃣ Send alert (Threshold removed by user request)
        print(f"🚀 SIGNAL ({confidence:.2f}%) → Sending Email")
        send_email_alert(user_email, ticker, email_data)

    except Exception as e:
        print(f"❌ Alert job failed for {ticker}: {e}")''',
'''        # 3️⃣ Send alert (Threshold removed by user request)
        print(f"🚀 SIGNAL ({confidence:.2f}%) → Sending Email")
        return send_email_alert(user_email, ticker, email_data)

    except Exception as e:
        print(f"❌ Alert job failed for {ticker}: {e}")
        return False'''
)


code = code.replace(
'''@app.post("/instant-report")
def instant_report(request: InstantReportRequest):
    # Passes force=True to ensure email is sent for testing purposes
    check_and_alert_job(request.user_email, request.ticker_name, force=True, alert_type="Instant Report (Manual)")
    return {"status": "success", "message": "Report sent"}''',
'''@app.post("/instant-report")
def instant_report(request: InstantReportRequest):
    # Passes force=True to ensure email is sent for testing purposes
    success = check_and_alert_job(request.user_email, request.ticker_name, force=True, alert_type="Instant Report (Manual)")
    if success:
        return {"status": "success", "message": "Report sent"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send email. Ensure ML Signal API is running and Email is configured properly.")'''
)

with open("alerts/main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Patched main.py")
