from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["documents"])


@router.get("/documents/{document_id}")
def get_document(document_id: int):
    raise HTTPException(status_code=501, detail="not implemented")
