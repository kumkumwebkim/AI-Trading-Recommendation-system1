# -*- coding: utf-8 -*-
"""
📁 Custom Dataset Analysis & AI Investment Prediction
Allows users to upload custom datasets (CSV, Excel, Parquet, JSON),
perform automated technical analysis, and generate AI predictions
(INVEST / BUY / HOLD / SELL) with actionable risk management and backtesting.
"""

import sys
import os
from pathlib import Path

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import datetime
import io
import re

from ui.utils.design import load_design_system
from contracts.schema import StockData, MLSignal
from ml.predictor import MLEngine
from backtesting.engine import BacktestEngine

# Page configuration
st.set_page_config(
    page_title="Dataset Analysis & AI Predictions - Stock AI",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load design system CSS
load_design_system()

# --- Custom Glassmorphism CSS ---
def inject_custom_styles():
    st.markdown("""
        <style>
        .stApp {
            background: radial-gradient(circle at 50% 0%, #1e2640 0%, #0c0f17 100%) !important;
            background-attachment: fixed;
        }
        
        .upload-header {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
            padding: 24px;
            margin-bottom: 24px;
            backdrop-filter: blur(16px);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        }
        
        .decision-card {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.85) 100%);
            border-radius: 20px;
            padding: 26px;
            margin-bottom: 20px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            backdrop-filter: blur(14px);
        }
        
        .badge-buy {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: #ffffff;
            padding: 8px 18px;
            border-radius: 30px;
            font-weight: 800;
            font-size: 18px;
            display: inline-block;
            box-shadow: 0 4px 15px rgba(16, 185, 129, 0.4);
        }
        
        .badge-sell {
            background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
            color: #ffffff;
            padding: 8px 18px;
            border-radius: 30px;
            font-weight: 800;
            font-size: 18px;
            display: inline-block;
            box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
        }
        
        .badge-hold {
            background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
            color: #ffffff;
            padding: 8px 18px;
            border-radius: 30px;
            font-weight: 800;
            font-size: 18px;
            display: inline-block;
            box-shadow: 0 4px 15px rgba(245, 158, 11, 0.4);
        }

        .stat-badge {
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 12px 16px;
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

# --- Helper Functions for Data Processing ---

def normalize_column_name(column) -> str:
    """
    Normalize column names so standard, exchange-style, and human-readable
    names can be matched consistently.

    Examples:
        'Close Price' -> 'closeprice'
        'ClsPric'     -> 'clspric'
        'Trad Dt'     -> 'traddt'
    """
    name = str(column).strip().lower()
    name = re.sub(r"[^a-z0-9]+", "", name)
    return name


def clean_uploaded_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean an uploaded dataset without changing its original meaning.

    Actions:
    - Remove completely empty rows and columns.
    - Strip whitespace from string column names.
    - Make duplicate column names unique.
    - Remove leading/trailing whitespace from string values.
    """
    if df is None:
        raise ValueError("Dataset is empty or could not be loaded.")

    result = df.copy()

    # Remove completely empty rows/columns.
    result = result.dropna(axis=0, how="all").dropna(axis=1, how="all")

    # Clean column labels.
    cleaned_columns = []
    seen = {}

    for col in result.columns:
        base = str(col).strip()
        if not base:
            base = "Unnamed"

        count = seen.get(base, 0)
        seen[base] = count + 1
        cleaned_columns.append(base if count == 0 else f"{base}_{count}")

    result.columns = cleaned_columns

    # Strip whitespace from text values.
    for col in result.columns:
        if pd.api.types.is_object_dtype(result[col]):
            result[col] = result[col].map(
                lambda value: value.strip() if isinstance(value, str) else value
            )

    return result.reset_index(drop=True)


def _build_normalized_columns(df: pd.DataFrame) -> dict:
    """Map normalized column names to their original column names."""
    normalized = {}
    for col in df.columns:
        key = normalize_column_name(col)
        if key not in normalized:
            normalized[key] = col
    return normalized


def _find_column(normalized: dict, aliases: list[str]):
    """Find a column using exact normalized aliases."""
    for alias in aliases:
        key = normalize_column_name(alias)
        if key in normalized:
            return normalized[key]
    return None


def _find_column_by_tokens(normalized: dict, tokens: list[str]):
    """Find a column using token/substring matching."""
    for key, original_col in normalized.items():
        if all(token in key for token in tokens):
            return original_col
    return None


def _numeric_fallback(df: pd.DataFrame, excluded=None):
    """
    Select a numeric column as a last-resort price fallback.
    Metadata, IDs, and categorical columns are excluded where possible.
    """
    excluded = set(excluded or [])

    candidates = []
    for col in df.columns:
        if col in excluded:
            continue

        numeric = pd.to_numeric(
            df[col].astype(str).str.replace(",", "", regex=False),
            errors="coerce"
        )

        valid_count = numeric.notna().sum()
        if valid_count == 0:
            continue

        # Prefer columns with meaningful numeric coverage.
        coverage = valid_count / max(len(df), 1)
        candidates.append((coverage, col))

    if not candidates:
        return None

    # Select the column with the highest numeric coverage.
    candidates.sort(reverse=True)
    return candidates[0][1]


def auto_detect_columns(df: pd.DataFrame) -> dict:
    """
    Automatically map standard and NSE/BSE-style market-data columns to
    the application's standard OHLCV fields.

    Supported examples include:

    Date:
        Date, Datetime, TradDt, BizDt, TradeDate

    Symbol:
        Ticker, Symbol, TckrSymb, Scrip, Security Name

    Open:
        Open, Open Price, OpnPric, OpnPrice

    High:
        High, High Price, HghPric, HghPrice

    Low:
        Low, Low Price, LwPric, LwPrice

    Close:
        Close, Close Price, ClsPric, ClsPrice, ClosingPrice

    Volume:
        Volume, Vol, TtlTradgVol, TotalTradingVolume,
        TotalTradedQuantity, TtlTradedQty
    """
    normalized = _build_normalized_columns(df)

    mapping = {
        "date": None,
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "volume": None,
        "ticker": None,
        "underlying_price": None,
        "settlement_price": None,
        "last_price": None,
        "previous_close": None,
        "open_interest": None,
        "change_open_interest": None,
        "instrument_type": None,
        "expiry_date": None,
    }

    # Date columns: prioritize actual trade date.
    mapping["date"] = _find_column(normalized, [
        "TradDt", "TradeDate", "TradingDate", "Date", "Datetime",
        "Timestamp", "Trade_Date", "TradedOn"
    ])

    if mapping["date"] is None:
        mapping["date"] = _find_column_by_tokens(normalized, ["date"])

    # Symbol/ticker columns.
    mapping["ticker"] = _find_column(normalized, [
        "TckrSymb", "Ticker", "TickerSymbol", "Symbol", "Stock",
        "Scrip", "ScripCode", "Security", "SecurityName", "Asset"
    ])

    if mapping["ticker"] is None:
        mapping["ticker"] = _find_column_by_tokens(normalized, ["symb"])

    # Actual contract OHLC prices.
    mapping["open"] = _find_column(normalized, [
        "OpnPric", "OpnPrice", "OpenPrice", "OpeningPrice",
        "Open", "TradeOpen", "PxOpen"
    ])

    mapping["high"] = _find_column(normalized, [
        "HghPric", "HghPrice", "HighPrice", "MaximumPrice",
        "MaxPrice", "High", "DayHigh", "TradeHigh", "PxHigh"
    ])

    mapping["low"] = _find_column(normalized, [
        "LwPric", "LwPrice", "LowPrice", "MinimumPrice",
        "MinPrice", "Low", "DayLow", "TradeLow", "PxLow"
    ])

    mapping["close"] = _find_column(normalized, [
        "ClsPric", "ClsPrice", "ClosePrice", "ClosingPrice",
        "Close", "Closing", "PxClose", "OfficialClose"
    ])

    # Additional market-data fields.
    mapping["last_price"] = _find_column(normalized, [
        "LastPric", "LastPrice", "LTP", "LastTradedPrice",
        "LastTradedPric", "PxLast"
    ])

    mapping["previous_close"] = _find_column(normalized, [
        "PrvsClsgPric", "PreviousClosePrice", "PreviousClose",
        "PrevClose", "PrevClsPric", "PrevClsPrice"
    ])

    mapping["underlying_price"] = _find_column(normalized, [
        "UndrlygPric", "UnderlyingPrice", "UnderlyingPric",
        "UnderlyingValue", "SpotPrice"
    ])

    mapping["settlement_price"] = _find_column(normalized, [
        "SttlmPric", "SettlementPrice", "SettlePrice",
        "Settlement"
    ])

    mapping["volume"] = _find_column(normalized, [
        "TtlTradgVol", "TotalTradingVolume", "TotalTradedVolume",
        "TotalTradedQuantity", "TtlTradedQty", "TradedVolume",
        "TradedQty", "TradeVolume", "Volume", "Vol",
        "Shares", "Quantity", "Qty"
    ])

    mapping["open_interest"] = _find_column(normalized, [
        "OpnIntrst", "OpenInterest", "OI", "OpenInt"
    ])

    mapping["change_open_interest"] = _find_column(normalized, [
        "ChngInOpnIntrst", "ChangeInOpenInterest",
        "ChangeOpenInterest", "OIChange"
    ])

    mapping["instrument_type"] = _find_column(normalized, [
        "FinInstrmTp", "FinancialInstrumentType", "InstrumentType",
        "Instrument"
    ])

    mapping["expiry_date"] = _find_column(normalized, [
        "XpryDt", "ExpiryDate", "ExpirationDate", "Expiry"
    ])

    # Fallbacks for common human-readable names.
    if mapping["open"] is None:
        mapping["open"] = _find_column_by_tokens(normalized, ["open"])
    if mapping["high"] is None:
        mapping["high"] = _find_column_by_tokens(normalized, ["high"])
    if mapping["low"] is None:
        mapping["low"] = _find_column_by_tokens(normalized, ["low"])
    if mapping["close"] is None:
        mapping["close"] = _find_column_by_tokens(normalized, ["close"])
    if mapping["volume"] is None:
        mapping["volume"] = _find_column_by_tokens(normalized, ["volume"])

    # Last-price fallback is useful for datasets that do not publish close.
    if mapping["close"] is None:
        mapping["close"] = mapping["last_price"]

    # Settlement price can be a fallback for some derivatives files.
    if mapping["close"] is None:
        mapping["close"] = mapping["settlement_price"]

    # Underlying price is a final fallback only.
    if mapping["close"] is None:
        mapping["close"] = mapping["underlying_price"]

    if mapping["close"] is None:
        excluded = [
            value for key, value in mapping.items()
            if key not in {"close"} and value is not None
        ]
        mapping["close"] = _numeric_fallback(df, excluded=excluded)

    return mapping


def _to_numeric_series(series: pd.Series, column_name: str) -> pd.Series:
    """
    Convert numeric-looking values to numbers.

    Supports commas, currency symbols, percentage-like formatting, and
    blank/null values. Invalid values become NaN.
    """
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
        .str.replace("₹", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace("N/A", "", regex=False)
        .str.replace("NA", "", regex=False)
        .str.replace("-", "", regex=False)
    )

    numeric = pd.to_numeric(cleaned, errors="coerce")

    if numeric.notna().sum() == 0:
        raise ValueError(
            f"Column '{column_name}' does not contain valid numeric values."
        )

    return numeric


def _get_numeric_column(
    df: pd.DataFrame,
    column: str | None,
    fallback: pd.Series | None,
    default_value: float | int,
    column_label: str,
    integer: bool = False
) -> pd.Series:
    """Read a numeric column or use a safe fallback series."""
    if column and column in df.columns:
        values = _to_numeric_series(df[column], column)

        if fallback is not None:
            values = values.fillna(fallback)
    elif fallback is not None:
        values = fallback.copy()
    else:
        values = pd.Series(default_value, index=df.index, dtype=float)

    if integer:
        return values.fillna(0).clip(lower=0).round().astype(int)

    return values.astype(float)


def calculate_technical_indicators(
    df: pd.DataFrame,
    close_col: str
) -> pd.DataFrame:
    """Compute technical indicators using a validated numeric close series."""
    res = df.copy()
    s_close = pd.to_numeric(res[close_col], errors="coerce").astype(float)

    # RSI (14)
    delta = s_close.diff()
    gain = delta.where(delta > 0, 0.0).rolling(
        window=14, min_periods=1
    ).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(
        window=14, min_periods=1
    ).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    res["RSI"] = rsi.replace([np.inf, -np.inf], np.nan).fillna(50.0)

    # Moving averages
    res["SMA_20"] = s_close.rolling(window=20, min_periods=1).mean()
    res["SMA_50"] = s_close.rolling(window=50, min_periods=1).mean()
    res["EMA_12"] = s_close.ewm(span=12, adjust=False).mean()
    res["EMA_26"] = s_close.ewm(span=26, adjust=False).mean()

    # MACD
    res["MACD"] = res["EMA_12"] - res["EMA_26"]
    res["MACD_Signal"] = res["MACD"].ewm(
        span=9, adjust=False
    ).mean()
    res["MACD_Hist"] = res["MACD"] - res["MACD_Signal"]

    # Bollinger Bands
    rolling_std_20 = s_close.rolling(
        window=20, min_periods=1
    ).std().fillna(0)
    res["BB_Upper"] = res["SMA_20"] + (rolling_std_20 * 2)
    res["BB_Lower"] = res["SMA_20"] - (rolling_std_20 * 2)

    # Returns and volatility
    res["Daily_Return"] = s_close.pct_change().replace(
        [np.inf, -np.inf], np.nan
    ).fillna(0.0)
    res["Volatility_14"] = (
        res["Daily_Return"]
        .rolling(window=14, min_periods=1)
        .std()
        .fillna(0.0)
        * np.sqrt(252)
        * 100.0
    )

    return res


def convert_df_to_stock_data(
    df: pd.DataFrame,
    mapping: dict,
    symbol: str
) -> StockData:
    """
    Convert any supported uploaded dataset into the standard StockData
    contract used by the prediction and backtesting engines.

    The original dataframe is not modified. The function standardizes:
    date, symbol, open, high, low, close, and volume.
    """
    df_sorted = clean_uploaded_dataframe(df)

    if df_sorted.empty:
        raise ValueError("Dataset is empty after cleaning.")

    # Parse and sort by date when a date column is available.
    date_col = mapping.get("date")
    if date_col and date_col in df_sorted.columns:
        parsed_dates = pd.to_datetime(
            df_sorted[date_col], errors="coerce", dayfirst=False
        )

        # If the first parse produced no usable dates, try day-first format.
        if parsed_dates.notna().sum() == 0:
            parsed_dates = pd.to_datetime(
                df_sorted[date_col], errors="coerce", dayfirst=True
            )

        df_sorted = df_sorted.assign(ParsedDate=parsed_dates)
        df_sorted = (
            df_sorted.dropna(subset=["ParsedDate"])
            .sort_values("ParsedDate")
            .reset_index(drop=True)
        )
        dates = df_sorted["ParsedDate"].dt.strftime("%Y-%m-%d").tolist()
    else:
        dates = [f"Day-{i + 1}" for i in range(len(df_sorted))]

    if df_sorted.empty:
        raise ValueError(
            "No valid rows remain after date parsing. "
            "Please verify the selected date column."
        )

    close_col = mapping.get("close")
    if not close_col or close_col not in df_sorted.columns:
        raise ValueError(
            "Close price column was not found. "
            f"Available columns: {list(df_sorted.columns)}"
        )

    # Close is the primary required field.
    close_values = _to_numeric_series(
        df_sorted[close_col], close_col
    )
    valid_close = close_values.notna()

    df_sorted = df_sorted.loc[valid_close].copy()
    close_values = close_values.loc[valid_close].reset_index(drop=True)
    df_sorted = df_sorted.reset_index(drop=True)

    if close_values.empty:
        raise ValueError(
            f"No valid price data found in column '{close_col}'."
        )

    df_sorted["_standard_close"] = close_values

    # Build OHLCV fields. Missing OHLC values use sensible fallbacks.
    opens = _get_numeric_column(
        df_sorted,
        mapping.get("open"),
        fallback=close_values,
        default_value=0,
        column_label="Open"
    )

    highs = _get_numeric_column(
        df_sorted,
        mapping.get("high"),
        fallback=pd.concat([opens, close_values], axis=1).max(axis=1),
        default_value=0,
        column_label="High"
    )

    lows = _get_numeric_column(
        df_sorted,
        mapping.get("low"),
        fallback=pd.concat([opens, close_values], axis=1).min(axis=1),
        default_value=0,
        column_label="Low"
    )

    # Ensure OHLC consistency even if source data contains minor errors.
    highs = pd.concat([highs, opens, lows, close_values], axis=1).max(axis=1)
    lows = pd.concat([lows, opens, highs, close_values], axis=1).min(axis=1)

    volumes = _get_numeric_column(
        df_sorted,
        mapping.get("volume"),
        fallback=None,
        default_value=1000000,
        column_label="Volume",
        integer=True
    )

    # Calculate indicators from the standardized close column.
    df_ind = calculate_technical_indicators(
        df_sorted,
        "_standard_close"
    )

    closes = close_values.tolist()
    opens_list = opens.tolist()
    highs_list = highs.tolist()
    lows_list = lows.tolist()
    volumes_list = volumes.tolist()

    current_price = float(closes[-1])
    previous_price = float(closes[-2]) if len(closes) > 1 else current_price
    price_change = current_price - previous_price
    price_change_pct = (
        (price_change / previous_price) * 100.0
        if previous_price != 0 else 0.0
    )

    # Keep symbol safe when the source symbol is missing or invalid.
    safe_symbol = str(symbol or "CUSTOM_STOCK").strip()
    if not safe_symbol or safe_symbol.lower() == "nan":
        safe_symbol = "CUSTOM_STOCK"

    return StockData(
        symbol=safe_symbol.upper(),
        current_price=round(current_price, 2),
        price_change=round(price_change, 2),
        price_change_pct=round(price_change_pct, 2),
        last_updated=datetime.datetime.now(),
        market_status="Uploaded Dataset",
        dates=dates,
        opens=opens_list,
        highs=highs_list,
        lows=lows_list,
        closes=closes,
        volumes=volumes_list,
        rsi=df_ind["RSI"].tolist(),
        sma_20=df_ind["SMA_20"].tolist(),
        sma_50=df_ind["SMA_50"].tolist(),
        ema_12=df_ind["EMA_12"].tolist(),
        ema_26=df_ind["EMA_26"].tolist(),
        macd=df_ind["MACD"].tolist(),
        macd_signal=df_ind["MACD_Signal"].tolist(),
        macd_hist=df_ind["MACD_Hist"].tolist()
    )


def generate_sample_dataset() -> pd.DataFrame:
    """Generates a rich multi-asset stock dataset for instant demo testing."""
    np.random.seed(42)
    days = 180
    dates = pd.date_range(end=datetime.date.today(), periods=days, freq='B')
    
    stocks = {
        "AAPL": {"base": 220.0, "drift": 0.0012, "vol": 0.015},
        "NVDA": {"base": 115.0, "drift": 0.0025, "vol": 0.028},
        "MSFT": {"base": 410.0, "drift": 0.0008, "vol": 0.012},
        "TSLA": {"base": 240.0, "drift": -0.0005, "vol": 0.032},
        "RELIANCE.NS": {"base": 1380.0, "drift": 0.0015, "vol": 0.014}
    }
    
    rows = []
    for ticker, params in stocks.items():
        price = params["base"]
        for dt in dates:
            ret = np.random.normal(params["drift"], params["vol"])
            price = max(1.0, price * (1.0 + ret))
            high = price * (1.0 + abs(np.random.normal(0.008, 0.004)))
            low = price * (1.0 - abs(np.random.normal(0.008, 0.004)))
            open_p = low + (high - low) * np.random.uniform(0.2, 0.8)
            vol = int(np.random.lognormal(14.5, 0.6))
            
            rows.append({
                "Date": dt.strftime("%Y-%m-%d"),
                "Ticker": ticker,
                "Open": round(open_p, 2),
                "High": round(high, 2),
                "Low": round(low, 2),
                "Close": round(price, 2),
                "Volume": vol
            })
            
    return pd.DataFrame(rows)


# --- UI Visualizations ---

def render_interactive_stock_chart(stock_data: StockData):
    """Renders interactive candlestick and moving average chart."""
    fig = make_subplots(
        rows=2, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.04, 
        row_heights=[0.75, 0.25],
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
    )
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=stock_data.dates,
        open=stock_data.opens,
        high=stock_data.highs,
        low=stock_data.lows,
        close=stock_data.closes,
        name="Price Action",
        increasing_line_color="#00ff7f",
        decreasing_line_color="#ff4b4b"
    ), row=1, col=1)
    
    # Moving Averages
    if stock_data.sma_20:
        fig.add_trace(go.Scatter(
            x=stock_data.dates, y=stock_data.sma_20,
            name="SMA 20", line=dict(color="#38bdf8", width=1.5)
        ), row=1, col=1)
        
    if stock_data.sma_50:
        fig.add_trace(go.Scatter(
            x=stock_data.dates, y=stock_data.sma_50,
            name="SMA 50", line=dict(color="#f59e0b", width=1.5)
        ), row=1, col=1)

    # Volume Bars
    colors = ["#00ff7f" if c >= o else "#ff4b4b" for c, o in zip(stock_data.closes, stock_data.opens)]
    fig.add_trace(go.Bar(
        x=stock_data.dates, y=stock_data.volumes,
        name="Volume", marker_color=colors, opacity=0.7
    ), row=2, col=1)
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(15, 23, 42, 0.4)",
        plot_bgcolor="rgba(15, 23, 42, 0.4)",
        margin=dict(l=20, r=20, t=30, b=20),
        height=520,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True)


