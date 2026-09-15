from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import corrections, documents, gaps, metrics, query, routing

app = FastAPI(title="Meridian Robotics Knowledge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router)
app.include_router(documents.router)
app.include_router(corrections.router)
app.include_router(gaps.router)
app.include_router(metrics.router)
app.include_router(routing.router)


@app.get("/health")
def health():
    return {"status": "ok"}
