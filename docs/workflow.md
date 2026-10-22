# Pipeline & Workflow

How a config in the grid becomes a live Zooniverse set, end to end — and how this
status site stays in sync.

## Producing a set

```bash
python run_set.py cluster-buster-NNN          # most cores by default
```

`run_set.py` (in this repo) reads the set's row from `phase1-configs.csv` or
`phase2-configs.csv`, applies its nine knobs to `base-config.json` (the frozen Phase-1
base config), and runs the arm-clustering pipeline once over the **500-galaxy Cluster
Buster set**:

1. **Cluster** all 500 galaxies with that config.
2. **Render** each result with the fixed `Set1` arm palette and the split panels
   `[overlay · clusters · tracings]`.
3. **Bundle** into `<set>_<hash>/`: one manifest row and three PNGs per galaxy with at
   least one arm, every row stamped with all nine knobs, alongside a `run.json` recording
   the exact config. Galaxies whose clustering has no arm are left out and counted
   unsuccessful (`skipped.txt`, then `no-arm-galaxies.csv`).
4. **Record** the corpus state and the code and environment (`provenance.txt`), mark the
   set clustered in `set-status.json`, and delete the per-galaxy FITS (regenerable).

Output lands in `artifacts/set_runs/<set>/`. Nothing uploads yet.

## Uploading

Auth is environment-only (`PANOPTES_USERNAME` / `PANOPTES_PASSWORD`, kept in a
chmod-600 file outside any repo). The upload is verified, then pushed:

```bash
source ~/.zooniverse_env
python zooniverse_upload.py --verify-only <bundle>          # offline schema check
python zooniverse_upload.py \
  --project-slug astro-lab-ncmns/spiral-graph-cluster-buster \
  --subject-set-name cluster-buster-NNN  <bundle>           # creates the set, pushes 500 subjects
```

The uploader is **resumable** (`uploaded.txt`) and **idempotent** (each subject
carries its bundle path, so re-runs skip what's already there). Each subject collects
**15 verdicts** before it retires.

## Keeping the record honest

The science depends on knowing **exactly which hyperparameters produced each uploaded
set.** The guard:

> After each upload, compare the uploaded **manifest metadata** against the run's
> **`run.json`**. Only if the hyperparameters match do we accept the upload and record
> the status change here in the status repo.

This catches the classic mistakes — uploading a bundle built with a different config,
or mislabelling a set — before they contaminate the training labels. The match check,
the upload outcome, and any later state change (uploaded → live → classification
counts) are written back to `set-status.json`, which drives the [Sets](/sets) table.

## Attention checks

After an automated account submitted ~25k junk classifications in July 2026,
a small set of **attention-check subjects** (`cluster-buster-qc`, 200 images
that literally say "TEST SUBJECT — please answer YES/NO") is mixed into the
serving pool at ~0.4%. Volunteers who read the image pass trivially; accounts
that answer them wrong get flagged by `captcha_check.py`. These subjects are
**excluded from all science aggregation** (see `captcha_subjects.json`), and
they slightly inflate the workflow-level subject/retired totals shown on this
site — the per-set table is unaffected.

## What's automated vs. manual

| Step | How |
|---|---|
| Cluster + bundle a set | `run_set.py` (automatic) |
| Verify bundle schema | `--verify-only` (automatic, offline) |
| Match manifest ↔ run.json | guard before upload |
| Upload to Zooniverse | `zooniverse_upload.py` (needs creds) |
| Update this site | edit `set-status.json` → push → GitHub Actions redeploys |
| Captcha tripwire | `captcha_check.py` (manual, read-only; exit 3 on flags) |
| Re-arm retired captchas | `captcha_check.py --unretire` (operator-only) |
