<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { AssetStatusPayload, MergePlanPayload, MergeStatePayload, AssetSnapshot } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const status = ref<AssetStatusPayload | null>(null)
const results = ref<{ target: string; ok: boolean; snapshot_id: string | null; files: number; bytes: number; message: string }[]>([])
const busy = ref(false)

const newName = ref('drive-a')
const newRepo = ref('')
const newPriority = ref(1)
const base = ref('')
const ours = ref('')
const theirs = ref('')
const plan = ref<MergePlanPayload | null>(null)
const mergeState = ref<MergeStatePayload | null>(null)
const testResults = ref<{ target: string; ok: boolean; message: string }[]>([])

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
    mergeState.value = await invoke<MergeStatePayload | null>({
      op: 'asset.state',
      workspace: store.currentWorkspace
    })
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function testTargets() {
  busy.value = true
  
  try {
    testResults.value = await invoke<{ target: string; ok: boolean; message: string }[]>({
      op: 'asset.test',
      workspace: store.currentWorkspace
    })
    store.flash('ok', '目标测试完成')
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function resolvePath(path: string, take: string) {
  busy.value = true
  try {
    mergeState.value = await invoke<MergeStatePayload>({
      op: 'asset.resolve',
      workspace: store.currentWorkspace,
      path,
      take
    })
    store.flash('ok', `已处理 ${path}（${take}）`)
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function finishMerge() {
  busy.value = true
  try {
    await invoke({ op: 'asset.continue', workspace: store.currentWorkspace })
    mergeState.value = null
    store.flash('ok', '合并已完成')
    await load()
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function invokeRaw<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function addTarget() {
  if (!store.currentWorkspace || !newRepo.value.trim()) {
    store.flash('bad', '请填写仓库路径（本地目录，例如 E:/backup/video-restic）')
    return
  }
  busy.value = true
  
  try {
    const current = await invokeRaw<{ text: string; exists: boolean }>({
      op: 'file.read',
      workspace: store.currentWorkspace,
      path: 'workspace.toml'
    })
    const block = [
      '',
      '[[backup.target]]',
      `name = "${newName.value.trim() || 'target'}"`,
      'kind = "local"',
      `repo = "${newRepo.value.trim().replace(/\\/g, '/')}"`,
      `priority = ${Number(newPriority.value) || 1}`,
      ''
    ].join('\n')
    await invokeRaw({
      op: 'file.write',
      workspace: store.currentWorkspace,
      path: 'workspace.toml',
      text: current.text + block
    })
    store.flash('ok', '已写入 workspace.toml；接着点「初始化仓库」再「备份全部」')
    newRepo.value = ''
    await load()
  } catch (error) {
    store.flash('bad', (error as Error).message)
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
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function backupAll() {
  busy.value = true
  
  try {
    const outcome = await invoke<{ results: typeof results.value; partial: boolean }>({
      op: 'asset.backup',
      workspace: store.currentWorkspace
    })
    results.value = outcome.results
    store.flash(outcome.partial ? 'bad' : 'ok', outcome.partial ? '部分目标失败（其余已成功）' : '全部目标备份完成')
    await load()
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function analyze() {
  if (!base.value || !ours.value || !theirs.value) {
    store.flash('bad', '请选择 base / ours / theirs 三个快照')
    return
  }
  busy.value = true
  
  try {
    plan.value = await invoke<MergePlanPayload>({
      op: 'asset.merge',
      workspace: store.currentWorkspace,
      base: base.value,
      ours: ours.value,
      theirs: theirs.value
    })
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function applyPlan(force: boolean) {
  if (!plan.value) return
  busy.value = true
  
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
    store.flash('ok', force ? '已应用无歧义部分（冲突保留）' : '合并完成')
    plan.value = null
    await load()
  } catch (error) {
    store.flash('bad', (error as Error).message)
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
    <header class="scale">
      <div>
        <div class="scale-kicker">资产</div>
        <h1>{{ store.workspaceStatus?.name || '备份' }}</h1>
        <p class="scale-read">
          <span>{{ status?.targets?.length ?? 0 }} 个目标</span>
          <span>{{ snapshots.length }} 个快照</span>
          <span>{{ status?.restic_version ? 'restic 可用' : 'restic 未就绪' }}</span>
        </p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="busy" @click="load">刷新</button>
        <button class="btn primary" :disabled="busy || !status?.restic_version" @click="backupAll">
          {{ busy ? '处理中…' : '备份全部' }}
        </button>
      </div>
    </header>

    <div v-if="!store.canCommit" class="banner warn">需要 Rust 核心：<code>cargo build --release</code></div>

    <details class="fold">
      <summary>目标与初始化</summary>
      <div class="form-row" style="margin-bottom: 12px">
        <button class="btn" :disabled="busy" @click="initRepos">初始化仓库</button>
        <button class="btn" :disabled="busy || !status?.targets?.length" @click="testTargets">测试目标</button>
      </div>
      <div class="panel-title"><span class="muted">写入 workspace.toml 的 [[backup.target]]</span></div>
      <div class="form-row">
        <label class="field"><span>名称</span><input v-model="newName" class="input" placeholder="drive-e" /></label>
        <label class="field" style="min-width: 320px"><span>仓库目录（本地绝对路径）</span><input v-model="newRepo" class="input" placeholder="E:/backup/video-restic" /></label>
        <label class="field" style="min-width: 90px"><span>优先级</span><input v-model.number="newPriority" class="input" type="number" min="1" /></label>
        <button class="btn primary" :disabled="busy" @click="addTarget">添加目标</button>
      </div>
      <p class="hint">仓库目录必须不存在或为空。两块盘用不同目录。初始化只做一次。</p>
    </details>

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

    <details class="fold merge-box">
      <summary>三路合并</summary>
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
    </details>

    <div v-if="testResults.length" class="panel pad">
      <div class="panel-title"><strong>目标连通性</strong></div>
      <div v-for="row in testResults" :key="row.target" class="kv">
        <span class="mono">{{ row.target }}</span>
        <span :class="row.ok ? 'ok' : 'bad'">{{ row.ok ? '可达' : row.message }}</span>
      </div>
    </div>

    <div v-if="mergeState && mergeState.pending.length" class="panel pad">
      <div class="panel-title">
        <strong>待解决冲突（{{ mergeState.pending.length }}）</strong>
        <span class="muted">逐文件选择：保留我们的 / 保留他们的 / 两个都留</span>
      </div>
      <div v-for="path in mergeState.pending" :key="path" class="conflict-row">
        <span class="mono">{{ path }}</span>
        <span class="nowrap">
          <button class="btn tiny" :disabled="busy" @click="resolvePath(path, 'ours')">我们的</button>
          <button class="btn tiny" :disabled="busy" @click="resolvePath(path, 'theirs')">他们的</button>
          <button class="btn tiny" :disabled="busy" @click="resolvePath(path, 'both')">都留</button>
        </span>
      </div>
      <div class="form-row" style="margin-top: 10px">
        <button class="btn primary" :disabled="busy" @click="finishMerge">完成合并</button>
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
