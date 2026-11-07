<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { ChangeRow } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const rows = ref<ChangeRow[]>([])
const selected = ref<Record<string, boolean>>({})
const message = ref('')
const busy = ref(false)

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

function codeLabel(code: string): string {
  if (code === '??') return '未跟踪'
  if (code.includes('A')) return '新增'
  if (code.includes('D')) return '删除'
  if (code.includes('R')) return '重命名'
  if (code.includes('M')) return '修改'
  return code
}

function toggleMember(member: string, value: boolean) {
  const next = { ...selected.value }
  for (const row of rows.value.filter((item) => item.member === member)) next[key(row)] = value
  selected.value = next
}

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
  try {
    rows.value = await invoke<ChangeRow[]>({ op: 'changes.list', workspace: store.currentWorkspace })
    selected.value = {}
  } catch (err) {
    store.flash('bad', (err as Error).message)
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
  try {
    const outcome = await invoke<{ revision: number }>({
      op: 'rev.commitPaths',
      workspace: store.currentWorkspace,
      message: message.value.trim(),
      selections: chosen.value
    })
    store.flash('ok', `已创建修订 ${outcome.revision}（${chosen.value.length} 个文件）`)
    message.value = ''
    await load()
    await store.refreshWorkspace()
    await store.refreshProjects()
  } catch (err) {
    store.flash('bad', (err as Error).message)
  } finally {
    busy.value = false
  }
}

async function discardSelected() {
  if (!chosen.value.length) return
  if (!window.confirm(`放弃 ${chosen.value.length} 个文件的改动？此操作不可撤销。`)) return
  busy.value = true
  try {
    await invoke({ op: 'changes.discard', workspace: store.currentWorkspace, selections: chosen.value })
    store.flash('ok', '已放弃所选改动')
    await load()
  } catch (err) {
    store.flash('bad', (err as Error).message)
  } finally {
    busy.value = false
  }
}

onMounted(load)

watch(
  () => store.currentWorkspace,
  () => {
    void load()
  }
)
</script>

<template>
  <section class="page">
    <header class="scale">
      <div>
        <div class="scale-kicker">待处理变更</div>
        <h1>{{ store.workspaceStatus?.name || '变更' }}</h1>
        <p class="scale-read">
          <span>{{ rows.length ? `${rows.length} 个文件` : '工作区干净' }}</span>
          <span>已选 {{ chosen.length }}</span>
        </p>
      </div>
      <button class="btn ghost" :disabled="busy" @click="load">刷新</button>
    </header>

    <div class="panel commit-box">
      <div class="commit-row">
        <input v-model="message" class="input" placeholder="修订说明" :disabled="busy" />
        <button class="btn primary" :disabled="busy || !chosen.length || !message.trim()" @click="commitSelected">
          提交选中（{{ chosen.length }}）
        </button>
        <button class="btn" :disabled="busy || !chosen.length" @click="discardSelected">放弃选中</button>
      </div>
      <p class="hint">
        <a href="#" @click.prevent="toggleAll(true)">全选</a>
        ·
        <a href="#" @click.prevent="toggleAll(false)">清空</a>
      </p>
    </div>

    <div v-for="group in groups" :key="group.member" class="panel pad">
      <div class="merge-head">
        <input
          type="checkbox"
          :checked="group.items.every((item) => selected[key(item)])"
          @change="toggleMember(group.member, ($event.target as HTMLInputElement).checked)"
        />
        <strong>{{ group.member }}</strong>
        <span class="dim">{{ group.items.length }} 个改动</span>
      </div>
      <table class="table">
        <thead><tr><th style="width:36px"></th><th>代码</th><th>路径</th></tr></thead>
        <tbody>
          <tr v-for="row in group.items" :key="key(row)">
            <td><input v-model="selected[key(row)]" type="checkbox" /></td>
            <td class="mono dim">{{ codeLabel(row.code) }}</td>
            <td class="mono">{{ row.path }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-if="!rows.length" class="panel"><div class="empty">{{ busy ? '正在读取…' : '工作区干净，没有待提交改动' }}</div></div>
  </section>
</template>
