# The Project

Cluster Buster is one link in a longer chain that turns **volunteer arm tracings**
into **black-hole science**. This page walks the whole chain so the rest of the
site has context.

## The science goal

A spiral galaxy's arms wind at a **pitch angle** φ — the angle between an arm and a
circle around the galaxy's centre. Tightly-wound arms have small φ; open, flocculent
arms have large φ. Crucially, **φ correlates with the mass of the galaxy's central
supermassive black hole** (the M–φ relation). Measure φ accurately across many
galaxies and you can weigh their black holes photometrically — and flag the rare
**intermediate-mass black holes** that bridge stellar and supermassive scales.

The chain:

```
Volunteers trace arms   →   Cluster tracings into arms   →   Measure pitch φ   →   Black-hole mass
   (Spiral Graph)            (this is what we tune)           (log-spiral fit)      (M–φ relation)
```

## Where the tracings come from

[**Spiral Graph**](https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph)
is the original Zooniverse project: **8,400+ volunteers traced spiral arms on
20,000+ galaxy images.** Every galaxy ends up with dozens to hundreds of individual
arm tracings — overlapping strokes drawn by different people.

For this study we use a curated subset: a two-reviewer pass reduced the pool to
**859 accepted galaxies**, from which we drew the **500-galaxy Cluster Buster set**
(weighted toward galaxies with more arms — they're the interesting, harder cases).

## The step we're validating: clustering

Dozens of overlapping tracings per galaxy are not yet "arms." A clustering algorithm
groups them: it seeds on the longest tracing, absorbs every tracing that agrees with
it into one arm, then merges arms that overlap too much. The result is a handful of
clean, separated arms — each a consensus of many volunteers.

That algorithm has **hyperparameters**: how much agreement is needed to join an arm,
how much overlap triggers a merge, how many tracings an arm needs to count. Set them
well and the arms come out right. Set them badly and arms merge together or shatter
into fragments — and the downstream pitch angle is wrong.

## The task volunteers do here

The Cluster Buster Zooniverse project shows volunteers a clustered result and asks a
simple question: **did the algorithm correctly separate the arms — good or bad?**

Each subject is one galaxy's clustered overlay. We collect **15 verdicts per subject**
to get a confident label. Those labels do two jobs:

1. **Validate** which hyperparameter settings actually produce good clustering.
2. **Train a model** to recognize good clustering from the image alone — so it can
   generalize to galaxies and settings it has never seen.

## Who runs it

A collaboration between the **NC Museum of Natural Sciences** (Astronomy &
Astrophysics Research Lab) and **Coastal Carolina University** (Department of
Computing Sciences) — the museum side runs the citizen-science pipeline; the
university side builds the model.

➜ Next: **[The Investigation](/investigation)** — exactly which knobs we sweep, the
bounds, and why.
