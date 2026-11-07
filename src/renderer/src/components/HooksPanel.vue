<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { HookStatusPayload } from '../../../shared/protocol'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const status = ref<HookStatusPayload | null>(null)
const notice = ref('')
const error = ref('')

const events = ['pre-commit', 'post-commit', 'pre-push']

const form = ref({ event: 'pre-commit', command: '', blocking: true, global: false })
const installForm = ref({ members: true, events: ['pre-commit'] as string[] })
const previewEvent = ref('pre-commit')

async function call<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function load() {
  if (!store.currentWorkspace) return
  try {
    status.value = await call<HookStatusPayload>({ op: 'hook.status', workspace: store.currentWorkspace })
  } catch (err) {
    error.value = (err as Error).message
  }
}

function hooksOf(event: string) {
  return (status.value?.hooks ?? []).filter((hook) => hook.event === event)
}

function repoHas(repo: string, event: string): boolean {
  return (status.value?.repos ?? []).find((row) => row.repo === repo)?.events.includes(event) ?? false
}

async function addHook() {
  if (!form.value.command.trim()) return
  try {
    status.value = await call<HookStatusPayload>({
      op: 'hook.add',
      workspace: store.currentWorkspace,
      event: form.value.event,
      command: form.value.command.trim(),
      blocking: form.value.blocking,
      global: form.value.global
    })
    notice.value = '已添加'
    form.value.command = ''
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function toggle(hook: { event: string; command: string; enabled: boolean; source: string }) {
  try {
    status.value = await call<HookStatusPayload>({
      op: 'hook.toggle',
      workspace: store.currentWorkspace,
      event: hook.event,
      command: hook.command,
      enabled: !hook.enabled,
      global: hook.source === 'global'
    })
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function removeHook(hook: { event: string; command: string; source: string }) {
  try {
    status.value = await call<HookStatusPayload>({
      op: 'hook.remove',
      workspace: store.currentWorkspace,
      event: hook.event,
      command: hook.command,
      global: hook.source === 'global'
    })
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function install() {
  try {
    status.value = await call<HookStatusPayload>({
      op: 'hook.install',
      workspace: store.currentWorkspace,
      events: installForm.value.events,
      members: installForm.value.members
    })
    notice.value = '已安装'
  } catch (err) {
    error.value = (err as Error).message
  }
}

async function uninstall() {
  try {
    status.value = await call<HookStatusPayload>({
      op: 'hook.uninstall',
      workspace: store.currentWorkspace,
      events: installForm.value.events,
      members: installForm.value.members
    })
    notice.value = '已移除'
  } catch (err) {
    error.value = (err as Error).message
  }
}

const preview = computed(
  () => status.value?.scripts.find((item) => item.event === previewEvent.value)?.text ?? '（安装后生成）'
)

function toggleEvent(event: string) {
  const list = installForm.value.events
  installForm.value.events = list.includes(event) ? list.filter((item) => item !== event) : [...list, event]
}

onMounted(load)
watch(() => store.currentWorkspace, load)
</script>

<template>
  <div class="panel pad">
    <div class="panel-title">
      <strong>Git Hooks</strong>
      <span class="muted">命令定义分「工作区 / 全局」；安装时可选择事件与仓库范围</span>
    </div>

    <div v-if="notice" class="banner ok">{{ notice }}</div>
    <div v-if="error" class="banner bad">{{ error }}</div>

    <div class="hook-grid">
      <div v-for="event in events" :key="event" class="hook-card">
        <div class="hook-card-head">
          <span class="mono strong">{{ event }}</span>
          <span class="badge" :class="repoHas('main', event) ? 'ok' : ''">{{ repoHas('main', event) ? '已安装' : '未安装' }}</span>
        </div>
        <div v-for="hook in hooksOf(event)" :key="hook.command + hook.source" class="hook-row">
          <div class="hook-cmd mono">{{ hook.command }}</div>
          <div class="hook-meta">
            <span class="badge" :class="hook.blocking ? 'warn' : ''">{{ hook.blocking ? '阻断' : '提示' }}</span>
            <span class="badge">{{ hook.source === 'global' ? '全局' : '工作区' }}</span>
            <button class="btn tiny" @click="toggle(hook)">{{ hook.enabled ? '停用' : '启用' }}</button>
            <button class="btn tiny" @click="removeHook(hook)">删除</button>
          </div>
        </div>
        <div v-if="!hooksOf(event).length" class="muted">（无命令）</div>
      </div>
    </div>

    <div class="form-row" style="margin-top: 12px">
      <label class="field"><span>事件</span>
        <select v-model="form.event" class="input">
          <option v-for="event in events" :key="event" :value="event">{{ event }}</option>
        </select>
      </label>
      <label class="field" style="min-width: 320px"><span>命令</span><input v-model="form.command" class="input" placeholder="npm test" /></label>
      <label class="check"><input v-model="form.blocking" type="checkbox" /> 失败阻断</label>
      <label class="check"><input v-model="form.global" type="checkbox" /> 写入全局</label>
      <button class="btn primary" @click="addHook()">添加</button>
    </div>

    <div class="panel-title" style="margin-top: 18px"><strong>安装</strong><span class="muted">写入 .git/hooks，保留原有内容</span></div>
    <div class="form-row">
      <label class="field"><span>范围</span>
        <select v-model="installForm.members" class="input">
          <option :value="false">仅主仓</option>
          <option :value="true">主仓 + 成员</option>
        </select>
      </label>
      <label v-for="event in events" :key="event" class="check">
        <input type="checkbox" :checked="installForm.events.includes(event)" @change="toggleEvent(event)" /> {{ event }}
      </label>
      <button class="btn" @click="install()">安装</button>
      <button class="btn ghost" @click="uninstall()">卸载</button>
    </div>

    <table class="table" style="margin-top: 12px">
      <thead><tr><th>仓库</th><th v-for="event in events" :key="event">{{ event }}</th></tr></thead>
      <tbody>
        <tr v-for="repo in status?.repos ?? []" :key="repo.repo">
          <td class="mono">{{ repo.repo }}</td>
          <td v-for="event in events" :key="event">
            <span :class="repoHas(repo.repo, event) ? 'ok' : 'dim'">{{ repoHas(repo.repo, event) ? '✓' : '—' }}</span>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="panel-title" style="margin-top: 16px"><strong>脚本预览</strong></div>
    <div class="form-row">
      <label class="field"><span>事件</span>
        <select v-model="previewEvent" class="input">
          <option v-for="event in events" :key="event" :value="event">{{ event }}</option>
        </select>
      </label>
    </div>
    <pre class="graph-pre">{{ preview }}</pre>

    <p class="hint">
      配置文件：工作区 <code>.gitmove/hooks.toml</code> · 全局 <code>~/.gitmove/hooks.toml</code>（同名命令以工作区为准）。
    </p>
  </div>
</template>