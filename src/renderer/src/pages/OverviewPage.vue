<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { useRouter } from 'vue-router'

import type { AuditRow } from '../../../shared/protocol'
import { memberDrift } from '../marks'
import { useWorkspaceStore } from '../stores/workspace'

const router = useRouter()

const store = useWorkspaceStore()

const drifted = computed(() => (store.workspaceStatus?.members ?? []).filter((member) => memberDrift(member)))
const revisionLabel = computed(() => {
  const latest = store.revisions[0]
  return latest ? `rev ${latest.id}` : '尚无修订'
})

const rows = computed(() => {
  const byAlias = new Map(store.audit.map((row) => [row.alias, row]))
  return store.projects.map((project) => ({
    project,
    audit: byAlias.get(project.alias) as AuditRow | undefined
  }))
})

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function versionText(audit: AuditRow | undefined): string {
  if (!audit) return '—'
  if (audit.dep_label && audit.dep_label !== '—') return audit.dep_label
  return audit.own_deps ? `${audit.own_deps} 项` : '—'
}

function depotAge(audit: AuditRow | undefined): string {
  if (!audit?.depot_configured) return '—'
  if (audit.depot_age_days === null || audit.depot_age_days === undefined) return 'never'
  return `${audit.depot_age_days.toFixed(1)}d`
}

function statusClass(status: string): string {
  if (status === 'OK') return 'ok'
  if (status === 'MISSING' || status === 'NOT_GIT') return 'bad'
  return 'warn'
}

const projectNote = ref('')
const projectForm = ref({ path: '', alias: '', group: '' })
const scanRoot = ref('')
const scanRows = ref<{ path: string; alias: string; registered: boolean }[]>([])
const manageNotice = ref('')

async function addProject(path = projectForm.value.path, alias = projectForm.value.alias) {
  if (!path.trim()) {
    manageNotice.value = '请填写仓库路径'
    return
  }
  try {
    await window.gitmove.invoke({
      op: 'projects.add',
      path: path.trim(),
      alias: alias.trim() || undefined,
      group: projectForm.value.group.trim() || undefined
    })
    manageNotice.value = `已添加 ${alias || path}`
    projectForm.value = { path: '', alias: '', group: '' }
    await store.bootstrap()
  } catch (error) {
    manageNotice.value = (error as Error).message
  }
}

async function scanProjects() {
  if (!scanRoot.value.trim()) return
  try {
    const result = (await window.gitmove.invoke({
      op: 'projects.scan',
      root: scanRoot.value.trim(),
      depth: 3
    })) as { ok: boolean; data?: { path: string; alias: string; registered: boolean }[]; error?: { message: string } }
    if (!result.ok) throw new Error(result.error?.message ?? '扫描失败')
    scanRows.value = result.data ?? []
    manageNotice.value = `发现 ${scanRows.value.length} 个仓库`
  } catch (error) {
    manageNotice.value = (error as Error).message
  }
}

async function loadNote() {
  projectNote.value = ''
  if (!store.currentWorkspace) return
  try {
    const result = (await window.gitmove.invoke({
      op: 'file.read',
      workspace: store.currentWorkspace,
      path: '.gitmove/config.toml'
    })) as { ok: boolean; data?: { text: string } }
    if (result.ok && result.data) {
      const match = result.data.text.match(/^\s*note\s*=\s*"([^"]*)"/m)
      if (match) projectNote.value = match[1]
    }
  } catch {
    projectNote.value = ''
  }
}

watch(() => store.currentWorkspace, () => {
  void loadNote()
})

onMounted(() => {
  void loadNote()
})
</script>

