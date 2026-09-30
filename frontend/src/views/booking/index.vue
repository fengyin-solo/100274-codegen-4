<template>
  <section class="page" data-module="booking">
    <header class="page-head">
      <div>
        <h2>订舱受理</h2>
        <p class="page-desc">
          先选航线与托运人定位订舱，结果按截关时间从近到远排列；
          同票重复提交只认第一次，已释放舱位、托运人信息不全的订舱自动过滤并逐条说明。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn ghost" type="button" @click="resetAll">重置定位条件</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="loadAll">
      <label class="filter-item">
        <span>航线</span>
        <select v-model="store.route" @change="onRouteChange">
          <option value="">全部航线</option>
          <option v-for="route in routes" :key="route" :value="route">{{ route }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>托运人</span>
        <select v-model="store.shipper" @change="onShipperChange">
          <option value="">全部托运人</option>
          <option v-for="shipper in shippers" :key="shipper" :value="shipper">{{ shipper }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
    </form>

    <div v-if="errorMessage" class="error-banner" role="alert">
      <span>{{ errorMessage }}</span>
      <button class="btn primary" type="button" @click="loadAll">重新加载</button>
    </div>

    <template v-else>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)" class="clickable-row" @click="openDetail(row.id)">
            <td>{{ row.订舱号 ?? '—' }}</td>
            <td>{{ row.托运人名称 ?? '—' }}</td>
            <td>{{ row.航线 ?? '—' }}</td>
            <td>{{ formatRange(row.起运港, row.目的港) }}</td>
            <td>{{ row.船名航次 ?? '—' }}</td>
            <td>{{ row.箱型箱量 ?? '—' }}</td>
            <td>{{ formatTime(row.截关时间) }}</td>
            <td>{{ formatTime(row.提交时间) }}</td>
            <td>
              <span :class="row.status === '待受理' ? 'tag tag-pending' : 'tag tag-done'">{{ row.status }}</span>
            </td>
            <td class="row-actions" @click.stop>
              <button v-if="row.status === '待受理'" class="link" type="button" @click="accept(row)">受理</button>
              <button class="link" type="button" @click="openDetail(row.id)">查看</button>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 1" class="empty-state">当前航线与托运人条件下没有可受理订舱</td>
          </tr>
        </tbody>
      </table>

      <footer class="page-foot">
        <span>共 {{ total }} 票可受理订舱</span>
        <span v-if="actionMessage" class="error-text">{{ actionMessage }}</span>
        <span v-else-if="excluded.length" class="excluded-summary">
          已过滤 {{ excluded.length }} 条：重复提交 {{ excludedCount.duplicate }} 条、
          舱位已释放 {{ excludedCount.released }} 条、托运人信息不全 {{ excludedCount.incomplete }} 条
        </span>
      </footer>

      <nav class="pagination">
        <button class="btn" type="button" :disabled="store.page <= 1" @click="goPage(store.page - 1)">上一页</button>
        <span>第 {{ store.page }} / {{ totalPages }} 页</span>
        <button class="btn" type="button" :disabled="store.page >= totalPages" @click="goPage(store.page + 1)">下一页</button>
        <label class="page-size">
          每页
          <select :value="store.size" @change="onSizeChange">
            <option v-for="sizeValue in sizeOptions" :key="sizeValue" :value="sizeValue">{{ sizeValue }}</option>
          </select>
          条
        </label>
      </nav>

      <section v-if="excluded.length" class="excluded-panel">
        <h3>已先过滤掉 {{ excluded.length }} 条订舱（不进入受理列表）</h3>
        <table class="data-table">
          <thead>
            <tr><th>ID</th><th>订舱号</th><th>托运人</th><th>航线</th><th>提交时间</th><th>过滤原因</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in excluded" :key="String(item.id)" class="excluded-row" @click="openDetail(item.id)">
              <td>{{ item.id }}</td>
              <td>{{ item.订舱号 ?? '—' }}</td>
              <td>{{ item.托运人名称 ?? '—' }}</td>
              <td>{{ item.航线 ?? '—' }}</td>
              <td>{{ formatTime(item.提交时间) }}</td>
              <td class="excluded-reasons">
                <span v-for="reason in item.reasons" :key="reason" class="reason-chip">{{ reason }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { request } from '@/api/client'
import { useBookingStore } from '@/stores/booking'

type Booking = {
  id: number
  订舱号: string | null
  托运人名称: string | null
  航线: string | null
  起运港: string | null
  目的港: string | null
  船名航次: string | null
  箱型箱量: string | null
  截关时间: string | null
  提交时间: string | null
  status: string
}

type ExcludedBooking = {
  id: number
  订舱号: string | null
  托运人名称: string | null
  航线: string | null
  提交时间: string | null
  reasons: string[]
}

type BookingPage = {
  items: Booking[]
  total: number
  page: number
  size: number
  excluded: ExcludedBooking[]
  options: Record<string, string[]>
}

type BookingSummary = { total: number; pending: number; accepted: number; excluded: number }

const router = useRouter()
const store = useBookingStore()

const columns = ['订舱号', '托运人', '航线', '起运/目的港', '船名航次', '箱型箱量', '截关时间', '提交时间', '订舱状态']
const sizeOptions = [10, 20, 50]

const rows = ref<Booking[]>([])
const total = ref(0)
const excluded = ref<ExcludedBooking[]>([])
const routes = ref<string[]>([])
const shippers = ref<string[]>([])
const errorMessage = ref('')
const actionMessage = ref('')
const summary = ref<BookingSummary>({ total: 0, pending: 0, accepted: 0, excluded: 0 })

const stats = computed(() => [
  { label: '可受理订舱', value: summary.value.total },
  { label: '待受理', value: summary.value.pending },
  { label: '已受理', value: summary.value.accepted },
  { label: '已过滤', value: summary.value.excluded },
])

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / store.size)))

