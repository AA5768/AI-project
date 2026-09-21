from pathlib import Path

from pydantic_settings import BaseSettings

# Corporate TLS interception (Teradyne proxy) re-signs HTTPS with a root CA that is
# in the Windows cert store but not in certifi's bundle, so HuggingFace model
# downloads die with CERTIFICATE_VERIFY_FAILED. truststore delegates verification to
# the OS store instead. Harmless on machines without an intercepting proxy.
try:
    import truststore

    truststore.inject_into_ssl()
except Exception:  # pragma: no cover - best effort, never block startup
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    anthropic_api_key: str = ""

    db_path: Path = PROJECT_ROOT / "backend" / "app.db"
    data_dir: Path = PROJECT_ROOT / "data"

    # Retrieval
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384
    chunk_target_chars: int = 900
    chunk_max_chars: int = 1600

    # LLM: Haiku for batch enrichment, Sonnet for query-time synthesis (Part 2).
    enrichment_model: str = "claude-haiku-4-5"
    synthesis_model: str = "claude-sonnet-5"

    confidence_threshold: float = 0.55

    # Browser origins allowed to call the API, comma-separated. Empty (the
    # default) means any localhost port, which is what a dev machine needs:
    # Vite moves to 5174+ whenever 5173 is taken, and a pinned single origin
    # turns that into "Cannot reach the API" with no clue why. Set this to an
    # explicit list before putting the API anywhere but a laptop.
    cors_allow_origins: str = ""

    model_config = {"env_file": PROJECT_ROOT / ".env", "extra": "ignore"}

    @property
    def has_api_key(self) -> bool:
        return bool(self.anthropic_api_key.strip())

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


settings = Settings()
