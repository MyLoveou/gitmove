<script setup lang="ts">
import { onMounted, watch, ref } from 'vue'

import type { DepRow } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const rows = ref<DepRow[]>([])
const busy = ref(false)
const error = ref('')

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
    rows.value = await invoke<DepRow[]>({ op: 'dep.list', workspace: store.currentWorkspace })
  } catch (err) {
    error.value = (err as Error).message
  } finally {
    busy.value = false
  }
}

onMounted(load)

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
        <h1>依赖</h1>
        <p class="sub">来自项目根 <code>project.lock.toml</code> 的声明与实装版本</p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="busy" @click="load">刷新</button>
      </div>
    </header>

    <div v-if="error" class="banner bad">{{ error }}</div>

    <div class="panel">
      <table class="table">
        <thead>
          <tr>
            <th>依赖</th>
            <th>类型</th>
            <th>声明</th>
            <th>实装</th>
            <th>状态</th>
            <th>行</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.name">
            <td class="mono strong">{{ row.name }}</td>
            <td class="mono dim">{{ row.kind || '—' }}</td>
            <td class="mono dim">{{ row.ref || row.commit?.slice(0, 7) || '—' }}</td>
            <td class="mono dim">{{ row.installed || '—' }}</td>
            <td>
              <span v-if="!row.in_effect" class="badge warn">未生效</span>
              <span v-else-if="row.drift" class="badge bad">漂移</span>
              <span v-else class="badge ok">一致</span>
            </td>
            <td class="mono dim">{{ row.label }}</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="6" class="empty">{{ busy ? '正在读取…' : '该项目没有 project.lock.toml 或没有声明依赖' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
