from pathlib import Path

from pydantic_settings import BaseSettings

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    db_path: Path = PROJECT_ROOT / "backend" / "app.db"
    data_dir: Path = PROJECT_ROOT / "data"
    embedding_model: str = "all-MiniLM-L6-v2"
    confidence_threshold: float = 0.55

    model_config = {"env_file": PROJECT_ROOT / ".env", "extra": "ignore"}


settings = Settings()
