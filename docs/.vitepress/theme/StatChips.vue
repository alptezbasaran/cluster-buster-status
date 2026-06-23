<script setup lang="ts">
import { data } from '../data/sets.data'
const c = data.counts
const uploadedSubjects = data.sets
  .filter((s) => s.uploaded)
  .reduce((n, s) => n + (s.subjects || 0), 0)
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
  </div>
</template>
