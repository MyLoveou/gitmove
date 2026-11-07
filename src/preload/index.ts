
import { contextBridge, ipcRenderer } from 'electron'

import { IPC_INVOKE, IPC_UPDATE, type Op } from '../shared/protocol'

const api = {
  invoke: (request: Op) => ipcRenderer.invoke(IPC_INVOKE, request),
  onUpdate: (callback: (state: unknown) => void) => {
    const listener = (_event: unknown, state: unknown) => callback(state)
    ipcRenderer.on(IPC_UPDATE, listener)
    return () => ipcRenderer.removeListener(IPC_UPDATE, listener)
  }
}

contextBridge.exposeInMainWorld('gitmove', api)

export type GitmoveApi = typeof api
