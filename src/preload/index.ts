import { contextBridge, ipcRenderer } from 'electron'

import { IPC_INVOKE, type Op } from '../shared/protocol'

const api = {
  invoke: (request: Op) => ipcRenderer.invoke(IPC_INVOKE, request)
}

contextBridge.exposeInMainWorld('gitmove', api)

export type GitmoveApi = typeof api
