import { join } from 'node:path'

import { BrowserWindow, app, ipcMain, shell } from 'electron'

import { IPC_INVOKE, type Op } from '../shared/protocol'
import { handleOp } from './operations'

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
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  window.once('ready-to-show', () => window.show())

  window.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    void window.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    void window.loadFile(join(__dirname, '../renderer/index.html'))
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
  const ops: Op[] = [{ op: 'app.info' }, { op: 'projects.list' }]
  for (const op of ops) {
    const result = await handleOp(op)
    if (!result.ok) {
      console.error(`SMOKE FAIL ${op.op}: ${result.error?.code} ${result.error?.message}`)
      return 1
    }
    if (op.op === 'projects.list') {
      const rows = result.data as unknown[]
      console.log(`SMOKE OK projects=${rows.length}`)
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
  ipcMain.handle(IPC_INVOKE, (_event, request: Op) => handleOp(request))
  if (isSmoke) {
    const code = await runSmoke()
    app.exit(code)
    return
  }

  createWindow()
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
