<script setup lang="ts">
import { computed } from 'vue'

import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const info = computed(() => store.info)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>设置</h1>
        <p class="sub">运行时信息与核心引擎</p>
      </div>
    </header>

    <div class="panel pad">
      <table class="table">
        <tbody>
          <tr>
            <th class="w180">应用版本</th>
            <td class="mono">{{ info?.version ?? '—' }}</td>
          </tr>
          <tr>
            <th>核心引擎</th>
            <td>
              <span class="badge" :class="info?.engine === 'rust' ? 'ok' : 'warn'">
                {{ info?.engine === 'rust' ? 'Rust core' : 'Python（过渡）' }}
              </span>
              <span class="mono dim"> {{ info?.core ?? '' }}</span>
            </td>
          </tr>
          <tr>
            <th>sidecar</th>
            <td class="mono dim">{{ info?.sidecar ?? '—' }}</td>
          </tr>
          <tr>
            <th>平台</th>
            <td class="mono dim">{{ info?.platform ?? '—' }}</td>
          </tr>
          <tr>
            <th>当前工作区</th>
            <td class="mono dim">{{ store.currentWorkspace || '—' }}</td>
          </tr>
          <tr>
            <th>项目数</th>
            <td class="mono">{{ store.projects.length }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p class="footnote">
      环境变量：<code>GITMOVE_CORE</code> 指定 Rust 核心二进制；<code>GITMOVE_PYTHON</code> 指定过渡期 Python；
      若 Electron 被以 <code>ELECTRON_RUN_AS_NODE=1</code> 启动需先清除。
    </p>
  </section>
</template>
