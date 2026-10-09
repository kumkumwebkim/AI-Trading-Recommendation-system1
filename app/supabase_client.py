"""
Supabase client initialization module.

This module creates a singleton Supabase client that can be imported
and used throughout the application.
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env file
load_dotenv()

# Get credentials from environment variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL environment variable not set. "
        "Please add it to your .env file."
    )

if not SUPABASE_ANON_KEY:
    raise ValueError(
        "SUPABASE_ANON_KEY environment variable not set. "
        "Please add it to your .env file."
    )

# Create the Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
