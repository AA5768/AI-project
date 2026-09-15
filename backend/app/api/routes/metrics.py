from fastapi import APIRouter

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def get_metrics():
    raise NotImplementedError
