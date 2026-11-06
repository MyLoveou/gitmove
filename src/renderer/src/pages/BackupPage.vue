<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { AssetStatusPayload, MergePlanPayload, AssetSnapshot } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const status = ref<AssetStatusPayload | null>(null)
const results = ref<{ target: string; ok: boolean; snapshot_id: string | null; files: number; bytes: number; message: string }[]>([])
const busy = ref(false)
const message = ref('')

const base = ref('')
const ours = ref('')
const theirs = ref('')
const plan = ref<MergePlanPayload | null>(null)

const snapshots = computed<AssetSnapshot[]>(() => status.value?.snapshots ?? [])

async function invoke<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function load() {
  if (!store.currentWorkspace) return
  busy.value = true
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
    results.value = await invoke({ op: 'asset.init', workspace: store.currentWorkspace })
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
    const outcome = await invoke<{ results: typeof results.value; partial: boolean }>({
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

async function analyze() {
  if (!base.value || !ours.value || !theirs.value) {
    message.value = '请选择 base / ours / theirs 三个快照'
    return
  }
  busy.value = true
  message.value = ''
  try {
    plan.value = await invoke<MergePlanPayload>({
      op: 'asset.merge',
      workspace: store.currentWorkspace,
      base: base.value,
      ours: ours.value,
      theirs: theirs.value
    })
  } catch (error) {
    message.value = (error as Error).message
  } finally {
    busy.value = false
  }
}

async function applyPlan(force: boolean) {
  if (!plan.value) return
  busy.value = true
  message.value = ''
  try {
    await invoke({
      op: 'asset.merge',
      workspace: store.currentWorkspace,
      base: plan.value.base,
      ours: plan.value.ours,
      theirs: plan.value.theirs,
      apply: true,
      force
    })
    message.value = force ? '已应用无歧义部分（冲突保留）' : '合并完成'
    plan.value = null
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
  return id ? id.slice(0, 8) : '—'
}

void load()

watch(
  () => store.currentWorkspace,
  () => {
    void store.refreshWorkspace()
    void (typeof load === 'function' ? load() : Promise.resolve())
  }
)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>备份</h1>
        <p class="sub">资产平面：双盘备份 + 三路合并（冲突不自动解决）</p>
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
    <div class="banner info">
      用法：①「初始化仓库」只做一次（每块盘各建一个 restic 仓库）→ ②「备份全部」写入两块盘 → ③ 下方「快照」列出历史；
      三路合并选 base/ours/theirs 三个快照即可分析。
    </div>
    <div v-if="message" class="banner ok">{{ message }}</div>

    <div class="panel">
      <table class="table">
        <thead><tr><th>目标</th><th>仓库</th><th>优先级</th><th>状态</th></tr></thead>
        <tbody>
          <tr v-for="target in status?.targets ?? []" :key="target.name">
            <td class="mono strong">{{ target.name }}</td>
            <td class="mono dim path">{{ target.repo }}</td>
            <td class="num">{{ target.priority }}</td>
            <td><span class="badge" :class="target.enabled ? 'ok' : 'warn'">{{ target.enabled ? 'enabled' : 'disabled' }}</span></td>
          </tr>
          <tr v-if="!status?.targets?.length"><td colspan="4" class="empty">没有配置 [[backup.target]]</td></tr>
        </tbody>
      </table>
    </div>

    <div class="panel pad merge-box">
      <div class="merge-head">
        <strong>三路合并</strong>
        <span class="dim">选 base / ours / theirs（同一目标仓库的快照）</span>
      </div>
      <div class="merge-selects">
        <label>base<select v-model="base" class="input"><option value="">—</option><option v-for="s in snapshots" :key="'b'+s.snapshot_id" :value="s.snapshot_id">{{ short(s.snapshot_id) }} · {{ s.target }}</option></select></label>
        <label>ours<select v-model="ours" class="input"><option value="">—</option><option v-for="s in snapshots" :key="'o'+s.snapshot_id" :value="s.snapshot_id">{{ short(s.snapshot_id) }} · {{ s.target }}</option></select></label>
        <label>theirs<select v-model="theirs" class="input"><option value="">—</option><option v-for="s in snapshots" :key="'t'+s.snapshot_id" :value="s.snapshot_id">{{ short(s.snapshot_id) }} · {{ s.target }}</option></select></label>
        <button class="btn" :disabled="busy" @click="analyze">分析</button>
      </div>

      <div v-if="plan" class="merge-result">
        <p class="hint">无歧义：{{ plan.merged.length }} 项 · 冲突：{{ plan.conflicts.length }} 项</p>
        <div class="merge-cols">
          <div>
            <div class="merge-col-title">合并规则</div>
            <div v-for="item in plan.merged" :key="item.path" class="merge-line">
              <span class="mono dim">{{ item.action }}</span> {{ item.path }}
            </div>
          </div>
          <div>
            <div class="merge-col-title bad">冲突</div>
            <div v-for="item in plan.conflicts" :key="item.path" class="merge-line">
              <span class="mono bad">{{ item.reason }}</span> {{ item.path }}
            </div>
            <div v-if="!plan.conflicts.length" class="dim">无冲突</div>
          </div>
        </div>
        <div class="merge-actions">
          <button class="btn primary" :disabled="busy || plan.conflicts.length > 0" @click="applyPlan(false)">应用合并</button>
          <button class="btn" :disabled="busy" @click="applyPlan(true)">只应用无歧义部分</button>
        </div>
      </div>
    </div>

    <div class="panel">
      <table class="table">
        <thead><tr><th>目标</th><th>快照</th><th class="num">文件</th><th class="num">体积</th><th>修订</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="snap in snapshots" :key="snap.target + snap.snapshot_id">
            <td class="mono">{{ snap.target }}</td>
            <td class="mono dim">{{ short(snap.snapshot_id) }}</td>
            <td class="num">{{ snap.files }}</td>
            <td class="num">{{ formatBytes(snap.bytes) }}</td>
            <td class="mono dim">{{ snap.revision_id ? `#${snap.revision_id}` : '—' }}</td>
            <td class="mono dim">{{ snap.created_at.slice(0, 19).replace('T', ' ') }}</td>
          </tr>
          <tr v-if="!snapshots.length"><td colspan="6" class="empty">还没有资产快照</td></tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<style scoped>
.merge-box { margin: 14px 0; }
.merge-head { display: flex; gap: 10px; align-items: baseline; margin-bottom: 10px; }
.merge-selects { display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 10px; align-items: end; }
.merge-selects label { display: flex; flex-direction: column; gap: 4px; color: var(--text-muted); font-size: 11px; }
.merge-result { margin-top: 12px; }
.merge-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.merge-col-title { font-size: 11px; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; }
.merge-line { font-size: 12px; padding: 2px 0; }
.merge-actions { display: flex; gap: 8px; margin-top: 12px; }
</style>
