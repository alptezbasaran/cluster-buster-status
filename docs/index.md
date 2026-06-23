---
layout: home
hero:
  name: Cluster Buster
  text: Live status of the spiral-arm clustering sweep
  tagline: A 126-config hyperparameter study, validated by Zooniverse volunteers — tracking which clustering settings produce good spiral arms.
  actions:
    - theme: brand
      text: Classify on Zooniverse
      link: https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph-cluster-buster
    - theme: alt
      text: All 126 sets
      link: /sets
    - theme: alt
      text: Data archive (Zenodo)
      link: https://zenodo.org/records/15882378
---

<div class="cb-hero-anim">
  <iframe src="/cluster-buster-status/animations/52-galaxy-rotation.html" title="Cluster Buster — rotating spiral galaxy" scrolling="no" loading="lazy"></iframe>
</div>

<StatChips />

## Sweep status

The headline view: every config in the Phase-1 grid, coloured by where it is in the
pipeline. Two panels for the `ratio_limit` split; hover any cell for its set and subject count.

<SweepGrid />

## Why this exists

Spiral arms wind at a characteristic **pitch angle** that tracks the mass of a galaxy's
central black hole — but measuring it depends on first **clustering volunteer arm tracings**
correctly, and that clustering has knobs. Cluster Buster sweeps those knobs across 126 configs
and lets Zooniverse volunteers judge which settings actually produce good arms.

<div class="cb-links">

➜ **[All 126 sets](/sets)** · **[The investigation](/investigation)** · **[How it works](/the-project)**

</div>
