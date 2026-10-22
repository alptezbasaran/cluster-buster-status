import { readFileSync, existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))

// Build-time loader: merges the config files (phase1-configs.csv = the 126-config
// grid, phase2-configs.csv = the 64-config sample; repo root) with per-set
// run/upload status (set-status.json). Re-runs when any of them changes.
const CONFIG_FILES: [string, 1 | 2][] = [
  ['../../../phase1-configs.csv', 1],
  ['../../../phase2-configs.csv', 2],
]

function readConfigs(file: string): Record<string, string>[] {
  const path = resolve(here, file)
  if (!existsSync(path)) return []
  const [header, ...lines] = readFileSync(path, 'utf-8').trim().split(/\r?\n/)
  const cols = header.split(',')
  return lines.map((line) => {
    const v = line.split(',')
    const row: Record<string, string> = {}
    cols.forEach((c, i) => (row[c] = v[i]))
    return row
  })
}

type State = 'planned' | 'clustered' | 'uploaded' | 'complete'

export default {
  watch: ['./set-status.json', ...CONFIG_FILES.map(([f]) => f)],
  load() {
    const status = JSON.parse(readFileSync(resolve(here, './set-status.json'), 'utf-8'))

    const sets = CONFIG_FILES.flatMap(([file, phase]) =>
      readConfigs(file).map((row) => {
        const st = status[row.set] || {}
        const state: State =
          st.uploaded && st.completeness >= 1
            ? 'complete'
            : st.uploaded
              ? 'uploaded'
              : st.clustered
                ? 'clustered'
                : 'planned'
        return {
          set: row.set,
          n: Number(row.set.split('-').pop()),
          phase,
          wave: row.wave ? Number(row.wave) : null,
          agreement: Number(row.agreement_threshold),
          correction: Number(row.correction_agreement),
          ratio: Number(row.ratio_limit),
          traceSupport: Number(row.trace_support),
          vanillaBlur: Number(row.vanilla_blur),
          correctionBlur: Number(row.arm_correction_blur),
          clustered: !!st.clustered,
          uploaded: !!st.uploaded,
          live: !!st.live,
          hash: st.hash || null,
          subjects: st.subjects ?? null,
          noArms: st.no_arms ?? null,
          classifications: st.classifications ?? 0,
          retired: st.retired ?? null,
          completeness: st.completeness ?? null,
          state,
        }
      })
    )

    const meta = status._meta || null

    const countStates = (rows: typeof sets) => ({
      total: rows.length,
      planned: rows.filter((s) => s.state === 'planned').length,
      clustered: rows.filter((s) => s.state === 'clustered').length,
      uploaded: rows.filter((s) => s.state === 'uploaded').length,
      complete: rows.filter((s) => s.state === 'complete').length,
    })
    const counts = countStates(sets)
    const phaseCounts = {
      1: countStates(sets.filter((s) => s.phase === 1)),
      2: countStates(sets.filter((s) => s.phase === 2)),
    }

    return { sets, counts, phaseCounts, meta }
  },
}

export interface SetRow {
  set: string
  n: number
  phase: 1 | 2
  wave: number | null
  agreement: number
  correction: number
  ratio: number
  traceSupport: number
  vanillaBlur: number
  correctionBlur: number
  clustered: boolean
  uploaded: boolean
  live: boolean
  hash: string | null
  subjects: number | null
  noArms: number | null
  classifications: number
  retired: number | null
  completeness: number | null
  state: State
}
type Counts = Record<'total' | 'planned' | 'clustered' | 'uploaded' | 'complete', number>
export declare const data: {
  sets: SetRow[]
  counts: Counts
  phaseCounts: Record<1 | 2, Counts>
  meta: {
    workflow_id: string
    workflow_active: boolean
    linked_subject_sets: number
    classifications: number
    retired_subjects: number
    subjects: number
    volunteers?: number
    project_state?: string
    finished_at?: string | null
    synced: string
  } | null
}
