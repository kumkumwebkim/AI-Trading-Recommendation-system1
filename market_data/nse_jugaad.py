# -*- coding: utf-8 -*-
"""
Port of jugaad-data NSELive client (read-only subset).

Implements live data fetch from public NSE website routes.

IMPORTANT LEGAL NOTICE:
- This is NOT an official NSE API client.
- NSE Terms of Use prohibit systematic or automated data collection.
- Website endpoints may change, become unavailable, or be IP-blocked,
  without notice.
- Do NOT use this to bypass CAPTCHA, cloudflare, or anti-bot protections.
- This module is provided for learning/demo purposes only. For production
  or commercial use, use a licensed market-data feed or a broker API.

For reference: https://github.com/jugaad-py/jugaad-data (jugaad_data/nse/live.py)
"""

from datetime import datetime
from typing import List, Optional
from requests import Session


class NSELive:
    """
    Read-only NSE live data client.

    Example:
        nse = NSELive()
        quote = nse.stock_quote("RELIANCE")
        meta = nse.symbol_meta("RELIANCE")
    """

    time_out = 5
    base_url = "https://www.nseindia.com/api"
    nextapi_url = "https://www.nseindia.com/api/NextApi/apiClient/GetQuoteApi"
    page_url = "https://www.nseindia.com/get-quotes/equity?symbol=LT"

    _routes = {
        "stock_meta": "/equity-meta-info",
        "stock_quote": "/quote-equity",
        "market_status": "/marketStatus",
        "chart_data": "/chart-databyindex",
        "market_turnover": "/market-turnover",
        "equity_derivative_turnover": "/equity-stock",
        "all_indices": "/allIndices",
        "live_index": "/equity-stock-indices",
        "option_chain_v3": "/option-chain-v3",
        "option_chain_contract_info": "/option-chain-contract-info",
        "pre_open_market": "/market-data-pre-open",
        "holiday_list": "/holiday-master?type=trading",
        "corporate_announcements": "/corporate-announcements",
        "integrated_filing": "/integrated-filing-results",
    }

    HOST_HEADERS = {
        "Host": "www.nseindia.com",
        "Referer": "https://www.nseindia.com/get-quotes/equity?symbol=SBIN",
        "X-Requested-With": "XMLHttpRequest",
        "pragma": "no-cache",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/134.0.0.0 Safari/537.36"
        ),
        "Sec-CH-UA": '"Google Chrome";v="134", "Chromium";v="134", "Not?A_Brand";v="99"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "DNT": "1",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }

    def __init__(self):
        self.s = Session()
        self.s.timeout = self.time_out
        self.s.headers.update(self.HOST_HEADERS)
        try:
            self.s.get(self.page_url)
        except Exception:
            # Session init may be blocked (403) - methods will surface the error.
            pass

    def get(self, route, payload={}):
        url = self.base_url + self._routes[route]
        r = self.s.get(url, params=payload)
        r.raise_for_status()
        return r.json()

    def _get_nextapi(self, function_name, **params):
        query_params = {"functionName": function_name}
        query_params.update(params)
        r = self.s.get(self.nextapi_url, params=query_params)
        r.raise_for_status()
        return r.json()

    # ---------------- QUOTES ----------------
    def stock_quote(self, symbol, market_type="N", series="EQ"):
        """Live equity quote: metaData, priceInfo, tradeInfo, secInfo, orderBook, lastUpdateTime."""
        r = self._get_nextapi("getSymbolData", marketType=market_type, series=series, symbol=symbol)
        return r["equityResponse"][0]

    def symbol_meta(self, symbol):
        """Metadata: FNO eligibility, ISIN, marketType, delisting status, activeSeries."""
        return self._get_nextapi("getMetaData", symbol=symbol)

    def symbol_name(self, symbol):
        """Company name lookup."""
        return self._get_nextapi("getSymbolName", symbol=symbol)

    # ---------------- MARKET BREADTH ----------------
    def top_stocks(self):
        """Top gainers/losers, most active (value/volume), volume spurts, 52-week highs/lows."""
        return self._get_nextapi("getTopTenStock")

    def market_status(self):
        return self.get("market_status", {})

    def all_indices(self):
        return self.get("all_indices")

    def live_index(self, symbol="NIFTY 50"):
        return self.get("live_index", {"index": symbol})

    def quote_index_data(self):
        return self._get_nextapi("getQuoteIndexData")

    def index_list(self, symbol):
        """Indices the symbol belongs to."""
        return self._get_nextapi("getIndexList", symbol=symbol)

    # ---------------- TECHNICAL ----------------
    def symbol_chart_data(self, symbol, series="EQ", days="1D"):
        """Intraday/historical chart data (grapthData, closePrice)."""
        return self._get_nextapi("getSymbolChartData", symbol=symbol + series + "N", days=days)

    def yearwise_data(self, symbol, series="EQ"):
        return self._get_nextapi("getYearwiseData", symbol=symbol + series + "N")

    def pre_open_market(self, key="NIFTY"):
        """Pre-open market snapshot (opening sentiment)."""
        return self.get("pre_open_market", {"key": key})

    # ---------------- DERIVATIVES ----------------
    def stock_quote_fno(self, symbol):
        """All F&O contracts for a symbol (futures & options) with OI, volume, prices."""
        return self._get_nextapi("getSymbolDerivativesData", symbol=symbol)

    def option_chain_contract_info(self, symbol):
        return self.get("option_chain_contract_info", {"symbol": symbol})

    def index_option_chain(self, symbol="NIFTY", expiry=None):
        if not expiry:
            contract_info = self.option_chain_contract_info(symbol)
            if contract_info.get("expiryDates"):
                expiry = contract_info["expiryDates"][0]
        data = {"type": "Indices", "symbol": symbol}
        if expiry:
            data["expiry"] = expiry
        return self.get("option_chain_v3", data)

    def equities_option_chain(self, symbol, expiry=None):
        if not expiry:
            contract_info = self.option_chain_contract_info(symbol)
            if contract_info.get("expiryDates"):
                expiry = contract_info["expiryDates"][0]
        data = {"type": "Equity", "symbol": symbol}
        if expiry:
            data["expiry"] = expiry
        return self.get("option_chain_v3", data)

    # ---------------- FUNDAMENTALS / EVENTS ----------------
    def corporate_announcements(self, segment="equities", from_date=None, to_date=None, symbol=None):
        payload = {"index": segment}
        if from_date and to_date:
            payload["from_date"] = from_date.strftime("%d-%m-%Y")
            payload["to_date"] = to_date.strftime("%d-%m-%Y")
        elif from_date or to_date:
            raise Exception("Please provide both from_date and to_date")
        if symbol:
            payload["symbol"] = symbol
        return self.get("corporate_announcements", payload)

    def reg_details(self, symbol):
        return self._get_nextapi("getRegDetails", symbol=symbol)

    def corporate_integrated_filing(
        self, symbol=None, filing_type="Integrated Filing- Financials",
        from_date=None, to_date=None, page=1, size=20
    ):
        payload = {"type": filing_type, "page": page, "size": size}
        if symbol:
            payload["symbol"] = symbol
        if from_date and to_date:
            payload["from_date"] = from_date.strftime("%d-%m-%Y")
            payload["to_date"] = to_date.strftime("%d-%m-%Y")
        return self.get("integrated_filing", payload)


if __name__ == "__main__":
    nse = NSELive()

    for name, fn in [
        ("market_status", nse.market_status),
    ]:
        try:
            print(f"{name} -> {fn()}")
        except Exception as error:
            print(f"{name} failed: {error}")