"""Convert acquired thymus atlas Seurat RDS files to processed AnnData/.h5ad.

Reads data/raw/manifest.json for downloaded thymus_atlas .rds files and
converts each to a .h5ad via `readseurat` (pure Python, no R needed -- see
the `convert` extra in pyproject.toml). Writes one entry per file to
data/processed/manifest.json, mirroring the raw-data manifest convention in
fatespace.manifest.

Disk on this box has run within ~1GB of full mid-install before, so each
conversion checks free space against the source file size first and refuses
to start (recording an "over_budget" entry) rather than risking a filled disk.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import readseurat

from fatespace.manifest import (
    MANIFEST_PATH as RAW_MANIFEST_PATH,
    ManifestEntry,
    REPO_ROOT,
    append_manifest,
    load_manifest,
    sha256_of,
)

PROCESSED_DIR = REPO_ROOT / "data" / "processed" / "thymus_atlas"
PROCESSED_MANIFEST_PATH = REPO_ROOT / "data" / "processed" / "manifest.json"

# Required free space, as a multiple of the source file's size, before a
# conversion is attempted.
DISK_HEADROOM_MULTIPLIER = 1.5


def _source_entries() -> list[dict]:
    entries = load_manifest(RAW_MANIFEST_PATH)
    return [
        e for e in entries
        if e["source"] == "thymus_atlas"
        and e["status"] == "downloaded"
        and e["local_path"]
        and e["local_path"].lower().endswith(".rds")
    ]


def convert_one(local_path: str, label: str) -> ManifestEntry:
    src = Path(local_path)
    dest = PROCESSED_DIR / f"{label}.h5ad"

    free_bytes = shutil.disk_usage(REPO_ROOT).free
    required_bytes = int(src.stat().st_size * DISK_HEADROOM_MULTIPLIER)
    if free_bytes < required_bytes:
        entry = ManifestEntry(
            source="thymus_atlas_processed", dataset_id=str(src), label=label,
            relative_path=str(dest.relative_to(REPO_ROOT)), status="over_budget",
            detail=(
                f"only {free_bytes / 1e9:.2f} GB free, want >= {required_bytes / 1e9:.2f} GB "
                f"({DISK_HEADROOM_MULTIPLIER}x source size {src.stat().st_size / 1e9:.2f} GB) "
                "before converting -- refusing to start"
            ),
        )
        append_manifest(entry, PROCESSED_MANIFEST_PATH)
        return entry

    try:
        adata = readseurat.read_seurat(str(src))
    except Exception as e:
        entry = ManifestEntry(
            source="thymus_atlas_processed", dataset_id=str(src), label=label,
            relative_path=str(dest.relative_to(REPO_ROOT)), status="error",
            detail=f"readseurat.read_seurat failed: {e!r}",
        )
        append_manifest(entry, PROCESSED_MANIFEST_PATH)
        return entry

    dest.parent.mkdir(parents=True, exist_ok=True)
    adata.write_h5ad(dest)

    entry = ManifestEntry(
        source="thymus_atlas_processed", dataset_id=str(src), label=label,
        relative_path=str(dest.relative_to(REPO_ROOT)), local_path=str(dest),
        status="converted", size_bytes=dest.stat().st_size, sha256=sha256_of(dest),
        detail=f"shape={adata.shape}, obs_columns={list(adata.obs.columns)}",
    )
    append_manifest(entry, PROCESSED_MANIFEST_PATH)
    print(f"{label}: shape={adata.shape}")
    print(f"{label}: obs columns={list(adata.obs.columns)}")
    return entry


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label", action="append", dest="labels", default=None,
        help="Only convert files whose manifest label matches (repeatable). Default: all downloaded thymus_atlas .rds files.",
    )
    args = parser.parse_args()

    sources = _source_entries()
    if args.labels:
        sources = [e for e in sources if e["label"] in args.labels]

    if not sources:
        print("convert_thymus_atlas: no matching downloaded thymus_atlas .rds files found in data/raw/manifest.json.")
        sys.exit(1)

    entries = [convert_one(e["local_path"], e["label"]) for e in sources]
    converted = [e for e in entries if e.status == "converted"]
    print(f"Thymus atlas conversion: {len(converted)}/{len(entries)} files converted.")


if __name__ == "__main__":
    main()
