<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { HookStatusPayload } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const info = computed(() => store.info)
const preview = ref<{ type: string; text: string }[] | null>(null)
const savedText = ref('')
const hookStatus = ref<HookStatusPayload | null>(null)
const hookNotice = ref('')

async function callOp<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function loadHooks() {
  if (!store.currentWorkspace) return
  try {
    hookStatus.value = await callOp<HookStatusPayload>({ op: 'hook.status', workspace: store.currentWorkspace })
  } catch (error) {
    hookNotice.value = (error as Error).message
  }
}

async function installHooks() {
  try {
    hookStatus.value = await callOp<HookStatusPayload>({ op: 'hook.install', workspace: store.currentWorkspace })
    hookNotice.value = '已安装 pre-commit / pre-push 回调'
  } catch (error) {
    hookNotice.value = (error as Error).message
  }
}

async function uninstallHooks() {
  try {
    hookStatus.value = await callOp<HookStatusPayload>({ op: 'hook.uninstall', workspace: store.currentWorkspace })
    hookNotice.value = '已移除 gitmove 钩子块'
  } catch (error) {
    hookNotice.value = (error as Error).message
  }
}

type DiffLine = { type: string; text: string }

function simpleDiff(before: string, after: string): DiffLine[] {
  const a = before.split(/\r?\n/)
  const b = after.split(/\r?\n/)
  const limit = 800
  if (a.length > limit || b.length > limit) {
    return [{ type: '!', text: `文件较大（${a.length} → ${b.length} 行），无法逐行预览` }]
  }
  const dp: number[][] = Array.from({ length: a.length + 1 }, () => new Array(b.length + 1).fill(0))
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1])
    }
  }
  const out: DiffLine[] = []
  let i = 0
  let j = 0
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ type: ' ', text: a[i] })
      i += 1
      j += 1
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: '-', text: a[i] })
      i += 1
    } else {
      out.push({ type: '+', text: b[j] })
      j += 1
    }
  }
  while (i < a.length) {
    out.push({ type: '-', text: a[i] })
    i += 1
  }
  while (j < b.length) {
    out.push({ type: '+', text: b[j] })
    j += 1
  }
  return out
}

function requestSave() {
  preview.value = simpleDiff(savedText.value, store.fileText)
}

async function confirmSave() {
  const ok = await store.saveFile(store.activeFile, store.fileText)
  if (ok) {
    savedText.value = store.fileText
    preview.value = null
  }
}

async function loadSelected(path: string) {
  await store.loadFile(path)
  savedText.value = store.fileText
  preview.value = null
}

function openWorkspace() {
  void window.gitmove.invoke({ op: 'open.workspace', workspace: store.currentWorkspace })
}

function openLogs() {
  void window.gitmove.invoke({ op: 'open.logs' })
}

const lineNumbers = computed(() => store.fileText.split(/\r?\n/).map((_, index) => index + 1))

onMounted(async () => {
  await store.loadFiles()
  savedText.value = store.fileText
  await loadHooks()
})

watch(
  () => store.currentWorkspace,
  async () => {
    await store.loadFiles()
    savedText.value = store.fileText
  }
)

