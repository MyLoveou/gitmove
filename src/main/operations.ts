import { app } from 'electron'

import {
  type AppInfo,
  type AuditRow,
  type Op,
  type ProjectRow
} from '../shared/protocol'
import { runCli, sidecarDescription } from './sidecar'

export interface OpResult<T = unknown> {
  ok: boolean
  data?: T
  error?: { code: string; message: string; steps?: string[] }
}

async function call<T>(key: string, argv: string[], cwd?: string): Promise<T> {
  const envelope = await runCli<T>(argv, { cwd })
  if (!envelope.ok) {
    const error = envelope.error
    throw Object.assign(new Error(error?.message ?? `${key} failed`), {
      code: error?.code ?? 'CLI_ERROR',
      steps: error?.steps ?? []
    })
  }
  return envelope.data as T
}

export async function handleOp(request: Op): Promise<OpResult> {
  try {
    switch (request.op) {
      case 'app.info': {
        const info: AppInfo = {
          version: app.getVersion(),
          platform: `${process.platform}-${process.arch}`,
          python: process.env.GITMOVE_PYTHON ?? 'python',
          sidecar: sidecarDescription()
        }
        return { ok: true, data: info }
      }
      case 'projects.list': {
        const rows = await call<ProjectRow[]>('projects.list', ['projects', 'list'])
        return { ok: true, data: rows }
      }
      case 'audit.all': {
        const rows = await call<AuditRow[]>('audit.all', ['audit', '--all'])
        return { ok: true, data: rows }
      }
      case 'doctor.one': {
        const data = await call<unknown>('doctor.one', ['-C', request.repo, 'doctor'], request.repo)
        return { ok: true, data }
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
