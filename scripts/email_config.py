# ==========================================
# EMAIL CONFIGURATION - Single source of truth
# ==========================================
# Configure mail credentials in the project .env file or service environment.
# Brevo API keys use the REST API; Brevo SMTP keys use the SMTP relay.
# Gmail requires an App Password, not the account password.
# ==========================================
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / "other Resources" / ".env")

EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "brevo")

# API keys (xkeysib-) use the REST API; SMTP keys (xsmtpsib-) use SMTP.
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SMTP_LOGIN = os.getenv("BREVO_SMTP_LOGIN", "")

EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