const excludedCount = computed(() => {
  let duplicate = 0
  let released = 0
  let incomplete = 0
  for (const item of excluded.value) {
    if (item.reasons.some((reason) => reason.includes('重复提交'))) duplicate += 1
    if (item.reasons.some((reason) => reason.includes('舱位已经释放'))) released += 1
    if (item.reasons.some((reason) => reason.includes('托运人信息不全'))) incomplete += 1
  }
  return { duplicate, released, incomplete }
})

function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  return value.replace('T', ' ')
}

function formatRange(from: string | null, to: string | null): string {
  if (!from && !to) return '—'
  return `${from ?? '—'} → ${to ?? '—'}`
}

function buildQuery(): string {
  const params = new URLSearchParams()
  if (store.route) params.set('route', store.route)
  if (store.shipper) params.set('shipper', store.shipper)
  params.set('page', String(store.page))
  params.set('size', String(store.size))
  return params.toString()
}

async function loadList() {
  errorMessage.value = ''
  actionMessage.value = ''
  try {
    const response = await request(`/api/booking?${buildQuery()}`)
    if (!response.ok) {
      throw new Error(`订舱列表读取失败（接口返回 ${response.status}）`)
    }
    const payload = (await response.json()) as BookingPage
    rows.value = payload.items ?? []
    total.value = payload.total ?? 0
    excluded.value = payload.excluded ?? []
    routes.value = payload.options?.['航线'] ?? []
    shippers.value = payload.options?.['托运人'] ?? []
    // 筛选后当前页可能越界（例如数据被受理走），回退到最后一页
    if (store.page > totalPages.value) {
      store.setPage(totalPages.value)
      await loadList()
      return
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '订舱数据没取到'
  }
}

async function loadSummary() {
  // 票数与列表同源：直接走后端 summary，summary 与列表共用同一套过滤口径
  try {
    const response = await request('/api/booking/summary')
    if (response.ok) {
      summary.value = (await response.json()) as BookingSummary
    }
  } catch {
    // 卡片取数失败不阻断列表，列表自己的错误提示仍会出现
  }
}

async function loadAll() {
  await loadList()
  await loadSummary()
}

function onRouteChange() {
  store.setRoute(store.route)
  void loadList()
}

function onShipperChange() {
  store.setShipper(store.shipper)
  void loadList()
}

function onSizeChange(event: Event) {
  store.setSize(Number((event.target as HTMLSelectElement).value))
  void loadList()
}

function goPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  store.setPage(page)
  window.scrollTo({ top: 0 })
  void loadList()
}

function resetAll() {
  store.reset()
  void loadAll()
}

function openDetail(id: number) {
  // 进详情前记住位置，返回时还原
  store.saveScroll(window.scrollY)
  void router.push(`/booking/${id}`)
}

async function accept(row: Booking) {
  actionMessage.value = ''
  try {
    const response = await request(`/api/booking/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '受理' } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message || '受理未生效，请重试')
    }
    actionMessage.value = payload.message || '订舱已受理'
    await loadAll()
  } catch (error) {
    // 受理失败保留列表，只在页脚提示；整页错误横幅仅用于数据没取到
    actionMessage.value = error instanceof Error ? error.message : '受理操作失败'
  }
}

onMounted(async () => {
  await loadList()
  await loadSummary()
  // 从单票详情返回：数据渲染完后还原到刚才的滚动位置
  await nextTick()
  requestAnimationFrame(() => {
    window.scrollTo({ top: store.scrollY })
  })
})
</script>

<style scoped>
.filter-item select {
  min-width: 180px;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.clickable-row {
  cursor: pointer;
}
.clickable-row:hover {
  background: #f1f6ff;
}
.tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.tag-pending {
  background: #fff4e5;
  color: #b54708;
}
.tag-done {
  background: #e7f6ec;
  color: #027a48;
}
.pagination {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 10px 0;
  font-size: 13px;
  color: var(--muted);
}
.page-size select {
  margin: 0 4px;
  padding: 4px;
}
.excluded-summary {
  color: #b54708;
}
.excluded-panel {
  margin-top: 16px;
  border: 1px dashed #e0a44a;
  border-radius: 8px;
  padding: 10px 12px;
  background: #fffaf0;
}
.excluded-panel h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: #8a4b00;
}
.excluded-row {
  cursor: pointer;
  background: #fff;
}
.excluded-reasons {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.reason-chip {
  background: #fef0c7;
  color: #7a3e00;
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 12px;
}
.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  margin: 12px 0;
  background: #fef3f2;
  border: 1px solid #fda29b;
  border-radius: 8px;
  color: #b42318;
}
</style>
