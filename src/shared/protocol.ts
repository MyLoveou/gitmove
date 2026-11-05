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

export interface RevisionMember {
  member: string
  commit: string
  dirty: boolean
}

export interface RevisionRow {
  id: number
  status: string
  git_commit: string | null
  snapshot: string | null
  message: string
  created_at: string
  branch: string | null
  parents: number[]
  members: RevisionMember[]
}

export interface CommitOutcome {
  revision: number
  git_commit: string | null
  members_committed: string[]
  dirty_members: string[]
  trailer_written: boolean
}

export interface MemberStatus {
  name: string
  path: string
  role: string
  strategy: string
  exists: boolean
  head: string | null
  pin: string | null
  dirty: boolean
  missing: boolean
}

export interface WorkspaceStatus {
  name: string
  root: string
  declared: boolean
  members: MemberStatus[]
}

export interface AppInfo {
  version: string
  platform: string
  python: string
  sidecar: string
  engine: 'rust' | 'python'
  core: string | null
}

export type Op =
  | { op: 'app.info' }
  | { op: 'projects.list' }
  | { op: 'audit.all' }
  | { op: 'doctor.one'; repo: string }
  | { op: 'rev.log'; workspace: string; limit?: number }
  | { op: 'rev.show'; workspace: string; id: number }
  | { op: 'rev.commit'; workspace: string; message: string; members?: boolean }
  | { op: 'rev.checkout'; workspace: string; id: number; force?: boolean }
  | { op: 'ws.status'; workspace: string }

export const IPC_INVOKE = 'gitmove:invoke'
