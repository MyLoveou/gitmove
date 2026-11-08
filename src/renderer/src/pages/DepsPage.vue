<script setup lang="ts">
import { computed, onMounted, watch, ref } from 'vue'

import type { DepRow, DepStatusRow } from '../../../shared/protocol'
import { useRouter } from 'vue-router'

import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const router = useRouter()
const rows = ref<DepRow[]>([])
const statusRows = ref<DepStatusRow[]>([])
const notice = ref('')
const checking = ref(false)

function statusOf(name: string): DepStatusRow | undefined {
  return statusRows.value.find((row) => row.name === name)
}

async function loadStatus(fetch = false) {
  if (!store.currentWorkspace) return
  checking.value = true
  notice.value = ''
  try {
    statusRows.value = await invoke<DepStatusRow[]>({ op: 'dep.status', workspace: store.currentWorkspace, fetch })
    const outdated = statusRows.value.filter((row) => row.state === 'outdated')
    notice.value = fetch ? `已检查上游：${outdated.length} 个依赖落后` : '已读取本地状态'
  } catch (err) {
    notice.value = (err as Error).message
  } finally {
    checking.value = false
  }
}

async function updateDep(name: string) {
  if (!window.confirm(`把 ${name} 的锁更新到上游最新并写入 project.lock.toml？`)) return
  checking.value = true
  try {
    await invoke({ op: 'dep.update', workspace: store.currentWorkspace, name })
    notice.value = `已更新 ${name}`
    await load()
    await loadStatus()
  } catch (err) {
    notice.value = (err as Error).message
  } finally {
    checking.value = false
  }
}
const offCount = computed(() => rows.value.filter((row) => row.drift || !row.in_effect).length)
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
    rows.value = await invoke<DepRow[]>({ op: 'dep.list', workspace: store.currentWorkspace })
  } catch (err) {
    store.flash('bad', (err as Error).message)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await load()
  await loadStatus()
})

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
        <div class="scale-kicker">依赖</div>
        <h1>{{ store.workspaceStatus?.name || '依赖' }}</h1>
        <p class="scale-read">
          <span>{{ rows.length }} 项</span>
          <span>{{ offCount ? `${offCount} 项偏离` : '声明与实装一致' }}</span>
        </p>
      </div>
      <button class="btn ghost" :disabled="busy" @click="load">刷新</button>
    </header>

    <details class="fold">
      <summary>怎么读这张表</summary>
      <p class="hint">
        数据来自项目根的 <code>project.lock.toml</code>。实装版本与声明不一致是漂移；声明了但没有产物是未生效。
      </p>
    </details>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>依赖</th>
            <th>类型</th>
            <th>声明</th>
            <th>实装</th>
            <th>上游</th>
            <th>落后</th>
            <th>状态</th>
            <th></th>
            <th>行</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.name">
            <td class="mono strong">{{ row.name }}</td>
            <td class="mono dim">{{ row.kind || '—' }}</td>
            <td class="mono dim">{{ row.ref || row.commit?.slice(0, 7) || '—' }}</td>
            <td class="mono dim">{{ row.installed || '—' }}</td>
            <td class="mono">{{ statusOf(row.name)?.upstream_version ?? '—' }}</td>
            <td class="mono">{{ statusOf(row.name)?.behind ?? '—' }}</td>
            <td>
              <span v-if="!row.in_effect" class="badge warn">未生效</span>
              <span v-else-if="row.drift" class="badge bad">漂移</span>
              <span v-else class="badge ok">一致</span>
            </td>
            <td class="mono dim">{{ row.label }}</td>
            <td>
              <button
                v-if="statusOf(row.name)?.state === 'outdated'"
                class="btn tiny"
                :disabled="checking"
                @click="updateDep(row.name)"
              >更新</button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="9" class="empty">{{ busy ? '正在读取…' : '该项目没有 project.lock.toml 或没有声明依赖' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
