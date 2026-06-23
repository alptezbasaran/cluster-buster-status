<script setup lang="ts">
import { data } from '../data/sets.data'
import type { SetRow } from '../data/sets.data'

// Phase-1 grid axes (see investigation.md). 9 × 7 × 2 = 126 configs.
const agreements = [50, 55, 60, 65, 70, 75, 80, 85, 90] // rows  (agreement_threshold)
const corrections = [50, 55, 60, 65, 70, 75, 80] //        cols  (correction_agreement)
const ratios = [1.0, 1.5]

const byKey = new Map<string, SetRow>()
for (const s of data.sets) byKey.set(`${s.ratio}|${s.agreement}|${s.correction}`, s)

const cell = (ratio: number, agreement: number, correction: number) =>
  byKey.get(`${ratio}|${agreement}|${correction}`)

function title(s: SetRow | undefined): string {
  if (!s) return 'unconfigured'
  const subj = s.subjects != null ? ` · ${s.subjects} subjects` : ''
  return `${s.set} · agreement ${s.agreement} · correction ${s.correction} · ${s.state}${subj}`
}

const c = data.counts
const legend = [
  { state: 'planned', label: 'planned', n: c.planned },
  { state: 'clustered', label: 'clustered', n: c.clustered },
  { state: 'uploaded', label: 'uploaded', n: c.uploaded },
]
</script>

<template>
  <div class="cb-sweep">
    <div class="cb-sweep-panels">
      <section class="cb-sweep-panel" v-for="r in ratios" :key="r">
        <header class="cb-sweep-head">
          <span class="cb-sweep-title">ratio_limit {{ r.toFixed(1) }}</span>
          <span class="cb-sweep-sub">63 configs</span>
        </header>

        <div class="cb-sweep-grid" role="grid" :aria-label="`ratio limit ${r}`">
          <div class="cb-sweep-corner" />
          <div class="cb-sweep-colhead" v-for="col in corrections" :key="col">{{ col }}</div>

          <template v-for="row in agreements" :key="row">
            <div class="cb-sweep-rowhead">{{ row }}</div>
            <div
              v-for="col in corrections"
              :key="col"
              class="cb-sweep-cell"
              :class="[cell(r, row, col)?.state || 'empty', { 'is-anchor': cell(r, row, col)?.n === 1 }]"
              :title="title(cell(r, row, col))"
              role="gridcell"
            />
          </template>
        </div>
      </section>
    </div>

    <div class="cb-sweep-foot">
      <div class="cb-sweep-legend">
        <span class="cb-sweep-key" v-for="l in legend" :key="l.state">
          <i class="cb-sweep-swatch" :class="l.state" />{{ l.label }}
          <b>{{ l.n }}</b>
        </span>
        <span class="cb-sweep-key"><i class="cb-sweep-anchor">★</i>anchor (cluster-buster-001)</span>
      </div>
      <p class="cb-sweep-axes">
        rows = <code>agreement_threshold</code> (50–90) · columns =
        <code>correction_agreement</code> (50–80) · two panels =
        <code>ratio_limit</code> 1.0 / 1.5
      </p>
    </div>
  </div>
</template>
