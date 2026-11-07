<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

import { useWorkspaceStore } from './stores/workspace'

const store = useWorkspaceStore()
const route = useRoute()
const router = useRouter()

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

const paletteOpen = ref(false)
const paletteQuery = ref('')
const paletteIndex = ref(0)

const paletteItems = computed(() => {
  const base = [
    ...nav.map((item) => ({ label: item.label, hint: '页面', run: () => void router.push(item.to) })),
    { label: '刷新工作区', hint: '动作', run: () => void store.refreshWorkspace() },
    { label: '从 git 历史重建索引', hint: '动作', run: () => void store.rebuildIndex() },
    { label: '打开日志目录', hint: '动作', run: () => void window.gitmove.invoke({ op: 'open.logs' }) },
    { label: '检查更新', hint: '动作', run: () => void window.gitmove.invoke({ op: 'update.check' }) }
  ]
  const keyword = paletteQuery.value.trim().toLowerCase()
  return keyword
    ? base.filter((item) => item.label.toLowerCase().includes(keyword) || item.hint.includes(keyword))
    : base
})

function openPalette() {
  paletteOpen.value = true
  paletteQuery.value = ''
  paletteIndex.value = 0
}

function closePalette() {
  paletteOpen.value = false
}

function runPaletteItem(item: { run: () => void }) {
  closePalette()
  item.run()
}

function onKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    openPalette()
    return
  }
  if (!paletteOpen.value) return
  if (event.key === 'Escape') {
    closePalette()
  } else if (event.key === 'ArrowDown') {
    event.preventDefault()
    paletteIndex.value = (paletteIndex.value + 1) % Math.max(1, paletteItems.value.length)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    paletteIndex.value = (paletteIndex.value - 1 + paletteItems.value.length) % Math.max(1, paletteItems.value.length)
  } else if (event.key === 'Enter') {
    const item = paletteItems.value[paletteIndex.value]
    if (item) runPaletteItem(item)
  }
}

onMounted(() => {
  void store.bootstrap()
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
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

  <div v-if="paletteOpen" class="palette-backdrop" @click.self="closePalette">
    <div class="palette">
      <input v-model="paletteQuery" class="palette-input" placeholder="跳转页面或执行动作（Esc 关闭）" autofocus @input="paletteIndex = 0" />
      <div class="palette-list">
        <button
          v-for="(item, index) in paletteItems"
          :key="item.label"
          class="palette-item"
          :class="{ active: index === paletteIndex }"
          @click="runPaletteItem(item)"
        >
          <span>{{ item.label }}</span>
          <span class="muted">{{ item.hint }}</span>
        </button>
        <div v-if="!paletteItems.length" class="muted" style="padding: 10px 12px">没有匹配项</div>
      </div>
    </div>
  </div>
</template>
