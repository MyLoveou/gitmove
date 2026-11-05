import { spawn } from 'node:child_process'
import { existsSync } from 'node:fs'
import { delimiter, join } from 'node:path'

import type { Envelope } from '../shared/protocol'

const DEFAULT_TIMEOUT_MS = 120_000

export function pythonCommand(): string {
  return process.env.GITMOVE_PYTHON?.trim() || 'python'
}

/** Locate the Rust core binary (M2+). Env wins; then the repo's cargo output. */
export function coreBinary(): string | null {
  const explicit = process.env.GITMOVE_CORE?.trim()
  if (explicit && existsSync(explicit)) return explicit
  const candidates = [
    join(process.cwd(), 'target', 'release', 'gitmove-core.exe'),
    join(process.cwd(), 'target', 'debug', 'gitmove-core.exe')
  ]
  return candidates.find((candidate) => existsSync(candidate)) ?? null
}

export function engineName(): 'rust' | 'python' {
  return coreBinary() ? 'rust' : 'python'
}

/** Locate the CLI entry for the M1 bridge (Python implementation). */
export function resolveCli(): { command: string; args: string[] } {
  const command = pythonCommand()
  return { command, args: ['-m', 'gitmove'] }
}

export function sidecarDescription(): string {
  const core = coreBinary()
  if (core) return `${core} (rust core)`
  const { command, args } = resolveCli()
  const venv = join(process.cwd(), '.venv', 'Scripts', 'python.exe')
  const hint = !process.env.GITMOVE_PYTHON && !existsSync(venv) ? ' (set GITMOVE_PYTHON to pin a venv)' : ''
  return `${command} ${args.join(' ')}${hint}`
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

/** Run the CLI with --json and parse the shared envelope from stdout. */
export async function runCli<T = unknown>(argv: string[], options: RunOptions = {}): Promise<Envelope<T>> {
  const core = coreBinary()
  const { command, args } = core
    ? { command: core, args: [] as string[] }
    : resolveCli()
  const fullArgs = [...args, ...argv, '--json']
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS

  return new Promise<Envelope<T>>((resolve, reject) => {
    const child = spawn(command, fullArgs, {
      cwd: options.cwd,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8', ...options.env },
      windowsHide: true
    })

    let stdout = ''
    let stderr = ''
    let settled = false
    const timer = setTimeout(() => {
      if (settled) return
      settled = true
      child.kill()
      reject(new CliError(`CLI timed out after ${timeoutMs}ms: ${command} ${fullArgs.join(' ')}`, 'CLI_TIMEOUT'))
    }, timeoutMs)

    child.stdout.on('data', (chunk: Buffer) => (stdout += chunk.toString('utf8')))
    child.stderr.on('data', (chunk: Buffer) => (stderr += chunk.toString('utf8')))

    child.on('error', (error) => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      reject(new CliError(`无法启动 CLI（${command}）：${error.message}`, 'CLI_SPAWN_FAILED'))
    })

    child.on('close', (code) => {
      if (settled) return
      settled = true
      clearTimeout(timer)

      const payload = extractEnvelope(stdout)
      if (payload) {
        // 1 = user-level error, still a valid envelope; 0 = success.
        resolve(payload)
        return
      }
      if (code === 2) {
        reject(new CliError(stderr.trim() || '环境缺失（退出码 2）', 'ENV_MISSING', stderr))
        return
      }
      reject(
        new CliError(
          stderr.trim() || `CLI 失败（退出码 ${code ?? 'null'}）且无 JSON 输出`,
          'CLI_NO_ENVELOPE',
          stderr
        )
      )
    })
  })
}

/** Envelopes are the last JSON object on stdout (warnings may precede them). */
export function extractEnvelope(text: string): Envelope | null {
  const trimmed = text.trim()
  if (!trimmed) return null
  try {
    const parsed = JSON.parse(trimmed)
    return isEnvelope(parsed) ? parsed : null
  } catch {
    // fall through: find the last line that parses as an envelope
  }
  const lines = trimmed.split(/\r?\n/)
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i].trim()
    if (!line.startsWith('{')) continue
    try {
      const parsed = JSON.parse(line)
      if (isEnvelope(parsed)) return parsed
    } catch {
      // keep looking
    }
  }
  return null
}

function isEnvelope(value: unknown): value is Envelope {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return typeof record.tool === 'string' && 'ok' in record
}

/** Absolute path helper used by the renderer header. */
export function describeEnvironment(): string {
  return [process.platform, process.arch, `path=${(process.env.PATH ?? '').split(delimiter).length} entries`].join(' · ')
}
