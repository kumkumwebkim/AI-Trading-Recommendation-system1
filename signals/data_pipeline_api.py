from fastapi import FastAPI, HTTPException
from datetime import datetime
import traceback

from data_pipeline import run_pipeline

app = FastAPI(title="Market Data Pipeline API")

@app.post("/run-pipeline")
def run_data_pipeline():
    """
    Blocking call:
    API returns ONLY after the dataset is fully updated.
    """
    try:
        start_time = datetime.utcnow()

        # 🔒 BLOCKING EXECUTION
        run_pipeline()

        end_time = datetime.utcnow()

        return {
            "status": "completed",
            "started_at": start_time.isoformat(),
            "completed_at": end_time.isoformat()
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "failed",
                "error": str(e),
                "trace": traceback.format_exc()
            }
        )


@app.get("/health")
def health():
    return {"status": "ok"}
