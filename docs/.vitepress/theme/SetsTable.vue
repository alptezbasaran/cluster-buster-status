<script setup lang="ts">
import { ref, computed } from 'vue'
import { data } from '../data/sets.data'

const q = ref('')
const stateFilter = ref('all')

const rows = computed(() =>
  data.sets.filter((s) => {
    if (stateFilter.value !== 'all' && s.state !== stateFilter.value) return false
    if (q.value) {
      const needle = q.value.trim()
      const hay = `${s.set} ${s.agreement} ${s.correction} ${s.ratio}`
      if (!hay.includes(needle)) return false
    }
    return true
  })
)
</script>

<template>
  <div class="cb-sets-controls">
    <input v-model="q" placeholder="search set / agreement / correction…" />
    <select v-model="stateFilter">
      <option value="all">all states</option>
      <option value="planned">planned</option>
      <option value="clustered">clustered</option>
      <option value="uploaded">uploaded</option>
    </select>
    <span style="color: var(--vp-c-text-2); font-size: 0.85rem">
      {{ rows.length }} / {{ data.sets.length }} sets
    </span>
  </div>

  <div class="cb-table-wrap">
    <table class="cb-sets">
      <thead>
        <tr>
          <th>Set</th>
          <th>Agree</th>
          <th>Corr</th>
          <th>Ratio</th>
          <th>Status</th>
          <th>Subjects</th>
          <th>Classifications</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in rows" :key="s.set" :class="{ 'anchor-row': s.n === 1 }">
          <td class="set-id">{{ s.set }}</td>
          <td>{{ s.agreement }}</td>
          <td>{{ s.correction }}</td>
          <td>{{ s.ratio }}</td>
          <td><span class="cb-badge" :class="s.state">{{ s.state }}</span></td>
          <td>{{ s.subjects ?? '—' }}</td>
          <td>{{ s.classifications || '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
