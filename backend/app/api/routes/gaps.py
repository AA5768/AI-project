from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["gaps"])


class GapStatusUpdate(BaseModel):
    status: str


@router.get("/gaps")
def list_gaps(status: str | None = None):
    raise NotImplementedError


@router.patch("/gaps/{gap_id}")
def update_gap(gap_id: int, update: GapStatusUpdate):
    raise NotImplementedError
