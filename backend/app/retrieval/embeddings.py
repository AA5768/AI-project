"""Local sentence-transformers embeddings -- offline, no API key.

Vectors are normalised at encode time, so cosine similarity is a plain dot
product and sqlite-vec's L2 distance is a monotone function of it. Retrieval can
therefore rank on distance without renormalising per query.
"""

import struct
from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_model():
    # Imported lazily: loading torch costs ~3s, and the API process should not
    # pay that unless something actually embeds.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


def embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    if not texts:
        return []
    vectors = get_model().encode(
        texts,
        normalize_embeddings=True,
        batch_size=batch_size,
        show_progress_bar=False,
    )
    return [v.tolist() for v in vectors]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]


def serialize(vector: list[float]) -> bytes:
    """float32 little-endian -- the layout sqlite-vec expects for a FLOAT[N] column."""
    return struct.pack(f"<{len(vector)}f", *vector)


def deserialize(blob: bytes) -> list[float]:
    return list(struct.unpack(f"<{len(blob) // 4}f", blob))
