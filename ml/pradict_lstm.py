import pandas as pd
import numpy as np
import joblib
from tensorflow.keras.models import load_model
import ta
from .input_api import get_indicators
from pathlib import Path

# Config
MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "lstm_stock_model.h5"
SCALER_PATH = MODEL_DIR / "scaler.pkl"
FEATURES_PATH = MODEL_DIR / "feature_cols.pkl"
LABEL_ENCODER_PATH = MODEL_DIR / "label_encoder.pkl"

SEQUENCE_LENGTH = 20
CONFIDENCE_THRESHOLD = 0.60

# Lazy-loaded artifacts
_model = None
_scaler = None
_feature_cols = None
_label_encoder = None

label_map = {0: "SELL", 1: "HOLD", 2: "BUY"}


def _ensure_models_loaded():
    """Lazily load model artifacts on first use."""
    global _model, _scaler, _feature_cols, _label_encoder
    if _model is None:
        try:
            _model = load_model(MODEL_PATH)
        except FileNotFoundError:
            raise FileNotFoundError(f"LSTM model not found at {MODEL_PATH}")
    if _scaler is None:
        try:
            _scaler = joblib.load(SCALER_PATH)
        except FileNotFoundError:
            raise FileNotFoundError(f"Scaler not found at {SCALER_PATH}")
    if _feature_cols is None:
        try:
            _feature_cols = joblib.load(FEATURES_PATH)
        except FileNotFoundError:
            raise FileNotFoundError(f"Feature columns not found at {FEATURES_PATH}")
    if _label_encoder is None:
        if LABEL_ENCODER_PATH.exists():
            try:
                _label_encoder = joblib.load(LABEL_ENCODER_PATH)
            except Exception:
                _label_encoder = None
        
        if _label_encoder is None:
            # Fallback to parquet
            parquet_path = Path(__file__).resolve().parents[1] / "signals" / "data" / "ticker_encoder.parquet"
            if parquet_path.exists():
                try:
                    df_enc = pd.read_parquet(parquet_path)
                    from sklearn.preprocessing import LabelEncoder
                    le = LabelEncoder()
                    le.classes_ = df_enc["ticker"].values
                    _label_encoder = le
                    try:
                        joblib.dump(le, LABEL_ENCODER_PATH)
                    except Exception:
                        pass
                except Exception:
                    pass


def get_model():
    global _model
    _ensure_models_loaded()
    return _model


def get_scaler():
    global _scaler
    _ensure_models_loaded()
    return _scaler


def get_feature_cols():
    global _feature_cols
    _ensure_models_loaded()
    return _feature_cols


def get_label_encoder():
    global _label_encoder
    _ensure_models_loaded()
    return _label_encoder


# Fetch data from API
def fetch_from_api(ticker: str) -> pd.DataFrame:
    """Fetch historical data directly using yfinance"""
    try:
        import yfinance as yf
        
        # Fetch last 100 days to have enough data after calculating indicators
        df = yf.download(
            ticker,
            period="6mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            timeout=30
        )
        
        if df.empty or len(df) < 51:
            raise ValueError("Not enough historical data")
        
        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.columns = [c.lower() for c in df.columns]
        
        return df.tail(100)
    except KeyboardInterrupt:
        raise Exception("Download was cancelled")
    except Exception as e:
        raise Exception(f"Failed to fetch stock data: {e}")

# Prepare features (MATCH TRAINING)
def prepare_sequence(df: pd.DataFrame, ticker: str):
    df = df.sort_values("date").reset_index(drop=True).copy()

    # Add ticker_id using label encoder
    ticker_id = 0
    try:
        le = get_label_encoder()
        if le is not None and hasattr(le, 'classes_') and ticker in le.classes_:
            ticker_id = int(np.where(le.classes_ == ticker)[0][0])
    except Exception:
        ticker_id = 0
    df["ticker_id"] = ticker_id

    # Calculate daily return
    df["daily_return"] = df["close"].pct_change(fill_method=None)
    df["volume_change"] = df["volume"].pct_change(fill_method=None)

    # Technical indicators (same as training)
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

    # Lag features (same as training)
    for lag in [1, 2, 3, 5]:
        df[f"close_lag_{lag}"] = df["close"].shift(lag)
        df[f"return_lag_{lag}"] = df["close"].pct_change(lag)

    # Forward fill then backward fill NaN values
    df = df.ffill().bfill()
    df = df.dropna().reset_index(drop=True)

    if len(df) < SEQUENCE_LENGTH:
        raise ValueError(f"Not enough rows for LSTM sequence: {len(df)} < {SEQUENCE_LENGTH}")

    X = df.tail(SEQUENCE_LENGTH)[get_feature_cols()].copy()
    
    # Replace any remaining NaN or infinity
    X = X.fillna(0)
    X = X.replace([np.inf, -np.inf], 0)
    
    X = get_scaler().transform(X)
    return np.expand_dims(X, axis=0)

# Predict
def predict_stock(ticker: str):
    """
    Predict stock signal using LSTM model.
    Returns prediction result with signal, confidence, and probabilities.
    """
    df = fetch_from_api(ticker)
    X = prepare_sequence(df, ticker)

    probs = get_model().predict(X, verbose=0)[0]
    confidence = probs.max()
    label = probs.argmax()

    signal = label_map[label] if confidence >= CONFIDENCE_THRESHOLD else "HOLD"

    result = {
        "ticker": ticker,
        "signal": signal,
        "confidence": round(confidence * 100, 2),
        "probabilities": {
            "SELL": round(probs[0] * 100, 2),
            "HOLD": round(probs[1] * 100, 2),
            "BUY": round(probs[2] * 100, 2),
        }
    }
    
    return result


def get_prediction_with_indicators(ticker: str) -> dict:
    """
    Get prediction along with current indicators from input_api.
    Returns both the LSTM prediction and live indicators.
    """
    try:
        indicators = get_indicators(ticker)
        prediction = predict_stock(ticker)
        
        return {
            "prediction": prediction,
            "indicators": indicators
        }
    except Exception as e:
        return {
            "error": str(e)
        }
