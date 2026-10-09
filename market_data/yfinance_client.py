# -*- coding: utf-8 -*-
"""
Working NSE/BSE data connector via Yahoo Finance.

yfinance returns live + historical market data for Indian equities:
  - NSE symbols use the ".NS" suffix (e.g., RELIANCE.NS)
  - BSE symbols use the ".BO" suffix (e.g., TCS.BO)

This is the practical replacement for the blocked unofficial NSE/BSE
website endpoints. It plugs into the same exchange-agnostic interface.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import yfinance as yf
from typing import Any


class YFinanceClient:
    """Exchange-agnostic market data via Yahoo Finance."""

    @staticmethod
    def _resolve_symbol(exchange: str, symbol: str) -> str:
        symbol = symbol.strip().upper()
        exchange = exchange.upper()

        if symbol.endswith(".NS") or symbol.endswith(".BO"):
            return symbol

        if exchange == "BSE":
            return f"{symbol}.BO"
        return f"{symbol}.NS"  # default to NSE

    def get_quote(self, exchange: str, symbol: str) -> dict[str, Any]:
        """Fetch the latest quote for an NSE/BSE symbol (near-real-time during market hours)."""
        yf_symbol = self._resolve_symbol(exchange, symbol)
        ticker = yf.Ticker(yf_symbol)
        history = ticker.history(period="5d", interval="1d")

        if history is None or history.empty:
            raise ValueError(
                f"No data found for {yf_symbol} (Yahoo Finance). "
                "Check the symbol or try again later."
            )

        info = {}
        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        # Use fast_info for the freshest intraday snapshot when available
        try:
            fi = ticker.fast_info
            last_price = float(fi.last_price) if fi.last_price else None
            prev_close = float(fi.previous_close) if fi.previous_close else None
            day_high = float(fi.day_high) if fi.day_high else None
            day_low = float(fi.day_low) if fi.day_low else None
            open_price = float(fi.open) if fi.open else None
            last_volume = int(fi.last_volume) if fi.last_volume else None
        except Exception:
            last_price = prev_close = day_high = day_low = open_price = last_volume = None

        # Fall back to history-based values
        if last_price is None:
            last_price = float(history["Close"].iloc[-1])
        if prev_close is None:
            prev_close = float(history["Close"].iloc[-2]) if len(history) > 1 else last_price
        if day_high is None:
            day_high = float(history["High"].max())
        if day_low is None:
            day_low = float(history["Low"].min())
        if open_price is None:
            open_price = float(history["Open"].iloc[-1])
        if last_volume is None:
            last_volume = int(float(history["Volume"].sum()))

        change = last_price - prev_close
        change_pct = (change / prev_close) * 100.0 if prev_close != 0 else 0.0

        return {
            "exchange": exchange.upper(),
            "symbol": symbol,
            "yf_symbol": yf_symbol,
            "company_name": info.get("longName") or info.get("shortName") or symbol,
            "last_price": last_price,
            "open": open_price,
            "day_high": day_high,
            "day_low": day_low,
            "previous_close": prev_close,
            "change": change,
            "change_percent": change_pct,
            "volume": last_volume,
            "timestamp": history.index[-1].strftime("%Y-%m-%d %H:%M:%S"),
        }


if __name__ == "__main__":
    client = YFinanceClient()

    for ex, sym in [("NSE", "RELIANCE"), ("BSE", "TCS")]:
        try:
            quote = client.get_quote(ex, sym)
            print(f"\n{ex} {sym} -> {quote}")
        except Exception as error:
            print(f"\n{ex} {sym} failed: {error}")