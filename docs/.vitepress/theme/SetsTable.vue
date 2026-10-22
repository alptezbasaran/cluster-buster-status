<script setup lang="ts">
import { ref, computed } from 'vue'
import { data } from '../data/sets.data'

const q = ref('')
const stateFilter = ref('all')
const phaseFilter = ref('all')

const rows = computed(() =>
  data.sets.filter((s) => {
    if (stateFilter.value !== 'all' && s.state !== stateFilter.value) return false
    if (phaseFilter.value !== 'all' && String(s.phase) !== phaseFilter.value) return false
    if (q.value) {
      const needle = q.value.trim()
      const hay = `${s.set} ${s.agreement} ${s.correction} ${s.ratio} ${s.traceSupport} ${s.vanillaBlur} ${s.correctionBlur}`
      if (!hay.includes(needle)) return false
    }
    return true
  })
)
</script>

<template>
  <div class="cb-sets-controls">
    <input v-model="q" placeholder="search set / knob value…" />
    <select v-model="phaseFilter">
      <option value="all">both phases</option>
      <option value="1">phase 1</option>
      <option value="2">phase 2</option>
    </select>
    <select v-model="stateFilter">
      <option value="all">all states</option>
      <option value="planned">planned</option>
      <option value="clustered">clustered</option>
      <option value="uploaded">uploaded</option>
      <option value="complete">complete</option>
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
          <th>Phase</th>
          <th>Agree</th>
          <th>Corr</th>
          <th>Ratio</th>
          <th title="trace_support">Supp</th>
          <th title="vanilla.blur">V.blur</th>
          <th title="arm_correction.blur">C.blur</th>
          <th>Status</th>
          <th>Subjects</th>
          <th title="galaxies whose clustering has no arm: counted unsuccessful, not uploaded">No arm</th>
          <th>Retired</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in rows" :key="s.set" :class="{ 'anchor-row': s.n === 1 }">
          <td class="set-id">{{ s.set }}</td>
          <td>{{ s.phase }}<span v-if="s.wave" class="retired-pct">·w{{ s.wave }}</span></td>
          <td>{{ s.agreement }}</td>
          <td>{{ s.correction }}</td>
          <td>{{ s.ratio }}</td>
          <td>{{ s.traceSupport }}</td>
          <td>{{ s.vanillaBlur }}</td>
          <td>{{ s.correctionBlur }}</td>
          <td><span class="cb-badge" :class="s.state">{{ s.state }}</span></td>
          <td>{{ s.subjects ?? '—' }}</td>
          <td>{{ s.noArms ?? '—' }}</td>
          <td>
            <template v-if="s.retired != null && s.subjects">
              {{ s.retired.toLocaleString() }}
              <span class="retired-pct">{{ Math.round((s.retired / s.subjects) * 100) }}%</span>
            </template>
            <template v-else>—</template>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.retired-pct {
  color: var(--vp-c-text-3);
  font-size: 0.8em;
  margin-left: 0.35em;
}
</style>
