from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import corrections, documents, gaps, metrics, query, routing
from app.config import settings

# Any localhost port, unless an explicit allowlist is configured. The dev server
# does not own a fixed port -- Vite silently moves to 5174 when 5173 is taken --
# and pinning one origin makes that look like the API is down. No credentials
# are accepted (allow_credentials stays off), so a permissive local origin grants
# a page nothing it could not get by calling the API directly.
LOCALHOST_ORIGIN_RE = r"http://(localhost|127\.0\.0\.1)(:\d+)?"

app = FastAPI(title="Meridian Microsystems Knowledge API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=None if settings.cors_origins else LOCALHOST_ORIGIN_RE,
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
