# cluster-buster-status

Tracking + status site for the **Cluster Buster** citizen-science hyperparameter
study. This repo holds the galaxy set, the config sweep, the per-set run/upload
tooling, and a VitePress status site deployed to GitHub Pages.

## The bigger picture

Cluster Buster validates spiral-arm **clustering** with Zooniverse volunteers (the
clustered arms feed pitch-angle → black-hole-mass science). The loop spans three
places:

- `astro/cluster-buster/` — generates per-galaxy volunteer tracings (`artifacts/`,
  incl. `reviewed_859/tracings/` and the `cluster_buster_galaxy_set/` symlink set).
- `~/Desktop/projects/arm_grouping/` — the clustering pipeline (`python -m arm_grouping`),
  the Zooniverse bundler, and `zooniverse_upload.py`. Its `.venv` (uv-managed; use
  `.venv/bin/python`, there is no `pip`) is what the tooling here calls.
- **this repo** — the experiment record + the status site.

## The investigation, in one paragraph

We sweep clustering hyperparameters on a **full grid** and show each config's results
to volunteers as a good/bad task. The goal is **training data for a model that learns
the morphology of good clustering** — NOT to find the single best config for this
dataset. So we keep the whole grid (bad configs are needed negative examples) and hold
trace-filtering constant (the model should read morphology, not learn to drop tracings).

## Key files

- `selected-500.csv` — the **Cluster Buster galaxy set** (500 gids; seed `20260622`).
- `phase1-configs.csv` — the **126-config grid**: `agreement_threshold` (50–90/5) ×
  `correction_agreement` (50–80/5) × `ratio_limit` ({1.0, 1.5}). One row = one set.
- `docs/.vitepress/data/set-status.json` — **live per-set status** (clustered / uploaded
  / subjects). Drives the site's Sets table. Edit this as sets progress.
- `run_set.py <set>` — cluster the 500-set with one config + build the bundle.
- `upload_set.py <set>` — the **guard** (manifest ↔ run.json ↔ phase1-configs 3-way
  hyperparameter match) → `--verify-only` → upload → update `set-status.json`.
- `docs/public/demo/` + `docs/demo.md` — the **interactive hyperparameter explorer** (the
  *Explore* page). Static, precomputed, no server: 780 WebP panels for 4 galaxies, two views
  (Simple = the 126-config Phase-1 grid with per-cell `cluster-buster-NNN` badges; Full = the
  strong knobs, combinable). Generated in **arm_grouping**, synced here — see "Regenerating the demo".

## Run + upload a set

```bash
python run_set.py cluster-buster-NNN        # cluster + bundle (most cores), outputs to
                                            #   astro/cluster-buster/artifacts/set_runs/<set>/
source ~/.zooniverse_env                    # PANOPTES_USERNAME / PANOPTES_PASSWORD (chmod 600)
python upload_set.py cluster-buster-NNN     # guard → verify → upload → set-status.json
# then commit set-status.json and push → GitHub Actions redeploys the site
```

Project slug: `astro-lab-ncmns/spiral-graph-cluster-buster`. Each subject collects
**15 verdicts**. **`ratio=1.0` and (future) Phase-2 sets legitimately yield <500
subjects** — galaxies with no arms at that config are correctly skipped; `set-status.json`
tracks each set's real count.

## The site

VitePress in `docs/`. Local dev: `docker compose up docs` → http://localhost:5173/cluster-buster-status/.
Build: `docker compose run --rm docs npm run docs:build` (or `npm run docs:build`).
CI builds inside `Dockerfile` and deploys to Pages via `.github/workflows/deploy.yml`.
Base path is `/cluster-buster-status/`.

- Don't re-enable `lastUpdated` in `config.mts` — it shells out to `git`, which the build
  container lacks (and `.dockerignore` excludes `.git`). It breaks the Docker build.
- Use `node:20-slim`, not alpine (musl trips Vite's rollup native binary).

## Regenerating the demo

The *Explore* page (`docs/public/demo/`) is **precomputed in the arm_grouping repo** and
copied here — the renderer and its `.venv` live there, not in this repo:

```bash
cd ~/Desktop/projects/arm_grouping
.venv/bin/python -m analysis_scripts.gen_tune_demo               # → docs/demo/ (~780 WebP, 16 MB)
rsync -a --delete docs/demo/ ../astro/cluster-buster-status/docs/public/demo/
```

Edit galaxies / knob axes at the top of `gen_tune_demo.py`. The Simple view's axes and the
per-cell `cluster-buster-NNN` mapping are read from this repo's `phase1-configs.csv`, so the
demo and the real subject sets stay in lockstep. `docs/demo.md` embeds the standalone page via
an iframe (`layout: page`, no sidebar).

## Conventions

- **No emojis** in code or commits. **No agent attribution** anywhere in git history
  (no `Co-Authored-By`, no "Generated with…").
- **The user runs `git push` themselves** — commit locally, then tell them. Local commits
  are fine.

## Gotchas

- `arm_grouping/run_set.py`-style scripts that spawn the multiprocessing pool MUST have an
  `if __name__ == "__main__"` guard (macOS spawn re-imports the script).
- `build_zooniverse_bundle` (in arm_grouping) still writes a manifest row even when a
  render PNG is missing — the `upload_set.py --verify-only` step is the safety net that
  catches it. Keep the guard; a proper arm_grouping fix is queued.
