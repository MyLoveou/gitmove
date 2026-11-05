<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import type { ChangeRow } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const rows = ref<ChangeRow[]>([])
const selected = ref<Record<string, boolean>>({})
const message = ref('')
const busy = ref(false)
const notice = ref('')
const error = ref('')

const groups = computed(() => {
  const map = new Map<string, ChangeRow[]>()
  for (const row of rows.value) {
    const list = map.get(row.member) ?? []
    list.push(row)
    map.set(row.member, list)
  }
  return [...map.entries()].map(([member, items]) => ({ member, items }))
})

const chosen = computed(() =>
  rows.value
    .filter((row) => selected.value[key(row)])
    .map((row) => ({ member: row.member, path: row.path }))
)

function key(row: ChangeRow): string {
  return `${row.member}:${row.path}`
}

async function invoke<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function load() {
  if (!store.currentWorkspace) return
  busy.value = true
  error.value = ''
  try {
    rows.value = await invoke<ChangeRow[]>({ op: 'changes.list', workspace: store.currentWorkspace })
    selected.value = {}
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

function toggleAll(value: boolean) {
  const next: Record<string, boolean> = {}
  for (const row of rows.value) next[key(row)] = value
  selected.value = next
}

async function commitSelected() {
  if (!message.value.trim() || !chosen.value.length) return
  busy.value = true
  notice.value = ''
  error.value = ''
  try {
    const outcome = await invoke<{ revision: number }>({
      op: 'rev.commitPaths',
      workspace: store.currentWorkspace,
      message: message.value.trim(),
      selections: chosen.value
    })
    notice.value = `已创建修订 ${outcome.revision}（${chosen.value.length} 个文件）`
    message.value = ''
    await load()
    await store.refreshWorkspace()
    await store.refreshProjects()
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

async function discardSelected() {
  if (!chosen.value.length) return
  if (!window.confirm(`放弃 ${chosen.value.length} 个文件的改动？此操作不可撤销。`)) return
  busy.value = true
  error.value = ''
  try {
    await invoke({ op: 'changes.discard', workspace: store.currentWorkspace, selections: chosen.value })
    notice.value = '已放弃所选改动'
    await load()
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>变更</h1>
        <p class="sub">按成员列出改动，勾选后提交或放弃（文件级，不再是整仓）</p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="busy" @click="load">刷新</button>
      </div>
    </header>

    <div v-if="error" class="banner bad">{{ error }}</div>
    <div v-if="notice" class="banner ok">{{ notice }}</div>

    <div class="panel commit-box">
      <div class="commit-row">
        <input v-model="message" class="input" placeholder="修订说明" :disabled="busy" />
        <button class="btn primary" :disabled="busy || !chosen.length || !message.trim()" @click="commitSelected">
          提交选中（{{ chosen.length }}）
        </button>
        <button class="btn" :disabled="busy || !chosen.length" @click="discardSelected">放弃选中</button>
      </div>
      <p class="hint">
        全选 / 清空：
        <a href="#" @click.prevent="toggleAll(true)">全选</a> ·
        <a href="#" @click.prevent="toggleAll(false)">清空</a>
        · 工作区：<code>{{ store.currentWorkspace }}</code>
      </p>
    </div>

    <div v-for="group in groups" :key="group.member" class="panel pad">
      <div class="merge-head"><strong>{{ group.member }}</strong><span class="dim">{{ group.items.length }} 个改动</span></div>
      <table class="table">
        <thead><tr><th style="width:36px"></th><th>代码</th><th>路径</th></tr></thead>
        <tbody>
          <tr v-for="row in group.items" :key="key(row)">
            <td><input v-model="selected[key(row)]" type="checkbox" /></td>
            <td class="mono dim">{{ row.code }}</td>
            <td class="mono">{{ row.path }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!rows.length" class="panel"><div class="empty">{{ busy ? '正在读取…' : '工作区干净，没有待提交改动' }}</div></div>
  </section>
</template>
