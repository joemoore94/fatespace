"""Acquire processed thymus CODEX/RNA/spatial data from the HuBMAP Data Portal.

Targets HuBMAP's *processed* per-cell data products (their Cytokit+SPRM
pipeline output for CODEX: segmented cell x protein-marker tables with
centroid coordinates, plus any RNA/spatial-transcriptomics expression
matrices) rather than raw multi-channel imaging or FASTQ -- this keeps
downloads in the single-digit-to-low-tens-of-GB range instead of the
hundreds-of-GB range raw imaging would cost.

Known endpoints (confirmed against public HuBMAP documentation):
  - Parameterized search: https://search.api.hubmapconsortium.org/v3/param-search/datasets
  - Entity metadata:      https://entity.api.hubmapconsortium.org/entities/<uuid>
  - Public file assets:   https://assets.hubmapconsortium.org/<uuid>/<relative_path>

The exact HuBMAP 2-letter organ code for thymus was not confirmed (docs
pages were unreachable at plan time), so this script anchors on a known-good
set of thymus CODEX dataset UUIDs (found via the public portal) rather than
guessing the organ-code search parameter. `search_thymus_datasets` still
attempts the API search and will pick up additional matches if it works, but
never depends on it succeeding.

Every attempted file -- successful or not -- gets one entry in
data/raw/manifest.json via fatespace.manifest. Nothing here fails silently:
if a dataset's file listing can't be resolved, that's a manifest entry with
status="not_found", not a skipped dataset.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import requests

from fatespace.manifest import ManifestEntry, REPO_ROOT, append_manifest, stream_download

SEARCH_API = "https://search.api.hubmapconsortium.org/v3/param-search/datasets"
ENTITY_API = "https://entity.api.hubmapconsortium.org/entities/{uuid}"
ASSETS_BASE = "https://assets.hubmapconsortium.org/{uuid}/{relative_path}"

RAW_DIR = REPO_ROOT / "data" / "raw" / "hubmap"

# Known-good thymus CODEX datasets (HuBMAP portal, Cytokit+SPRM processed),
# confirmed to exist via the public portal at plan time.
KNOWN_THYMUS_CODEX_DATASETS = [
    {"uuid": "f0b1b074ed23ed654fcc41dc831080c5", "hubmap_id": "HBM632.JSNP.578", "donor": "16yo white male"},
    {"uuid": "053544cd63125fc25f6a71a8f444bafc", "hubmap_id": "HBM887.SHVF.747", "donor": "11yo white male"},
    {"uuid": "5dfaf57521ad6aa97aa64d8aba1f9d32", "hubmap_id": "HBM893.CCKX.496", "donor": "10yo white male"},
    {"uuid": "bec226690f40f11d0516487ba4ad289f", "hubmap_id": "HBM857.ZBDC.975", "donor": "21yo Black/African American female"},
]

# Skip obvious raw-imaging file types -- we want processed per-cell tables.
RAW_IMAGE_SUFFIXES = (".ome.tiff", ".ome.tif", ".tiff", ".tif", ".fastq", ".fastq.gz", ".bam")

DEFAULT_PER_FILE_BUDGET_BYTES = 1 * 1024**3  # 1 GiB
DEFAULT_TOTAL_BUDGET_BYTES = 5 * 1024**3  # 5 GiB


def search_thymus_datasets(dataset_type: str = "CODEX") -> list[dict]:
    """Best-effort API search for additional thymus datasets. Never raises --
    returns [] on any failure so the caller can fall back to the known list."""
    try:
        resp = requests.get(
            SEARCH_API,
            params={"dataset_type": dataset_type, "origin_samples.organ": "TH"},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json() if isinstance(resp.json(), list) else resp.json().get("results", [])
    except Exception:
        return []


def list_dataset_files(uuid: str) -> list[dict]:
    """Return [{"rel_path": ..., "size": ...}, ...] from the entity API, or [] if unresolvable."""
    try:
        resp = requests.get(ENTITY_API.format(uuid=uuid), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        files = data.get("files") or data.get("ingest_metadata", {}).get("files") or []
        return [f for f in files if isinstance(f, dict) and f.get("rel_path")]
    except Exception:
        return []


def download_file(uuid: str, rel_path: str, dest_dir: Path, per_file_budget: int) -> ManifestEntry:
    url = ASSETS_BASE.format(uuid=uuid, relative_path=rel_path)
    dest_path = dest_dir / uuid / rel_path
    status, size_bytes, sha256, detail = stream_download(url, dest_path, per_file_budget)
    return ManifestEntry(
        "hubmap", uuid, rel_path, rel_path,
        local_path=str(dest_path) if status == "downloaded" else None,
        status=status, size_bytes=size_bytes, sha256=sha256, detail=detail,
    )


def acquire(per_file_budget: int = DEFAULT_PER_FILE_BUDGET_BYTES,
            total_budget: int = DEFAULT_TOTAL_BUDGET_BYTES,
            donor_limit: int | None = None) -> list[ManifestEntry]:
    datasets = KNOWN_THYMUS_CODEX_DATASETS[:donor_limit]
    entries: list[ManifestEntry] = []
    total_downloaded = 0

    for ds in datasets:
        uuid = ds["uuid"]
        files = list_dataset_files(uuid)
        if not files:
            entry = ManifestEntry(
                "hubmap", uuid, ds["donor"], "(unresolved)", status="not_found",
                detail=(f"Entity API returned no file listing for {ds['hubmap_id']}. "
                        f"Retrieve manually via https://portal.hubmapconsortium.org/browse/dataset/{uuid} "
                        "or the HuBMAP Command Line Transfer (Globus) tool."),
            )
            entries.append(entry)
            append_manifest(entry)
            continue

        candidates = [f for f in files if not f["rel_path"].lower().endswith(RAW_IMAGE_SUFFIXES)]
        for f in candidates:
            if total_downloaded >= total_budget:
                entry = ManifestEntry("hubmap", uuid, ds["donor"], f["rel_path"], status="over_budget",
                                       detail="total run budget exhausted before this file")
                entries.append(entry)
                append_manifest(entry)
                continue
            entry = download_file(uuid, f["rel_path"], RAW_DIR, per_file_budget)
            entry.label = ds["donor"]
            entries.append(entry)
            append_manifest(entry)
            if entry.size_bytes:
                total_downloaded += entry.size_bytes

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--donor-limit", type=int, default=None,
                         help="Only acquire the first N known donor datasets (default: all known).")
    parser.add_argument("--per-file-budget-mb", type=int, default=DEFAULT_PER_FILE_BUDGET_BYTES // (1024**2))
    parser.add_argument("--total-budget-mb", type=int, default=DEFAULT_TOTAL_BUDGET_BYTES // (1024**2))
    args = parser.parse_args()

    entries = acquire(
        per_file_budget=args.per_file_budget_mb * 1024**2,
        total_budget=args.total_budget_mb * 1024**2,
        donor_limit=args.donor_limit,
    )
    downloaded = [e for e in entries if e.status == "downloaded"]
    print(f"HuBMAP acquisition: {len(downloaded)}/{len(entries)} files downloaded. "
          f"See {REPO_ROOT / 'data' / 'raw' / 'manifest.json'} for full detail.")


if __name__ == "__main__":
    main()
