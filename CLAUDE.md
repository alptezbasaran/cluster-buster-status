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
- `cleaning/excluded_manifest_2026-07-06.csv` — the **trace-cleaning record** (966 excluded
  tracings across 389 galaxies; the 2026-07-06 manual pass with arm_grouping's `/clean`).
  **Corpus boundary: sets 001-020 = pre-cleaning, 021+ = cleaned corpus** (forward-only;
  001-020 are not re-run). Exclusions live as `.fits.excluded` renames in the tracings DB —
  invisible to the clustering glob; `run_set.py` records the corpus state per run
  (`corpus_state.txt` in the run dir).
- `phase1-configs.csv` — the **126-config grid**: `agreement_threshold` (50–90/5) ×
  `correction_agreement` (50–80/5) × `ratio_limit` ({1.0, 1.5}). One row = one set.
- `docs/.vitepress/data/set-status.json` — **live per-set status** (clustered / uploaded
  / subjects / retired / completeness, plus workflow totals under `_meta`). Drives the
  site's Sets table and stat chips. Upload state is edited by `upload_set.py`;
  classification progress comes from `sync_progress.py`.
- `sync_progress.py` — **classification-progress sync** (anonymous Zooniverse API reads,
  no credentials): per-set retirement via subject-set completeness for workflow 26736 +
  workflow totals into `_meta`. Run any time volunteers have been busy, commit
  `set-status.json`, push to redeploy.
- `set_progress.py <set>` — **per-subject drill-down** for one set (anonymous API):
  exact classifications_count per subject via `subject_workflow_statuses` (batched
  `subject_ids` filter), verdict distribution, and which subjects are still short of
  the 15-verdict retirement. ~16 requests/set — fine per set, don't loop all 126
  casually.
- `run_set.py <set>` — cluster the 500-set with one config + build the bundle.
- `upload_set.py <set>` — the **guard** (manifest ↔ run.json ↔ phase1-configs 3-way
  hyperparameter match) → `--verify-only` → upload → update `set-status.json`.
- `make_captcha_bundle.py` — generates the **attention-check ("captcha") bundle**
  (see the Attention-check subjects section below).
- `link_set.py <display-name>` — link/unlink a subject set to workflow 26736
  (authenticated; `--dry-run`; the committed replacement for July's one-off).
- `reconcile_captchas.py` — post-upload: writes `captcha_subjects.json`
  (subject_id → expected answer; anonymous API reads). For opaque-id sets (v3+):
  `--answers <bundle>/captcha_answers.csv --private` → gitignored
  `state/captcha_subjects_private.json` instead.
- `captcha_check.py` — the **captcha tripwire**: incremental authenticated
  classification harvest (bookmark in gitignored `state/`), per-user
  pass/fail verdicts (FLAG/WATCH/OK), live-pool status, `--unretire`
  (operator-confirmed re-arm), `--write-incident`. Exit 3 = new FLAG accounts.
- `captcha_subjects.json` — committed subject_id ↔ expected-answer map for the
  v1/v2 qc sets; read by the checker AND by any future label aggregation (see
  below). Opaque-id sets (v3+) live in the gitignored
  `state/captcha_subjects_private.json` — never commit it; `captcha_check.py`
  and `forensics.captcha_map()` / `CAPTCHA_SETS` merge both files.
- **Classification quality review** — methods, validation and thresholds in
  `METHODS.md`; run `harvest.py` → `forensics.py` → `linkage.py` →
  `triangulate.py` (commands in METHODS.md).
  - `harvest.py` — the **raw classification store**: every project
    classification, compact, under gitignored `state/raw/` (parallel `--full`
    rebuild ~4 min; incremental otherwise). Analyses read this instead of
    re-harvesting into scratch dirs (lost twice in July/August).
  - `forensics.py` — Dawid–Skene content scoring (J, d′, criterion), tiers
    (AUTOMATION / FIXED / AT CHANCE / LOW INFO / BIASED / OK), drift, captcha
    rates + exposure, linked accounts, impact on labels.
  - `linkage.py` — same-operator detection from timing (handoffs, co-activity,
    day-shift null); IP / device only as corroboration.
  - `triangulate.py` — cross-validates the content scores with independent
    methods (majority, anchor consensus, GLAD, SDT, person-fit, reliability,
    robust outliers, aggregator comparison).
  - Inputs downloaded by hand into `state/`: `export_subjects.csv.gz` (subject →
    set) and the classification export (hashed IPs → `state/ip_map.tsv.gz`).
  - **This repo is public: never commit account-level findings or volunteer
    names.** Per-account results stay in `state/` (gitignored); notes on
    investigated accounts live in `state/known_accounts.json`; dated reviews
    that name accounts go in `state/reviews/<date>/`, not `incidents/`.
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

## Attention-check ("captcha") subjects

Deployed after the 2026-07-12 bot incident: subject set **`cluster-buster-qc`**
(200 synthetic subjects, 100 YES / 100 NO) whose images instruct the volunteer
which answer to pick ("TEST SUBJECT — Please answer: YES/NO" on all 3 frames).
Served uniformly alongside the science sets (~0.4% of serves); accounts that
answer them wrong were not reading — bot / careless-clicker flags with
unambiguous ground truth. Answer is encoded in the gid prefix (`qcyes###` /
`qcno###`) and `#data_set=attention_check`; `#expected_number_of_arms` is left
EMPTY on purpose (a number there could mis-join arm-count aggregations).

**v3 (`cluster-buster-qc3`, built 2026-10-21, not yet uploaded):** same amber
look as v2 (`--style plain --palette amber --frame 26`), but `--opaque-ids` —
gids are `qc3` + 6 random hex digits and the manifest order is shuffled, so no
metadata and no subject-id order carry the answer. The answers stay in the
bundle's `captcha_answers.csv` (under `set_runs/`, outside this repo) and,
after upload, in the private map via `reconcile_captchas.py --private`. Upload
and link it together with the next science sets, never alone (an otherwise
out-of-data workflow would serve nothing but captchas).

- **EXCLUSION RULE: every label aggregation must drop the subject ids in
  `captcha_subjects.json` and `state/captcha_subjects_private.json`**
  (equivalently: subjects with
  `#data_set == "attention_check"` or gid prefix `qc`), **and down-weight or
  exclude accounts in `incidents/*captcha-flags*.json`, in addition to the
  known bot user 3055564.**
- Workflow-level totals (`subjects_count`, retired counts, `sync_progress.py`
  `_meta` numbers) INCLUDE the 200 captchas; the per-set science table does
  not (the qc set is not in `phase1-configs.csv`).
- **Never upload the qc set via `upload_set.py`** — its hyperparameter guard
  aborts on the empty knob columns. Use `zooniverse_upload.py` directly (the
  exact command is in `make_captcha_bundle.py`'s docstring).
- Captchas retire at 15 votes like any subject; `captcha_check.py` reports the
  live count and `--unretire` re-arms the pool (operator-run, interactive).
  Re-arming a fully retired pool buys almost nothing: retirement counts total
  classifications, so a card already at 15 retires again on its next vote —
  build a fresh pool instead (as for v3).
- All Zooniverse mutations (upload, link, unretire) are operator-triggered.

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
