<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { withBase } from 'vitepress'
import { data } from '../data/gallery.data'

const props = defineProps<{ default?: string }>()

const sets = data.sets
const selected = ref(props.default && data.galleries[props.default] ? props.default : sets[0])
const gallery = computed(() => data.galleries[selected.value])

const q = ref('')
const armFilter = ref('')
const sort = ref('arms')

// reset filters when switching sets (arm counts differ between configs)
watch(selected, () => {
  q.value = ''
  armFilter.value = ''
})

const armOptions = computed(() =>
  [...new Set(gallery.value.subjects.map((s) => s.arms))].sort((a, b) => a - b),
)

const subjects = computed(() => {
  const needle = q.value.trim()
  const list = gallery.value.subjects.filter((s) => {
    if (needle && !s.gid.includes(needle)) return false
    if (armFilter.value && String(s.arms) !== armFilter.value) return false
    return true
  })
  return [...list].sort((a, b) =>
    sort.value === 'gid'
      ? a.gid.localeCompare(b.gid)
      : sort.value === 'arms-d'
        ? b.arms - a.arms || a.gid.localeCompare(b.gid)
        : a.arms - b.arms || a.gid.localeCompare(b.gid),
  )
})

const img = (num: string, gid: string) => withBase(`/sets/${num}/${gid}.webp`)
const statusOf = (g: { live: boolean; state: string }) => (g.live ? 'live' : g.state)

const zooniverse = 'https://www.zooniverse.org/projects/astro-lab-ncmns/spiral-graph-cluster-buster'

// lightbox
const lb = ref<string | null>(null)
const lbGid = ref('')
const open = (gid: string) => {
  lb.value = img(gallery.value.num, gid)
  lbGid.value = gid
}
const close = () => (lb.value = null)
const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') close()
}
onMounted(() => window.addEventListener('keydown', onKey))
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="cb-gal">
    <div class="cb-gal-switch" role="tablist" aria-label="subject sets">
      <button
        v-for="s in sets"
        :key="s"
        class="cb-gal-pill"
        :class="{ on: s === selected }"
        role="tab"
        :aria-selected="s === selected"
        @click="selected = s"
      >
        <i class="cb-gal-dot" :class="statusOf(data.galleries[s])" />
        {{ data.galleries[s].num }}
        <span class="cb-gal-pill-n">{{ data.galleries[s].subjects.length }}</span>
      </button>
    </div>

    <header class="cb-gal-head">
      <div class="cb-gal-id">
        <span class="cb-gal-name">{{ gallery.set }}</span>
        <span class="cb-badge" :class="statusOf(gallery)">{{ statusOf(gallery) }}</span>
      </div>
      <div class="cb-gal-config">
        <code>agreement {{ gallery.config.agreement }}</code>
        <code>correction {{ gallery.config.correction }}</code>
        <code>trace_support {{ gallery.config.trace_support }}</code>
        <code>ratio_limit {{ gallery.config.ratio_limit }}</code>
      </div>
      <a v-if="gallery.live" class="cb-gal-cta" :href="zooniverse" target="_blank" rel="noopener">
        Classify this set ↗
      </a>
      <span v-else class="cb-gal-queued">queued — not yet on Zooniverse</span>
    </header>

    <div class="cb-gal-controls">
      <input v-model="q" placeholder="search gid…" />
      <select v-model="armFilter">
        <option value="">all arm counts</option>
        <option v-for="a in armOptions" :key="a" :value="String(a)">{{ a }} arms</option>
      </select>
      <select v-model="sort">
        <option value="arms">sort: arms ↑</option>
        <option value="arms-d">sort: arms ↓</option>
        <option value="gid">sort: gid</option>
      </select>
      <span class="cb-gal-count">
        showing <b>{{ subjects.length }}</b> / {{ gallery.subjects.length }} overlays
      </span>
    </div>

    <div class="cb-gal-grid">
      <figure v-for="s in subjects" :key="s.gid" class="cb-gal-card">
        <div class="cb-gal-imgwrap" @click="open(s.gid)">
          <img :src="img(gallery.num, s.gid)" :alt="s.gid" loading="lazy" width="592" height="592" />
          <span class="cb-gal-arms">{{ s.arms }} {{ s.arms === 1 ? 'arm' : 'arms' }}</span>
        </div>
        <figcaption class="cb-gal-meta">
          <span class="cb-gal-gid">{{ s.gid }}</span>
          <span class="cb-gal-links">
            <a v-if="s.sdss" :href="s.sdss" target="_blank" rel="noopener">SDSS</a>
            <a v-if="s.legacy" :href="s.legacy" target="_blank" rel="noopener">Legacy</a>
            <a v-if="s.leda" :href="s.leda" target="_blank" rel="noopener">LEDA</a>
          </span>
        </figcaption>
      </figure>
    </div>

    <div v-if="!subjects.length" class="cb-gal-empty">no overlays match</div>
  </div>

  <Teleport to="body">
    <div v-if="lb" class="cb-gal-lb" @click="close">
      <img :src="lb" :alt="lbGid" />
      <div class="cb-gal-lb-cap">{{ lbGid }}</div>
    </div>
  </Teleport>
</template>
