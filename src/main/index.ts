import { join } from 'node:path'

import { BrowserWindow, Menu, app, ipcMain, shell } from 'electron'

import { IPC_INVOKE, type Op } from '../shared/protocol'
import { logDir, logEvent } from './logger'
import { handleOp } from './operations'
import { checkForUpdates, initUpdater } from './updater'

const isSmoke = process.argv.includes('--smoke')

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1180,
    height: 780,
    minWidth: 900,
    minHeight: 600,
    show: false,
    backgroundColor: '#0b1014',
    title: 'gitmove',
    titleBarStyle: 'hidden',
    titleBarOverlay: { color: '#0b1014', symbolColor: '#8aa0a8', height: 32 },
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  window.once('ready-to-show', () => window.show())
  window.setMenu(null)

  window.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  const startPage = process.env.GITMOVE_START_PAGE?.trim()
  if (process.env.ELECTRON_RENDERER_URL) {
    const url = process.env.ELECTRON_RENDERER_URL + (startPage ? `#${startPage}` : '')
    void window.loadURL(url)
  } else {
    void window.loadFile(join(__dirname, '../renderer/index.html'), startPage ? { hash: startPage } : undefined)
  }
  return window
}

async function loadRendererProbe(): Promise<boolean> {
  const window = new BrowserWindow({
    show: false,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })
  const loaded = await new Promise<boolean>((resolve) => {
    const timer = setTimeout(() => resolve(false), 15_000)
    window.webContents.once('did-finish-load', () => {
      clearTimeout(timer)
      resolve(true)
    })
    window.webContents.once('did-fail-load', () => {
      clearTimeout(timer)
      resolve(false)
    })
    if (process.env.ELECTRON_RENDERER_URL) {
      void window.loadURL(process.env.ELECTRON_RENDERER_URL)
    } else {
      void window.loadFile(join(__dirname, '../renderer/index.html'))
    }
  })
  window.destroy()
  return loaded
}

async function runSmoke(): Promise<number> {
  const cwd = process.cwd()
  const ops: Op[] = [
    { op: 'app.info' },
    { op: 'projects.list' },
    { op: 'audit.all' },
    { op: 'ws.status', workspace: cwd },
    { op: 'rev.log', workspace: cwd, limit: 5 }
  ]
  for (const op of ops) {
    const result = await handleOp(op)
    if (!result.ok) {
      console.error(`SMOKE FAIL ${op.op}: ${result.error?.code} ${result.error?.message}`)
      return 1
    }
    if (op.op === 'projects.list') {
      const rows = result.data as unknown[]
      console.log(`SMOKE OK projects=${rows.length}`)
    } else if (op.op === 'audit.all') {
      const rows = result.data as Array<{ alias: string; tracked_files: number; tracked_bytes: number }>
      console.log(`SMOKE OK audit=${rows.length} first=${rows[0]?.alias}:${rows[0]?.tracked_files}f/${rows[0]?.tracked_bytes}b`)
    } else if (op.op === 'ws.status') {
      const status = result.data as { name: string; members: unknown[] }
      console.log(`SMOKE OK ws=${status.name} members=${status.members.length}`)
    } else if (op.op === 'rev.log') {
      const rows = result.data as unknown[]
      console.log(`SMOKE OK revisions=${rows.length}`)
    } else {
      const info = result.data as { version: string; sidecar: string }
      console.log(`SMOKE INFO version=${info.version} sidecar=${info.sidecar}`)
    }
  }

  const rendererLoaded = await loadRendererProbe()
  if (!rendererLoaded) {
    console.error('SMOKE FAIL renderer did not finish loading')
    return 1
  }
  console.log('SMOKE OK renderer')
  return 0
}

if (typeof app?.whenReady !== 'function') {
  // Happens when the binary is started as plain Node (ELECTRON_RUN_AS_NODE=1).
  console.error('gitmove: Electron 未以应用模式启动（检查 ELECTRON_RUN_AS_NODE）')
  process.exit(2)
}

void app.whenReady().then(async () => {
  logEvent('app.ready', { version: app.getVersion(), logs: logDir() })
  Menu.setApplicationMenu(null)
  ipcMain.handle(IPC_INVOKE, (_event, request: Op) => handleOp(request))
  if (isSmoke) {
    const code = await runSmoke()
    app.exit(code)
    return
  }

  const window = createWindow()
  initUpdater(window)
  if (app.isPackaged) {
    setTimeout(() => {
      void checkForUpdates()
    }, 5000)
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      const next = createWindow()
      initUpdater(next)
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
