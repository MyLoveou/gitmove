<script setup lang="ts">
import { computed } from 'vue'

import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const status = computed(() => store.workspaceStatus)

function roleClass(role: string): string {
  if (role === 'main') return 'ok'
  if (role === 'editable') return 'warn'
  return ''
}
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>工作区</h1>
        <p class="sub">多仓组合：主仓 + AI 规范库 + 工具库 + 本地素材仓（M2：Rust 解析 workspace.toml）</p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="store.busy" @click="store.refreshWorkspace()">刷新</button>
      </div>
    </header>

    <div v-if="store.error" class="banner bad">{{ store.error }}</div>
    <div v-if="!status" class="banner warn">
      选择一个项目后显示成员；若没有 Rust 核心，该页不可用。
    </div>

    <template v-if="status">
      <div class="stats">
        <div class="stat">
          <span class="stat-label">工作区</span>
          <span class="stat-value small">{{ status.name }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">成员</span>
          <span class="stat-value">{{ status.members.length }}</span>
        </div>
        <div class="stat">
          <span class="stat-label">已声明</span>
          <span class="stat-value small">{{ status.declared ? 'workspace.toml' : '隐式（单仓）' }}</span>
        </div>
      </div>

      <div class="panel">
        <table class="table">
          <thead>
            <tr>
              <th>成员</th>
              <th>角色</th>
              <th>策略</th>
              <th>HEAD</th>
              <th>pin</th>
              <th>状态</th>
              <th>路径</th>
            </tr>
          </thead>
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

      <p class="footnote">
        依赖回推（editable 成员）与双盘备份在 M4 接入；此处先展示成员与版本锚点。
      </p>
    </template>
  </section>
</template>
