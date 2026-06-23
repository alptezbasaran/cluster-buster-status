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

## Run / upload status

**Naming convention:** each set is a Zooniverse subject set `cluster-buster-NNN`,
set in `input.toml`'s `[zooniverse.upload].subject_set_name` before each run.

| Set | agree | corr | ratio | Clustered | Uploaded | Classifications | run.json |
|-----|---|---|---|---|---|---|---|
| `cluster-buster-001` | 65 | 55 | 1.5 | | | | |
