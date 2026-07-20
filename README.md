# fatespace

Multimodal latent cell-state modeling for T-cell fate prediction, using human
thymic T-cell development (early thymic progenitor -> double-negative ->
double-positive -> mature single-positive CD4/CD8 T cell) as the benchmark
system. The central question: does constraining a learned multimodal latent
space (RNA + protein + spatial) with developmental trajectory supervision
produce a better representation of cell-fate-determining variables than
reconstruction alone?

**Current stage: data acquisition only.** No model code exists yet.

## Data sources

- [HuBMAP Data Portal](https://portal.hubmapconsortium.org) — processed
  (Cytokit+SPRM) CODEX protein-imaging datasets for human thymus, plus
  RNA-seq/spatial transcriptomics data types for the same organ.
- Li et al. 2024, *Nature Communications* — [thymus spatial transcriptomics +
  single-cell multi-omics atlas](https://www.nature.com/articles/s41467-024-51767-y)
  ([code](https://github.com/lihuamei/Thymus)). Exact accession still needs
  confirming by a human — see `src/fatespace/acquire_thymus_atlas.py`.

## Running data acquisition

```bash
pip install -e .
python -m fatespace.acquire_hubmap
python -m fatespace.acquire_thymus_atlas
pytest tests/
```

Downloaded files land under `data/raw/` (gitignored, never committed) with a
manifest at `data/raw/manifest.json` recording what was fetched, from where,
and its checksum/size. See `CLAUDE.md` for repo conventions and compute
expectations.
