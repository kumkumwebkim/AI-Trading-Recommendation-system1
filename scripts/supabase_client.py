# -*- coding: utf-8 -*-
"""Supabase configuration and client for Supabase API integration."""
import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

# Initialize Supabase client
supabase = None

def init_supabase():
    """Initialize Supabase client."""
    global supabase
    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        return True
    except Exception as e:
        print(f"Failed to initialize Supabase: {e}")
        return False

def get_supabase():
    """Get Supabase client instance."""
    global supabase
    if supabase is None:
        init_supabase()
    return supabase

# Example usage functions
def fetch_recent_data(ticker: str, days: int = 30) -> list:
    """Fetch recent stock data from Supabase."""
    supabase = get_supabase()
    if supabase:
        try:
            result = supabase.table("stock_data").select("*").eq("ticker", ticker).order("date", desc=True).limit(days).execute()
            return result.data
        except Exception as e:
            print(f"Error fetching data: {e}")
    return []

def fetch_latest_data(ticker: str, limit: int = 100) -> list:
    """Fetch latest stock data from Supabase."""
    supabase = get_supabase()
    if supabase:
        try:
            result = supabase.table("stock_data").select("*").eq("ticker", ticker).order("date", desc=True).limit(limit).execute()
            return result.data
        except Exception as e:
            print(f"Error fetching data: {e}")
    return []

def fetch_stock_stats(ticker: str, start_date: str = "2024-01-01") -> dict:
    """Fetch statistical analysis for a ticker from Supabase."""
    supabase = get_supabase()
    if supabase:
        try:
            result = supabase.table("stock_stats").select("*").eq("ticker", ticker).gte("start_date", start_date).execute()
            return result.data
        except Exception as e:
            print(f"Error fetching stats: {e}")
    return {}

# Example usage
if __name__ == "__main__":
    # Initialize Supabase
    if init_supabase():
        print("Supabase initialized successfully")
        # Fetch recent data example
        data = fetch_recent_data("AAPL", days=7)
        print(f"Recent AAPL data: {len(data)} records")
    else:
        print("Failed to initialize Supabase. Check your credentials.")