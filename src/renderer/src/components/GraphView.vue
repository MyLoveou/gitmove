<script setup lang="ts">
import dagre from '@dagrejs/dagre'
import { computed, ref } from 'vue'

import type { GraphNode } from '../../../shared/protocol'

const props = defineProps<{ nodes: GraphNode[]; selected?: string }>()
const emit = defineEmits<{ select: [sha: string] }>()

const scale = ref(1)
const hovered = ref('')

const palette = ['#2fd7c4', '#7aa2f7', '#bb9af7', '#f7768e', '#e0af68', '#9ece6a', '#7dcfff', '#ff9e64']

function branchOf(node: GraphNode): string {
  const head = node.refs.find((ref) => ref.startsWith('HEAD -> '))
  if (head) return head.replace('HEAD -> ', '')
  const tag = node.refs.find((ref) => ref.startsWith('tag: '))
  if (tag) return tag.replace('tag: ', '')
  const remote = node.refs.find((ref) => ref.startsWith('origin/'))
  if (remote) return remote
  const local = node.refs.find((ref) => !ref.includes('->'))
  return local ?? ''
}

const colors = computed(() => {
  const branches = [...new Set(props.nodes.map(branchOf).filter(Boolean))].sort()
  const map = new Map<string, string>()
  branches.forEach((branch, index) => map.set(branch, palette[index % palette.length]))
  return map
})

function colorOf(node: GraphNode): string {
  return colors.value.get(branchOf(node)) ?? '#5c7078'
}

interface NodePoint {
  node: GraphNode
  x: number
  y: number
}

interface EdgeLine {
  key: string
  from: string
  to: string
  d: string
  color: string
}

const layout = computed(() => {
  const nodes = props.nodes
  if (!nodes.length) return { width: 0, height: 0, points: [] as NodePoint[], edges: [] as EdgeLine[] }

  const graph = new dagre.graphlib.Graph({ multigraph: false, compound: false })
  graph.setGraph({ rankdir: 'TB', nodesep: 42, ranksep: 44, marginx: 30, marginy: 24 })
  graph.setDefaultEdgeLabel(() => ({}))

  const known = new Set(nodes.map((node) => node.sha))
  for (const node of nodes) graph.setNode(node.sha, { width: 12, height: 12 })
  for (const node of nodes) {
    for (const parent of node.parents) {
      if (known.has(parent)) graph.setEdge(node.sha, parent)
    }
  }

  dagre.layout(graph)

  const bySha = new Map(nodes.map((node) => [node.sha, node]))
  const points: NodePoint[] = []
  for (const sha of graph.nodes()) {
    const position = graph.node(sha)
    const node = bySha.get(sha)
    if (node) points.push({ node, x: position.x, y: position.y })
  }

  const edges: EdgeLine[] = []
  for (const edge of graph.edges()) {
    const data = graph.edge(edge)
    const from = graph.node(edge.v)
    const to = graph.node(edge.w)
    const path = (data.points ?? []).map((point: { x: number; y: number }) => `${point.x},${point.y}`).join(' ')
    edges.push({
      key: `${edge.v}-${edge.w}`,
      from: edge.v,
      to: edge.w,
      d: path ? `M ${path.replace(/ /g, ' L ')}` : `M ${from.x},${from.y} L ${to.x},${to.y}`,
      color: colors.value.get(branchOf(bySha.get(edge.v)!)) ?? '#5c7078'
    })
  }

  return {
    width: graph.graph().width ?? 0,
    height: graph.graph().height ?? 0,
    points,
    edges
  }
})

const chain = computed(() => {
  const start = hovered.value
  if (!start) return new Set<string>()
  const parents = new Map(props.nodes.map((node) => [node.sha, node.parents]))
  const seen = new Set<string>()
  let current: string | undefined = start
  while (current && !seen.has(current)) {
    seen.add(current)
    current = parents.get(current)?.[0]
  }
  return seen
})

function dimNode(sha: string): boolean {
  return Boolean(hovered.value) && !chain.value.has(sha)
}

function dimEdge(edge: EdgeLine): boolean {
  return Boolean(hovered.value) && !(chain.value.has(edge.from) && chain.value.has(edge.to))
}

function zoom(delta: number) {
  scale.value = Math.min(2, Math.max(0.5, Number((scale.value + delta).toFixed(2))))
}
</script>

<template>
  <div class="graph-shell">
    <div class="graph-toolbar">
      <span class="muted">缩放 {{ Math.round(scale * 100) }}%</span>
      <button class="btn tiny" @click="zoom(0.1)">＋</button>
      <button class="btn tiny" @click="zoom(-0.1)">－</button>
      <button class="btn tiny" @click="scale = 1">重置</button>
    </div>
    <div class="graph-scroll">
      <svg
        :width="Math.max(1100, layout.width + 320) * scale"
        :height="Math.max(160, layout.height + 40) * scale"
        :viewBox="`0 0 ${Math.max(1100, layout.width + 320)} ${Math.max(160, layout.height + 40)}`"
      >
        <g>
          <path
            v-for="edge in layout.edges"
            :key="edge.key"
            :d="edge.d"
            fill="none"
            :stroke="edge.color"
            :stroke-opacity="dimEdge(edge) ? 0.08 : 0.6"
            :stroke-width="dimEdge(edge) ? 1 : 1.8"
          />
        </g>
        <g v-for="point in layout.points" :key="point.node.sha">
          <circle
            :cx="point.x"
            :cy="point.y"
            :r="props.selected === point.node.sha ? 7 : 4.5"
            :fill="colorOf(point.node)"
            :stroke="props.selected === point.node.sha ? '#ffffff' : 'transparent'"
            stroke-width="2"
            class="graph-node"
            :opacity="dimNode(point.node.sha) ? 0.2 : 1"
            @click="emit('select', point.node.sha)"
            @mouseenter="hovered = point.node.sha"
            @mouseleave="hovered = ''"
          />
          <text
            :x="point.x"
            :y="point.y + 18"
            text-anchor="middle"
            class="graph-text"
            :opacity="dimNode(point.node.sha) ? 0.25 : 1"
            @click="emit('select', point.node.sha)"
            @mouseenter="hovered = point.node.sha"
            @mouseleave="hovered = ''"
          >
            {{ point.node.short }}
            <title>{{ point.node.refs.join(' ') }} · {{ point.node.subject }}</title>
          </text>
        </g>
      </svg>
    </div>
  </div>
</template>