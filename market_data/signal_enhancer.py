# -*- coding: utf-8 -*-
"""
Enhanced signal generation for BUY / SELL / HOLD decisions.

Combines multiple quantitative factors into a grounded recommendation:

  Technical  : RSI, MACD, trend position, 52-week proximity, volume surge
  Fundamental: analyst consensus, valuation (PE), dividend yield
  Market     : optional NSE inputs - order book imbalance, PCR, F&O OI change,
               pre-open gap, relative strength vs index

Design rule: the recommendation is grounded in measurable model outputs,
never raw prices alone. The LLM/agent layer can summarize this evidence.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf


# Factor weights (sums to 1.0 for the ensemble score)
WEIGHTS = {
    "momentum": 0.20,       # 52-week position + SMA trend
    "rsi": 0.10,            # mean-reversion oscillator
    "macd": 0.10,           # trend momentum
    "volume": 0.15,         # conviction via volume surge
    "analyst": 0.15,        # Wall Street/analyst consensus
    "valuation": 0.15,      # PE + dividend relative value
    "volatility": 0.05,     # risk-adjusted confidence
    "market_sentiment": 0.10,  # NSE: PCR / OI / order book / pre-open
}


def _score_rsi(rsi: float) -> tuple:
    """RSI mean-reversion: <30 bullish, >70 bearish, 45-55 neutral."""
    if rsi is None or np.isnan(rsi):
        return 0.0, "RSI: data unavailable"
    if rsi <= 30:
        return 1.0, f"RSI {rsi:.1f} - oversold (buy zone)"
    if rsi <= 40:
        return 0.5, f"RSI {rsi:.1f} - nearing oversold"
    if rsi >= 75:
        return -1.0, f"RSI {rsi:.1f} - overbought (sell zone)"
    if rsi >= 65:
        return -0.5, f"RSI {rsi:.1f} - nearing overbought"
    if 45 <= rsi <= 55:
        return 0.0, f"RSI {rsi:.1f} - neutral"
    return 0.2 if rsi < 45 else -0.2, f"RSI {rsi:.1f} - mildly {('bullish' if rsi < 45 else 'bearish')}"


def _score_momentum(close: float, high52: float, low52: float, sma20: float, sma50: float) -> tuple:
    """Position within 52-week range + SMA trend."""
    if not all([close, high52, low52]) or high52 == low52:
        return 0.0, "Momentum: range data unavailable"
    pos = (close - low52) / (high52 - low52)  # 0=at low, 1=at high
    score = (pos - 0.5) * 2.0  # -1..+1
    if sma20 is not None and close > sma20:
        score += 0.2
    elif sma20 is not None:
        score -= 0.2
    if sma50 is not None and close > sma50:
        score += 0.2
    elif sma50 is not None:
        score -= 0.2
    score = max(-1.0, min(1.0, score))
    zone = "high" if pos > 0.75 else ("low" if pos < 0.25 else "mid")
    return score, f"Price at {pos*100:.0f}% of 52-week range ({zone} zone), {'above' if close > sma20 else 'below'} SMA20"


def _score_macd(macd_line: float, macd_signal: float, macd_hist: float) -> tuple:
    """MACD golden/death cross momentum."""
    if macd_line is None or macd_signal is None or np.isnan(macd_line) or np.isnan(macd_signal):
        return 0.0, "MACD: data unavailable"
    if macd_line > macd_signal and macd_hist > 0:
        return 0.8, "MACD bullish (above signal, histogram rising)"
    if macd_line < macd_signal and macd_hist < 0:
        return -0.8, "MACD bearish (below signal, histogram falling)"
    if macd_line > macd_signal:
        return 0.3, "MACD above signal"
    return -0.3, "MACD below signal"


def _score_volume(last_volume: float, avg_volume: float) -> tuple:
    """Volume surge = conviction (only if > 3x avg)."""
    if not last_volume or not avg_volume or avg_volume <= 0:
        return 0.0, "Volume: data unavailable"
    ratio = last_volume / avg_volume
    if ratio >= 3:
        return 0.9, f"Volume surge {ratio:.1f}x average (strong conviction)"
    if ratio >= 2:
        return 0.5, f"Above-average volume ({ratio:.1f}x)"
    if ratio >= 1.5:
        return 0.2, f"Moderate volume ({ratio:.1f}x)"
    if ratio <= 0.4:
        return -0.4, f"Thin volume ({ratio:.1f}x avg) - weak follow-through"
    return 0.0, f"Normal volume ({ratio:.1f}x)"


def _score_analyst(recommendation_mean: Optional[float], rating_count: int) -> tuple:
    """Analyst consensus: 1.0=Strong Buy ... 5.0=Strong Sell."""
    if recommendation_mean is None:
        return 0.0, "Analyst: no coverage/consensus"
    if recommendation_mean <= 1.5:
        return 1.0, f"Analyst consensus {recommendation_mean:.2f} = Strong Buy ({rating_count} analysts)"
    if recommendation_mean <= 2.5:
        return 0.5, f"Analyst consensus {recommendation_mean:.2f} = Buy ({rating_count} analysts)"
    if recommendation_mean <= 3.5:
        return 0.0, f"Analyst consensus {recommendation_mean:.2f} = Hold"
    if recommendation_mean <= 4.5:
        return -0.5, f"Analyst consensus {recommendation_mean:.2f} = Sell"
    return -1.0, f"Analyst consensus {recommendation_mean:.2f} = Strong Sell"


def _score_valuation(forward_pe: Optional[float], trailing_pe: Optional[float], div_yield: Optional[float]) -> tuple:
    """Relative valuation: improving forward vs trailing PE, dividend support."""
    score = 0.0
    reasons = []
    if forward_pe and trailing_pe and trailing_pe > 0:
        ratio = forward_pe / trailing_pe
        if ratio < 0.7:
            score += 0.6
            reasons.append(f"Forward PE {forward_pe:.1f} < trailing {trailing_pe:.1f} (earnings growth expected)")
        elif ratio < 0.9:
            score += 0.2
            reasons.append("Earnings growth priced in (forward PE lower)")
        elif ratio > 1.3:
            score -= 0.4
            reasons.append("Earnings contraction expected (forward PE higher)")
        else:
            reasons.append(f"Valuation steady (PE {trailing_pe:.1f})")
    if div_yield is not None:
        dy = float(div_yield) * 100 if float(div_yield) < 1 else float(div_yield)  # handle both 0.0048 and 0.48
        if dy >= 2.0:
            score += 0.3
            reasons.append(f"Dividend yield {dy:.2f}% provides downside support")
        elif dy >= 1.0:
            score += 0.1
            reasons.append(f"Modest dividend yield {dy:.2f}%")
    if not reasons:
        reasons.append("Valuation: data unavailable")
    return max(-1.0, min(1.0, score)), "; ".join(reasons)


def _score_market_sentiment(pcr=None, oi_change_pct=None, bid_ask_imbalance=None,
                            pre_open_gap_pct=None, strength_vs_index=None) -> tuple:
    """NSE-only sentiment: PCR, OI change, order book, pre-open gap, relative strength."""
    reasons = []
    accum = 0.0
    n = 0
    if pcr is not None and pcr > 0:
        # PCR > 1.2 bearish contrarian / defensive, < 0.8 bullish; use inverse cautiously
        accum += max(-1.0, min(1.0, (1.0 - pcr) * 1.5))
        reasons.append(f"Put-Call ratio {pcr:.2f}")
        n += 1
    if oi_change_pct is not None:
        accum += max(-1.0, min(1.0, oi_change_pct / 10.0))
        reasons.append(f"F&O OI change {oi_change_pct:+.1f}% ({'institutional inflow' if oi_change_pct > 0 else 'positions closing'})")
        n += 1
    if bid_ask_imbalance is not None:
        accum += max(-1.0, min(1.0, bid_ask_imbalance))
        reasons.append(f"Order-book imbalance {bid_ask_imbalance:+.2f}")
        n += 1
    if pre_open_gap_pct is not None:
        accum += max(-1.0, min(1.0, pre_open_gap_pct / 5.0))
        reasons.append(f"Pre-open gap {pre_open_gap_pct:+.2f}%")
        n += 1
    if strength_vs_index is not None:
        accum += max(-1.0, min(1.0, strength_vs_index / 5.0))
        reasons.append(f"Relative strength vs index {strength_vs_index:+.2f}%")
        n += 1
    if n == 0:
        return 0.0, "Market sentiment: NSE live data not available (technical/fundamental used)"
    return max(-1.0, min(1.0, accum / n)), "; ".join(reasons)


class SignalEnhancer:
    """Generates an enhanced BUY/HOLD/SELL recommendation from multiple data sources."""

    def __init__(self, exchange: str = "NSE"):
        self.exchange = exchange.upper()

    @staticmethod
    def _suffix(symbol: str, exchange: str) -> str:
        if symbol.upper().endswith((".NS", ".BO")):
            return symbol
        return f"{symbol}.NS" if exchange == "NSE" else f"{symbol}.BO"

    def _fetch_features(self, symbol: str):
        """Fetch price history + info from yfinance (works in all networks)."""
        yf_symbol = self._suffix(symbol, self.exchange)
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period="1y", interval="1d")
        if df is None or df.empty:
            raise ValueError(f"No price history for {yf_symbol}")
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        info = {}
        try:
            info = ticker.info or {}
        except Exception:
            info = {}

        close = df["Close"]
        last = float(close.iloc[-1])
        sma20 = float(close.rolling(20).mean().iloc[-1])
        sma50 = float(close.rolling(50).mean().iloc[-1])

        exp12 = close.ewm(span=12, adjust=False).mean()
        exp26 = close.ewm(span=26, adjust=False).mean()
        macd = float((exp12 - exp26).iloc[-1])
        macd_sig = float((exp12 - exp26).ewm(span=9, adjust=False).mean().iloc[-1])
        macd_hist = macd - macd_sig

        rsi = self._rsi(close)

        # Use info dict for 52-week values (more reliable than rolling)
        high_52w = info.get("fiftyTwoWeekHigh")
        low_52w = info.get("fiftyTwoWeekLow")
        if high_52w is None:
            high_52w = df["High"].max()
        if low_52w is None:
            low_52w = df["Low"].min()

        # Use info avg_volume if available (more accurate)
        avg_vol = info.get("averageVolume")
        if avg_vol is None:
            avg_vol = float(df["Volume"].tail(20).mean())

        volatility = float(df["Close"].pct_change(fill_method=None).rolling(20).std().iloc[-1] * np.sqrt(252) * 100)

        features = {
            "last_price": last,
            "previous_close": float(close.iloc[-2]) if len(close) > 1 else last,
            "day_high": float(df["High"].iloc[-1]),
            "day_low": float(df["Low"].iloc[-1]),
            "sma20": sma20,
            "sma50": sma50,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": macd_sig,
            "macd_hist": macd_hist,
            "high_52w": float(high_52w),
            "low_52w": float(low_52w),
            "avg_volume": float(avg_vol),
            "last_volume": float(df["Volume"].iloc[-1]),
            "recommendation_mean": info.get("recommendationMean"),
            "analyst_count": int(info.get("numberOfAnalystOpinions") or 0),
            "forward_pe": info.get("forwardPE"),
            "trailing_pe": info.get("trailingPE"),
            "dividend_yield": info.get("dividendYield"),
            "volatility": volatility,
            "company_name": info.get("longName") or info.get("shortName") or symbol,
        }
        return features

    @staticmethod
    def _rsi(close: pd.Series, period: int = 14) -> float:
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return float(val) if not np.isnan(val) else 50.0

    def generate(self, symbol: str, **market_inputs) -> dict:
        """
        Generate the enhanced BUY/HOLD/SELL signal.

        Optional NSE inputs (when NSELive is reachable):
          pcr, oi_change_pct, bid_ask_imbalance, pre_open_gap_pct, strength_vs_index
        """
        feats = self._fetch_features(symbol)

        factors = {
            "momentum": _score_momentum(feats["last_price"], feats["high_52w"], feats["low_52w"], feats["sma20"], feats["sma50"]),
            "rsi": _score_rsi(feats["rsi"]),
            "macd": _score_macd(feats["macd"], feats["macd_signal"], feats["macd_hist"]),
            "volume": _score_volume(feats["last_volume"], feats["avg_volume"]),
            "analyst": _score_analyst(feats["recommendation_mean"], feats["analyst_count"]),
            "valuation": _score_valuation(feats["forward_pe"], feats["trailing_pe"], feats["dividend_yield"]),
            "volatility": (max(-0.5, min(0.5, 0.5 - feats["volatility"] / 100)),
                           f"Volatility {feats['volatility']:.1f}% annualized"),
            "market_sentiment": _score_market_sentiment(**market_inputs),
        }

        score = sum(score * WEIGHTS[name] for name, (score, _reason) in factors.items())
        normalized = max(-100.0, min(100.0, score * 100))

        if normalized >= 20:
            action = "BUY"
        elif normalized <= -20:
            action = "SELL"
        else:
            action = "HOLD"

        # Agreement / confidence: consistency of factor signs
        signs = [factor[0] for factor in factors.values()]
        agreement = abs(sum(signs)) / len(signs) if signs else 0.0
        confidence = min(95.0, 40 + (abs(normalized) * 0.4) + (agreement * 25))

        reasons = [f"{name}: {info}" for name, (_s, info) in factors.items() if _s != 0]

        return {
            "symbol": symbol,
            "exchange": self.exchange,
            "action": action,
            "score": round(normalized, 1),
            "confidence": round(confidence, 1),
            "reasons": reasons,
            "factors": {name: round(score, 3) for name, (score, _r) in factors.items()},
            "features": {
                "last_price": feats["last_price"],
                "previous_close": feats["previous_close"],
                "day_high": feats["day_high"],
                "day_low": feats["day_low"],
                "high_52w": feats["high_52w"],
                "low_52w": feats["low_52w"],
                "rsi": round(feats["rsi"], 1),
                "sma20": round(feats["sma20"], 2),
                "sma50": round(feats["sma50"], 2),
                "volatility_pct": round(feats["volatility"], 1),
                "company_name": feats["company_name"],
            },
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


if __name__ == "__main__":
    enhancer = SignalEnhancer(exchange="NSE")

    for sym in ["RELIANCE", "TCS.BO"]:
        try:
            signal = enhancer.generate(sym)
            print(f"\n=== {sym} ({signal['exchange']}) ===")
            print(f"Action: {signal['action']} | Score: {signal['score']} | Confidence: {signal['confidence']}%")
            for r in signal["reasons"]:
                print(f"  - {r}")
            print(f"Factors: {signal['factors']}")
        except Exception as error:
            print(f"{sym} failed: {error}")