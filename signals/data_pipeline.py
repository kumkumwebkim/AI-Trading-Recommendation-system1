import os
import yfinance as yf
import pandas as pd
from datetime import datetime
import ta

# Configuration for data locations and date range
TICKER_FILE = "data/ticker.txt"
RAW_FILE = "data/raw_market.parquet"
FEATURED_FILE = "data/featured_market.parquet"
CLEAN_FILE = "data/clean_market.parquet"
ENCODER_FILE = "data/ticker_encoder.parquet"

START_DATE = "2018-01-01"
END_DATE = datetime.today().strftime("%Y-%m-%d")
LOOKBACK_DAYS = 50

os.makedirs("data", exist_ok=True)


# Load ticker symbols from text file
def load_tickers(path):
    with open(path) as f:
        return sorted(set(line.strip() for line in f if line.strip()))


# Download historical OHLCV data from Yahoo Finance
def fetch_raw_data(tickers):
    df = yf.download(
        tickers=tickers,
        start=START_DATE,
        end=END_DATE,
        group_by="ticker",
        threads=True,
        auto_adjust=False
    )
    df = df.stack(level=0, future_stack=True).reset_index()
    df.columns = [c.lower() for c in df.columns]
    return df


# Create or load numeric encoding for tickers
def load_or_create_encoder(tickers):
    if os.path.exists(ENCODER_FILE):
        return pd.read_parquet(ENCODER_FILE)

    encoder = pd.DataFrame({
        "ticker": tickers,
        "ticker_id": range(len(tickers))
    })
    encoder.to_parquet(ENCODER_FILE, index=False)
    return encoder


# Generate technical indicators using ta library
def add_features(df):
    df = df.sort_values(["ticker", "date"])
    out = []

    for _, g in df.groupby("ticker"):
        g = g.copy()

        g["daily_return"] = g["close"].pct_change(fill_method=None)
        g["volume_change"] = g["volume"].pct_change(fill_method=None)

        g["ma20"] = ta.trend.SMAIndicator(g["close"], 20).sma_indicator()
        g["ma50"] = ta.trend.SMAIndicator(g["close"], 50).sma_indicator()
        g["close_ma20_ratio"] = g["close"] / g["ma20"]

        g["volatility"] = g["daily_return"].rolling(20).std()
        g["rsi"] = ta.momentum.RSIIndicator(g["close"], 14).rsi()

        g["ema12"] = ta.trend.EMAIndicator(g["close"], 12).ema_indicator()
        g["ema26"] = ta.trend.EMAIndicator(g["close"], 26).ema_indicator()

        macd = ta.trend.MACD(g["close"])
        g["macd"] = macd.macd()
        g["macd_signal"] = macd.macd_signal()

        out.append(g)

    return pd.concat(out, ignore_index=True)


# Remove unstable initial rows caused by rolling indicators
def drop_initial_rows(df, n):
    return (
        df.sort_values(["ticker", "date"])
          .groupby("ticker", group_keys=False)
          .apply(lambda x: x.iloc[n:])
    )


# Remove accidental index columns created during IO
def remove_bad_index_columns(df):
    bad = ["__index_level_0__", "index", "level_0"]
    return df.drop(columns=[c for c in bad if c in df.columns])


# Run full market data pipeline from raw to clean
def run_pipeline():
    print("Starting data pipeline")

    tickers = load_tickers(TICKER_FILE)

    raw_df = fetch_raw_data(tickers)
    raw_df = remove_bad_index_columns(raw_df)

    if os.path.exists(RAW_FILE):
        old = pd.read_parquet(RAW_FILE)
        raw_df = (
            pd.concat([old, raw_df], ignore_index=True)
              .drop_duplicates(subset=["date", "ticker"], keep="last")
        )

    raw_df.to_parquet(RAW_FILE, index=False)

    featured_df = add_features(raw_df)
    featured_df.to_parquet(FEATURED_FILE, index=False)

    encoder = load_or_create_encoder(tickers)

    clean_df = featured_df.merge(encoder, on="ticker", how="left")
    clean_df = drop_initial_rows(clean_df, LOOKBACK_DAYS)
    clean_df = clean_df.dropna()
    clean_df = remove_bad_index_columns(clean_df)

    final_columns = [
        "date", "open", "high", "low", "close", "adj close", "volume",
        "ticker", "ticker_id",
        "daily_return", "volume_change",
        "ma20", "ma50", "close_ma20_ratio",
        "volatility", "rsi",
        "ema12", "ema26", "macd", "macd_signal"
    ]

    clean_df = clean_df[final_columns].sort_values(["ticker", "date"])
    clean_df.to_parquet(CLEAN_FILE, index=False)

    print("Pipeline finished successfully")


if __name__ == "__main__":
    run_pipeline()