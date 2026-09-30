<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div class="stat-row">
      <RouterLink
        v-for="card in displayCards"
        :key="card.label"
        class="stat-card"
        :class="{ 'stat-link': card.to }"
        :to="card.to ?? { path: '/' }"
      >
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </RouterLink>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Card = { label: string; value: number; to?: string }

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
  pending_bookings?: number
}

const cards = ref<Card[]>([])
const moduleRows = ref<Overview['modules']>([])

// 待受理订舱卡片直接链接到订舱受理页；票数来自 /api/overview，与订舱列表同源
const displayCards = computed(() =>
  cards.value.map((card) =>
    card.label === '待受理订舱' ? { ...card, to: '/booking' } : card,
  ),
)

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = [
      ...(payload.cards ?? []),
      // 兜底：后端若没带待受理订舱，也保持入口可见且票数为 0
      ...(payload.cards?.some((card) => card.label === '待受理订舱')
        ? []
        : [{ label: '待受理订舱', value: payload.pending_bookings ?? 0 }]),
    ]
    moduleRows.value = payload.modules
  } catch {
    cards.value = [
      {"label": "业务模块", "value": 0},
      {"label": "待受理订舱", "value": 0, "to": "/booking"},
      {"label": "今日新增", "value": 0},
    ]
    moduleRows.value = []
  }
})
</script>

<style scoped>
.stat-link {
  text-decoration: none;
  color: inherit;
  cursor: pointer;
}
.stat-link:hover {
  border-color: var(--brand);
  box-shadow: 0 1px 4px rgba(31, 111, 235, 0.15);
}
</style>
