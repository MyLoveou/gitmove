
import { BrowserWindow, app } from 'electron'
import { autoUpdater } from 'electron-updater'

import { logEvent } from './logger'

export type UpdateStatus =
  | 'idle'
  | 'dev'
  | 'checking'
  | 'available'
  | 'none'
  | 'downloading'
  | 'downloaded'
  | 'error'

export interface UpdateState {
  status: UpdateStatus
  version?: string
  notes?: string
  percent?: number
  message?: string
  checkedAt?: string
}

let state: UpdateState = { status: 'idle' }
let target: BrowserWindow | null = null

function publish(): void {
  try {
    target?.webContents.send('gitmove:update', state)
  } catch {
    // window may be gone
  }
}

function set(next: Partial<UpdateState>): void {
  state = { ...state, ...next, checkedAt: new Date().toISOString() }
  logEvent('update.state', state)
  publish()
}

export function initUpdater(window: BrowserWindow): void {
  target = window
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = true

  autoUpdater.on('checking-for-update', () => set({ status: 'checking' }))
  autoUpdater.on('update-available', (info) =>
    set({ status: 'available', version: info.version, notes: typeof info.releaseNotes === 'string' ? info.releaseNotes : '' })
  )
  autoUpdater.on('update-not-available', () => set({ status: 'none', version: app.getVersion() }))
  autoUpdater.on('download-progress', (progress) => set({ status: 'downloading', percent: Math.round(progress.percent) }))
  autoUpdater.on('update-downloaded', (info) => set({ status: 'downloaded', version: info.version }))
  autoUpdater.on('error', (error) => set({ status: 'error', message: error.message }))

  if (!app.isPackaged) {
    set({ status: 'dev', message: '开发构建不检查更新（打包后生效）' })
  }
}

export function getUpdateState(): UpdateState {
  return state
}

export async function checkForUpdates(): Promise<UpdateState> {
  if (!app.isPackaged) {
    set({ status: 'dev', message: '开发构建不检查更新（打包后生效）' })
    return state
  }
  set({ status: 'checking' })
  try {
    await autoUpdater.checkForUpdates()
  } catch (error) {
    set({ status: 'error', message: (error as Error).message })
  }
  return state
}

export async function downloadUpdate(): Promise<UpdateState> {
  if (state.status !== 'available') {
    set({ status: 'error', message: '当前没有可下载的更新' })
    return state
  }
  set({ status: 'downloading', percent: 0 })
  try {
    await autoUpdater.downloadUpdate()
  } catch (error) {
    set({ status: 'error', message: (error as Error).message })
  }
  return state
}

export function installUpdate(): void {
  if (state.status === 'downloaded') {
    autoUpdater.quitAndInstall(false, true)
  }
}
