from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    text: str


class Citation(BaseModel):
    source_path: str
    author_or_attendees: list[str]
    anchor: str


class Routing(BaseModel):
    person: str
    rationale: str
    matched_content: str
    draft_question: str


class QueryResponse(BaseModel):
    query_id: int
    answer: str | None = None
    confidence: float
    citations: list[Citation] = []
    derived_metadata: dict = {}
    routing: Routing | None = None


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    raise NotImplementedError
