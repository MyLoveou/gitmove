import { app } from 'electron'

import type {
  AppInfo,
  AssetStatusPayload,
  AssetTargetResult,
  AuditRow,
  CommitOutcome,
  MergePlanPayload,
  Op,
  ProjectRow,
  RevisionRow,
  WorkspaceStatus
} from '../shared/protocol'
import { coreBinary, engineName, runCli, sidecarDescription } from './sidecar'

export interface OpResult<T = unknown> {
  ok: boolean
  data?: T
  error?: { code: string; message: string; steps?: string[] }
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
  try {
    switch (request.op) {
      case 'app.info': {
        const info: AppInfo = {
          version: app.getVersion(),
          platform: `${process.platform}-${process.arch}`,
          python: 'not required',
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
      case 'config.export': {
        requireCore()
        const data = await call<{ toml: string }>(['-C', request.workspace, 'config', 'export'])
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
    return {
      ok: false,
      error: { code: err.code ?? 'OP_FAILED', message: err.message, steps: err.steps }
    }
  }
}
