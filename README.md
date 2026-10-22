# Cluster Buster — galaxy set & run status

Tracking repo for the Cluster Buster citizen-science round: the selected galaxy
set, its provenance, and the status of clustering runs / Zooniverse uploads.

## The Cluster Buster galaxy set (500 galaxies)

**`selected-500.csv`** is the canonical set — 500 galaxies, columns
`gid, num_arms, source`.

### Provenance

```
spiral-graph-classifications_2021_04_05.csv  (raw Zooniverse volunteer tracings)
        │  reviewer 1 (manual pre-screen)
        ▼
selected-galaxies.csv   1024 galaxies, <dr7id>,<label>
        │  reviewer 2 labels: 859 yes / 32 maybe / 133 no
        ▼
859 "yes"  ──►  tracings generated (sg_extract → sg_recenter → sg_map)
        │  select 500
        ▼
selected-500.csv   ← THE Cluster Buster galaxy set
```

### Selection rule (reproducible)

Baseline clustered all 859 with the standard `input.toml` parameters, then:

- **Kept all 160** galaxies with **4, 5, or 6 arms** (`source = kept_456`).
- **Randomly sampled 340** from the 699 with **1, 2, or 3 arms** (`source = sampled_123`),
  using **`random.seed(20260622)`** over the gid-sorted pool (deterministic).

Final arm-count mix (baseline `input.toml` counts): 1:68 / 2:149 / 3:123 / 4:127 / 5:32 / 6:1.
The 4/5/6-arm fraction is enriched from ~19% (of 859) to 32% (of 500).

> `num_arms` in the CSV is the **baseline** clustering count; it will shift once
> the clustering hyperparameters are tuned.

## Tracings

- All 859 "yes" galaxies: `astro/cluster-buster/artifacts/reviewed_859/tracings/<gid>/arms/arm_<n>_<gid>.fits` (~97 GB).
- The 500-set, materialized for runs as symlinks:
  `astro/cluster-buster/artifacts/cluster_buster_galaxy_set/` (one `<gid>` → `../reviewed_859/tracings/<gid>`).
- The arm-clustering pipeline (`arm_grouping`) points its `[parallel].folder_list` at that set folder.
- **2026-07-06:** the set's tracings were manually cleaned — see
  [Trace cleaning](#trace-cleaning-2026-07-06) below for the record and the corpus boundary.

## Trace cleaning (2026-07-06)

The 500-set tracings were reviewed one galaxy at a time with arm_grouping's
`/clean` console page: **500/500 galaxies reviewed; 966 outlier tracings
excluded (2.6%) across 389 galaxies; 35,871 active tracings remain** (no galaxy
below 24 active tracings). An excluded tracing is *parked in place* —
`arm_<n>_<gid>.fits` → `arm_<n>_<gid>.fits.excluded` — through the
`cluster_buster_galaxy_set/<gid>` symlinks, so the clustering glob
(`arms/*.fits`) never sees it and the rename stays fully reversible.

- **`cleaning/excluded_manifest_2026-07-06.csv`** — the frozen record: one row
  per excluded tracing (`gid, trace_filename`; 966 rows).
- **Corpus boundary: sets `001`–`020` clustered the *pre-cleaning* corpus;
  sets `021+` run on the *cleaned* corpus.** Forward-only by decision —
  001–020 are not re-run. `run_set.py` prints the corpus state and writes a
  `corpus_state.txt` into each run dir, so every run records which corpus it saw.

## Phase-1 config sampling

**Goal:** generate training data so a model learns the *morphological patterns* of
good vs. bad arm clustering — **not** to find the single best config for this
dataset. So every config (good and bad) is a needed example, and we run the full
grid.

**Grid (`phase1-configs.csv`, 126 configs):**

| Knob | Values | n |
|---|---|---|
| `agreement_threshold` | 50, 55, 60, 65, 70, 75, 80, 85, 90 | 9 |
| `correction_agreement` | 50, 55, 60, 65, 70, 75, 80 | 7 |
| `ratio_limit` | 1.0, 1.5 | 2 |
| held constant | `trace_support 2`, `filter (5, 99)`, blurs `51/31`, Tier-2 on | |

→ **126 configs = 126 sets**, each = the 500-galaxy set clustered with one config
(500 subjects × 15 confirmations = 7,500 classifications/set). `ratio_limit`
`2.0/2.5` are excluded — byte-identical to `1.5`. Order: `001–014` = the focused
`agreement=65` block (anchor `001` = agree 65 / corr 55 / ratio 1.5); `015–126`
expand `agreement`. `trace_support` + blurs are a later phase.

## Phase-2 config sampling

Phase 2 varies all six knobs together: `agreement_threshold` 50–90, `correction_agreement`
50–80, `ratio_limit` 1.00–1.50 (0.05 steps), `trace_support` 2–5, `vanilla.blur` 21–81 and
`arm_correction.blur` 11–61 (odd). **`phase2-configs.csv`** holds 64 configs
(`cluster-buster-127` … `-190`) drawn by `make_phase2_design.py` (scrambled Sobol, seed
`20261021`), uploaded in waves of 16 (`wave` column). Runs start from **`base-config.json`**,
the frozen Phase-1 base config, on the same 500 galaxies and the cleaned tracings. Each wave is
test-clustered in memory first (`analysis/probe_phase2.py --wave N`).

## Run / upload status

Each set is a Zooniverse subject set `cluster-buster-NNN`. Live per-set status lives in
`docs/.vitepress/data/set-status.json` and on the site's Sets page.
