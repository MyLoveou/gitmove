import { appendFileSync, mkdirSync } from 'node:fs'
import { join } from 'node:path'

import { app } from 'electron'

export function logDir(): string {
  return join(app.getPath('userData'), 'logs')
}

export function logFile(): string {
  const dir = logDir()
  mkdirSync(dir, { recursive: true })
  return join(dir, 'main.log')
}

/** JSON-lines event log; never throws (logging must not break the app). */
export function logEvent(event: string, data?: unknown): void {
  try {
    const line = JSON.stringify({ ts: new Date().toISOString(), event, data: data ?? null })
    appendFileSync(logFile(), line + '\n', 'utf8')
  } catch {
    // ignore logging failures
  }
}
