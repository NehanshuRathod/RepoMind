from fastapi import APIRouter

from app.core.metrics import metrics


router = APIRouter(prefix="/metrics", tags=["Metrics"])


@router.get("")
def get_metrics():
    return metrics.snapshot()
