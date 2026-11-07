import { app, shell } from 'electron'
import { copyFileSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { isAbsolute, join, normalize } from 'node:path'

import type {
  AppInfo,
  AssetStatusPayload,
  AssetTargetResult,
  AuditRow,
  AssetFile,
  BranchRefs,
  HookStatusPayload,
  MergeStatePayload,
  GraphNode,
  BranchRow,
  ChangeRow,
  DepRow,
  SyncCheck,
  CommitOutcome,
  MergePlanPayload,
  Op,
  ProjectRow,
  RevisionRow,
  WorkspaceStatus
} from '../shared/protocol'
import { logDir, logEvent, logFile } from './logger'
import { coreBinary, engineName, runCli, sidecarDescription } from './sidecar'

export interface OpResult<T = unknown> {
  ok: boolean
  data?: T
  error?: { code: string; message: string; steps?: string[] }
}


/** Files the UI may read or edit, relative to the workspace root. */
const EDITABLE_FILES = [
  '.gitignore',
  '.git/info/exclude',
  '.gitmove/config.toml',
  'workspace.toml',
  'workspace.lock.toml',
  'project.lock.toml'
]

function editablePath(workspace: string, relative: string): string {
  const normalized = normalize(relative).replace(/\\/g, '/')
  if (!EDITABLE_FILES.includes(normalized)) {
    throw Object.assign(new Error(`不允许编辑该文件: ${relative}`), { code: 'FILE_NOT_ALLOWED' })
  }
  return join(workspace, normalized)
}

async function call<T>(argv: string[], cwd?: string): Promise<T> {
  const envelope = await runCli<T>(argv, { cwd })
  if (!envelope.ok) {
    const error = envelope.error
    throw Object.assign(new Error(error?.message ?? 'CLI failed'), {
      code: error?.code ?? 'CLI_ERROR',
      steps: error?.steps ?? []
    })
  }
  return envelope.data as T
}

function requireCore(): void {
  if (!coreBinary()) {
    const error = new Error('该操作需要 Rust 核心：先运行 cargo build --release，或设置 GITMOVE_CORE') as Error & {
      code?: string
    }
    error.code = 'CORE_REQUIRED'
    throw error
  }
}

export async function handleOp(request: Op): Promise<OpResult> {
  const started = Date.now()
  try {
    switch (request.op) {
      case 'file.list': {
        return { ok: true, data: EDITABLE_FILES.map((file) => ({ path: file, exists: existsSync(join(request.workspace, file)) })) }
      }
      case 'file.read': {
        const path = editablePath(request.workspace, request.path)
        const exists = existsSync(path)
        return { ok: true, data: { path: request.path, exists, text: exists ? readFileSync(path, 'utf8') : '' } }
      }
      case 'file.write': {
        const path = editablePath(request.workspace, request.path)
        if (existsSync(path)) copyFileSync(path, path + '.bak')
        writeFileSync(path, request.text, 'utf8')
        logEvent('file.write', { path: request.path, bytes: request.text.length })
        return { ok: true, data: { path: request.path, bytes: request.text.length } }
      }
      case 'open.logs': {
        await shell.openPath(logDir())
        return { ok: true, data: { dir: logDir() } }
      }
      case 'open.workspace': {
        await shell.openPath(request.workspace)
        return { ok: true, data: { dir: request.workspace } }
      }
      case 'app.info': {
        const info: AppInfo = {
          version: app.getVersion(),
          platform: `${process.platform}-${process.arch}`,
          sidecar: sidecarDescription(),
          engine: engineName(),
          core: coreBinary()
        }
        return { ok: true, data: info }
      }
      case 'projects.list': {
        const rows = await call<ProjectRow[]>(['projects', 'list'])
        return { ok: true, data: rows }
      }
      case 'audit.all': {
        const rows = await call<AuditRow[]>(['audit', '--all'])
        return { ok: true, data: rows }
      }
      case 'doctor.one': {
        const data = await call<unknown>(['-C', request.repo, 'doctor'], request.repo)
        return { ok: true, data }
      }
      case 'rev.log': {
        requireCore()
        const rows = await call<RevisionRow[]>(['-C', request.workspace, 'rev', 'log', '--limit', String(request.limit ?? 50)])
        return { ok: true, data: rows }
      }
      case 'rev.show': {
        requireCore()
        const row = await call<RevisionRow>(['-C', request.workspace, 'rev', 'show', String(request.id)])
        return { ok: true, data: row }
      }
      case 'rev.commit': {
        requireCore()
        const argv = ['-C', request.workspace, 'commit', '-m', request.message]
        if (request.members) argv.push('--members')
        const outcome = await call<CommitOutcome>(argv)
        return { ok: true, data: outcome }
      }
      case 'rev.checkout': {
        requireCore()
        const argv = ['-C', request.workspace, 'checkout', String(request.id)]
        if (request.force) argv.push('--force')
        const outcome = await call<unknown>(argv)
        return { ok: true, data: outcome }
      }
      case 'ws.status': {
        requireCore()
        const status = await call<WorkspaceStatus>(['-C', request.workspace, 'ws', 'status'])
        return { ok: true, data: status }
      }
      case 'asset.status': {
        requireCore()
        const status = await call<AssetStatusPayload>(['-C', request.workspace, 'asset', 'status'])
        return { ok: true, data: status }
      }
      case 'asset.init': {
        requireCore()
        const argv = ['-C', request.workspace, 'asset', 'init']
        if (request.target) argv.push('--target', request.target)
        const results = await call<AssetTargetResult[]>(argv)
        return { ok: true, data: results }
      }
      case 'rev.checkout': {
        requireCore()
        const argv = ['-C', request.workspace, 'checkout', String(request.id)]
        if (request.force) argv.push('--force')
        const data = await call<unknown>(argv)
        return { ok: true, data }
      }
      case 'dep.list': {
        requireCore()
        const rows = await call<DepRow[]>(['-C', request.workspace, 'dep', 'list'])
        return { ok: true, data: rows }
      }
      case 'ws.branches': {
        requireCore()
        const rows = await call<BranchRow[]>(['-C', request.workspace, 'ws', 'branch-list'])
        return { ok: true, data: rows }
      }
      case 'ws.switch': {
        requireCore()
        const argv = ['-C', request.workspace, 'ws', 'branch-switch', request.name]
        if (request.member) argv.push('--member', request.member)
        const rows = await call<BranchRow[]>(argv)
        return { ok: true, data: rows }
      }
      case 'ws.branch.create': {
        requireCore()
        const rows = await call<BranchRow[]>([
          '-C',
          request.workspace,
          'ws',
          'branch-create',
          request.name,
          '--member',
          request.member
        ])
        return { ok: true, data: rows }
      }
      case 'ws.branch.refs': {
        requireCore()
        const names = await call<string[]>(['-C', request.workspace, 'ws', 'branch-refs', request.member])
        return { ok: true, data: names }
      }
      case 'member.commit': {
        requireCore()
        const data = await call<{ member: string; commit: string; branch: string }>([
          '-C',
          request.workspace,
          'ws',
          'member-commit',
          request.member,
          '-m',
          request.message
        ])
        return { ok: true, data }
      }
      case 'sync.check': {
        requireCore()
        const data = await call<SyncCheck>(['-C', request.workspace, 'sync', 'check'])
        return { ok: true, data }
      }
      case 'ws.refs': {
        requireCore()
        const data = await call<BranchRefs>(['-C', request.workspace, 'ws', 'refs'])
        return { ok: true, data }
      }
      case 'ws.add': {
        requireCore()
        const argv = [
          '-C',
          request.workspace,
          'ws',
          'add',
          request.name,
          '--path',
          request.path,
          '--role',
          request.role,
          '--strategy',
          request.strategy,
          '--source',
          request.source
        ]
        if (request.pin) argv.push('--pin', request.pin)
        if (request.track) argv.push('--track', request.track)
        const data = await call<unknown>(argv)
        return { ok: true, data }
      }
      case 'ws.contribute': {
        requireCore()
        const data = await call<unknown>(['-C', request.workspace, 'ws', 'contribute', request.member])
        return { ok: true, data }
      }
      case 'hook.status': {
        requireCore()
        const data = await call<HookStatusPayload>(['-C', request.workspace, 'hook', 'status'])
        return { ok: true, data }
      }
      case 'hook.install': {
        requireCore()
        const argv = ['-C', request.workspace, 'hook', 'install']
        for (const event of request.events) argv.push('--event', event)
        if (request.members) argv.push('--members')
        const data = await call<HookStatusPayload>(argv)
        return { ok: true, data }
      }
      case 'hook.uninstall': {
        requireCore()
        const argv = ['-C', request.workspace, 'hook', 'uninstall']
        for (const event of request.events) argv.push('--event', event)
        if (request.members) argv.push('--members')
        const data = await call<HookStatusPayload>(argv)
        return { ok: true, data }
      }
      case 'hook.add': {
        requireCore()
        const argv = ['-C', request.workspace, 'hook', 'add', '--event', request.event, '--command', request.command]
        if (!request.blocking) argv.push('--advisory')
        if (request.global) argv.push('--global')
        const data = await call<HookStatusPayload>(argv)
        return { ok: true, data }
      }
      case 'hook.remove': {
        requireCore()
        const argv = ['-C', request.workspace, 'hook', 'remove', '--event', request.event, '--command', request.command]
        if (request.global) argv.push('--global')
        const data = await call<HookStatusPayload>(argv)
        return { ok: true, data }
      }
      case 'hook.toggle': {
        requireCore()
        const argv = [
          '-C',
          request.workspace,
          'hook',
          request.enabled ? 'enable' : 'disable',
          '--event',
          request.event,
          '--command',
          request.command
        ]
        if (request.global) argv.push('--global')
        const data = await call<HookStatusPayload>(argv)
        return { ok: true, data }
      }
      case 'hook.run': {
        requireCore()
        const data = await call<unknown[]>(['-C', request.workspace, 'hook', 'run', request.event])
        return { ok: true, data }
      }
      case 'asset.test': {
        requireCore()
        const argv = ['-C', request.workspace, 'asset', 'test']
        if (request.target) argv.push('--target', request.target)
        const data = await call<unknown[]>(argv)
        return { ok: true, data }
      }
      case 'asset.files': {
        requireCore()
        const argv = ['-C', request.workspace, 'asset', 'files', request.snapshot]
        if (request.target) argv.push('--target', request.target)
        const data = await call<AssetFile[]>(argv)
        return { ok: true, data }
      }
      case 'asset.restore': {
        requireCore()
        const argv = ['-C', request.workspace, 'asset', 'restore', request.snapshot]
        if (request.target) argv.push('--target', request.target)
        for (const path of request.paths) argv.push('--path', path)
        if (request.to) argv.push('--to', request.to)
        const data = await call<unknown>(argv)
        return { ok: true, data }
      }
      case 'asset.state': {
        requireCore()
        const data = await call<MergeStatePayload | null>(['-C', request.workspace, 'asset', 'state'])
        return { ok: true, data }
      }
      case 'asset.resolve': {
        requireCore()
        const data = await call<MergeStatePayload>(['-C', request.workspace, 'asset', 'resolve', request.path, '--take', request.take])
        return { ok: true, data }
      }
      case 'asset.continue': {
        requireCore()
        const data = await call<MergeStatePayload>(['-C', request.workspace, 'asset', 'continue'])
        return { ok: true, data }
      }
      case 'ws.sync': {
        requireCore()
        const argv = ['-C', request.workspace, 'ws', 'sync']
        if (request.member) argv.push('--member', request.member)
        const data = await call<unknown[]>(argv)
        return { ok: true, data }
      }
      case 'ws.update': {
        requireCore()
        const argv = ['-C', request.workspace, 'ws', 'update']
        if (request.member) argv.push('--member', request.member)
        if (request.to) argv.push('--to', request.to)
        const data = await call<unknown[]>(argv)
        return { ok: true, data }
      }
      case 'graph': {
        requireCore()
        const argv = ['-C', request.workspace, 'graph', '--limit', String(request.limit ?? 200)]
        if (request.all) argv.push('--all')
        else if (request.branch) argv.push('--branch', request.branch)
        const data = await call<GraphNode[]>(argv)
        return { ok: true, data }
      }
      case 'logs.read': {
        const path = logFile()
        const text = existsSync(path) ? readFileSync(path, 'utf8') : ''
        const lines = text.split(/\r?\n/).filter(Boolean)
        const tail = lines.slice(-(request.lines ?? 200)).join('\n')
        return { ok: true, data: { path, text: tail, total: lines.length } }
      }
      case 'sync.pull': {
        requireCore()
        const argv = ['-C', request.workspace, 'sync', 'pull']
        if (request.fetch) argv.push('--fetch')
        if (request.mode === 'merge') argv.push('--merge')
        if (request.mode === 'rebase') argv.push('--rebase')
        const data = await call<unknown>(argv)
        return { ok: true, data }
      }
      case 'changes.list': {
        requireCore()
        const rows = await call<ChangeRow[]>(['-C', request.workspace, 'changes'])
        return { ok: true, data: rows }
      }
      case 'changes.discard': {
        requireCore()
        const argv = ['-C', request.workspace, 'discard']
        for (const item of request.selections) argv.push('--path', `${item.member}:${item.path}`)
        const data = await call<string[]>(argv)
        return { ok: true, data }
      }
      case 'rev.commitPaths': {
        requireCore()
        const argv = ['-C', request.workspace, 'commit', '-m', request.message]
        for (const item of request.selections) argv.push('--path', `${item.member}:${item.path}`)
        const data = await call<CommitOutcome>(argv)
        return { ok: true, data }
      }
      case 'config.save': {
        requireCore()
        const dir = mkdtempSync(join(tmpdir(), 'gitmove-config-'))
        const file = join(dir, 'config.toml')
        try {
          writeFileSync(file, request.toml, 'utf8')
          const data = await call<unknown>(['-C', request.workspace, 'config', 'import', file])
          return { ok: true, data }
        } finally {
          rmSync(dir, { recursive: true, force: true })
        }
      }
      case 'config.export': {
        requireCore()
        const data = await call<{ toml: string }>(['-C', request.workspace, 'config', 'export'])
        return { ok: true, data }
      }
      case 'rev.importGit': {
        requireCore()
        const argv = ['-C', request.workspace, 'rev', 'import-git']
        if (request.limit) argv.push('--limit', String(request.limit))
        const data = await call<{ imported: number }>(argv)
        return { ok: true, data }
      }
      case 'rev.rebuild': {
        requireCore()
        const data = await call<{ revisions: number }>(['-C', request.workspace, 'index', 'rebuild'])
        return { ok: true, data }
      }
      case 'asset.merge': {
        requireCore()
        const argv = [
          '-C',
          request.workspace,
          'asset',
          'merge',
          '--base',
          request.base,
          '--ours',
          request.ours,
          '--theirs',
          request.theirs
        ]
        if (request.target) argv.push('--target', request.target)
        if (request.apply) argv.push('--apply')
        if (request.force) argv.push('--force')
        const data = await call<MergePlanPayload>(argv)
        return { ok: true, data }
      }
      case 'asset.backup': {
        requireCore()
        const argv = ['-C', request.workspace, 'asset', 'backup']
        if (request.target) argv.push('--target', request.target)
        const outcome = await call<{ results: AssetTargetResult[]; partial: boolean }>(argv)
        return { ok: true, data: outcome }
      }
      default: {
        const exhaustive: never = request
        return { ok: false, error: { code: 'UNKNOWN_OP', message: `未知操作: ${JSON.stringify(exhaustive)}` } }
      }
    }
  } catch (error) {
    const err = error as Error & { code?: string; steps?: string[] }
    logEvent('op.error', { op: request.op, code: err.code ?? 'OP_FAILED', message: err.message, ms: Date.now() - started })
    return {
      ok: false,
      error: { code: err.code ?? 'OP_FAILED', message: err.message, steps: err.steps }
    }
  } finally {
    if (request.op !== 'app.info') logEvent('op.done', { op: request.op, ms: Date.now() - started })
  }
}
