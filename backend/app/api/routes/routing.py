from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["routing"])


class RoutingSendRequest(BaseModel):
    query_id: int
    person: str
    question: str


@router.post("/routing/send")
def send_routing(request: RoutingSendRequest):
    print(f"[routing:send] to={request.person} query_id={request.query_id} question={request.question!r}")
    return {"status": "sent"}
