# fatespace

Multimodal latent cell-state model for T-cell fate prediction, benchmarked on
human thymic T-cell development: progenitor to double-negative to
double-positive to mature single-positive CD4/CD8 T cell.

Three models are compared:
- **Model A**: RNA-only reconstruction
- **Model B**: RNA + protein + spatial reconstruction
- **Model C**: RNA + protein + spatial + trajectory supervision

Validated two ways: **decoding** (held-out reconstruction error) and
**prediction** (linear-probe accuracy on annotated terminal cell type from
frozen latent z, scored against the dataset's own labels).

## Data sources

- [HuBMAP Data Portal](https://portal.hubmapconsortium.org): processed CODEX
  protein-imaging datasets for human thymus (Cytokit+SPRM pipeline), plus
  RNA-seq and spatial transcriptomics data for the same organ.
- Li et al. 2024, *Nature Communications*: [thymus spatial transcriptomics and
  single-cell multi-omics atlas](https://www.nature.com/articles/s41467-024-51767-y)
  ([code](https://github.com/lihuamei/Thymus)). Accession still needs
  confirming by a human; see `src/fatespace/acquire_thymus_atlas.py`.

## Running data acquisition

```bash
pip install -e .
python -m fatespace.acquire_hubmap
python -m fatespace.acquire_thymus_atlas
pytest tests/
```
