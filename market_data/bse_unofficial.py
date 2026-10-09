# -*- coding: utf-8 -*-
"""
Experimental, read-only BSE website connector (under investigation).

IMPORTANT: The current BSE website does not expose a documented public
JSON API. Endpoints found in old GitHub repos are likely stale.
Per the integration plan, verify the exact endpoint, response format and
access conditions on the live site BEFORE relying on this module.

This is NOT an official BSE API client.
"""

import requests
from typing import Any


class BSEUnofficialClient:
    """
    Experimental, read-only BSE website connector.

    Requires an initialized web-like session; the site may serve
    intermediary HTML pages instead of JSON.
    """

    API_BASE = "https://api.bseindia.com/BseIndiaAPI/api"

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
            "Referer": "https://www.bseindia.com/",
        })

    def get_equity_quote(self, scripcode: str) -> dict[str, Any]:
        """
        Fetch an experimental quote for a BSE scrip code.

        Example: INFY -> scripcode 500209
        """
        scripcode = str(scripcode).strip()
        if not scripcode:
            raise ValueError("Scrip code cannot be empty.")

        # Placeholder endpoint - MUST be verified against the live site first.
        response = self.session.get(
            f"{self.API_BASE}/StockReachGraph/w",
            params={"scripcode": scripcode},
            timeout=self.timeout
        )
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type.lower():
            raise RuntimeError(
                "BSE did not return JSON (got HTML). "
                "The endpoint/session handling must be verified on the live site first."
            )

        return response.json()


if __name__ == "__main__":
    print("BSE connector: experimental. Endpoint verification required first.")