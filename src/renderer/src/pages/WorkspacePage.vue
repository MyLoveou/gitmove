<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { BranchRow } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const status = computed(() => store.workspaceStatus)
const branches = ref<BranchRow[]>([])
const target = ref('')
const busy = ref(false)

async function invoke<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function load() {
  if (!store.currentWorkspace) return
  busy.value = true
  try {
    branches.value = await invoke<BranchRow[]>({ op: 'ws.branches', workspace: store.currentWorkspace })
  } catch (error) {
    store.error = (error as Error).message
  } finally {
    busy.value = false
  }
}

function roleClass(role: string): string {
  if (role === 'main') return 'ok'
  if (role === 'editable') return 'warn'
  return ''
}

onMounted(() => {
  void load()
  void store.loadRefs()
})
watch(() => store.currentWorkspace, () => {
  void load()
  void store.loadRefs()
  void store.refreshWorkspace()
})
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>工作区</h1>
        <p class="sub">一个大项目可以由多个 git 仓库组成；这里显示成员、分支与同步状态。</p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="busy || store.busy" @click="() => { load(); store.refreshWorkspace() }">刷新</button>
      </div>
    </header>

    <div v-if="store.error" class="banner bad">{{ store.error }}</div>
    <div v-if="store.notice" class="banner ok">{{ store.notice }}</div>
    <div v-if="!status" class="banner warn">选择一个项目后显示成员</div>

    <template v-if="status">
      <div class="stats">
        <div class="stat"><span class="stat-label">工作区</span><span class="stat-value small">{{ status.name }}</span></div>
        <div class="stat"><span class="stat-label">成员</span><span class="stat-value">{{ status.members.length }}</span></div>
        <div class="stat"><span class="stat-label">声明</span><span class="stat-value small">{{ status.declared ? 'workspace.toml' : '隐式单仓' }}</span></div>
      </div>

      <div v-if="!status.declared" class="banner info">
        该项目没有 <code>workspace.toml</code>，当前按<strong>单仓工作区</strong>处理（成员只有 main）。
        要纳管 AI 规范库、工具库等，请创建 <code>workspace.toml</code> 并声明 <code>[[member]]</code>（可在「设置 → 配置文件」里新建）。
      </div>

      <div class="panel">
        <table class="table">
          <thead><tr><th>成员</th><th>角色</th><th>策略</th><th>HEAD</th><th>PIN</th><th>状态</th><th>路径</th></tr></thead>
          <tbody>
            <tr v-for="member in status.members" :key="member.name">
              <td class="mono strong">{{ member.name }}</td>
              <td><span class="badge" :class="roleClass(member.role)">{{ member.role }}</span></td>
              <td class="mono dim">{{ member.strategy || '—' }}</td>
              <td class="mono dim">{{ member.head ? member.head.slice(0, 7) : '—' }}</td>
              <td class="mono dim">{{ member.pin || '—' }}</td>
              <td>
                <span v-if="member.missing" class="badge bad">MISSING</span>
                <span v-else-if="member.dirty" class="badge warn">dirty</span>
                <span v-else class="badge ok">clean</span>
              </td>
              <td class="mono dim path">{{ member.path }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="panel pad">
        <div class="panel-title">
          <strong>分支与同步</strong>
          <span class="muted">切换会作用于每个成员仓（脏仓会被拒绝）</span>
        </div>
        <div class="form-row">
          <label class="field">
            <span>分支名</span>
            <input v-model="target" class="input" placeholder="feature/x" />
          </label>
          <button class="btn" :disabled="busy || !target" @click="store.switchBranch(target)">切换</button>
          <button class="btn ghost" :disabled="busy" @click="load">刷新分支</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.syncCheck()">同步检查</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.pull()">快进拉取</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.pull('merge')">合并拉取</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.pull('rebase')">变基拉取</button>
        </div>

        <div class="split">
          <div>
            <div class="muted label">成员当前分支</div>
            <div v-for="row in branches" :key="row.member" class="kv">
              <span class="mono dim">{{ row.member }}</span>
              <span class="mono">{{ row.branch || '—' }}</span>
            </div>
            <div v-if="!branches.length" class="muted">（无）</div>
          </div>
          <div>
            <div class="muted label">同步状态</div>
            <div v-if="store.syncInfo" class="kv">
              <span class="muted">ahead / behind</span>
              <span class="mono">{{ store.syncInfo.ahead }} / {{ store.syncInfo.behind }}</span>
            </div>
            <div v-if="store.syncInfo" class="kv">
              <span class="muted">upstream</span>
              <span class="mono">{{ store.syncInfo.upstream ?? '—' }}</span>
            </div>
            <div v-else class="muted">点「同步检查」查看</div>
          </div>
        </div>
      </div>
    </template>
  </section>
</template>