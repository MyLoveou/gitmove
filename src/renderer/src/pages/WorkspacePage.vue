<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import type { BranchRow, MemberStatus } from '../../../shared/protocol'
import { commitsMatch, memberDrift } from '../marks'
import { useWorkspaceStore } from '../stores/workspace'

const store = useWorkspaceStore()
const status = computed(() => store.workspaceStatus)
const branches = ref<BranchRow[]>([])
const target = ref('')
const newMember = ref({ name: '', path: '', role: 'editable', strategy: 'vendor', source: '', pin: '', track: '' })
const busy = ref(false)
const openMember = ref('')
const branchName = ref('')
const useName = ref('')
const commitMessage = ref('')
const localBranches = ref<string[]>([])

async function invoke<T>(request: Parameters<Window['gitmove']['invoke']>[0]): Promise<T> {
  const result = (await window.gitmove.invoke(request)) as { ok: boolean; data?: T; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '失败')
  return result.data as T
}

async function readWorkspaceToml(): Promise<string> {
  const result = (await window.gitmove.invoke({
    op: 'file.read',
    workspace: store.currentWorkspace,
    path: 'workspace.toml'
  })) as { ok: boolean; data?: { text: string } }
  if (!result.ok || !result.data) return ''
  return result.data.text
}

async function writeWorkspaceToml(text: string) {
  const result = (await window.gitmove.invoke({
    op: 'file.write',
    workspace: store.currentWorkspace,
    path: 'workspace.toml',
    text
  })) as { ok: boolean; error?: { message: string } }
  if (!result.ok) throw new Error(result.error?.message ?? '写入失败')
}

