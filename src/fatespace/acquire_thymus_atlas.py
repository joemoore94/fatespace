"""Acquire processed data from the Li et al. 2024 thymus spatial+multiomics atlas.

Source paper: "Unraveling the spatial organization and development of human
thymocytes through integration of spatial transcriptomics and single-cell
multi-omics profiling" (Li et al., Nature Communications, 2024).
  https://www.nature.com/articles/s41467-024-51767-y
Companion GitHub repo (analysis code, thymusTSO R package):
  https://github.com/lihuamei/Thymus

STATUS: the exact accession (GEO/GSA/Zenodo/other) for the processed data was
not resolved during planning -- the paper's Data Availability section and the
GitHub repo both returned HTTP 403 to automated fetches from this
environment, so it needs a direct human look. Rather than guess an accession
and silently fetch the wrong (or no) data, this script fails loudly with
clear next steps until DATASET_FILES below is filled in -- it will not
pretend to have downloaded something it didn't.

To activate: visit the paper's Data Availability section and/or the GitHub
repo above, confirm the accession and exact file URLs, then populate
DATASET_FILES with {"label": ..., "url": ...} entries and re-run.
"""
from __future__ import annotations

import argparse

from fatespace.manifest import ManifestEntry, REPO_ROOT, append_manifest, stream_download

PAPER_URL = "https://www.nature.com/articles/s41467-024-51767-y"
REPO_URL = "https://github.com/lihuamei/Thymus"

RAW_DIR = REPO_ROOT / "data" / "raw" / "thymus_atlas"

# Fill in once the accession is confirmed, e.g.:
# DATASET_FILES = [{"label": "processed_rna_spatial.h5ad", "url": "https://.../GSE.../processed.h5ad"}]
DATASET_FILES: list[dict] = []

DEFAULT_PER_FILE_BUDGET_BYTES = 1 * 1024**3  # 1 GiB


def acquire(per_file_budget: int = DEFAULT_PER_FILE_BUDGET_BYTES) -> list[ManifestEntry]:
    if not DATASET_FILES:
        entry = ManifestEntry(
            source="thymus_atlas",
            dataset_id="unconfigured",
            label="Li et al. 2024 thymus atlas",
            relative_path="(unresolved)",
            status="unconfigured",
            detail=(
                f"DATASET_FILES is empty. Confirm the exact accession/download URLs from "
                f"the paper's Data Availability section ({PAPER_URL}) and/or {REPO_URL}, "
                "then populate DATASET_FILES in this file and re-run."
            ),
        )
        append_manifest(entry)
        return [entry]

    entries = []
    for f in DATASET_FILES:
        dest_path = RAW_DIR / f["label"]
        status, size_bytes, sha256, detail = stream_download(f["url"], dest_path, per_file_budget)
        entry = ManifestEntry(
            source="thymus_atlas", dataset_id=f["url"], label=f["label"], relative_path=f["label"],
            local_path=str(dest_path) if status == "downloaded" else None,
            status=status, size_bytes=size_bytes, sha256=sha256, detail=detail,
        )
        entries.append(entry)
        append_manifest(entry)
    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-file-budget-mb", type=int, default=DEFAULT_PER_FILE_BUDGET_BYTES // (1024**2))
    args = parser.parse_args()

    entries = acquire(per_file_budget=args.per_file_budget_mb * 1024**2)
    if entries and entries[0].status == "unconfigured":
        print("acquire_thymus_atlas: no accession configured yet -- see data/raw/manifest.json "
              "for exactly what to confirm and where to fill it in.")
    else:
        downloaded = [e for e in entries if e.status == "downloaded"]
        print(f"Thymus atlas acquisition: {len(downloaded)}/{len(entries)} files downloaded.")


if __name__ == "__main__":
    main()
