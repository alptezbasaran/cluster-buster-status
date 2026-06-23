import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))

// Build-time loader: bundles every committed per-set gallery (set-NNN.json,
// produced by build_gallery.py) into a map keyed by set name, annotated with
// live/upload status from set-status.json. Re-runs when any input changes.
export default {
  watch: ['./set-*.json', './set-status.json'],
  load(): { galleries: Record<string, Gallery>; sets: string[] } {
    const status = JSON.parse(readFileSync(resolve(here, 'set-status.json'), 'utf-8'))
    const files = readdirSync(here)
      .filter((f) => /^set-\d+\.json$/.test(f))
      .sort()
    const galleries: Record<string, Gallery> = {}
    for (const f of files) {
      const g = JSON.parse(readFileSync(resolve(here, f), 'utf-8')) as Gallery
      const st = status[g.set] || {}
      g.live = !!st.live
      g.state = st.uploaded ? 'uploaded' : st.clustered ? 'clustered' : 'planned'
      g.classifications = st.classifications ?? 0
      galleries[g.set] = g
    }
    return { galleries, sets: Object.keys(galleries) }
  },
}

export interface Subject {
  gid: string
  arms: number
  sdss: string
  legacy: string
  leda: string
}
export interface Gallery {
  set: string
  num: string
  hash: string
  config: {
    agreement: string
    correction: string
    trace_support: string
    longest_arm_support: string
    ratio_limit: string
  }
  subjects: Subject[]
  live: boolean
  state: 'planned' | 'clustered' | 'uploaded'
  classifications: number
}
export declare const data: { galleries: Record<string, Gallery>; sets: string[] }
