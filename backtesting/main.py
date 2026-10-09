import sys
from pathlib import Path
# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from fastapi import FastAPI
from pydantic import BaseModel
from app.data_loader import load_historical_data
from app.engine import BacktestEngine
import uvicorn

app = FastAPI(title="Backtesting Service")

# -------------------------------------------------
# REQUEST SCHEMA
# -------------------------------------------------
class BacktestRequest(BaseModel):
    ticker: str


# -------------------------------------------------
# RUN BACKTEST
# -------------------------------------------------
@app.post("/api/v1/backtest/run")
def run_backtest(request: BacktestRequest):
    try:
        ticker = request.ticker.upper()

        df = load_historical_data(ticker=ticker)

        engine = BacktestEngine(df)

        market = engine.run_market()
        ml = engine.run_ml()

        confidence = engine.calculate_confidence(
            ml_metrics=ml["ml_metrics"],
            market_metrics=market["metrics"]
        )

        # Build graphs inline (BacktestEngine has no build_graphs;
        # see BacktestEngineVBT.build_graphs / run_backtest wrapper)
        import numpy as np
        market_equity = market["equity"]
        ml_equity = ml["equity"]
        equity_curve = [
            {
                "date": str(d),
                "market": float(market_equity.iloc[i] / market_equity.iloc[0]),
                "ml": float(ml_equity.iloc[i] / ml_equity.iloc[0]),
            }
            for i, d in enumerate(market_equity.index)
        ]
        trades_df = ml["trades"]
        pnl_graph = []
        if not trades_df.empty:
            for _, row in trades_df.iterrows():
                pnl_graph.append({
                    "entry_date": str(row["Entry Timestamp"]),
                    "exit_date": str(row["Exit Timestamp"]),
                    "entry_price": float(row["Avg Entry Price"]),
                    "exit_price": float(row["Avg Exit Price"]),
                    "pnl": float(row["PnL"]),
                    "return_pct": float(row["Return"] * 100),
                    "direction": str(row["Direction"]),
                    "is_profit": bool(row["PnL"] > 0),
                })
        trade_visual = {
            "dates": df.index.astype(str).tolist(),
            "close": df["Close"].tolist(),
            "buy_dates": df.index[df["Signal"] == 1].astype(str).tolist(),
            "sell_dates": df.index[df["Signal"] == -1].astype(str).tolist(),
        }

        # JSON-safe: convert numpy types
        def _py(v):
            if hasattr(v, "item"):
                try:
                    return v.item()
                except Exception:
                    return float(v)
            if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                return 0.0
            return v

        def _clean(obj):
            if isinstance(obj, dict):
                return {k: _clean(val) for k, val in obj.items()}
            if isinstance(obj, list):
                return [_clean(v) for v in obj]
            return _py(obj)

        return {
            "confidence_score": _py(confidence),
            "ml_metrics": _clean(ml["ml_metrics"]),
            "market_metrics": _clean(market["metrics"]),
            "trading_metrics": _clean(ml["trading_metrics"]),
            "equity_curve": equity_curve,
            "pnl_graph": pnl_graph,
            "trade_visualization": trade_visual
        }


    except ValueError as e:
        # Expected data validation error
        print(f"⚠️ Validation Error: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print("❌ BACKTEST ERROR:", e)
        # Re-raise or generic 500
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)