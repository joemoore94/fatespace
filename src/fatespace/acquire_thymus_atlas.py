"""Acquire processed data from the Li et al. 2024 thymus spatial+multiomics atlas.

Source paper: "Unraveling the spatial organization and development of human
thymocytes through integration of spatial transcriptomics and single-cell
multi-omics profiling" (Li et al., Nature Communications, 2024).
  https://www.nature.com/articles/s41467-024-51767-y
Companion GitHub repo (analysis code, thymusTSO R package):
  https://github.com/lihuamei/Thymus

STATUS: resolved. Per the paper's Data Availability section (confirmed by a
human, since automated fetches of that section were unreliable from this
environment):

- Processed data (what this script pulls) -- Seurat objects on Zenodo,
  DOI 10.5281/zenodo.13207776: thymus.st.rds (spatial transcriptomics) and
  thymus.sc.RDS (single-cell).
- Raw sequence data -- GSA-Human (ngdc.cncb.ac.cn, restricted-access,
  requires an application): HRA007984 (scRNA-seq), HRA007980 (spatial
  transcriptomics), HRA007988 (scTCR-seq). Deliberately NOT pulled here --
  raw and access-gated, out of scope per this project's processed-data-only
  policy.
- Other datasets the paper reuses from prior studies (Park et al. scRNA/
  scTCR-seq, Zenodo 10.5281/zenodo.3572422; Cordes et al., GEO GSE195812;
  Suo et al. spatial samples, https://developmental.cellatlas.io/fetal-immune)
  are external to the Li et al. atlas itself and out of scope for this
  script.
"""
from __future__ import annotations

import argparse

from fatespace.manifest import ManifestEntry, REPO_ROOT, append_manifest, stream_download

PAPER_URL = "https://www.nature.com/articles/s41467-024-51767-y"
REPO_URL = "https://github.com/lihuamei/Thymus"
ZENODO_RECORD_URL = "https://doi.org/10.5281/zenodo.13207776"

RAW_DIR = REPO_ROOT / "data" / "raw" / "thymus_atlas"

DATASET_FILES: list[dict] = [
    {
        "label": "thymus.st.rds",
        "url": "https://zenodo.org/api/records/13207776/files/thymus.st.rds/content",
    },
    {
        "label": "thymus.sc.RDS",
        "url": "https://zenodo.org/api/records/13207776/files/thymus.sc.RDS/content",
    },
]

DEFAULT_PER_FILE_BUDGET_BYTES = 5 * 1024**3  # 5 GiB -- thymus.sc.RDS is ~4.1 GiB


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
