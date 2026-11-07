import { defineStore } from 'pinia'

import type { AuditRow, CommitOutcome, ProjectRow, RevisionRow, WorkspaceStatus } from '../../../shared/protocol'

export interface AppInfo {
  version: string
  platform: string
  python: string
  sidecar: string
  engine: 'rust' | 'python'
  core: string | null
}

type Result<T> = { ok: boolean; data?: T; error?: { code: string; message: string; steps?: string[] } }

async function invoke<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as Result<T>
  if (!result.ok) {
    const error = new Error(result.error?.message ?? '操作失败') as Error & { code?: string; steps?: string[] }
    error.code = result.error?.code
    error.steps = result.error?.steps
    throw error
  }
  return result.data as T
}

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    info: null as AppInfo | null,
    projects: [] as ProjectRow[],
    audit: [] as AuditRow[],
    currentWorkspace: '',
    revisions: [] as RevisionRow[],
    workspaceStatus: null as WorkspaceStatus | null,
    configToml: '' as string,
    editableFiles: [] as { path: string; exists: boolean }[],
    activeFile: '' as string,
    fileText: '' as string,
    branchRefs: { local: [] as string[], remote: [] as string[] },
    graphNodes: [] as import('../../../shared/protocol').GraphNode[],
    graphAll: false,
    graphBranch: '',
    logText: '',
    syncInfo: null as { ahead: number; behind: number; upstream: string | null; dirty: string[] } | null,
    loading: false,
    busy: false,
    error: null as string | null,
    notice: null as string | null,
    toasts: [] as { id: number; tone: 'ok' | 'bad'; text: string }[],
    lastRefresh: null as Date | null
  }),
  getters: {
    errors: (state) => state.audit.reduce((sum, row) => sum + row.errors, 0),
    warns: (state) => state.audit.reduce((sum, row) => sum + row.warns, 0),
    totalBytes: (state) => state.audit.reduce((sum, row) => sum + row.tracked_bytes, 0),
    totalFiles: (state) => state.audit.reduce((sum, row) => sum + row.tracked_files, 0),
    canCommit: (state) => state.info?.engine === 'rust'
  },
  actions: {
    flash(tone: 'ok' | 'bad', text: string) {
      const id = Date.now() + Math.floor(Math.random() * 1000)
      this.toasts = [...this.toasts, { id, tone, text }]
      window.setTimeout(() => {
        this.toasts = this.toasts.filter((item) => item.id !== id)
      }, tone === 'bad' ? 7000 : 3800)
    },
    dismissToast(id: number) {
      this.toasts = this.toasts.filter((item) => item.id !== id)
    },
    async bootstrap() {
      this.loading = true
      this.error = null
      try {
        this.info = await invoke<AppInfo>({ op: 'app.info' })
        await this.refreshProjects()
        const first = this.projects[0]
        if (first && !this.currentWorkspace) {
          this.currentWorkspace = first.path
          await this.refreshWorkspace()
        }
      } catch (error) {
        this.flash('bad', (error as Error).message)
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
        this.flash('bad', (error as Error).message)
      } finally {
        this.loading = false
      }
    },
    async setWorkspace(path: string) {
      this.currentWorkspace = path
      this.notice = null
      this.error = null
      this.syncInfo = null
      this.graphNodes = []
      await this.refreshWorkspace()
      await this.loadRefs()
      await this.loadGraph()
    },
    async loadRefs() {
      if (!this.currentWorkspace) return
      try {
        this.branchRefs = await invoke<{ local: string[]; remote: string[] }>({
          op: 'ws.refs',
          workspace: this.currentWorkspace
        })
      } catch (error) {
        this.flash('bad', (error as Error).message)
      }
    },
    async loadGraph(branch?: string, all?: boolean) {
      if (!this.currentWorkspace) return
      try {
        this.graphNodes = await invoke<import('../../../shared/protocol').GraphNode[]>({
          op: 'graph',
          workspace: this.currentWorkspace,
          limit: 200,
          branch: branch ?? this.graphBranch ?? undefined,
          all: all ?? this.graphAll
        })
      } catch (error) {
        this.flash('bad', (error as Error).message)
      }
    },
    async loadLogs(lines = 200) {
      try {
        const data = await invoke<{ text: string; total: number }>({ op: 'logs.read', lines })
        this.logText = data.text
      } catch (error) {
        this.flash('bad', (error as Error).message)
      }
    },
    async addMember(payload: {
      name: string
      path: string
      role: string
      strategy: string
      source: string
      pin?: string
      track?: string
    }) {
      if (!this.currentWorkspace) return false
      this.busy = true
      try {
        await invoke({ op: 'ws.add', workspace: this.currentWorkspace, ...payload })
        this.flash('ok', `已添加成员 ${payload.name}`)
        await this.refreshWorkspace()
        return true
      } catch (error) {
        this.flash('bad', (error as Error).message)
        return false
      } finally {
        this.busy = false
      }
    },
    async wsPush(member: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'ws.contribute', workspace: this.currentWorkspace, member })
        this.flash('ok', `已回推成员 ${member}`)
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async wsSync(member?: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'ws.sync', workspace: this.currentWorkspace, member })
        this.flash('ok', '已按 workspace.lock.toml 同步成员')
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async wsUpdate(member?: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'ws.update', workspace: this.currentWorkspace, member })
        this.flash('ok', '已更新 pin 并写入 workspace.lock.toml')
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    /** 对齐 = 先把上游写进 lock，再按 lock 检出。两步都成功才算这个成员对齐。 */
    async alignMember(member: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      this.error = null
      try {
        await invoke({ op: 'ws.update', workspace: this.currentWorkspace, member })
        await invoke({ op: 'ws.sync', workspace: this.currentWorkspace, member })
        this.flash('ok', `已对齐 ${member}`)
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async pull(mode?: 'merge' | 'rebase') {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'sync.pull', workspace: this.currentWorkspace, fetch: true, mode })
        this.flash('ok', mode ? `已${mode === 'merge' ? '合并' : '变基'}拉取` : '已快进拉取')
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async refreshWorkspace() {
      if (!this.currentWorkspace) return
      this.busy = true
      this.error = null
      try {
        this.workspaceStatus = await invoke<WorkspaceStatus>({ op: 'ws.status', workspace: this.currentWorkspace })
        this.revisions = await invoke<RevisionRow[]>({ op: 'rev.log', workspace: this.currentWorkspace, limit: 50 })
      } catch (error) {
        const err = error as Error & { code?: string }
        if (err.code === 'CORE_REQUIRED') {
          this.workspaceStatus = null
          this.revisions = []
        } else {
          this.flash('bad', err.message)
        }
      } finally {
        this.busy = false
      }
    },
    async checkout(id: number, force = false) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'rev.checkout', workspace: this.currentWorkspace, id, force })
        this.flash('ok', `已回滚到修订 ${id}`)
        await this.refreshWorkspace()
        await this.refreshProjects()
        await this.loadGraph()
      } catch (error) {
        const err = error as Error & { code?: string }
        if (!force && /dirty/i.test(err.message)) {
          if (window.confirm('工作区有未提交改动。强制回滚会丢弃它们，继续吗？')) {
            await this.checkout(id, true)
            return
          }
        }
        this.flash('bad', err.message)
      } finally {
        this.busy = false
      }
    },
    async memberBranches(member: string): Promise<string[]> {
      if (!this.currentWorkspace) return []
      return invoke<string[]>({ op: 'ws.branch.refs', workspace: this.currentWorkspace, member })
    },
    async createMemberBranch(member: string, name: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'ws.branch.create', workspace: this.currentWorkspace, name, member })
        this.flash('ok', `已在 ${member} 新建 ${name}`)
        await this.refreshWorkspace()
      } finally {
        this.busy = false
      }
    },
    async switchMemberBranch(member: string, name: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'ws.switch', workspace: this.currentWorkspace, name, member })
        this.flash('ok', `已让 ${member} 使用 ${name}`)
        await this.refreshWorkspace()
      } finally {
        this.busy = false
      }
    },
    async commitMember(member: string, message: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'member.commit', workspace: this.currentWorkspace, member, message })
        this.flash('ok', `已提交 ${member}`)
        await this.refreshWorkspace()
      } finally {
        this.busy = false
      }
    },
    async switchBranch(name: string) {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'ws.switch', workspace: this.currentWorkspace, name })
        this.flash('ok', `已切换到分支 ${name}`)
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async syncCheck() {
      if (!this.currentWorkspace) return
      try {
        this.syncInfo = await invoke<{ ahead: number; behind: number; upstream: string | null; dirty: string[] }>({
          op: 'sync.check',
          workspace: this.currentWorkspace
        })
      } catch (error) {
        this.flash('bad', (error as Error).message)
      }
    },
    async syncPull() {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        await invoke({ op: 'sync.pull', workspace: this.currentWorkspace, fetch: true })
        this.flash('ok', '已快进拉取')
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async loadConfig() {
      if (!this.currentWorkspace) return
      try {
        const data = await invoke<{ toml: string }>({ op: 'config.export', workspace: this.currentWorkspace })
        this.configToml = data.toml
      } catch (error) {
        this.flash('bad', (error as Error).message)
      }
    },
    async saveConfig(toml: string) {
      if (!this.currentWorkspace) return false
      try {
        await invoke({ op: 'config.save', workspace: this.currentWorkspace, toml })
        this.configToml = toml
        this.flash('ok', '配置已保存')
        return true
      } catch (error) {
        this.flash('bad', (error as Error).message)
        return false
      }
    },
    async loadFiles() {
      if (!this.currentWorkspace) return
      try {
        this.editableFiles = await invoke<{ path: string; exists: boolean }[]>({
          op: 'file.list',
          workspace: this.currentWorkspace
        })
        if (!this.activeFile && this.editableFiles.length) {
          this.activeFile = this.editableFiles.find((file) => file.exists)?.path ?? this.editableFiles[0].path
        }
        await this.loadFile(this.activeFile)
      } catch (error) {
        this.flash('bad', (error as Error).message)
      }
    },
    async loadFile(path: string) {
      if (!this.currentWorkspace || !path) return
      this.activeFile = path
      try {
        const data = await invoke<{ text: string }>({ op: 'file.read', workspace: this.currentWorkspace, path })
        this.fileText = data.text
      } catch (error) {
        this.flash('bad', (error as Error).message)
      }
    },
    async saveFile(path: string, text: string) {
      if (!this.currentWorkspace) return false
      try {
        await invoke({ op: 'file.write', workspace: this.currentWorkspace, path, text })
        this.flash('ok', `已保存 ${path}（旧文件备份为 .bak）`)
        await this.loadFiles()
        return true
      } catch (error) {
        this.flash('bad', (error as Error).message)
        return false
      }
    },
    async importGitHistory() {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        const data = await invoke<{ imported: number }>({
          op: 'rev.importGit',
          workspace: this.currentWorkspace,
          limit: 200
        })
        this.flash('ok', data.imported ? `已从 git 历史导入 ${data.imported} 条修订` : '没有可导入的提交')
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async rebuildIndex() {
      if (!this.currentWorkspace) return
      this.busy = true
      try {
        const data = await invoke<{ revisions: number }>({ op: 'rev.rebuild', workspace: this.currentWorkspace })
        if (!data.revisions) {
          const imported = await invoke<{ imported: number }>({
            op: 'rev.importGit',
            workspace: this.currentWorkspace,
            limit: 200
          })
          this.flash('ok', `没有 trailer 可重建；已从 git 历史导入 ${imported.imported} 条修订`)
        } else {
          this.flash('ok', `索引重建完成：${data.revisions} 条修订`)
        }
        await this.refreshWorkspace()
      } catch (error) {
        this.flash('bad', (error as Error).message)
      } finally {
        this.busy = false
      }
    },
    async commit(message: string, members: boolean) {
      if (!this.currentWorkspace) return false
      this.busy = true
      this.error = null
      this.notice = null
      try {
        const outcome = await invoke<CommitOutcome>({
          op: 'rev.commit',
          workspace: this.currentWorkspace,
          message,
          members
        })
        this.flash('ok', `已创建修订 ${outcome.revision}（${outcome.git_commit?.slice(0, 7) ?? 'no-commit'}）`)
        await this.refreshWorkspace()
        await this.refreshProjects()
        return true
      } catch (error) {
        const err = error as Error & { steps?: string[] }
        this.flash('bad', err.steps?.length ? `${err.message}（${err.steps.join(' / ')}）` : err.message)
        return false
      } finally {
        this.busy = false
      }
    }
  }
})
