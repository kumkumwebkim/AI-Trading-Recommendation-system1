import yfinance as yf
import pandas as pd
import ta


def fetch_last_51_days(ticker: str) -> pd.DataFrame:
    df = yf.download(
        ticker,
        period="3mo",       # guarantees >= 51 trading days
        interval="1d",
        auto_adjust=False,
        progress=False
    )

    if df.empty or len(df) < 51:
        raise ValueError("Not enough historical data")

    df = df.reset_index()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)
    df.columns = [c.lower() for c in df.columns]
    return df.tail(51)


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").copy()

    df["daily_return"] = df["close"].pct_change(fill_method=None)
    df["volume_change"] = df["volume"].pct_change(fill_method=None)

    df["ma20"] = ta.trend.SMAIndicator(df["close"], 20).sma_indicator()
    df["ma50"] = ta.trend.SMAIndicator(df["close"], 50).sma_indicator()
    df["close_ma20_ratio"] = df["close"] / df["ma20"]

    df["volatility"] = df["daily_return"].rolling(20).std()
    df["rsi"] = ta.momentum.RSIIndicator(df["close"], 14).rsi()

    df["ema12"] = ta.trend.EMAIndicator(df["close"], 12).ema_indicator()
    df["ema26"] = ta.trend.EMAIndicator(df["close"], 26).ema_indicator()

    macd = ta.trend.MACD(df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    return df


def get_indicators(ticker: str) -> dict:
    """
    Fetch and compute indicators for a given ticker.
    Returns today's indicators as a dictionary.
    """
    df = fetch_last_51_days(ticker)
    df = compute_indicators(df)

    today = df.iloc[-1]

    return {
        "Open": float(today["open"]),
        "High": float(today["high"]),
        "Low": float(today["low"]),
        "Adj Close": float(today["adj close"]),
        "Volume": float(today["volume"]),
        "Company": None,

        "Daily_Return": float(today["daily_return"]),
        "Volume_Change": float(today["volume_change"]),
        "MA20": float(today["ma20"]),
        "MA50": float(today["ma50"]),
        "Close_MA20_Ratio": float(today["close_ma20_ratio"]),
        "Volatility": float(today["volatility"]),
        "RSI": float(today["rsi"]),
        "EMA12": float(today["ema12"]),
        "EMA26": float(today["ema26"]),
        "MACD": float(today["macd"]),
        "MACD_Signal": float(today["macd_signal"]),
    }
