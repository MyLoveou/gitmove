import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { join } from 'node:path'

import type { Envelope } from '../shared/protocol'

const DEFAULT_TIMEOUT_MS = 120_000

export function coreBinary(): string | null {
  const explicit = process.env.GITMOVE_CORE?.trim()
  if (explicit && existsSync(explicit)) return explicit
  const packaged = process.resourcesPath ? join(process.resourcesPath, 'core', 'gitmove-core.exe') : ''
  const candidates = [
    packaged,
    join(process.cwd(), 'target', 'release', 'gitmove-core.exe'),
    join(process.cwd(), 'target', 'debug', 'gitmove-core.exe')
  ].filter(Boolean)
  return candidates.find((candidate) => existsSync(candidate)) ?? null
}

export function engineName(): 'rust' {
  return 'rust'
}

export function sidecarDescription(): string {
  return `${coreBinary() ?? 'gitmove-core.exe (missing)'} (rust core)`
}

interface RunOptions {
  cwd?: string
  timeoutMs?: number
  env?: NodeJS.ProcessEnv
}

export class CliError extends Error {
  constructor(
    message: string,
    readonly code: string = 'CLI_FAILED',
    readonly stderr = ''
  ) {
    super(message)
  }
}

export async function runCli<T = unknown>(argv: string[], options: RunOptions = {}): Promise<Envelope<T>> {
  const core = coreBinary()
  if (!core) {
    throw new CliError('Rust 核心缺失：重新安装 gitmove，或设置 GITMOVE_CORE 指向 gitmove-core.exe', 'CORE_REQUIRED')
  }
  const fullArgs = [...argv, '--json']
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS

  return new Promise<Envelope<T>>((resolve, reject) => {
    const child = spawn(core, fullArgs, {
      cwd: options.cwd,
      env: { ...process.env, ...options.env },
      windowsHide: true
    })

    let stdout = ''
    let stderr = ''
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      child.kill()
      reject(new CliError(`core timed out after ${timeoutMs}ms`, 'CLI_TIMEOUT'))
    }, timeoutMs)

    child.stdout.on('data', (chunk: Buffer) => (stdout += chunk.toString('utf8')))
    child.stderr.on('data', (chunk: Buffer) => (stderr += chunk.toString('utf8')))

    child.on('error', (error) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      reject(new CliError(`无法启动核心：${error.message}`, 'CLI_SPAWN_FAILED'))
    })

    child.on('close', (code) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      const payload = extractEnvelope(stdout)
      if (payload) {
        resolve(payload)
        return
      }
      if (code === 2) {
        reject(new CliError(stderr.trim() || '环境缺失（退出码 2）', 'ENV_MISSING', stderr))
        return
      }
      reject(new CliError(stderr.trim() || `core 失败（退出码 ${code ?? 'null'}）`, 'CLI_NO_ENVELOPE', stderr))
    })
  })
}

export function extractEnvelope(text: string): Envelope | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  try {
    const parsed = JSON.parse(trimmed)
    return isEnvelope(parsed) ? parsed : null
  } catch {
    // keep looking
  }
  const lines = trimmed.split(/\r?\n/)
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim()
    if (!line.startsWith('{')) continue
    try {
      const parsed = JSON.parse(line)
      if (isEnvelope(parsed)) return parsed
    } catch {
      // ignore
    }
  }
  return null
}

function isEnvelope(value: unknown): value is Envelope {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return typeof record.tool === 'string' && 'ok' in record
}