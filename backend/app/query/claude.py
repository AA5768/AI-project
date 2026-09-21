"""One Anthropic client for the query path.

Cached because the API process answers many queries per process lifetime and
each construction rebuilds an httpx client (and, behind the corporate proxy, a
fresh TLS context). Kept separate from enrichment, which runs as a batch job in
its own process.
"""

from functools import lru_cache

from app.config import settings


@lru_cache(maxsize=1)
def get_client():
    import anthropic

    return anthropic.Anthropic(api_key=settings.anthropic_api_key)
