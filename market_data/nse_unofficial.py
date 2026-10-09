# -*- coding: utf-8 -*-
"""
Experimental, read-only NSE website connector.

This is NOT an official NSE API client.
Website endpoints may change or become unavailable.
Read the NSE Terms of Use before automated use.
"""

import requests
from typing import Any


class NSEUnofficialClient:
    """
    Experimental, read-only NSE website connector.

    This is NOT an official NSE API client.
    Website endpoints may change or become unavailable.
    """

    BASE_URL = "https://www.nseindia.com"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        })

    def _initialize_session(self):
        """Load the public NSE website to establish a normal session."""
        response = self.session.get(
            self.BASE_URL,
            timeout=self.timeout
        )
        response.raise_for_status()

    def get_equity_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch an experimental quote for an NSE equity symbol."""
        symbol = symbol.strip().upper()

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

        self._initialize_session()

        response = self.session.get(
            f"{self.BASE_URL}/api/quote-equity",
            params={"symbol": symbol},
            timeout=self.timeout
        )

        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "application/json" not in content_type.lower():
            raise RuntimeError(
                "NSE did not return JSON. "
                "The endpoint may require different access or may have changed."
            )

        return response.json()

    def get_market_status(self) -> dict[str, Any]:
        """Fetch current market status."""
        self._initialize_session()

        response = self.session.get(
            f"{self.BASE_URL}/api/marketStatus",
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()


if __name__ == "__main__":
    client = NSEUnofficialClient()

    try:
        data = client.get_equity_quote("RELIANCE")

        print("NSE response received successfully.")
        print(data)

    except Exception as error:
        print(f"NSE request failed: {error}")