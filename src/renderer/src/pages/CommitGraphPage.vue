<script setup lang="ts">
import { computed, ref } from 'vue'

import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const message = ref('')
const includeMembers = ref(false)

const rows = computed(() => [...store.revisions].sort((a, b) => b.id - a.id))
const canCommit = computed(() => store.canCommit && message.value.trim().length > 0 && !store.busy)

async function submit() {
  const ok = await store.commit(message.value.trim(), includeMembers.value)
  if (ok) {
    message.value = ''
    includeMembers.value = false
  }
}

function short(commit: string | null): string {
  return commit ? commit.slice(0, 7) : '—'
}
</script>

<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h1>提交图</h1>
        <p class="sub">
          修订 = git commit + 成员 commits + 资产快照（M3：Rust 核心已接管 commit/log）
        </p>
      </div>
      <div class="actions">
        <button class="btn ghost" :disabled="store.busy" @click="store.refreshWorkspace()">刷新</button>
      </div>
    </header>

    <div v-if="!store.canCommit" class="banner warn">
      <strong>需要 Rust 核心</strong>
      <span>构建核心后可用提交/回滚：<code>cargo build --release</code>，或设置 <code>GITMOVE_CORE</code>。</span>
    </div>
    <div v-if="store.notice" class="banner ok">{{ store.notice }}</div>
    <div v-if="store.error" class="banner bad">{{ store.error }}</div>

    <div class="panel commit-box">
      <div class="commit-row">
        <input
          v-model="message"
          class="input"
          placeholder="修订说明，例如：第一集剪辑完成"
          :disabled="!store.canCommit || store.busy"
          @keyup.enter="submit"
        />
        <label class="check">
          <input v-model="includeMembers" type="checkbox" :disabled="!store.canCommit" />
          同时提交成员
        </label>
        <button class="btn primary" :disabled="!canCommit" @click="submit">
          {{ store.busy ? '提交中…' : '提交修订' }}
        </button>
      </div>
      <p class="hint">
        工作区：<code>{{ store.currentWorkspace || '未选择' }}</code> · 成员脏时首次提交会被拒绝（再点一次只提交主仓）
      </p>
    </div>

    <div class="panel">
      <div class="timeline">
        <div v-for="row in rows" :key="row.id" class="rev">
          <div class="rev-gutter">
            <span class="rev-dot" :class="{ head: row.id === rows[0]?.id }"></span>
            <span class="rev-line"></span>
          </div>
          <div class="rev-body">
            <div class="rev-head">
              <span class="rev-id mono">#{{ row.id }}</span>
              <span class="rev-msg">{{ row.message }}</span>
              <span class="rev-meta mono">{{ short(row.git_commit) }}</span>
              <span v-if="row.branch" class="badge">{{ row.branch }}</span>
            </div>
            <div class="rev-members">
              <span v-for="member in row.members" :key="member.member" class="chip" :class="{ dirty: member.dirty }">
                {{ member.member }}@{{ member.commit.slice(0, 7) }}{{ member.dirty ? ' · 脏' : '' }}
              </span>
              <span v-if="!row.members.length" class="dim">（未记录成员）</span>
              <span class="rev-time mono">{{ row.created_at.slice(0, 19).replace('T', ' ') }}</span>
            </div>
          </div>
        </div>
        <div v-if="!rows.length" class="empty">
          {{ store.busy ? '正在读取…' : '还没有修订：提交第一个修订试试' }}
        </div>
      </div>
    </div>
  </section>
</template>