def render_indicators_charts(stock_data: StockData):
    """Renders RSI and MACD subplots."""
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 📈 RSI (Relative Strength Index)")
        fig_rsi = go.Figure()
        fig_rsi.add_trace(go.Scatter(
            x=stock_data.dates, y=stock_data.rsi,
            name="RSI 14", line=dict(color="#a855f7", width=2)
        ))
        fig_rsi.add_hline(y=70, line_dash="dash", line_color="#ef4444", annotation_text="Overbought (70)")
        fig_rsi.add_hline(y=30, line_dash="dash", line_color="#10b981", annotation_text="Oversold (30)")
        fig_rsi.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(15, 23, 42, 0.4)",
            plot_bgcolor="rgba(15, 23, 42, 0.4)",
            height=250,
            margin=dict(l=10, r=10, t=20, b=20),
            yaxis=dict(range=[0, 100])
        )
        st.plotly_chart(fig_rsi, use_container_width=True)
        
    with col2:
        st.markdown("##### 📉 MACD (Trend & Momentum)")
        fig_macd = go.Figure()
        fig_macd.add_trace(go.Scatter(
            x=stock_data.dates, y=stock_data.macd,
            name="MACD", line=dict(color="#38bdf8", width=1.5)
        ))
        fig_macd.add_trace(go.Scatter(
            x=stock_data.dates, y=stock_data.macd_signal,
            name="Signal", line=dict(color="#f97316", width=1.5)
        ))
        hist_colors = ["#10b981" if h >= 0 else "#ef4444" for h in stock_data.macd_hist]
        fig_macd.add_trace(go.Bar(
            x=stock_data.dates, y=stock_data.macd_hist,
            name="Histogram", marker_color=hist_colors, opacity=0.7
        ))
        fig_macd.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(15, 23, 42, 0.4)",
            plot_bgcolor="rgba(15, 23, 42, 0.4)",
            height=250,
            margin=dict(l=10, r=10, t=20, b=20),
            legend=dict(orientation="h", y=1.1, x=0.5, xanchor="center")
        )
        st.plotly_chart(fig_macd, use_container_width=True)


