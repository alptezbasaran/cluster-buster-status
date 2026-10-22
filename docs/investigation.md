# The Investigation

## The guiding principle

We are **not** searching for the single best config for these 500 galaxies. The
current defaults already cluster this dataset well — but they were chosen by hand,
and a setting that happens to work here may not generalize.

Instead, the goal is to build **training data for a model that learns the morphology
of good vs. bad clustering**, so it can generalize to new galaxies and new settings.
That reframing changes every design decision:

- **We keep the full grid.** Configs that produce *bad* clustering are not waste —
  they are essential negative examples. A model that never sees bad clustering can't
  recognize it.
- **We hold trace-filtering fixed.** The model should understand the morphology of
  the tracing overlay, not learn to throw tracings away. So the outlier filter stays
  constant and is never a swept axis.
- **Sensitivity guides ordering, not pruning.** We learned which knobs move the
  result most (below) — we use that to decide what to run *first*, never to drop
  configs.

## What we sweep — Phase 1

Three knobs, swept on a full grid. Every cell becomes one upload set of the same 500
galaxies.

| Knob | What it controls | Values | n |
|---|---|---|---|
| `agreement_threshold` | how strongly a tracing must overlap the seed to join an arm | 50, 55, 60, 65, 70, 75, 80, 85, 90 | 9 |
| `correction_agreement` | how much two arms must overlap to be merged | 50, 55, 60, 65, 70, 75, 80 | 7 |
| `ratio_limit` | guard on which tracing may seed an arm | 1.0, 1.5 | 2 |

→ **9 × 7 × 2 = 126 configs.** `ratio_limit` 2.0 / 2.5 are excluded because they
produce byte-identical clustering to 1.5 — duplicate examples would only bias the
model.

::: tip See it for yourself
Drive these three knobs on real galaxies in the **[interactive explorer](/demo)** — the
*Zooniverse grid* tab is exactly this 126-config sweep, and each cell shows the
`cluster-buster-NNN` subject set it maps to.
:::

## Held constant (Phase 1)

| Knob | Value | Why fixed |
|---|---|---|
| `trace_support` | 2 | strong knob — deferred to Phase 2 |
| `filter_outliers` | (5, 99) percentile | morphology, not elimination — never swept |
| `vanilla.blur` / `arm_correction.blur` | 51 / 31 | deferred to Phase 2 |
| post-check, pre-filter, correction toggles | on | structural, diagnostic only |

## What we sweep — Phase 2

Phase 2 varies all six knobs together: the three Phase-1 knobs plus the three it held fixed.

| Knob | Range |
|---|---|
| `agreement_threshold` | 50–90 |
| `correction_agreement` | 50–80 |
| `ratio_limit` | 1.00–1.50, in 0.05 steps (Phase 1 used only the two ends) |
| `trace_support` | 2–5 |
| `vanilla.blur` | 21–81 (odd kernel sizes) |
| `arm_correction.blur` | 11–61 (odd kernel sizes) |

A full grid over six knobs would need thousands of sets, so Phase 2 samples the space
instead: 64 configs from a scrambled Sobol sequence, uploaded in four waves of 16 as
`cluster-buster-127` to `cluster-buster-190`
([`phase2-configs.csv`](https://github.com/alptezbasaran/cluster-buster-status/blob/main/phase2-configs.csv)).
Each wave spans every knob's full range on its own, and the sample stays balanced after
waves 1, 2 and 4. Phase 1's 126 sets are the slice of the same space at `trace_support` 2
and blurs 51 / 31, so the two phases form one map. Same 500 galaxies, same manually cleaned
tracings, 15 verdicts per subject.

- **No arm, no upload.** A galaxy whose clustering has no arm counts as unsuccessful straight
  away, in both phases; it is listed in `no-arm-galaxies.csv` instead of being uploaded.
- **Every image goes up**, including ones identical to an image volunteers already judged
  under another config. Those repeats show how consistently the same image is judged.
- **Blur kernels skip sizes 15 and 21.** OpenCV on Apple-silicon Macs rounds those two
  sizes differently from every other platform, so a sampled 15 or 21 moves up to 17 or 23
  and every set reproduces exactly on any machine.

Every config is test-clustered on all 500 galaxies before its set is built. Wave 1: all 16
configs ran cleanly, giving 7,846 subjects plus 154 galaxy/config pairs with no arm; 15% of
the images repeat one volunteers already judged, against 77% in Phase 1's finer grid.

## What the sensitivity sweep told us

Before committing, we swept each knob wide on a sample of galaxies and watched the
mean arm count — a proxy for over- vs. under-clustering:

| Knob | Effect across its range | Verdict |
|---|---|---|
| `correction_agreement` | 1.8 → 4.0 arms (20 → 99) | **strong** |
| `trace_support` | 4.1 → 2.1 arms (1 → 8) | **strong** |
| `agreement_threshold` | 2.7 → ~3.4 arms (20 → 99) | **weak**, even at extremes |

The clustering is remarkably **robust to `agreement_threshold`** — which is exactly
why the hand-picked default works. The strong knobs are `correction` and
`trace_support`. Phase 1 puts `correction` on the grid; `trace_support` and the blurs
follow in Phase 2.

::: tip Expect uniformity first
Because Phase 1's most-varied knob is one of the gentler ones, early sets may earn
fairly uniform good/bad labels. That uniformity is a signal, not a failure — it tells
us when to expand into the stronger knobs.
:::

## Phasing

| Phase | Adds | Status |
|---|---|---|
| **Phase 1** | `agreement` × `correction` × `ratio` (126 configs) | **complete** — 941,794 classifications, finished 2026-10-21 |
| **Phase 2** | all six knobs together (64 configs, 4 waves of 16) | **wave 1 live** since 2026-10-22 |
| Phase 3 | the `filter_outliers` percentiles — only if responses warrant | conditional |

## How a config becomes evidence

Each config is run identically: cluster all 500 galaxies, render the arms in a
fixed colour palette, build a Zooniverse subject set named `cluster-buster-NNN`, and
collect 15 good/bad verdicts per galaxy. One config in, 7,500 classifications out.

➜ See it live: **[Sets](/sets)**.
