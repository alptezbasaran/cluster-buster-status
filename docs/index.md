---
layout: home
hero:
  name: Cluster Buster
  text: Validating spiral-arm clustering with citizen scientists
  tagline: A live log of the hyperparameter study behind the Spiral Graph pitch-angle pipeline — and the data it is generating to teach a model what good clustering looks like.
  actions:
    - theme: brand
      text: The Investigation
      link: /investigation
    - theme: alt
      text: Live set status
      link: /sets
    - theme: alt
      text: How it works
      link: /the-project
features:
  - icon: 🌀
    title: Volunteers judge the grouping
    details: Each galaxy's volunteer arm tracings are clustered into individual arms by an algorithm. Citizen scientists then label each result good or bad — validating whether the arms were correctly separated.
  - icon: 🎛️
    title: A systematic 126-config sweep
    details: Rather than one hand-tuned setting, we sweep agreement, correction, and ratio across a full grid — each config uploaded as its own subject set of the same 500 galaxies.
  - icon: 🧠
    title: Teaching a model to see
    details: The good/bad labels become training data for a model that learns the morphology of good clustering — to generalize, not to over-fit this one dataset.
---

<GalaxySpiral />

<StatChips />

## Why this exists

Spiral galaxies wind their arms at a characteristic **pitch angle**, and that angle
correlates with the mass of the galaxy's central black hole. Measuring it well, at
scale, is how the [Spiral Graph](https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph-cluster-buster)
team hunts for rare **intermediate-mass black holes**.

The measurement starts with volunteers tracing arms. Those tracings are then
**clustered into individual arms** — and that clustering has knobs. Pick them badly
and arms merge or fragment; the pitch measurement inherits the error. The defaults
we use today work well, but they were chosen by hand.

**Cluster Buster** replaces that guesswork with evidence: sweep the clustering
hyperparameters, show the results to volunteers, and let their good/bad verdicts —
and a model trained on them — tell us what actually works.

<div class="cb-lead" style="margin-top: 1.5rem">

➜ **[The Project](/the-project)** — the science and the pipeline, end to end.
**[The Investigation](/investigation)** — the parameter grid and why these bounds.
**[Sets](/sets)** — live status of every upload set.

</div>
