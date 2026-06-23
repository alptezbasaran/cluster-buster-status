# The Project

Cluster Buster is one link in a chain that turns **volunteer arm tracings** into
**black-hole science**. The short version:

<div class="cb-flow">
  <span class="cb-flow-step"><b>Trace arms</b><span>Spiral Graph volunteers</span></span>
  <span class="cb-flow-arrow">→</span>
  <span class="cb-flow-step is-focus"><b>Cluster into arms</b><span>what we tune</span></span>
  <span class="cb-flow-arrow">→</span>
  <span class="cb-flow-step"><b>Measure pitch φ</b><span>log-spiral fit</span></span>
  <span class="cb-flow-arrow">→</span>
  <span class="cb-flow-step"><b>Black-hole mass</b><span>M–φ relation</span></span>
</div>

## The science goal

A spiral galaxy's arms wind at a **pitch angle** φ — tightly-wound arms have small φ,
open arms have large φ. Crucially, **φ correlates with the mass of the galaxy's central
black hole** (the M–φ relation), so measuring φ accurately across many galaxies lets us
weigh their black holes photometrically — and flag the rare **intermediate-mass black
holes** that bridge stellar and supermassive scales.

## Where the tracings come from

[**Spiral Graph**](https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph)
is the original Zooniverse project: **8,400+ volunteers traced spiral arms on 20,000+
galaxy images.** A two-reviewer pass reduced that pool to **859 accepted galaxies**, from
which we drew the **500-galaxy Cluster Buster set** (weighted toward many-armed galaxies —
the harder, more interesting cases).

## The step we're validating: clustering

Dozens of overlapping tracings per galaxy are not yet "arms." A clustering algorithm groups
them: it seeds on the longest tracing, absorbs every tracing that agrees with it into one arm,
then merges arms that overlap too much. Set its **hyperparameters** well and the arms come out
clean; set them badly and arms merge or shatter — and the downstream pitch angle is wrong.

## The task volunteers do here

The Cluster Buster Zooniverse project shows volunteers a clustered result and asks one question:
**did the algorithm correctly separate the arms — good or bad?** We collect **15 verdicts per
subject**, and those labels do two jobs:

1. **Validate** which hyperparameter settings actually produce good clustering.
2. **Train a model** to recognize good clustering from the image alone, so it can generalize to
   galaxies and settings it has never seen.

➜ Next: **[The Investigation](/investigation)** — exactly which knobs we sweep, the bounds, and why.
