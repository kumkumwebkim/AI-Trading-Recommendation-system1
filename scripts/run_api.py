import uvicorn
import pandas as pd
import numpy as np
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from ml.predictor import MLEngine
from contracts.schema import StockData

app = FastAPI(title="ML Signal Service", version="2.0")

# -------------------------------------------------
# DATA PROVIDER HELPER (for Supabase emulation)
# -------------------------------------------------
def fetch_real_market_data(ticker: str, period: str = "1mo", interval: str = "1d"):
    """Fetch real data using yfinance for Supabase emulation"""
    try:
        df = yf.download(ticker, period=period, interval=interval, progress=False, auto_adjust=True)
        if df.empty:
            return []
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df.reset_index(inplace=True)
        data = []
        for _, row in df.iterrows():
            record = {
                "ticker": ticker.upper(),
                "date": row["Date"].strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"])
            }
            data.append(record)
        return data
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
        return []


# -------------------------------------------------
# REQUEST SCHEMA
# -------------------------------------------------
class SignalRequest(BaseModel):
    ticker: str

# -------------------------------------------------
# DATA PROCESSING HELPER
# -------------------------------------------------
def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators required for StockData"""
    df = df.copy()
    close = df['Close']
    
    # RSI
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # SMA
    df['sma_20'] = close.rolling(window=20).mean()
    df['sma_50'] = close.rolling(window=50).mean()
    
    # EMA
    df['ema_12'] = close.ewm(span=12, adjust=False).mean()
    df['ema_26'] = close.ewm(span=26, adjust=False).mean()
    
    # MACD
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    return df

def fetch_stock_data(ticker: str) -> StockData:
    """Fetch data from yfinance and convert to StockData format"""
    # Fetch enough data for indicators (at least 60 days)
    df = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True)
    
    if df.empty:
        raise ValueError(f"No data found for {ticker}")
    
    # Flatten MultiIndex if present (yfinance update)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
        
    # Calculate indicators
    df = calculate_indicators(df)
    
    # Handle NaN values (fill with 0 or forward fill)
    df.ffill(inplace=True)
    df.fillna(0, inplace=True) # For initial NaNs
    
    # Get latest data point
    latest = df.iloc[-1]
    
    # Create lists for series data (taking last 100 points to keep payload manageable)
    subset = df.tail(100)
    dates = subset.index.strftime('%Y-%m-%d').tolist()
    
    return StockData(
        symbol=ticker,
        current_price=float(latest['Close']),
        price_change=float(latest['Close'] - df.iloc[-2]['Close']) if len(df) > 1 else 0.0,
        price_change_pct=float((latest['Close'] - df.iloc[-2]['Close']) / df.iloc[-2]['Close'] * 100) if len(df) > 1 else 0.0,
        last_updated=datetime.now(),
        market_status="Open", # Simplified
        
        # Time Series
        dates=dates,
        opens=subset['Open'].tolist(),
        highs=subset['High'].tolist(),
        lows=subset['Low'].tolist(),
        closes=subset['Close'].tolist(),
        volumes=subset['Volume'].tolist(),
        
        # Indicators
        rsi=subset['rsi'].tolist(),
        sma_20=subset['sma_20'].tolist(),
        sma_50=subset['sma_50'].tolist(),
        ema_12=subset['ema_12'].tolist(),
        ema_26=subset['ema_26'].tolist(),
        macd=subset['macd'].tolist(),
        macd_signal=subset['macd_signal'].tolist(),
        macd_hist=subset['macd_hist'].tolist()
    )

# -------------------------------------------------
# LIVE SIGNAL ENDPOINT
# -------------------------------------------------
@app.post("/api/v1/ml/signal/live")
def get_live_signal(request: SignalRequest):
    try:
        ticker = request.ticker.upper()
        print(f"📡 Received signal request for {ticker}")

        # 1. Get Market Data in StockData format
        stock_data = fetch_stock_data(ticker)
        
        # 2. Run ML Engine (Local Prediction with News)
        engine = MLEngine()
        # IMPORTANT: skip_api=True to prevent recursion loop
        # Pass empty news list to trigger internal RSS fetching in MLEngine
        prediction = engine.predict(stock_data, skip_api=True, news=[])
        
        if not prediction:
            raise HTTPException(status_code=500, detail="Failed to generate prediction")

        # 3. Return result
        # The API in signals/api.py returns a dictionary. MLEngine returns MLSignal object.
        # We should return a dictionary that matches what the dashboard expects.
        # However, run_api.py uses MLEngine which produces MLSignal.
        # Let's verify what the Dashboard expects. 
        # If dashboard uses the same `MLEngine.predict`... wait.
        
        # Dashboard (pages/1_AI_Signals.py) likely calls THIS API.
        # If it calls this API, it expects the JSON response.
        # contracts.schema.MLSignal has fields. I can just return prediction.dict()
        
        return prediction.dict()

    except Exception as e:
        print(f"❌ ML SIGNAL ERROR: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# -------------------------------------------------
# SUPABASE EMULATION ENDPOINTS
# -------------------------------------------------

@app.get("/supabase/recent/{ticker}")
def get_recent_data(ticker: str, days: int = Query(30, description="Number of days")):
    """Get recent stock data for a ticker with REAL data"""
    try:
        data = fetch_real_market_data(ticker, period=f"{days+10}d")
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        filtered_data = [d for d in data if d["date"] >= cutoff_date]
        filtered_data.sort(key=lambda x: x["date"], reverse=True)
        return {
            "ticker": ticker.upper(),
            "days": days,
            "count": len(filtered_data),
            "data": filtered_data
        }
    except Exception as e:
        return {"data": [], "error": str(e)}

@app.get("/supabase/ticker/{ticker}")
def get_ticker_data(
    ticker: str,
    start_date: str = Query("2024-01-01", description="Start date (YYYY-MM-DD)"),
    limit: int = Query(100, description="Max records")
):
    """Get ticker data with date range and limit"""
    try:
        data = fetch_real_market_data(ticker, period="2y")
        filtered_data = [d for d in data if d["date"] >= start_date]
        filtered_data.sort(key=lambda x: x["date"], reverse=True)
        return {
            "ticker": ticker.upper(),
            "start_date": start_date,
            "limit": limit,
            "count": min(len(filtered_data), limit),
            "data": filtered_data[:limit]
        }
    except Exception as e:
        return {"data": [], "error": str(e)}

@app.get("/supabase/latest")
def get_latest_market(limit: int = Query(10, description="Number of latest records")):
    """Get latest market data for top accessible tickers"""
    TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "SPY"]
    market_data = []
    try:
        for t in TICKERS[:limit]:
            d = fetch_real_market_data(t, period="5d")
            if d:
                latest = d[-1]
                latest["ticker"] = t
                market_data.append(latest)
        return {
            "limit": limit,
            "data": market_data,
            "count": len(market_data)
        }
    except Exception as e:
        return {"data": [], "error": str(e)}

@app.get("/supabase/top-performers")
def get_top_performers(top_n: int = Query(10, description="Top N performers")):
    """Get top performing stocks (Simulation)"""
    TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]
    performers = []
    try:
        for t in TICKERS:
            d = fetch_real_market_data(t, period="5d")
            if len(d) >= 2:
                change = (d[-1]["close"] - d[-2]["close"]) / d[-2]["close"] * 100
                performers.append({
                    "ticker": t,
                    "price": d[-1]["close"],
                    "change_pct": change
                })
        performers.sort(key=lambda x: x["change_pct"], reverse=True)
        return {
            "top_n": top_n,
            "data": performers[:top_n]
        }
    except Exception as e:
        return {"data": [], "error": str(e)}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)