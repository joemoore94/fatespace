"""Shared manifest recording for data acquisition scripts.

Every acquisition script appends one ManifestEntry per file it attempts to
obtain -- whether the attempt succeeded, was skipped for being over the size
budget, or failed -- so validation tests and a human reviewer can see exactly
what was pulled, from where, and how big it is, without re-downloading.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "raw" / "manifest.json"


@dataclass
class ManifestEntry:
    source: str  # "hubmap" | "thymus_atlas"
    dataset_id: str  # HuBMAP dataset UUID, or paper/accession identifier
    label: str  # human-readable identifier, e.g. donor age/sex or file role
    relative_path: str  # candidate file path/name requested from the source
    local_path: str | None = None
    status: str = "pending"  # "downloaded" | "not_found" | "over_budget" | "error" | "unconfigured"
    size_bytes: int | None = None
    sha256: str | None = None
    detail: str = ""
    retrieved_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path = MANIFEST_PATH) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text())


def append_manifest(entry: ManifestEntry, path: Path = MANIFEST_PATH) -> None:
    entries = load_manifest(path)
    entries.append(asdict(entry))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2))


def stream_download(url: str, dest_path: Path, budget_bytes: int) -> tuple[str, int | None, str | None, str]:
    """Stream a URL to disk, aborting if it exceeds budget_bytes.

    Returns (status, size_bytes, sha256, detail) where status is one of
    "downloaded" | "not_found" | "over_budget" | "error".
    """
    try:
        with requests.get(url, stream=True, timeout=60) as resp:
            if resp.status_code == 404:
                return "not_found", None, None, f"404 at {url}"
            resp.raise_for_status()

            content_length = resp.headers.get("Content-Length")
            if content_length and int(content_length) > budget_bytes:
                return "over_budget", int(content_length), None, (
                    f"Content-Length {content_length} exceeds budget {budget_bytes}"
                )

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            with open(dest_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1 << 20):
                    written += len(chunk)
                    if written > budget_bytes:
                        f.close()
                        dest_path.unlink(missing_ok=True)
                        return "over_budget", written, None, f"aborted mid-stream past budget {budget_bytes}"
                    f.write(chunk)

            return "downloaded", written, sha256_of(dest_path), ""
    except requests.RequestException as e:
        return "error", None, None, str(e)
