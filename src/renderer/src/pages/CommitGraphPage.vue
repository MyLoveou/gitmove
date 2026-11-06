<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { GraphNode } from '../../../shared/protocol'
import GraphView from '../components/GraphView.vue'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const message = ref('')
const includeMembers = ref(false)
const graphBranch = ref('')
const graphAll = ref(false)
const selectedSha = ref('')

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
  store.notice = '已复制 SHA'
}

function short(commit: string | null): string {
  return commit ? commit.slice(0, 7) : '—'
}

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
    <header class="page-head">
      <div>
        <h1>提交图</h1>
        <p class="sub">分支切出、合并、标签都在图里；点节点看详情</p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="store.busy" @click="store.rebuildIndex()">重建索引</button>
        <button class="btn ghost" :disabled="store.busy" @click="store.refreshWorkspace()">刷新</button>
      </div>
    </header>

    <div v-if="!store.canCommit" class="banner warn">
      <strong>需要 Rust 核心</strong>
      <span>构建核心后可用提交/回滚：<code>cargo build --release</code></span>
    </div>
    <div v-if="store.notice" class="banner ok">{{ store.notice }}</div>
    <div v-if="store.error" class="banner bad">{{ store.error }}</div>

    <div class="panel pad">
      <div class="panel-title">
        <strong>提交图</strong>
        <span class="muted">默认只看当前分支；勾选「全部分支」可看所有历史</span>
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