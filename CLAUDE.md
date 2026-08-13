# CLAUDE.md

Guidance for working in this repo.

## Current stage
Data acquisition only. There is no model/training code yet — do not add
PyTorch, encoders, VAEs, or training loops until the data layer below is
acquired and validated. See "Modeling approach" below for the model and
validation design that comes after this stage.

## Modeling approach (future phases, not implemented yet)
Three models will be compared once Phase 1/2 modeling starts:
- **Model A**: RNA-only reconstruction (baseline)
- **Model B**: RNA + protein + spatial reconstruction (no trajectory loss)
- **Model C**: RNA + protein + spatial + trajectory supervision
  (Palantir-derived pseudotime/fate)

Validation splits into two axes:
- **Decoding**: held-out reconstruction error per modality, Model B vs
  Model C.
- **Prediction**: linear-probe accuracy predicting annotated terminal cell
  type (e.g. CD4 SP vs CD8 SP) from frozen latent z, Model B vs Model C.
  Ground truth is the dataset's existing cell-type annotations, not
  Palantir's own pseudotime/fate output — scoring against Palantir's own
  output would be circular, since Palantir is computed from the same z
  being evaluated.

Pinned for later — how Palantir itself (Setty et al. 2019) validated
without circularity, worth mirroring:
1. Automatic terminal-state detection matched cell types already known from
   prior literature.
2. Marker-gene/transcription-factor trends along inferred trajectories
   matched established developmental biology (e.g. GATA1, PU.1, MPO).
3. Benchmarked against independent trajectory-inference methods (Slingshot,
   PAGA, Monocle2, DPT, FateID).
4. Reproducibility checked across independent donors/replicates.

## Potential future direction: pan-immune expansion (not scoped, not started)
Discussed as a possible follow-on after Models A/B/C are validated on thymus
data — not current work, and the "Current stage" rules above (no torch, no
model code) still apply until this is picked up.

Idea: split off from **Model A** (RNA-only) specifically, not B/C. Models
B/C are thymus-bound by construction — the spatial/CODEX modality is
HuBMAP-only, and the Palantir trajectory/fate supervision only makes sense
along the one thymic developmental axis (DN→DP→SP). RNA-only reconstruction
is the one piece that generalizes: scRNA is the modality most other
immune-cell atlases share.

Sketch:
- Add scRNA datasets beyond the thymus atlas — candidates: the Open
  Problems Single-Cell Perturbations dataset (PBMC, real primary immune
  cells: T/B/NK/monocyte) and at least one more pan-immune atlas, TBD.
- Open question: fine-tune Model A's thymus-trained weights on the added
  data, or retrain the same RNA-only architecture from scratch on the
  combined corpus. Treat as empirical, not assumed.
- Multi-dataset batch effects (systematic non-biological differences
  between cohorts/sequencing runs/chemistry versions) need correcting for,
  not ignored. Natural fit: an scVI-style conditional-VAE design, where
  batch/dataset identity is a covariate concatenated onto `z` and fed into
  the decoder (`decoder(z, batch_onehot) → x_hat`), so the decoder absorbs
  the technical shift and the encoder's `z` stays batch-agnostic.
- Validation target changes: CD4 SP vs CD8 SP doesn't exist outside the
  thymus. A pan-immune linear probe needs a broader cell-type target
  (T/B/NK/monocyte/etc.), separate from the thymus-trajectory validation
  Models B/C keep using.
- Originally motivated by a further idea (even more speculative, fully
  gated on this expansion happening first): a compound-perturbation decoder
  head conditioned on SMILES/compound embeddings, predicting a cell's
  post-treatment state from its baseline latent. Needs paired
  compound-response data (e.g. Open Problems), which only exists for
  PBMC-type cells, not thymocytes — hence why this depends on the
  pan-immune expansion, not the other way around.

## Tech stack
Python 3.10+. CPU-only dependencies for this stage: `requests`, `pandas`,
`anndata`, `scanpy`, `pyyaml`. Do not add `torch` or any GPU dependency until
Phase 1 modeling actually starts — flag it explicitly first if you think
that's needed.

## Data policy
- Never commit anything under `data/raw/` or `data/processed/` — both are
  gitignored. Everything there must be reproducible by re-running the
  acquisition scripts, not by hand-editing or committing artifacts.
- Every file an acquisition script touches gets one entry in
  `data/raw/manifest.json` (see `src/fatespace/manifest.py`) — dataset id,
  status, size, checksum — whether the fetch succeeded or not. Don't
  silently skip a failed download; record why.
- Enforce the per-file and total size budgets already in
  `acquire_hubmap.py`/`acquire_thymus_atlas.py` — this project targets
  *processed* per-cell tables (CODEX Cytokit+SPRM output, expression
  matrices), never raw multi-channel imaging or FASTQ. If a change would
  pull raw imaging/sequencing, stop and flag it first.

## Compute expectations
This stage is CPU-only: 16-32GB RAM, ~50-100GB disk is the assumed ceiling.
Don't provision or code against a GPU here.

## Validating data
After any change to an acquisition script, run:
```
pytest tests/test_data_validation.py
```
This checks file/checksum integrity, expected schema (marker channels,
centroid coordinates, lineage annotations), biological sanity (recognizable
thymocyte-lineage stages, plausible per-donor cell counts), and
cross-modality alignment where applicable. Tests skip (not fail) when no
data has been acquired yet, e.g. in a sandboxed environment without network
access to HuBMAP/Nature — but must hard-fail on corrupt/malformed data once
it exists.

## Where to look first
- `src/fatespace/acquire_hubmap.py` — HuBMAP CODEX acquisition (has a
  known-good hardcoded set of thymus donor dataset UUIDs; the organ-code
  API search is best-effort only).
- `src/fatespace/acquire_thymus_atlas.py` — Li et al. 2024 thymus atlas
  acquisition. Resolved: processed Seurat objects on Zenodo (DOI
  10.5281/zenodo.13207776), `DATASET_FILES` is populated and the script is
  runnable.
- `src/fatespace/convert_thymus_atlas.py` — converts acquired thymus atlas
  `.rds` files to `.h5ad` via `readseurat`, writing to
  `data/processed/manifest.json`.
- `src/fatespace/manifest.py` — shared download/manifest helpers used by
  both acquisition scripts.
