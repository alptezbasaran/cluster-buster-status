# Sets

Every config, the 126 of the [Phase-1 grid](/investigation#what-we-sweep-—-phase-1) and the 64
of the [Phase-2 sample](/investigation#what-we-sweep-—-phase-2), becomes one **subject set**: the
same 500 galaxies clustered with that config and uploaded to Zooniverse as `cluster-buster-NNN`.
Phase 1 (001–126) has been complete since 21 October 2026; Phase 2 (127–190) goes up in waves
of 16.

A galaxy whose clustering has no arm is never uploaded: it counts as an unsuccessful
clustering straight away (the **No arm** column; every such galaxy is listed in
[`no-arm-galaxies.csv`](https://github.com/alptezbasaran/cluster-buster-status/blob/main/no-arm-galaxies.csv)).

<StatChips />

## Set lifecycle

Each set moves through these states:

<p>
<span class="cb-badge planned">planned</span> — config defined, not yet run &nbsp;·&nbsp;
<span class="cb-badge clustered">clustered</span> — 500 galaxies clustered, bundle built &nbsp;·&nbsp;
<span class="cb-badge uploaded">uploaded</span> — subjects pushed to Zooniverse &nbsp;·&nbsp;
<span class="cb-badge live">live</span> — collecting volunteer verdicts &nbsp;·&nbsp;
<span class="cb-badge complete">complete</span> — every subject retired with its 15 verdicts
</p>

The anchor set, `cluster-buster-001` (★), is the known-good default — the positive
control the rest are measured against.

<SetsTable />

::: info Reproducibility
Every row's full config lives in
[`phase1-configs.csv`](https://github.com/alptezbasaran/cluster-buster-status/blob/main/phase1-configs.csv)
or [`phase2-configs.csv`](https://github.com/alptezbasaran/cluster-buster-status/blob/main/phase2-configs.csv).
A set is produced with `python run_set.py cluster-buster-NNN` — see
[Workflow](/workflow).
:::
