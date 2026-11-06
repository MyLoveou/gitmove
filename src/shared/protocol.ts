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

export interface AssetTarget {
  name: string
  kind: string
  repo: string
  priority: number
  enabled: boolean
  restic: boolean
}

export interface AssetSnapshot {
  target: string
  snapshot_id: string
  files: number
  bytes: number
  created_at: string
  revision_id: number | null
}

export interface AssetStatusPayload {
  restic_version: string | null
  targets: AssetTarget[]
  snapshots: AssetSnapshot[]
}

export interface AssetTargetResult {
  target: string
  ok: boolean
  snapshot_id: string | null
  files: number
  bytes: number
  message: string
}

export interface ChangeRow {
  member: string
  code: string
  path: string
}

export interface BranchRow {
  member: string
  branch: string
}

export interface BranchRefs {
  local: string[]
  remote: string[]
}

export interface GraphNode {
  sha: string
  short: string
  parents: string[]
  refs: string[]
  subject: string
  author: string
  date: string
}

export interface SyncCheck {
  dirty: string[]
  ahead: number
  behind: number
  upstream: string | null
}

export interface DepRow {
  name: string
  kind: string
  ref: string | null
  commit: string | null
  installed: string | null
  drift: boolean
  in_effect: boolean
  label: string
}

export interface MergeItem {
  path: string
  action: string
}

export interface MergeConflict {
  path: string
  reason: string
}

export interface MergePlanPayload {
  base: string
  ours: string
  theirs: string
  merged: MergeItem[]
  conflicts: MergeConflict[]
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
  | { op: 'asset.status'; workspace: string }
  | { op: 'asset.init'; workspace: string; target?: string }
  | { op: 'asset.backup'; workspace: string; target?: string }
  | { op: 'config.export'; workspace: string }
  | { op: 'config.save'; workspace: string; toml: string }
  | { op: 'rev.checkout'; workspace: string; id: number; force?: boolean }
  | { op: 'dep.list'; workspace: string }
  | { op: 'ws.branches'; workspace: string }
  | { op: 'ws.switch'; workspace: string; name: string }
  | { op: 'sync.check'; workspace: string }
  | { op: 'sync.pull'; workspace: string; fetch?: boolean; mode?: 'merge' | 'rebase' }
  | { op: 'ws.refs'; workspace: string }
  | { op: 'ws.sync'; workspace: string; member?: string }
  | { op: 'ws.update'; workspace: string; member?: string; to?: string }
  | { op: 'graph'; workspace: string; limit?: number; branch?: string; all?: boolean }
  | { op: 'logs.read'; lines?: number }
  | { op: 'rev.importGit'; workspace: string; limit?: number }
  | { op: 'file.list'; workspace: string }
  | { op: 'file.read'; workspace: string; path: string }
  | { op: 'file.write'; workspace: string; path: string; text: string }
  | { op: 'open.logs' }
  | { op: 'open.workspace'; workspace: string }
  | { op: 'changes.list'; workspace: string }
  | { op: 'changes.discard'; workspace: string; selections: { member: string; path: string }[] }
  | { op: 'rev.commitPaths'; workspace: string; message: string; selections: { member: string; path: string }[] }
  | { op: 'rev.rebuild'; workspace: string }
  | {
      op: 'asset.merge'
      workspace: string
      base: string
      ours: string
      theirs: string
      target?: string
      apply?: boolean
      force?: boolean
    }

export const IPC_INVOKE = 'gitmove:invoke'
