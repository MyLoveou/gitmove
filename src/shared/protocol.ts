/** Shared contract between main, preload and renderer. */

export interface Envelope<T = unknown> {
  schema_version: number
  tool: string
  ok: boolean
  repo?: string | null
  data?: T
  error?: { code: string; message: string; cause?: string; steps?: string[] }
}

export interface ProjectRow {
  alias: string
  path: string
  group: string
  init: boolean
  status: string
}

export interface AuditRow {
  alias: string
  path: string
  exists: boolean
  status: string
  tracked_files: number
  tracked_bytes: number
  skip_paths: number
  links: number
  vendors: number
  worktrees: number
  env_steps: number
  depot_configured: boolean
  depot_age_days: number | null
  errors: number
  warns: number
  unreadable: number
  dep_label: string
  own_deps: number
}

export interface AppInfo {
  version: string
  platform: string
  python: string
  sidecar: string
}

export type Op =
  | { op: 'app.info' }
  | { op: 'projects.list' }
  | { op: 'audit.all' }
  | { op: 'doctor.one'; repo: string }

export const IPC_INVOKE = 'gitmove:invoke'