<template>
  <section class="page">
    <header class="scale">
      <div>
        <div class="scale-kicker">当前工作区</div>
        <h1>{{ store.workspaceStatus?.name || '未选择' }}</h1>
        <p class="scale-read">
          <span class="mono">{{ revisionLabel }}</span>
          <span>{{ drifted.length ? `${drifted.length} 个成员偏离` : '成员对齐' }}</span>
        </p>
      </div>
      <div class="actions">
        <button class="btn primary" :disabled="!drifted.length" @click="router.push('/workspace')">处理偏离</button>
        <button class="btn ghost" :disabled="store.loading" @click="store.refreshProjects()">
          {{ store.loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </header>

    <div v-if="projectNote" class="banner info">{{ projectNote }}</div>

    <div class="panel pad">
      <div class="panel-title"><strong>项目管理</strong><span class="muted">登记本地 git 仓库，或扫描目录批量发现</span></div>
      <div v-if="manageNotice" class="banner ok">{{ manageNotice }}</div>
      <div class="form-row">
        <label class="field" style="min-width: 300px"><span>仓库路径</span><input v-model="projectForm.path" class="input" placeholder="D:/Project/foo" /></label>
        <label class="field"><span>别名</span><input v-model="projectForm.alias" class="input" placeholder="foo" /></label>
        <label class="field"><span>分组</span><input v-model="projectForm.group" class="input" placeholder="biz" /></label>
        <button class="btn primary" @click="addProject()">添加</button>
      </div>
      <div class="form-row" style="margin-top: 8px">
        <label class="field" style="min-width: 300px"><span>扫描目录</span><input v-model="scanRoot" class="input" placeholder="D:/Project" /></label>
        <button class="btn ghost" @click="scanProjects()">扫描</button>
      </div>
      <div v-if="scanRows.length" class="scan-list">
        <div v-for="row in scanRows" :key="row.path" class="scan-row">
          <span class="mono">{{ row.alias }}</span>
          <span class="mono dim">{{ row.path }}</span>
          <span v-if="row.registered" class="badge ok">已登记</span>
          <button v-else class="btn tiny" @click="addProject(row.path, row.alias)">添加</button>
        </div>
      </div>
    </div>

    <div class="meta-row">
      <span>项目 <strong>{{ store.projects.length }}</strong></span>
      <span>文件 <strong>{{ store.totalFiles.toLocaleString() }}</strong></span>
      <span>体积 <strong>{{ formatBytes(store.totalBytes) }}</strong></span>
      <span :class="{ bad: store.errors > 0 }">错误 <strong>{{ store.errors }}</strong></span>
      <span :class="{ warn: store.warns > 0 }">警告 <strong>{{ store.warns }}</strong></span>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>别名</th>
            <th>状态</th>
            <th>版本</th>
            <th class="num">文件</th>
            <th class="num">体积</th>
            <th>备份</th>
            <th class="num">错误</th>
            <th class="num">警告</th>
            <th>路径</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in rows"
            :key="row.project.alias"
            class="row-click"
            :class="{ selected: store.currentWorkspace === row.project.path }"
            @click="store.setWorkspace(row.project.path)"
          >
            <td class="mono strong">{{ row.project.alias }}</td>
            <td>
              <span class="badge" :class="statusClass(row.audit?.status ?? row.project.status)">
                {{ row.audit?.status ?? row.project.status }}
              </span>
            </td>
            <td class="mono dim">{{ versionText(row.audit) }}</td>
            <td class="num">{{ (row.audit?.tracked_files ?? 0).toLocaleString() }}</td>
            <td class="num">{{ formatBytes(row.audit?.tracked_bytes ?? 0) }}</td>
            <td class="mono dim">{{ depotAge(row.audit) }}</td>
            <td class="num" :class="{ bad: (row.audit?.errors ?? 0) > 0 }">{{ row.audit?.errors ?? 0 }}</td>
            <td class="num" :class="{ warn: (row.audit?.warns ?? 0) > 0 }">{{ row.audit?.warns ?? 0 }}</td>
            <td class="mono dim path">{{ row.project.path }}</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="9" class="empty">
              {{ store.loading ? '正在读取…' : '注册表为空：先用 gitmove projects add 注册项目' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="footnote">点击一行，把它设为当前工作区。</p>
  </section>
</template>
