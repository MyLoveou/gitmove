<script setup lang="ts">
import { onMounted, ref } from 'vue'

import type { AssetSnapshot, AssetStatusPayload, AssetTargetResult } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const status = ref<AssetStatusPayload | null>(null)
const results = ref<AssetTargetResult[]>([])
const busy = ref(false)
const message = ref('')

async function invoke<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function load() {
  if (!store.currentWorkspace) return
  busy.value = true
  message.value = ''
  try {
    status.value = await invoke<AssetStatusPayload>({ op: 'asset.status', workspace: store.currentWorkspace })
  } catch (error) {
    message.value = (error as Error).message
  } finally {
    busy.value = false
  }
}

async function initRepos() {
  busy.value = true
  try {
    results.value = await invoke<AssetTargetResult[]>({ op: 'asset.init', workspace: store.currentWorkspace })
    await load()
  } catch (error) {
    message.value = (error as Error).message
  } finally {
    busy.value = false
  }
}

async function backupAll() {
  busy.value = true
  message.value = ''
  try {
    const outcome = await invoke<{ results: AssetTargetResult[]; partial: boolean }>({
      op: 'asset.backup',
      workspace: store.currentWorkspace
    })
    results.value = outcome.results
    message.value = outcome.partial ? '部分目标失败（其余已成功）' : '全部目标备份完成'
    await load()
  } catch (error) {
    message.value = (error as Error).message
  } finally {
    busy.value = false
  }
}

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function short(id: string): string {
  return id.slice(0, 8)
}

onMounted(load)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>备份</h1>
        <p class="sub">资产平面：两块本地盘各写一份快照（restic 不捆绑）</p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="busy" @click="load">刷新</button>
        <button class="btn ghost" :disabled="busy" @click="initRepos">初始化仓库</button>
        <button class="btn primary" :disabled="busy || !status?.restic_version" @click="backupAll">
          {{ busy ? '处理中…' : '备份全部' }}
        </button>
      </div>
    </header>

    <div v-if="!store.canCommit" class="banner warn">需要 Rust 核心：<code>cargo build --release</code></div>
    <div v-if="message" class="banner ok">{{ message }}</div>
    <div v-if="!status?.restic_version" class="banner warn">
      restic 不在 PATH；资产平面不可用（代码平面不受影响）。
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr><th>目标</th><th>仓库</th><th>优先级</th><th>状态</th></tr>
        </thead>
        <tbody>
          <tr v-for="target in status?.targets ?? []" :key="target.name">
            <td class="mono strong">{{ target.name }}</td>
            <td class="mono dim path">{{ target.repo }}</td>
            <td class="num">{{ target.priority }}</td>
            <td>
              <span class="badge" :class="target.enabled ? 'ok' : 'warn'">{{ target.enabled ? 'enabled' : 'disabled' }}</span>
            </td>
          </tr>
          <tr v-if="!status?.targets?.length">
            <td colspan="4" class="empty">没有配置 [[backup.target]]（workspace.toml）</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="results.length" class="panel">
      <table class="table">
        <thead>
          <tr><th>目标</th><th>结果</th><th class="num">文件</th><th class="num">新增</th><th>快照 / 说明</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in results" :key="item.target">
            <td class="mono">{{ item.target }}</td>
            <td><span class="badge" :class="item.ok ? 'ok' : 'bad'">{{ item.ok ? 'ok' : 'failed' }}</span></td>
            <td class="num">{{ item.files }}</td>
            <td class="num">{{ formatBytes(item.bytes) }}</td>
            <td class="mono dim">{{ item.snapshot_id ? short(item.snapshot_id) : item.message }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr><th>目标</th><th>快照</th><th class="num">文件</th><th class="num">体积</th><th>修订</th><th>时间</th></tr>
        </thead>
        <tbody>
          <tr v-for="snap in status?.snapshots ?? []" :key="snap.target + snap.snapshot_id">
            <td class="mono">{{ snap.target }}</td>
            <td class="mono dim">{{ short(snap.snapshot_id) }}</td>
            <td class="num">{{ snap.files }}</td>
            <td class="num">{{ formatBytes(snap.bytes) }}</td>
            <td class="mono dim">{{ snap.revision_id ? `#${snap.revision_id}` : '—' }}</td>
            <td class="mono dim">{{ snap.created_at.slice(0, 19).replace('T', ' ') }}</td>
          </tr>
          <tr v-if="!status?.snapshots?.length">
            <td colspan="6" class="empty">还没有资产快照</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
