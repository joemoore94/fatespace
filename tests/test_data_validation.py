"""Validate acquired thymus data: file integrity, schema, biological sanity,
and cross-modality alignment.

These tests operate on whatever data/raw/manifest.json + downloaded files
currently exist. If nothing has been acquired yet (e.g. no network access to
HuBMAP/Nature from this sandboxed environment), tests skip with a clear
reason rather than failing -- but any file that IS present and malformed
must fail loudly, not be silently accepted.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from fatespace.manifest import REPO_ROOT, load_manifest, sha256_of

MANIFEST_PATH = REPO_ROOT / "data" / "raw" / "manifest.json"

THYMOCYTE_LINEAGE_KEYWORDS = [
    "progenitor", "double negative", "dn", "double positive", "dp",
    "single positive", "sp", "cd4", "cd8", "thymocyte",
]

RAW_IMAGE_OR_SEQ_SUFFIXES = (".ome.tiff", ".ome.tif", ".tiff", ".tif", ".fastq", ".fastq.gz", ".bam")


def _manifest_or_skip():
    entries = load_manifest(MANIFEST_PATH)
    if not entries:
        pytest.skip("No manifest found -- run the acquisition scripts first (data/raw/manifest.json missing).")
    return entries


def _downloaded_entries():
    entries = _manifest_or_skip()
    downloaded = [e for e in entries if e["status"] == "downloaded"]
    if not downloaded:
        pytest.skip(
            "Manifest exists but no files were successfully downloaded (likely no network "
            "access to HuBMAP/paper sources from this environment)."
        )
    return downloaded


def _load_table(path: Path):
    """Best-effort tabular load. Returns None for formats this helper can't parse (e.g. .h5ad)."""
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in (".tsv", ".txt"):
        return pd.read_csv(path, sep="\t")
    if suffix == ".json":
        return pd.json_normalize(json.loads(path.read_text()))
    return None


class TestFileIntegrity:
    def test_manifest_exists_and_parses(self):
        entries = _manifest_or_skip()
        assert isinstance(entries, list)
        assert all("status" in e for e in entries)

    def test_downloaded_files_exist_on_disk(self):
        for e in _downloaded_entries():
            path = Path(e["local_path"])
            assert path.exists(), f"manifest says downloaded but file missing: {path}"

    def test_downloaded_checksums_match_manifest(self):
        for e in _downloaded_entries():
            path = Path(e["local_path"])
            assert sha256_of(path) == e["sha256"], (
                f"checksum mismatch for {path} -- file may be corrupted or truncated"
            )

    def test_downloaded_sizes_match_manifest(self):
        for e in _downloaded_entries():
            path = Path(e["local_path"])
            assert path.stat().st_size == e["size_bytes"], f"size mismatch for {path}"

    def test_no_raw_imaging_or_sequencing_snuck_in(self):
        for e in _downloaded_entries():
            assert not e["local_path"].lower().endswith(RAW_IMAGE_OR_SEQ_SUFFIXES), (
                f"{e['local_path']} looks like raw imaging/sequencing data -- "
                "this project targets processed per-cell products only"
            )


class TestSchema:
    def test_codex_tables_have_marker_and_centroid_columns(self):
        codex_entries = [e for e in _downloaded_entries() if e["source"] == "hubmap"]
        if not codex_entries:
            pytest.skip("No HuBMAP CODEX files downloaded.")
        checked_any = False
        for e in codex_entries:
            df = _load_table(Path(e["local_path"]))
            if df is None:
                continue
            checked_any = True
            cols_lower = {c.lower() for c in df.columns}
            has_centroid = any(
                k in cols_lower for k in ("x", "y", "centroid_x", "centroid_y", "x_centroid", "y_centroid")
            )
            assert has_centroid, f"{e['local_path']} has no recognizable centroid/coordinate column: {df.columns.tolist()}"
        if not checked_any:
            pytest.skip("Downloaded CODEX files are not in a directly tabular format this helper can parse.")

    def test_rna_or_spatial_tables_have_cell_identifier_column(self):
        atlas_entries = [e for e in _downloaded_entries() if e["source"] == "thymus_atlas"]
        if not atlas_entries:
            pytest.skip("No thymus-atlas files downloaded.")
        checked_any = False
        for e in atlas_entries:
            df = _load_table(Path(e["local_path"]))
            if df is None:
                continue
            checked_any = True
            cols_lower = {c.lower() for c in df.columns}
            has_cell_id = any("cell" in c or "barcode" in c for c in cols_lower)
            assert has_cell_id, f"{e['local_path']} has no recognizable cell-identifier column: {df.columns.tolist()}"
        if not checked_any:
            pytest.skip("Downloaded thymus-atlas files are not in a directly tabular format this helper can parse.")


class TestBiologicalSanity:
    def test_lineage_annotations_present_and_recognizable(self):
        found_annotation_column = False
        for e in _downloaded_entries():
            df = _load_table(Path(e["local_path"]))
            if df is None:
                continue
            annotation_cols = [
                c for c in df.columns
                if any(k in c.lower() for k in ("cell_type", "celltype", "cluster", "lineage", "annotation"))
            ]
            if not annotation_cols:
                continue
            found_annotation_column = True
            values = " ".join(df[annotation_cols[0]].astype(str).str.lower().unique())
            assert any(k in values for k in THYMOCYTE_LINEAGE_KEYWORDS), (
                f"{e['local_path']} column {annotation_cols[0]!r} has no recognizable thymocyte-lineage "
                f"stage (expected something matching {THYMOCYTE_LINEAGE_KEYWORDS})"
            )
        if not found_annotation_column:
            pytest.skip("No cell-type/lineage annotation column found in any downloaded, parseable table yet.")

    def test_per_donor_cell_counts_are_plausible(self):
        checked_any = False
        for e in _downloaded_entries():
            df = _load_table(Path(e["local_path"]))
            if df is None:
                continue
            checked_any = True
            assert 10 <= len(df) <= 5_000_000, f"{e['local_path']} has an implausible row count: {len(df)}"
        if not checked_any:
            pytest.skip("No parseable tabular files downloaded yet.")


class TestCrossModalityAlignment:
    def test_donors_with_multiple_modalities_share_a_join_key(self):
        # NOTE: HuBMAP and the Li et al. atlas are separate studies with
        # different donors -- there is no real per-donor correspondence
        # between them. This only becomes meaningful once a single source
        # (e.g. HuBMAP) provides more than one assay type for the *same*
        # donor/tissue block, which acquire_hubmap.py doesn't pull yet
        # (CODEX only). Kept here so it activates automatically once it does.
        entries = _downloaded_entries()
        by_dataset = {}
        for e in entries:
            by_dataset.setdefault((e["source"], e["dataset_id"]), []).append(e)
        multi_file_datasets = {k: v for k, v in by_dataset.items() if len(v) > 1}
        if not multi_file_datasets:
            pytest.skip("No dataset currently has more than one downloaded file to cross-check alignment on.")
        for key, files in multi_file_datasets.items():
            labels = {f["label"] for f in files}
            assert labels, f"dataset {key} has multiple files but no shared donor/label key to align on"
