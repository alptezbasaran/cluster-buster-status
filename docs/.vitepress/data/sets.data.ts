import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))

// Build-time loader: merges the config grid (phase1-configs.csv, repo root) with
// per-set run/upload status (set-status.json). Re-runs on either file changing.
export default {
  watch: ['./set-status.json', '../../../phase1-configs.csv'],
  load() {
    const csv = readFileSync(resolve(here, '../../../phase1-configs.csv'), 'utf-8').trim()
    const status = JSON.parse(readFileSync(resolve(here, './set-status.json'), 'utf-8'))
    const [header, ...lines] = csv.split(/\r?\n/)
    const cols = header.split(',')

    const sets = lines.map((line) => {
      const v = line.split(',')
      const row: Record<string, string> = {}
      cols.forEach((c, i) => (row[c] = v[i]))
      const st = status[row.set] || {}
      const state = st.uploaded ? 'uploaded' : st.clustered ? 'clustered' : 'planned'
      return {
        set: row.set,
        n: Number(row.set.split('-').pop()),
        agreement: Number(row.agreement_threshold),
        correction: Number(row.correction_agreement),
        ratio: Number(row.ratio_limit),
        clustered: !!st.clustered,
        uploaded: !!st.uploaded,
        live: !!st.live,
        hash: st.hash || null,
        subjects: st.subjects ?? null,
        classifications: st.classifications ?? 0,
        retired: st.retired ?? null,
        completeness: st.completeness ?? null,
        state,
      }
    })

    const meta = status._meta || null

    const counts = {
      total: sets.length,
      planned: sets.filter((s) => s.state === 'planned').length,
      clustered: sets.filter((s) => s.state === 'clustered').length,
      uploaded: sets.filter((s) => s.state === 'uploaded').length,
    }

    return { sets, counts, meta }
  },
}

export interface SetRow {
  set: string
  n: number
  agreement: number
  correction: number
  ratio: number
  clustered: boolean
  uploaded: boolean
  live: boolean
  hash: string | null
  subjects: number | null
  classifications: number
  retired: number | null
  completeness: number | null
  state: 'planned' | 'clustered' | 'uploaded'
}
export declare const data: {
  sets: SetRow[]
  counts: Record<string, number>
  meta: {
    workflow_id: string
    workflow_active: boolean
    linked_subject_sets: number
    classifications: number
    retired_subjects: number
    subjects: number
    synced: string
  } | null
}
