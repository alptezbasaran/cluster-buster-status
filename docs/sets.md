# Sets

Every config in the [Phase-1 grid](/investigation) becomes one **subject set** —
the same 500 galaxies clustered with that config and uploaded to Zooniverse as
`cluster-buster-NNN`. This table is the live status of all 126.

<StatChips />

## Set lifecycle

Each set moves through four states:

<p>
<span class="cb-badge planned">planned</span> — config defined, not yet run &nbsp;·&nbsp;
<span class="cb-badge clustered">clustered</span> — 500 galaxies clustered, bundle built &nbsp;·&nbsp;
<span class="cb-badge uploaded">uploaded</span> — subjects pushed to Zooniverse &nbsp;·&nbsp;
<span class="cb-badge live">live</span> — collecting volunteer verdicts
</p>

The anchor set, `cluster-buster-001` (★), is the known-good default — the positive
control the rest are measured against.

<SetsTable />

::: info Reproducibility
Every row's full config lives in
[`phase1-configs.csv`](https://github.com/alptezbasaran/cluster-buster-status/blob/main/phase1-configs.csv).
A set is produced with `python run_set.py cluster-buster-NNN` — see
[Workflow](/workflow).
:::
