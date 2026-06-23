<script setup lang="ts">
// A parametric logarithmic-spiral galaxy: N arms, brand-coloured, slow-rotating.
const N = 6
const colors = ['#c050c2', '#8dc63f', '#fbb040', '#46a1eb', '#ec008c', '#a8d666']
const cx = 200
const cy = 200
const a = 4
const b = 0.205
const turns = 2.55

function armPath(offset: number): string {
  const pts: string[] = []
  for (let t = 0; t <= turns * Math.PI * 2; t += 0.1) {
    const r = a * Math.exp(b * t)
    const ang = t + offset
    pts.push(`${(cx + r * Math.cos(ang)).toFixed(1)},${(cy + r * Math.sin(ang)).toFixed(1)}`)
  }
  return 'M' + pts.join(' L')
}

const arms = Array.from({ length: N }, (_, k) => ({
  d: armPath((k * 2 * Math.PI) / N),
  color: colors[k % colors.length],
}))
</script>

<template>
  <div class="cb-spiral-wrap">
    <svg class="cb-spiral" viewBox="0 0 400 400" role="img" aria-label="Spiral galaxy with coloured arms">
      <defs>
        <radialGradient id="cbCore" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.9" />
          <stop offset="35%" stop-color="#fbb040" stop-opacity="0.5" />
          <stop offset="100%" stop-color="#92278f" stop-opacity="0" />
        </radialGradient>
      </defs>
      <circle :cx="cx" :cy="cy" r="46" fill="url(#cbCore)" />
      <path v-for="(arm, i) in arms" :key="i" class="arm" :d="arm.d" :stroke="arm.color" />
    </svg>
  </div>
</template>
