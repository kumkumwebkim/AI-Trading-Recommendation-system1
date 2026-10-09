# -*- coding: utf-8 -*-
"""
Exchange-agnostic market data service.

Provides a common interface so the AI pipeline never depends on a single
exchange or provider. Swap implementations at any time without touching
downstream code.

Providers:
  - yfinance (default, working)  -> NSE (.NS) / BSE (.BO)
  - NSE / BSE unofficial clients -> experimental, blocked from most networks
"""

from typing import Any
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from market_data.yfinance_client import YFinanceClient
from market_data.nse_unofficial import NSEUnofficialClient
from market_data.bse_unofficial import BSEUnofficialClient
from market_data.normalizer import normalize_quote


class MarketDataService:

    def __init__(self, provider: str = "yfinance"):
        """
        provider: 'yfinance' (default) or 'unofficial'
        """
        self.provider = provider
        self.yf_client = YFinanceClient()
        self.nse_client = NSEUnofficialClient()
        self.bse_client = BSEUnofficialClient()

    def get_quote(self, exchange: str, symbol: str) -> dict:
        """
        Fetch and normalize a quote for the given exchange + symbol.

        exchange: 'NSE' or 'BSE'
        symbol:   e.g., RELIANCE (NSE) / 500209 (BSE scrip code) /
                  INFY.NS / TCS.BO
        Returns the common normalized market-data format.
        """
        exchange = exchange.upper()

        if self.provider == "yfinance":
            return self.yf_client.get_quote(exchange, symbol)

        if exchange == "NSE":
            raw = self.nse_client.get_equity_quote(symbol)
        elif exchange == "BSE":
            raw = self.bse_client.get_equity_quote(symbol)
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")

        return normalize_quote(exchange, raw)


if __name__ == "__main__":
    service = MarketDataService()

    for ex, sym in [("NSE", "RELIANCE"), ("BSE", "TCS")]:
        try:
            quote = service.get_quote(ex, sym)
            print(f"\n{ex} quote -> {quote}")
        except Exception as error:
            print(f"\n{ex} quote failed: {error}")