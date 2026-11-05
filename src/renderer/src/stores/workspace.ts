import { defineStore } from 'pinia'

import type { AuditRow, ProjectRow } from '../../../shared/protocol'

export interface AppInfo {
  version: string
  platform: string
  python: string
  sidecar: string
}

type Result<T> = { ok: boolean; data?: T; error?: { code: string; message: string; steps?: string[] } }

async function invoke<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as Result<T>
  if (!result.ok) {
    const error = new Error(result.error?.message ?? '操作失败') as Error & { code?: string }
    error.code = result.error?.code
    throw error
  }
  return result.data as T
}

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    info: null as AppInfo | null,
    projects: [] as ProjectRow[],
    audit: [] as AuditRow[],
    loading: false,
    error: null as string | null,
    lastRefresh: null as Date | null
  }),
  getters: {
    errors: (state) => state.audit.reduce((sum, row) => sum + row.errors, 0),
    warns: (state) => state.audit.reduce((sum, row) => sum + row.warns, 0),
    totalBytes: (state) => state.audit.reduce((sum, row) => sum + row.tracked_bytes, 0),
    totalFiles: (state) => state.audit.reduce((sum, row) => sum + row.tracked_files, 0)
  },
  actions: {
    async bootstrap() {
      this.loading = true
      this.error = null
      try {
        this.info = await invoke<AppInfo>({ op: 'app.info' })
        await this.refreshProjects()
      } catch (error) {
        this.error = (error as Error).message
      } finally {
        this.loading = false
      }
    },
    async refreshProjects() {
      this.loading = true
      this.error = null
      try {
        this.projects = await invoke<ProjectRow[]>({ op: 'projects.list' })
        this.audit = await invoke<AuditRow[]>({ op: 'audit.all' })
        this.lastRefresh = new Date()
      } catch (error) {
        this.error = (error as Error).message
      } finally {
        this.loading = false
      }
    }
  }
})
