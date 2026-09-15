from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["corrections"])


class CorrectionRequest(BaseModel):
    query_id: int
    corrected_answer: str
    corrected_by: str


@router.post("/corrections")
def create_correction(request: CorrectionRequest):
    raise NotImplementedError


@router.get("/corrections")
def list_corrections(status: str | None = None):
    raise NotImplementedError
