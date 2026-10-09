# -*- coding: utf-8 -*-
"""
Normalization layer for exchange quote responses.

Converts raw exchange JSON into the project's common market-data format,
so the ML pipeline never depends on exchange-specific schemas.
"""

from typing import Any, Optional


def normalize_nse_quote(raw_data: dict) -> dict:
    """
    Convert NSE quote response into the common market-data format.

    Note: Field names/positions may change. Inspect a live response
    before relying on exact keys.
    """
    price_info = raw_data.get("priceInfo", {})
    metadata = raw_data.get("metadata", {})
    info = raw_data.get("info", {})

    hl = price_info.get("intraDayHighLow", {})

    timestamp = None
    if metadata.get("asOn"):
        timestamp = str(metadata.get("asOn"))
    elif info.get("exDate"):
        timestamp = str(info.get("exDate"))

    return {
        "exchange": "NSE",
        "symbol": info.get("symbol") or metadata.get("symbol"),
        "company_name": info.get("companyName") or metadata.get("companyName"),
        "last_price": price_info.get("lastPrice"),
        "open": price_info.get("open"),
        "day_high": hl.get("max"),
        "day_low": hl.get("min"),
        "previous_close": price_info.get("previousClose"),
        "change": price_info.get("change"),
        "change_percent": price_info.get("pChange"),
        "volume": price_info.get("totalTradedVolume") or price_info.get("totalTradedValue"),
        "timestamp": timestamp,
    }


def normalize_bse_quote(raw_data: dict) -> dict:
    """
    Convert BSE quote response into the common market-data format.

    BSE response schema is not documented publicly - verify with a
    live response before relying on exact keys.
    """
    return {
        "exchange": "BSE",
        "symbol": raw_data.get("symbol") or raw_data.get("sCode"),
        "company_name": raw_data.get("scripName") or raw_data.get("fullName"),
        "last_price": _to_float(raw_data.get("CurrentPrice") or raw_data.get("ltp")),
        "open": _to_float(raw_data.get("Open")),
        "day_high": _to_float(raw_data.get("high")),
        "day_low": _to_float(raw_data.get("low")),
        "previous_close": _to_float(raw_data.get("PreviousClose")),
        "change": _to_float(raw_data.get("change")),
        "change_percent": _to_float(raw_data.get("pChange")),
        "volume": raw_data.get("totalTradedVolume"),
        "timestamp": raw_data.get("updatedOn"),
    }


def _to_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_quote(exchange: str, raw_data: dict) -> dict:
    """Dispatch to the correct normalizer based on exchange."""
    exchange = exchange.upper()
    if exchange == "NSE":
        return normalize_nse_quote(raw_data)
    if exchange == "BSE":
        return normalize_bse_quote(raw_data)
    raise ValueError(f"Unsupported exchange: {exchange}")