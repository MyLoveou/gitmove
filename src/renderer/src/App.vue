<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { useWorkspaceStore } from './stores/workspace'

const store = useWorkspaceStore()
const route = useRoute()

const nav = [
  { label: '总览', to: '/' },
  { label: '变更', to: '/changes' },
  { label: '提交图', to: '/graph' },
  { label: '工作区', to: '/workspace' },
  { label: '依赖', to: '/deps' },
  { label: '备份', to: '/backup' },
  { label: '设置', to: '/settings' }
]

const statusText = computed(() => {
  if (store.error) return `错误：${store.error}`
  if (store.loading) return '正在读取…'
  if (!store.lastRefresh) return '等待刷新'
  return `${store.projects.length} 个项目 · ${store.errors} 错误 · ${store.warns} 警告`
})

onMounted(() => {
  void store.bootstrap()
})
</script>

<template>
  <div class="titlebar"><span>gitmove</span></div>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div>
          <div class="brand-name">gitmove</div>
          <div class="brand-sub">{{ store.workspaceStatus?.name || '未选择工作区' }}</div>
        </div>
      </div>

      <nav class="nav">
        <RouterLink v-for="item in nav" :key="item.to" class="nav-item" :class="{ active: route.path === item.to }" :to="item.to">
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <div class="meta-line">sidecar</div>
        <div class="meta-value mono">{{ store.info?.sidecar ?? '—' }}</div>
        <div class="meta-line">platform</div>
        <div class="meta-value mono">{{ store.info?.platform ?? '—' }}</div>
      </div>
    </aside>

    <main class="content">
      <RouterView />
    </main>

    <div class="toasts" aria-live="polite">
      <div v-for="toast in store.toasts" :key="toast.id" class="toast" :class="toast.tone">
        <p>{{ toast.text }}</p>
        <button type="button" aria-label="关闭" @click="store.dismissToast(toast.id)">×</button>
      </div>
    </div>

    <footer class="statusbar">
      <span class="dot" :class="{ busy: store.loading, bad: Boolean(store.error) }"></span>
      <span>{{ statusText }}</span>
      <span class="spacer"></span>
      <span class="mono">{{ store.info ? `app ${store.info.version}` : '' }}</span>
    </footer>
  </div>
</template>
