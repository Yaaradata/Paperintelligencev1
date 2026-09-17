"""Replayable raw-response cache: deterministic hash → timestamped JSON.gz on disk."""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paper_intelligence.common.config import RAW_CACHE_DIR


def request_hash(provider: str, endpoint: str, payload: Any) -> str:
    blob = json.dumps(
        {"provider": provider, "endpoint": endpoint, "payload": payload},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _provider_dir(provider: str, when: datetime) -> Path:
    return RAW_CACHE_DIR / provider / f"{when:%Y}" / f"{when:%m}" / f"{when:%d}"


def find_cached(provider: str, req_hash: str) -> Path | None:
    base = RAW_CACHE_DIR / provider
    if not base.exists():
        return None
    matches = sorted(base.rglob(f"*_{req_hash}_*.json.gz"))
    return matches[-1] if matches else None


def read_cached(path: Path) -> Any:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def write_raw(provider: str, req_hash: str, entity: str, payload: Any) -> tuple[str, str]:
    """Persist a raw response. Returns (path, sha256)."""
    now = datetime.now(timezone.utc)
    directory = _provider_dir(provider, now)
    directory.mkdir(parents=True, exist_ok=True)
    safe_entity = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(entity))[:60]
    path = directory / f"{now:%Y%m%dT%H%M%SZ}_{req_hash}_{safe_entity}.json.gz"
    body = json.dumps(payload, default=str).encode("utf-8")
    with gzip.open(path, "wb") as fh:
        fh.write(body)
    return str(path), hashlib.sha256(body).hexdigest()
