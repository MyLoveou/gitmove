<script setup lang="ts">
import { computed } from 'vue'

import type { AuditRow } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()

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
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>总览</h1>
        <p class="sub">全局项目与健康状态（M1：读取现有 CLI 的 --json）</p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="store.loading" @click="store.refreshProjects()">
          {{ store.loading ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </header>

    <div v-if="store.error" class="banner bad">
      <strong>读取失败</strong>
      <span>{{ store.error }}</span>
    </div>

    <div class="stats">
      <div class="stat">
        <span class="stat-label">项目</span>
        <span class="stat-value">{{ store.projects.length }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">文件</span>
        <span class="stat-value">{{ store.totalFiles.toLocaleString() }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">体积</span>
        <span class="stat-value">{{ formatBytes(store.totalBytes) }}</span>
      </div>
      <div class="stat" :class="{ bad: store.errors > 0 }">
        <span class="stat-label">错误</span>
        <span class="stat-value">{{ store.errors }}</span>
      </div>
      <div class="stat" :class="{ warn: store.warns > 0 }">
        <span class="stat-label">警告</span>
        <span class="stat-value">{{ store.warns }}</span>
      </div>
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

    <p class="footnote">
      点击任意行可把它设为当前工作区（其他页面会跟随切换）。<br />
      注意：这里的「文件 / 体积」只统计 <strong>git 跟踪</strong> 的内容；素材、模型等由「备份」页的资产快照管理（例如 video 项目 38 GB 素材不在此列）。<br />
    </p>
    <p class="footnote">
      数据源：<code>gitmove projects list --json</code> + <code>gitmove audit --all --json</code>。
      M2 起由 Rust 核心接管，接口保持不变。
    </p>
  </section>
</template>
