<script setup lang="ts">
import { data } from '../data/sets.data'
const c = data.counts
const m = data.meta
const subjectsIn = (state: string) =>
  data.sets.filter((s) => s.state === state).reduce((n, s) => n + (s.subjects || 0), 0)
const classifiedSubjects = subjectsIn('complete')
const openSubjects = subjectsIn('uploaded')
const retiredPct = m ? Math.round((m.retired_subjects / m.subjects) * 100) : null
const building = c.uploaded + c.complete < c.total
const finished = !!(m && m.finished_at && m.retired_subjects === m.subjects)
</script>

<template>
  <div class="cb-stats">
    <div class="cb-stat" style="--accent: var(--cb-magenta-light)">
      <div class="num">{{ c.total }}</div>
      <div class="label">Configs / sets</div>
    </div>
    <div v-if="building" class="cb-stat" style="--accent: var(--cb-amber)">
      <div class="num">{{ c.clustered + c.uploaded + c.complete }}</div>
      <div class="label">Clustered</div>
    </div>
    <div v-if="building" class="cb-stat" style="--accent: var(--cb-lime)">
      <div class="num">{{ c.uploaded + c.complete }}</div>
      <div class="label">Uploaded</div>
    </div>
    <div v-if="classifiedSubjects" class="cb-stat" style="--accent: var(--cb-pink)">
      <div class="num">{{ classifiedSubjects.toLocaleString() }}</div>
      <div class="label">Subjects classified</div>
    </div>
    <div v-if="openSubjects" class="cb-stat" style="--accent: var(--cb-pink-soft)">
      <div class="num">{{ openSubjects.toLocaleString() }}</div>
      <div class="label">Subjects awaiting verdicts</div>
    </div>
    <div v-if="m" class="cb-stat" style="--accent: var(--cb-magenta-light)">
      <div class="num">{{ m.classifications.toLocaleString() }}</div>
      <div class="label">Classifications</div>
    </div>
    <div v-if="m && m.volunteers" class="cb-stat" style="--accent: var(--cb-lime)">
      <div class="num">{{ m.volunteers.toLocaleString() }}</div>
      <div class="label">Volunteers</div>
    </div>
    <div v-if="m" class="cb-stat" style="--accent: var(--cb-amber)">
      <div class="num">{{ retiredPct }}%</div>
      <div class="label">Subjects retired</div>
    </div>
  </div>
  <p v-if="m" class="cb-synced">
    <template v-if="finished">
      Classification finished {{ m.finished_at }}: every subject collected its 15 verdicts.
      <template v-if="m.project_state === 'paused'">The project is paused while the next batch is prepared.</template>
      Synced {{ m.synced }}.
    </template>
    <template v-else>
      Classification progress synced {{ m.synced }} — {{ m.linked_subject_sets }} subject sets linked to the
      <a href="https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph-cluster-buster" target="_blank" rel="noreferrer">live workflow</a>.
    </template>
    Workflow totals include the attention-check subjects, which are excluded from the science.
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