# --- Main Application Page ---

def main():
    inject_custom_styles()
    
    st.markdown("""
        <div class="upload-header">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div>
                    <h1 style="margin: 0; font-size: 32px; font-weight: 800; background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                        📁 Custom Dataset Analysis & AI Predictor
                    </h1>
                    <p style="margin: 6px 0 0; color: #94a3b8; font-size: 15px;">
                        Upload stock price datasets to compute instant technical indicators, ML ensemble forecasts, and actionable investment signals (Invest / Buy / Hold / Sell).
                    </p>
                </div>
                <div style="font-size: 40px;">🔮</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar: Data Source & Settings
    with st.sidebar:
        st.markdown("### 📥 Dataset Options")
        
        data_mode = st.radio(
            "Select Input Mode:",
            ["📂 Upload File", "⚡ Load Demo Dataset"],
            index=0
        )
        
        uploaded_df = None
        
        if data_mode == "📂 Upload File":
            uploaded_file = st.file_uploader(
                "Upload Stock File",
                type=["csv", "xlsx", "xls", "parquet", "json"],
                help="Accepts CSV, Excel, Parquet, or JSON with Date and Price/Close columns."
            )
            
            if uploaded_file is not None:
                try:
                    file_ext = uploaded_file.name.split(".")[-1].lower()
                    if file_ext == "csv":
                        uploaded_df = pd.read_csv(uploaded_file)
                    elif file_ext in ["xlsx", "xls"]:
                        uploaded_df = pd.read_excel(uploaded_file)
                    elif file_ext == "parquet":
                        uploaded_df = pd.read_parquet(uploaded_file)
                    elif file_ext == "json":
                        uploaded_df = pd.read_json(uploaded_file)
                        
                    uploaded_df = clean_uploaded_dataframe(uploaded_df)
                    st.success(
                        f"✅ Loaded {uploaded_file.name} "
                        f"({len(uploaded_df)} rows, {len(uploaded_df.columns)} columns)"
                    )
                except Exception as e:
                    st.error(f"Failed to read file: {e}")
        else:
            if st.button("🚀 Load Multi-Stock Demo Data", type="primary", use_container_width=True):
                st.session_state["demo_dataset"] = generate_sample_dataset()
                st.success("✅ Multi-stock demo dataset loaded!")
            
            if "demo_dataset" in st.session_state:
                uploaded_df = clean_uploaded_dataframe(st.session_state["demo_dataset"])
                st.caption(f"Demo Data: {len(uploaded_df)} records (AAPL, NVDA, MSFT, TSLA, RELIANCE)")

    # If no data loaded yet, show intuitive landing instructions
    if uploaded_df is None or uploaded_df.empty:
        st.info("👈 Upload your stock dataset (CSV/Excel/Parquet) in the sidebar or click **Load Multi-Stock Demo Data** to begin analysis.")
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.markdown("""
                <div class="decision-card">
                    <h4>1️⃣ Instant Ingestion</h4>
                    <p style="color: #94a3b8; font-size: 13px;">Auto-detects columns like Date, Open, High, Low, Close, Volume, and Ticker across various naming formats.</p>
                </div>
            """, unsafe_allow_html=True)
        with col_b:
            st.markdown("""
                <div class="decision-card">
                    <h4>2️⃣ AI & ML Predictions</h4>
                    <p style="color: #94a3b8; font-size: 13px;">Computes Ensemble Machine Learning (RF + XGBoost + LSTM + Trend Oscillator) signals with confidence ratings.</p>
                </div>
            """, unsafe_allow_html=True)
        with col_c:
            st.markdown("""
                <div class="decision-card">
                    <h4>3️⃣ Investment Guidance</h4>
                    <p style="color: #94a3b8; font-size: 13px;">Generates definitive Buy/Hold/Sell/Invest actions, target prices, stop-loss protection, and strategy backtest results.</p>
                </div>
            """, unsafe_allow_html=True)
        return

    # Auto-detect Columns & Allow Custom Override
    with st.expander("⚙️ Verify & Configure Column Mapping", expanded=False):
        mapping = auto_detect_columns(uploaded_df)
        all_cols = ["None"] + list(uploaded_df.columns)
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            sel_date = st.selectbox("Date Column", all_cols, index=all_cols.index(mapping["date"]) if mapping["date"] in all_cols else 0)
        with c2:
            sel_close = st.selectbox("Close / Price Column*", all_cols, index=all_cols.index(mapping["close"]) if mapping["close"] in all_cols else 0)
        with c3:
            sel_open = st.selectbox("Open Column", all_cols, index=all_cols.index(mapping["open"]) if mapping["open"] in all_cols else 0)
        with c4:
            sel_vol = st.selectbox("Volume Column", all_cols, index=all_cols.index(mapping["volume"]) if mapping["volume"] in all_cols else 0)
            
        c5, c6, c7, _ = st.columns(4)
        with c5:
            sel_high = st.selectbox("High Column", all_cols, index=all_cols.index(mapping["high"]) if mapping["high"] in all_cols else 0)
        with c6:
            sel_low = st.selectbox("Low Column", all_cols, index=all_cols.index(mapping["low"]) if mapping["low"] in all_cols else 0)
        with c7:
            sel_ticker = st.selectbox("Ticker / Symbol Column", all_cols, index=all_cols.index(mapping["ticker"]) if mapping["ticker"] in all_cols else 0)

        # Update mapping
        mapping["date"] = None if sel_date == "None" else sel_date
        mapping["close"] = None if sel_close == "None" else sel_close
        mapping["open"] = None if sel_open == "None" else sel_open
        mapping["high"] = None if sel_high == "None" else sel_high
        mapping["low"] = None if sel_low == "None" else sel_low
        mapping["volume"] = None if sel_vol == "None" else sel_vol
        mapping["ticker"] = None if sel_ticker == "None" else sel_ticker

        st.markdown("##### 🔎 Detected Source-to-Standard Mapping")
        mapping_display = {
            "Date": mapping.get("date") or "Not detected",
            "Ticker / Symbol": mapping.get("ticker") or "Not detected",
            "Open": mapping.get("open") or "Fallback to Close",
            "High": mapping.get("high") or "Fallback to OHLC values",
            "Low": mapping.get("low") or "Fallback to OHLC values",
            "Close": mapping.get("close") or "Not detected",
            "Volume": mapping.get("volume") or "Default volume",
            "Underlying Price": mapping.get("underlying_price") or "Not detected",
            "Settlement Price": mapping.get("settlement_price") or "Not detected",
            "Open Interest": mapping.get("open_interest") or "Not detected",
        }
        st.dataframe(
            pd.DataFrame(
                list(mapping_display.items()),
                columns=["Standard Field", "Source Column"]
            ),
            hide_index=True,
            use_container_width=True
        )

    if not mapping["close"]:
        st.error("⚠️ Please select a valid Close / Price column in the configuration above.")
        return

    # Check for multiple tickers
    ticker_col = mapping.get("ticker")
    tickers = []
    if ticker_col and ticker_col in uploaded_df.columns:
        tickers = sorted(uploaded_df[ticker_col].dropna().unique().tolist())

    ml_engine = MLEngine()

    # --- Multi-Stock Screener Overview (if dataset contains multiple stocks) ---
    if len(tickers) > 1:
        st.markdown("### 🏆 Multi-Asset Investment Screener")
        st.markdown("AI scan of all assets identified in your uploaded dataset:")
        
        screener_rows = []
        for sym in tickers:
            df_sym = uploaded_df[uploaded_df[ticker_col] == sym].copy()
            if len(df_sym) < 5:
                continue
            stock_data_sym = convert_df_to_stock_data(df_sym, mapping, sym)
            signal_sym = ml_engine.predict(stock_data_sym, skip_api=True)
            
            # Target projection & upside
            target_p = round(stock_data_sym.current_price * (1.0 + (0.05 if signal_sym.action == "BUY" else (-0.05 if signal_sym.action == "SELL" else 0.01))), 2)
            upside_pct = round(((target_p / stock_data_sym.current_price) - 1.0) * 100.0, 2)
            
            # Recommendation label
            if signal_sym.action == "BUY" and signal_sym.confidence >= 80:
                rec = "🚀 STRONG BUY / INVEST"
            elif signal_sym.action == "BUY":
                rec = "🟢 BUY / ACCUMULATE"
            elif signal_sym.action == "SELL":
                rec = "🔴 SELL / EXIT"
            else:
                rec = "🟡 HOLD / NEUTRAL"
                
            screener_rows.append({
                "Asset / Ticker": sym,
                "Current Price": f"₹{stock_data_sym.current_price:.2f}",
                "Change %": f"{stock_data_sym.price_change_pct:+.2f}%",
                "AI Recommendation": rec,
                "Confidence": f"{signal_sym.confidence:.1f}%",
                "Target Price": f"₹{target_p:.2f} ({upside_pct:+.2f}%)",
                "RSI (14)": f"{stock_data_sym.rsi[-1]:.1f}" if stock_data_sym.rsi else "N/A",
                "Trend": "Bullish" if stock_data_sym.current_price > (stock_data_sym.sma_50[-1] if stock_data_sym.sma_50 else stock_data_sym.current_price) else "Bearish"
            })
            
        st.dataframe(pd.DataFrame(screener_rows), use_container_width=True)
        st.markdown("---")

    # Select Active Asset to Deep-Dive
    selected_ticker = "CUSTOM_STOCK"
    if len(tickers) > 1:
        selected_ticker = st.selectbox("🎯 Select Asset for In-Depth Prediction & Backtest:", tickers)
        active_df = uploaded_df[uploaded_df[ticker_col] == selected_ticker].copy()
    else:
        active_df = uploaded_df.copy()
        if ticker_col and ticker_col in uploaded_df.columns:
            first_symbol = uploaded_df[ticker_col].dropna()
            if not first_symbol.empty:
                selected_ticker = str(first_symbol.iloc[0])

    # Convert to StockData object
    try:
        stock_data = convert_df_to_stock_data(active_df, mapping, selected_ticker)
    except ValueError as e:
        st.error(str(e))
        st.info("💡 Please verify your dataset has a valid price/close column and try again.")
        return

    # Run AI Prediction
    with st.spinner(f"🧠 Computing AI Ensemble Prediction for {selected_ticker}..."):
        signal = ml_engine.predict(stock_data, skip_api=True)

    # Calculate investment parameters
    curr_p = stock_data.current_price
    if signal.action == "BUY":
        rec_title = "INVEST / BUY (BULLISH ACCUMULATION)"
        badge_class = "badge-buy"
        badge_icon = "🟢"
        target_price = round(curr_p * (1.0 + max(0.03, (signal.confidence - 50) * 0.003)), 2)
        stop_loss = round(curr_p * 0.94, 2)
        portfolio_alloc = "15% - 25%"
        risk_level = "Low to Moderate"
    elif signal.action == "SELL":
        rec_title = "SELL / TAKE PROFIT (BEARISH DISTRIBUTION)"
        badge_class = "badge-sell"
        badge_icon = "🔴"
        target_price = round(curr_p * (1.0 - max(0.03, (signal.confidence - 50) * 0.003)), 2)
        stop_loss = round(curr_p * 1.05, 2)
        portfolio_alloc = "0% (Exit / Hedge)"
        risk_level = "High"
    else:
        rec_title = "HOLD / CONSOLIDATION (RANGE-BOUND)"
        badge_class = "badge-hold"
        badge_icon = "🟡"
        target_price = round(curr_p * 1.01, 2)
        stop_loss = round(curr_p * 0.96, 2)
        portfolio_alloc = "5% - 10%"
        risk_level = "Moderate"

    upside_downside = ((target_price - curr_p) / curr_p) * 100.0

    # ==========================================
    # 🎯 PRIMARY PREDICTION & INVESTMENT CARD
    # ==========================================
    st.markdown(f"""
        <div class="decision-card">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 15px;">
                <div>
                    <span style="font-size: 13px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px;">AI Investment Verdict for {selected_ticker}</span>
                    <div style="margin-top: 6px;">
                        <span class="{badge_class}">{badge_icon} {signal.action} - {rec_title}</span>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 13px; color: #94a3b8;">Confidence Rating</div>
                    <div style="font-size: 28px; font-weight: 800; color: #38bdf8;">{signal.confidence:.1f}% ({signal.confidence_level})</div>
                </div>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 15px; margin-top: 24px;">
                <div class="stat-badge">
                    <div style="font-size: 12px; color: #94a3b8;">Current Price</div>
                    <div style="font-size: 20px; font-weight: 700; color: #ffffff;">₹{curr_p:.2f}</div>
                    <div style="font-size: 12px; color: {'#00ff7f' if stock_data.price_change_pct >= 0 else '#ff4b4b'};">{stock_data.price_change_pct:+.2f}%</div>
                </div>
                <div class="stat-badge">
                    <div style="font-size: 12px; color: #94a3b8;">Target Price Projection</div>
                    <div style="font-size: 20px; font-weight: 700; color: #38bdf8;">₹{target_price:.2f}</div>
                    <div style="font-size: 12px; color: #38bdf8;">{upside_downside:+.2f}% expected</div>
                </div>
                <div class="stat-badge">
                    <div style="font-size: 12px; color: #94a3b8;">Suggested Stop-Loss</div>
                    <div style="font-size: 20px; font-weight: 700; color: #f43f5e;">₹{stop_loss:.2f}</div>
                    <div style="font-size: 12px; color: #94a3b8;">Capital Protection</div>
                </div>
                <div class="stat-badge">
                    <div style="font-size: 12px; color: #94a3b8;">Suggested Allocation</div>
                    <div style="font-size: 20px; font-weight: 700; color: #f59e0b;">{portfolio_alloc}</div>
                    <div style="font-size: 12px; color: #94a3b8;">Risk: {risk_level}</div>
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Detailed Analysis Tabs
    tab_chart, tab_ai, tab_backtest, tab_data = st.tabs([
        "📊 Interactive Charts", 
        "🧠 AI Rationale & Factors", 
        "🧪 Strategy Simulation", 
        "📋 Data & Export"
    ])

    with tab_chart:
        st.markdown(f"#### 📈 {selected_ticker} - Price Action & Moving Averages")
        render_interactive_stock_chart(stock_data)
        st.markdown("#### 🎯 Momentum & Trend Oscillators")
        render_indicators_charts(stock_data)

    with tab_ai:
        st.markdown("#### 🤖 AI Trading Coach Analysis")
        st.markdown(f"""
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 14px; padding: 20px; margin-bottom: 20px;">
                <div style="font-size: 16px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;">Market Sentiment: {signal.market_mood}</div>
                <div style="font-size: 14px; color: #e2e8f0; line-height: 1.7;">{signal.reasoning}</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 🔑 Key Decision Factors")
        cols_fac = st.columns(min(3, len(signal.key_factors)) if signal.key_factors else 1)
        for i, factor in enumerate(signal.key_factors):
            with cols_fac[i % len(cols_fac)]:
                st.markdown(f"""
                    <div style="background: rgba(255, 255, 255, 0.04); border-left: 3px solid #38bdf8; border-radius: 8px; padding: 12px 14px; margin-bottom: 10px;">
                        <span style="font-size: 13px; color: #f1f5f9;">{factor}</span>
                    </div>
                """, unsafe_allow_html=True)

    with tab_backtest:
        st.markdown("#### 🧪 Backtesting Strategy on Uploaded Data")
        st.caption("Simulating rule-based strategy execution on this dataset vs Buy & Hold benchmark:")
        
        try:
            metrics = BacktestEngine.run_backtest(stock_data)
            
            b_col1, b_col2, b_col3, b_col4 = st.columns(4)
            with b_col1:
                st.metric("Strategy Total Return", f"{metrics.ml_metrics['total_return_pct']:+.2f}%")
            with b_col2:
                st.metric("Market Benchmark Return", f"{metrics.market_metrics['total_return_pct']:+.2f}%")
            with b_col3:
                st.metric("Win Rate", f"{metrics.ml_metrics['win_rate_pct']:.1f}%")
            with b_col4:
                st.metric("Strategy Sharpe", f"{metrics.ml_metrics['sharpe_ratio']:.2f}")

            # Equity Curve Comparison
            fig_eq = go.Figure()
            fig_eq.add_trace(go.Scatter(
                x=metrics.dates, y=metrics.equity_curve,
                name="AI Strategy Equity", line=dict(color="#00ff7f", width=2.5)
            ))
            fig_eq.add_trace(go.Scatter(
                x=metrics.dates, y=metrics.market_equity,
                name="Buy & Hold Benchmark", line=dict(color="#94a3b8", width=1.5, dash="dash")
            ))
            fig_eq.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(15, 23, 42, 0.4)",
                plot_bgcolor="rgba(15, 23, 42, 0.4)",
                height=350,
                margin=dict(l=20, r=20, t=20, b=20),
                legend=dict(orientation="h", y=1.05, x=0.5, xanchor="center")
            )
            st.plotly_chart(fig_eq, use_container_width=True)

        except Exception as e:
            st.warning(f"Could not complete automated backtest on this specific dataset: {e}")

    with tab_data:
        st.markdown("#### 📋 Calculated Dataset with Indicators & Signals")
        
        # Build enriched DataFrame
        df_export = pd.DataFrame({
            "Date": stock_data.dates,
            "Symbol": stock_data.symbol,
            "Open": stock_data.opens,
            "High": stock_data.highs,
            "Low": stock_data.lows,
            "Close": stock_data.closes,
            "Volume": stock_data.volumes,
            "RSI_14": stock_data.rsi,
            "SMA_20": stock_data.sma_20,
            "SMA_50": stock_data.sma_50,
            "MACD": stock_data.macd,
            "MACD_Signal": stock_data.macd_signal,
            "AI_Signal": signal.action,
            "Confidence": round(signal.confidence, 1)
        })
        
        st.dataframe(df_export.tail(100), use_container_width=True)
        
        # Download buttons
        csv_buffer = io.StringIO()
        df_export.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Download Analyzed CSV",
            data=csv_buffer.getvalue(),
            file_name=f"{selected_ticker}_AI_Analysis.csv",
            mime="text/csv",
            type="primary"
        )

if __name__ == "__main__":
    main()




