watch(
  () => store.activeFile,
  () => {
    savedText.value = store.fileText
    preview.value = null
  }
)
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>设置</h1>
        <p class="sub">配置文件（.gitignore / gitmove 配置 / workspace / lock）与运行时信息</p>
      </div>
      <div class="actions">
        <button class="btn ghost" @click="store.importGitHistory()">导入 git 历史</button>
      </div>
    </header>

    <div v-if="store.error" class="banner bad">{{ store.error }}</div>
    <div v-if="store.notice" class="banner ok">{{ store.notice }}</div>

    <div class="panel pad">
      <div class="panel-title">
        <strong>编辑器</strong>
        <span class="muted">保存前先看差异，确认后才写入；写入前自动保留 .bak</span>
      </div>

      <div class="form-row">
        <label class="field">
          <span>文件</span>
          <select class="input" :value="store.activeFile" @change="loadSelected(($event.target as HTMLSelectElement).value)">
            <option v-for="file in store.editableFiles" :key="file.path" :value="file.path">
              {{ file.path }}{{ file.exists ? '' : '（不存在，保存即创建）' }}
            </option>
          </select>
        </label>
        <button class="btn primary" @click="requestSave">保存…</button>
        <button class="btn ghost" @click="loadSelected(store.activeFile)">重新加载</button>
        <button class="btn ghost" @click="openWorkspace">打开工作区目录</button>
        <button class="btn ghost" @click="openLogs">打开日志目录</button>
      </div>

      <div class="editor">
        <div class="gutter">
          <div v-for="n in lineNumbers" :key="n">{{ n }}</div>
        </div>
        <textarea v-model="store.fileText" class="editor-area" spellcheck="false" wrap="off"></textarea>
      </div>
      <p class="hint">当前文件：<code>{{ store.activeFile || '—' }}</code> · {{ lineNumbers.length }} 行</p>
    </div>

    <div v-if="preview" class="panel pad">
      <div class="panel-title">
        <strong>保存预览</strong>
        <span class="muted">+ 新增 · − 删除 · 空白为未改动</span>
      </div>
      <div class="diff">
        <div
          v-for="(line, index) in preview"
          :key="index"
          class="diff-line"
          :class="{ add: line.type === '+', del: line.type === '-' }"
        >
          <span class="diff-sign">{{ line.type === ' ' ? '' : line.type }}</span>
          <span class="diff-text mono">{{ line.text }}</span>
        </div>
      </div>
      <div class="form-row" style="margin-top: 12px">
        <button class="btn primary" @click="confirmSave">确认保存</button>
        <button class="btn ghost" @click="preview = null">取消</button>
      </div>
    </div>

    <div class="panel pad">
      <div class="panel-title">
        <strong>日志</strong>
        <button class="btn ghost" @click="store.loadLogs()">刷新日志</button>
        <button class="btn ghost" @click="openLogs">打开日志目录</button>
      </div>
      <pre class="graph-pre">{{ store.logText || '点击「刷新日志」读取 %APPDATA%\\gitmove\\logs\\main.log' }}</pre>
    </div>

    <div class="panel pad">
      <div class="panel-title">
        <strong>Git Hooks</strong>
        <span class="muted">安装后提交/推送时回调 gitmove（命令定义在 hooks.toml）</span>
      </div>
      <div v-if="hookNotice" class="banner ok">{{ hookNotice }}</div>
      <div class="form-row">
        <button class="btn ghost" @click="loadHooks()">刷新</button>
        <button class="btn" @click="installHooks()">安装钩子</button>
        <button class="btn ghost" @click="uninstallHooks()">移除钩子</button>
      </div>
      <div class="kv"><span class="muted">已安装</span><span class="mono">{{ hookStatus?.installed.join(', ') || '—' }}</span></div>
      <div class="kv"><span class="muted">配置文件</span><span class="mono">{{ hookStatus?.config || '—' }}</span></div>
      <div v-for="hook in hookStatus?.hooks ?? []" :key="hook.event + hook.command" class="kv">
        <span class="mono">{{ hook.event }}{{ hook.blocking ? '' : ' (advisory)' }}</span>
        <span class="mono dim">{{ hook.command }}</span>
      </div>
      <p class="hint">在 <code>.gitmove/hooks.toml</code> 里写 <code>[[hook]] event/command/blocking</code>，或用 <code>gitmove hook add --event pre-commit --command "npm test"</code>。</p>
    </div>

    <div class="panel pad">
      <div class="panel-title"><strong>运行时</strong></div>
      <table class="table">
        <tbody>
          <tr><th class="w180">应用版本</th><td class="mono">{{ info?.version ?? '—' }}</td></tr>
          <tr><th>核心引擎</th><td class="mono dim">{{ info?.sidecar ?? '—' }}</td></tr>
          <tr><th>平台</th><td class="mono dim">{{ info?.platform ?? '—' }}</td></tr>
          <tr><th>当前工作区</th><td class="mono dim">{{ store.currentWorkspace || '—' }}</td></tr>
        </tbody>
      </table>
    </div>

    <p class="footnote">
      日志：<code>%APPDATA%\gitmove\logs\main.log</code>（JSON lines）。<br />
      「总览」的文件/体积只统计 git 跟踪内容；素材由「备份」页的资产快照管理。
    </p>
  </section>
</template>