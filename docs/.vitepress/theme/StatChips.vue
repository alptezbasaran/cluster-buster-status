<script setup lang="ts">
import { data } from '../data/sets.data'
const c = data.counts
const m = data.meta
const uploadedSubjects = data.sets
  .filter((s) => s.uploaded)
  .reduce((n, s) => n + (s.subjects || 0), 0)
const retiredPct = m ? Math.round((m.retired_subjects / m.subjects) * 100) : null
</script>

<template>
  <div class="cb-stats">
    <div class="cb-stat" style="--accent: var(--cb-magenta-light)">
      <div class="num">{{ c.total }}</div>
      <div class="label">Configs / sets</div>
    </div>
    <div class="cb-stat" style="--accent: var(--cb-amber)">
      <div class="num">{{ c.clustered }}</div>
      <div class="label">Clustered</div>
    </div>
    <div class="cb-stat" style="--accent: var(--cb-lime)">
      <div class="num">{{ c.uploaded }}</div>
      <div class="label">Uploaded</div>
    </div>
    <div class="cb-stat" style="--accent: var(--cb-pink)">
      <div class="num">{{ uploadedSubjects.toLocaleString() }}</div>
      <div class="label">Subjects live</div>
    </div>
    <div v-if="m" class="cb-stat" style="--accent: var(--cb-magenta-light)">
      <div class="num">{{ m.classifications.toLocaleString() }}</div>
      <div class="label">Classifications</div>
    </div>
    <div v-if="m" class="cb-stat" style="--accent: var(--cb-amber)">
      <div class="num">{{ retiredPct }}%</div>
      <div class="label">Subjects retired</div>
    </div>
  </div>
  <p v-if="m" class="cb-synced">
    Classification progress synced {{ m.synced }} — all {{ m.linked_subject_sets }} sets linked to the
    <a href="https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph-cluster-buster" target="_blank" rel="noreferrer">live workflow</a>.
  </p>
</template>

<style scoped>
.cb-synced {
  text-align: center;
  color: var(--vp-c-text-3);
  font-size: 0.82rem;
  margin-top: 0.5rem;
}
</style>
