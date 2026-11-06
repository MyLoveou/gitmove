<script setup lang="ts">
import { computed, onMounted, watch } from 'vue'

import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const info = computed(() => store.info)

function openWorkspace() {
  void window.gitmove.invoke({ op: 'open.workspace', workspace: store.currentWorkspace })
}

function openLogs() {
  void window.gitmove.invoke({ op: 'open.logs' })
}

onMounted(() => {
  void store.loadFiles()
})

watch(
  () => store.currentWorkspace,
  () => {
    void store.loadFiles()
  }
)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>设置</h1>
        <p class="sub">配置文件、运行时信息与日志</p>
      </div>
      <div class="actions">
        <button class="btn ghost" @click="store.loadFiles()">重新加载</button>
        <button class="btn ghost" @click="store.importGitHistory()">导入 git 历史</button>
      </div>
    </header>

    <div v-if="store.error" class="banner bad">{{ store.error }}</div>
    <div v-if="store.notice" class="banner ok">{{ store.notice }}</div>

    <div class="panel pad">
      <div class="merge-head">
        <strong>配置文件</strong>
        <span class="dim">保存前自动保留一份 .bak</span>
      </div>
      <div class="merge-selects">
        <label>
          文件
          <select class="input" :value="store.activeFile" @change="store.loadFile(($event.target as HTMLSelectElement).value)">
            <option v-for="file in store.editableFiles" :key="file.path" :value="file.path">
              {{ file.path }}{{ file.exists ? '' : '（不存在，保存即创建）' }}
            </option>
          </select>
        </label>
        <button class="btn primary" @click="store.saveFile(store.activeFile, store.fileText)">保存</button>
        <button class="btn ghost" @click="openWorkspace">打开工作区目录</button>
        <button class="btn ghost" @click="openLogs">打开日志目录</button>
      </div>
      <textarea
        v-model="store.fileText"
        class="config-pre"
        spellcheck="false"
        :placeholder="store.activeFile ? '（空文件，直接输入后保存）' : '选择一个文件'"
      ></textarea>
      <p class="hint">当前文件：<code>{{ store.activeFile || '—' }}</code> · 支持 .gitignore / .git/info/exclude / gitmove 配置 / workspace / lock</p>
    </div>

    <div class="panel pad">
      <div class="merge-head"><strong>运行时</strong></div>
      <table class="table">
        <tbody>
          <tr><th class="w180">应用版本</th><td class="mono">{{ info?.version ?? '—' }}</td></tr>
          <tr><th>核心引擎</th><td class="mono dim">{{ info?.sidecar ?? '—' }}</td></tr>
          <tr><th>平台</th><td class="mono dim">{{ info?.platform ?? '—' }}</td></tr>
          <tr><th>当前工作区</th><td class="mono dim">{{ store.currentWorkspace || '—' }}</td></tr>
          <tr><th>项目数</th><td class="mono">{{ store.projects.length }}</td></tr>
        </tbody>
      </table>
    </div>

    <p class="footnote">
      日志：主进程把每个操作写入 <code>%APPDATA%\gitmove\logs\main.log</code>（JSON lines），点「打开日志目录」查看。<br />
      说明：总览里的「文件/体积」只统计 <strong>git 跟踪的文件</strong>；素材、模型等未跟踪内容不计入，它们由「备份」页的资产快照管理。
    </p>
  </section>
</template>