<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

import { useWorkspaceStore } from './stores/workspace'

const store = useWorkspaceStore()
const route = useRoute()

const nav = [
  { label: '总览', hint: '项目与健康', to: '/', enabled: true },
  { label: '变更', hint: '文件级', to: '/changes', enabled: true },
  { label: '提交图', hint: 'M3', to: '/graph', enabled: true },
  { label: '工作区', hint: 'M2', to: '/workspace', enabled: true },
  { label: '依赖', hint: 'lock', to: '/deps', enabled: true },
  { label: '备份', hint: 'M4', to: '/backup', enabled: true },
  { label: '设置', hint: 'M5', to: '/settings', enabled: true }
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
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">gm</div>
        <div>
          <div class="brand-name">gitmove</div>
          <div class="brand-sub">v2 preview</div>
        </div>
      </div>

      <nav class="nav">
        <template v-for="item in nav" :key="item.label">
          <RouterLink v-if="item.enabled" class="nav-item" :class="{ active: route.path === item.to }" :to="item.to">
            <span>{{ item.label }}</span>
            <span class="nav-hint">{{ item.hint }}</span>
          </RouterLink>
          <div v-else class="nav-item disabled" :title="`${item.label}（${item.hint} 交付）`">
            <span>{{ item.label }}</span>
            <span class="nav-hint">{{ item.hint }}</span>
          </div>
        </template>
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

    <footer class="statusbar">
      <span class="dot" :class="{ busy: store.loading, bad: Boolean(store.error) }"></span>
      <span>{{ statusText }}</span>
      <span class="spacer"></span>
      <span class="mono">{{ store.info ? `app ${store.info.version}` : '' }}</span>
    </footer>
  </div>
</template>
