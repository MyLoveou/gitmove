<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { CommitFile, DiffPayload, GraphNode } from '../../../shared/protocol'
import GraphView from '../components/GraphView.vue'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const message = ref('')
const includeMembers = ref(false)
const graphBranch = ref('')
const graphAll = ref(false)
const selectedSha = ref('')
const commitFiles = ref<CommitFile[]>([])
const fileDiff = ref<DiffPayload | null>(null)
const filesBusy = ref(false)

async function invokeOp<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function loadFiles(sha: string) {
  commitFiles.value = []
  fileDiff.value = null
  if (!sha) return
  filesBusy.value = true
  try {
    commitFiles.value = await invokeOp<CommitFile[]>({ op: 'rev.files', workspace: store.currentWorkspace, sha })
  } catch (error) {
    store.error = (error as Error).message
  } finally {
    filesBusy.value = false
  }
}

async function loadFileDiff(path: string) {
  if (!selectedSha.value) return
  try {
    fileDiff.value = await invokeOp<DiffPayload>({
      op: 'changes.diff',
      workspace: store.currentWorkspace,
      member: 'main',
      path,
      commit: selectedSha.value
    })
  } catch (error) {
    store.error = (error as Error).message
  }
}

const rows = computed(() => [...store.revisions].sort((a, b) => b.id - a.id))
const canCommit = computed(() => store.canCommit && message.value.trim().length > 0 && !store.busy)
const selected = computed<GraphNode | undefined>(() =>
  store.graphNodes.find((node) => node.sha === selectedSha.value)
)

async function submit() {
  const ok = await store.commit(message.value.trim(), includeMembers.value)
  if (ok) {
    message.value = ''
    includeMembers.value = false
    await store.loadGraph(graphBranch.value || undefined, graphAll.value)
  }
}

function rollback(id: number) {
  if (!window.confirm(`回滚到修订 #${id}？代码与成员仓库都会切换，资产需单独恢复。`)) return
  void store.checkout(id)
}

async function refreshGraph() {
  await store.loadGraph(graphBranch.value || undefined, graphAll.value)
}

async function copySha() {
  if (!selected.value) return
  await navigator.clipboard.writeText(selected.value.sha)
  store.flash('ok', '已复制 SHA')
}

function short(commit: string | null): string {
  return commit ? commit.slice(0, 7) : '—'
}

watch(selectedSha, (sha) => {
  void loadFiles(sha)
})

onMounted(async () => {
  await store.loadRefs()
  await refreshGraph()
})

watch(
  () => store.currentWorkspace,
  async () => {
    await store.refreshWorkspace()
    await store.loadRefs()
    await refreshGraph()
  }
)
</script>

<template>
  <section class="page">
    <header class="scale">
      <div>
        <div class="scale-kicker">修订</div>
        <h1>{{ rows[0] ? `rev ${rows[0].id}` : '尚无修订' }}</h1>
        <p class="scale-read">
          <span>{{ store.workspaceStatus?.name || '提交图' }}</span>
          <span>{{ rows.length }} 条</span>
        </p>
      </div>
      <button class="btn ghost" :disabled="store.busy" @click="store.refreshWorkspace()">刷新</button>
    </header>

    <div v-if="!store.canCommit" class="banner warn">
      <strong>需要 Rust 核心</strong>
      <span>构建核心后可用提交/回滚：<code>cargo build --release</code></span>
    </div>
    <div class="panel pad">
      <div class="panel-title">
        <strong>图</strong>
        <button class="btn ghost" :disabled="store.busy" @click="store.rebuildIndex()">重建索引</button>
      </div>
      <div class="form-row">
        <label class="field">
          <span>分支</span>
          <select v-model="graphBranch" class="input" @change="refreshGraph">
            <option value="">当前分支</option>
            <option v-for="name in store.branchRefs.local" :key="'l' + name" :value="name">{{ name }}</option>
            <option v-for="name in store.branchRefs.remote" :key="'r' + name" :value="name">origin/{{ name }}</option>
          </select>
        </label>
        <label class="check"><input v-model="graphAll" type="checkbox" @change="refreshGraph" /> 全部分支</label>
        <button class="btn ghost" @click="refreshGraph">刷新图</button>
      </div>

      <GraphView :nodes="store.graphNodes" :selected="selectedSha" @select="selectedSha = $event" />

      <div v-if="selected" class="graph-detail">
        <div class="kv"><span class="muted">SHA</span><span class="mono">{{ selected.sha }}</span></div>
        <div class="kv"><span class="muted">REF</span><span class="mono">{{ selected.refs.join(', ') || '—' }}</span></div>
        <div class="kv"><span class="muted">作者</span><span class="mono">{{ selected.author }} · {{ selected.date.slice(0, 19).replace('T', ' ') }}</span></div>
        <div class="kv"><span class="muted">说明</span><span>{{ selected.subject }}</span></div>
        <div class="form-row" style="margin-top: 8px">
          <button class="btn ghost" @click="copySha">复制 SHA</button>
        </div>
      </div>

      <div v-if="selected && commitFiles.length" class="commit-files">
        <div class="muted label">变更文件（{{ commitFiles.length }}）</div>
        <div v-for="file in commitFiles" :key="file.path" class="commit-file" @click="loadFileDiff(file.path)">
          <span class="mono badge">{{ file.status }}</span>
          <span class="mono">{{ file.path }}</span>
        </div>
      </div>

      <pre v-if="fileDiff" class="diff-pre" style="margin-top: 10px">{{ fileDiff.diff || '（无差异内容）' }}</pre>
      <div v-if="filesBusy" class="muted">正在读取文件…</div>
      </div>
    </div>

    <div class="panel commit-box">
      <div class="commit-row">
        <input v-model="message" class="input" placeholder="修订说明，例如：第一集剪辑完成" :disabled="!store.canCommit || store.busy" />
        <label class="check"><input v-model="includeMembers" type="checkbox" :disabled="!store.canCommit" /> 同时提交成员</label>
        <button class="btn primary" :disabled="!canCommit" @click="submit">{{ store.busy ? '提交中…' : '提交修订' }}</button>
      </div>
    </div>

    <div class="panel">
      <div class="timeline">
        <div v-for="row in rows" :key="row.id" class="rev">
          <div class="rev-gutter"><span class="rev-dot" :class="{ head: row.id === rows[0]?.id }"></span><span class="rev-line"></span></div>
          <div class="rev-body">
            <div class="rev-head">
              <span class="rev-id mono">#{{ row.id }}</span>
              <span class="rev-msg">{{ row.message }}</span>
              <span class="rev-meta mono">{{ short(row.git_commit) }}</span>
              <span v-if="row.branch" class="badge">{{ row.branch }}</span>
              <button class="btn tiny" :disabled="store.busy" @click="rollback(row.id)">回滚</button>
            </div>
            <div class="rev-members">
              <span v-for="member in row.members" :key="member.member" class="chip" :class="{ dirty: member.dirty }">
                {{ member.member }}@{{ member.commit.slice(0, 7) }}{{ member.dirty ? ' · 脏' : '' }}
              </span>
              <span class="rev-time mono">{{ row.created_at.slice(0, 19).replace('T', ' ') }}</span>
            </div>
          </div>
        </div>
        <div v-if="!rows.length" class="empty">
          <template v-if="store.busy">正在读取…</template>
          <template v-else>
            还没有 gitmove 修订；可用「重建索引」从 git 历史导入，或提交第一个修订。
          </template>
        </div>
      </div>
    </div>
  </section>
</template>