async function addMember() {
  const member = newMember.value
  if (!member.name.trim() || !member.path.trim()) {
    store.flash('bad', '成员名和路径必填')
    return
  }
  if (member.strategy !== 'link' && !member.source.trim()) {
    store.flash('bad', 'vendor / clone 策略需要来源地址')
    return
  }
  busy.value = true
  try {
    const ok = await store.addMember({
      name: member.name.trim(),
      path: member.path.trim().replace(/\\/g, '/'),
      role: member.role,
      strategy: member.strategy,
      source: member.source.trim(),
      pin: member.pin.trim() || undefined,
      track: member.track.trim() || undefined
    })
    if (ok) {
      newMember.value = { name: '', path: '', role: 'editable', strategy: 'vendor', source: '', pin: '', track: '' }
      await load()
    }
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function removeMember(name: string) {
  if (!window.confirm(`从 workspace.toml 移除成员 ${name}？（不会删除磁盘上的仓库）`)) return
  busy.value = true
  try {
    const current = await readWorkspaceToml()
    const blocks = current.split(/(?=\[\[member\]\])/)
    const kept = blocks.filter((block) => {
      if (!block.startsWith('[[member]]')) return true
      const match = block.match(/name\s*=\s*"([^"]*)"/)
      return !(match && match[1] === name)
    })
    await writeWorkspaceToml(kept.join(''))
    store.flash('ok', `已移除成员 ${name}（仓库目录保留）`)
    await store.refreshWorkspace()
    await load()
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

async function load() {
  if (!store.currentWorkspace) return
  busy.value = true
  try {
    branches.value = await invoke<BranchRow[]>({ op: 'ws.branches', workspace: store.currentWorkspace })
  } catch (error) {
    store.flash('bad', (error as Error).message)
  } finally {
    busy.value = false
  }
}

function writable(role: string): boolean {
  return role !== 'readonly'
}

async function toggleBranch(name: string) {
  if (openMember.value === name) {
    openMember.value = ''
    return
  }
  openMember.value = name
  branchName.value = ''
  useName.value = ''
  commitMessage.value = ''
  try {
    localBranches.value = await store.memberBranches(name)
  } catch (error) {
    localBranches.value = []
    store.flash('bad', (error as Error).message)
  }
}

async function runRow(action: () => Promise<void>) {
  try {
    await action()
    if (openMember.value) localBranches.value = await store.memberBranches(openMember.value)
    await load()
  } catch (error) {
    store.flash('bad', (error as Error).message)
  }
}

function alignText(member: MemberStatus): string {
  if (member.missing) return '缺失'
  if (member.dirty) return '未提交'
  if (!commitsMatch(member.head, member.pin)) return '落后'
  return '对齐'
}

function alignClass(member: MemberStatus): string {
  if (member.missing) return 'bad'
  if (memberDrift(member)) return 'warn'
  return 'ok'
}

function roleClass(role: string): string {
  if (role === 'main') return 'ok'
  if (role === 'editable') return 'warn'
  return ''
}

onMounted(() => {
  void load()
  void store.loadRefs()
})
watch(() => store.currentWorkspace, () => {
  void load()
  void store.loadRefs()
  void store.refreshWorkspace()
})
</script>

<template>
  <section class="page">
    <header class="scale">
      <div>
        <div class="scale-kicker">成员刻度</div>
        <h1>{{ status?.name || '工作区' }}</h1>
        <p class="scale-read">
          <span>{{ status ? `${status.members.length} 个成员` : '未选择' }}</span>
          <span>{{ status?.declared ? '已声明' : '隐式单仓' }}</span>
        </p>
      </div>
      <button class="btn ghost" :disabled="busy || store.busy" @click="() => { load(); store.refreshWorkspace() }">刷新</button>
    </header>

    <div v-if="!status" class="banner warn">选择一个项目后显示成员</div>

    <template v-if="status">
      <div v-if="!status.declared" class="banner info">
        该项目没有 <code>workspace.toml</code>，当前按<strong>单仓工作区</strong>处理（成员只有 main）。
        要纳管 AI 规范库、工具库等，请创建 <code>workspace.toml</code> 并声明 <code>[[member]]</code>（可在「设置 → 配置文件」里新建）。
      </div>

      <div class="panel">
        <table class="table">
          <thead><tr><th>成员</th><th>角色</th><th>策略</th><th>HEAD</th><th>PIN</th><th>状态</th><th>路径</th><th></th></tr></thead>
          <tbody>
            <template v-for="member in status.members" :key="member.name">
            <tr>
              <td class="mono strong">{{ member.name }}</td>
              <td><span class="badge" :class="roleClass(member.role)">{{ member.role }}</span></td>
              <td class="mono dim">{{ member.strategy || '—' }}</td>
              <td class="mono dim">{{ member.head ? member.head.slice(0, 7) : '—' }}</td>
              <td class="mono dim">{{ member.pin || '—' }}</td>
              <td>
                <span class="badge" :class="alignClass(member)">{{ alignText(member) }}</span>
              </td>
              <td class="mono dim path">{{ member.path }}</td>
              <td>
                <div class="row-actions">
                  <button
                    class="btn tiny"
                    :class="{ primary: memberDrift(member) }"
                    :disabled="busy || store.busy || member.missing"
                    @click="store.alignMember(member.name)"
                  >对齐</button>
                  <button
                    class="btn tiny"
                    :disabled="busy || store.busy || member.missing"
                    @click="toggleBranch(member.name)"
                  >分支</button>
                  <details class="more">
                    <summary>更多</summary>
                    <div class="more-menu">
                      <button class="btn tiny" :disabled="busy || store.busy" @click="store.wsSync(member.name)">按 lock 同步</button>
                      <button class="btn tiny" :disabled="busy || store.busy" @click="store.wsPush(member.name)">回推</button>
                      <button class="btn tiny" :disabled="busy" @click="removeMember(member.name)">移除</button>
                    </div>
                  </details>
                </div>
              </td>
            </tr>
            <tr v-if="openMember === member.name">
              <td colspan="8">
                <div v-if="!writable(member.role)" class="muted">只读成员不能新建、切换或提交。</div>
                <template v-else>
                  <div class="form-row">
                    <label class="field">
                      <span>新建</span>
                      <input v-model="branchName" class="input" placeholder="feature/x" />
                    </label>
                    <button
                      class="btn"
                      :disabled="busy || store.busy || !branchName.trim()"
                      @click="runRow(() => store.createMemberBranch(member.name, branchName.trim()))"
                    >新建分支</button>
                    <label class="field">
                      <span>使用</span>
                      <select v-model="useName" class="input">
                        <option value="">选择已有分支</option>
                        <option v-for="name in localBranches" :key="name" :value="name">{{ name }}</option>
                      </select>
                    </label>
                    <button
                      class="btn"
                      :disabled="busy || store.busy || !useName"
                      @click="runRow(() => store.switchMemberBranch(member.name, useName))"
                    >使用</button>
                  </div>
                  <div class="form-row" style="margin-top: 8px">
                    <label class="field" style="min-width: 280px">
                      <span>提交说明</span>
                      <input v-model="commitMessage" class="input" placeholder="只提交这个成员" />
                    </label>
                    <button
                      class="btn primary"
                      :disabled="busy || store.busy || !commitMessage.trim()"
                      @click="runRow(() => store.commitMember(member.name, commitMessage.trim()))"
                    >提交该成员</button>
                  </div>
                </template>
              </td>
            </tr>
            </template>
          </tbody>
        </table>
      </div>

      <details class="fold">
        <summary>添加成员</summary>
        <div class="panel-title"><span class="muted">写入 workspace.toml 的 [[member]]</span></div>
        <div class="form-row">
          <label class="field"><span>成员名</span><input v-model="newMember.name" class="input" placeholder="spec" /></label>
          <label class="field"><span>路径（相对工作区）</span><input v-model="newMember.path" class="input" placeholder="spec" /></label>
          <label class="field"><span>角色</span>
            <select v-model="newMember.role" class="input">
              <option value="editable">editable（可改可回推）</option>
              <option value="readonly">readonly（只读钉版本）</option>
              <option value="local">local（本地，仅备份）</option>
              <option value="main">main（主仓）</option>
            </select>
          </label>
          <label class="field"><span>策略</span>
            <select v-model="newMember.strategy" class="input">
              <option value="vendor">vendor（缓存+junction）</option>
              <option value="clone">clone（嵌套真仓）</option>
              <option value="link">link（外部目录）</option>
            </select>
          </label>
        </div>
        <div class="form-row" style="margin-top: 8px">
          <label class="field" style="min-width: 320px"><span>来源（可选）</span><input v-model="newMember.source" class="input" placeholder="git@github.com:you/spec.git" /></label>
          <label class="field"><span>pin（可选）</span><input v-model="newMember.pin" class="input" placeholder="v0.5.0 / commit" /></label>
          <label class="field"><span>track（可选）</span><input v-model="newMember.track" class="input" placeholder="master" /></label>
          <button class="btn primary" :disabled="busy" @click="addMember">添加成员</button>
        </div>
      </details>

      <details class="fold">
        <summary>主仓与分支</summary>
        <div class="panel-title">
          <span class="muted">这里的切换会作用于每个成员仓（脏仓会被拒绝）。单个成员的分支在成员行的「分支」里。</span>
        </div>
        <div class="form-row">
          <label class="field">
            <span>分支名</span>
            <input v-model="target" class="input" placeholder="feature/x" />
          </label>
          <button class="btn" :disabled="busy || !target" @click="store.switchBranch(target)">切换</button>
          <button class="btn ghost" :disabled="busy" @click="load">刷新分支</button>
          <button class="btn" :disabled="store.busy" @click="store.wsSync()">按 lock 同步</button>
          <button class="btn" :disabled="store.busy" @click="store.wsUpdate()">更新 pin</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.syncCheck()">同步检查</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.pull()">快进拉取</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.pull('merge')">合并拉取</button>
          <button class="btn ghost" :disabled="store.busy" @click="store.pull('rebase')">变基拉取</button>
        </div>

        <div class="split">
          <div>
            <div class="muted label">成员当前分支</div>
            <div v-for="row in branches" :key="row.member" class="kv">
              <span class="mono dim">{{ row.member }}</span>
              <span class="mono">{{ row.branch || '—' }}</span>
            </div>
            <div v-if="!branches.length" class="muted">（无）</div>
          </div>
          <div>
            <div class="muted label">同步状态</div>
            <div v-if="store.syncInfo" class="kv">
              <span class="muted">ahead / behind</span>
              <span class="mono">{{ store.syncInfo.ahead }} / {{ store.syncInfo.behind }}</span>
            </div>
            <div v-if="store.syncInfo" class="kv">
              <span class="muted">upstream</span>
              <span class="mono">{{ store.syncInfo.upstream ?? '—' }}</span>
            </div>
            <div v-else class="muted">点「同步检查」查看</div>
          </div>
        </div>
      </details>
    </template>
  </section>
</template>