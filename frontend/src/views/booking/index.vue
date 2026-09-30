<template>
  <section ref="rootEl" class="page" data-module="booking">
    <header class="page-head">
      <div>
        <h2>订舱受理</h2>
        <p class="page-desc">先选航线与托运人定位订舱，列表按截关时间从近到远排列；重复提交、舱位释放与托运人信息不全的已先行过滤并列出原因。</p>
      </div>
      <div class="page-actions">
        <button class="btn ghost" type="button" @click="clearScope">清除定位条件</button>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">当前条件待受理</span>
        <strong class="stat-value">{{ pendingTotal }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">符合受理口径</span>
        <strong class="stat-value">{{ total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已过滤订舱</span>
        <strong class="stat-value">{{ excluded.length }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>航线</span>
        <select v-model="selectedRoute">
          <option value="">全部航线</option>
          <option v-for="item in routeOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>托运人</span>
        <select v-model="selectedShipper">
          <option value="">全部托运人</option>
          <option v-for="item in shipperOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
        </select>
      </label>
      <button class="btn primary" type="submit" :disabled="loading">{{ loading ? '查询中…' : '定位订舱' }}</button>
      <span v-if="activeScope" class="scope-tip">已锁定：{{ activeScope }}（翻页不丢失）</span>
    </form>

    <div v-if="loadError" class="retry-banner">
      <span class="error-text">{{ loadError }}</span>
      <button class="btn" type="button" @click="reload(false)">重试</button>
    </div>

    <template v-else>
      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>状态 / 操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
            <td class="row-actions">
              <span v-if="row.status !== '待受理'" class="muted">{{ row.status }}</span>
              <RouterLink v-else class="link" :to="detailLink(Number(row.id))">查看 / 受理</RouterLink>
            </td>
          </tr>
          <tr v-if="!loading && !rows.length">
            <td :colspan="columns.length + 1" class="empty-state">当前航线与托运人下没有符合受理口径的订舱</td>
          </tr>
        </tbody>
      </table>

      <section v-if="excluded.length" class="excluded-box">
        <h3>以下 {{ excluded.length }} 条订舱已被过滤（不参与受理）</h3>
        <ul>
          <li v-for="item in excluded" :key="String(item.id)">
            <RouterLink class="link" :to="detailLink(Number(item.id))">id {{ item.id }} · {{ item['订舱号'] }}</RouterLink>
            <span class="muted">（{{ item['托运人代码'] || '托运人缺失' }} / {{ item['航线'] }}，提交 {{ item['提交时间'] }}）</span>
            <span class="exclude-reason">— {{ item['过滤原因'] }}</span>
          </li>
        </ul>
      </section>

      <footer class="page-foot pager">
        <span>共 {{ total }} 条订舱，第 {{ page }} / {{ totalPages }} 页</span>
        <span class="pager-btns">
          <button class="btn" type="button" :disabled="page <= 1 || loading" @click="goPage(page - 1)">上一页</button>
          <button class="btn" type="button" :disabled="page >= totalPages || loading" @click="goPage(page + 1)">下一页</button>
        </span>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>
type ExcludedRow = Record<string, string | number | null>
type Option = { value: string; label: string }
type ListPayload = {
  items: Row[]
  total: number
  page: number
  size: number
  pending_total: number
  excluded: ExcludedRow[]
}

const ENDPOINT = '/api/booking'
const PAGE_SIZE = 10
const columns = ['订舱号', '航线', '托运人代码', '托运人名称', '联系电话', '船名航次', '箱型尺寸', '箱量', '截关时间', '提交时间']
const SCROLL_KEY = 'booking-list-scroll-y'

const router = useRouter()
const route = useRoute()

const rows = ref<Row[]>([])
const excluded = ref<ExcludedRow[]>([])
const total = ref(0)
const pendingTotal = ref(0)
const page = ref(1)
const routeOptions = ref<Option[]>([])
const shipperOptions = ref<Option[]>([])
const loading = ref(false)
const loadError = ref('')

let firstActivation = true
let returningFromDetail = false

// 表单里的临时选择；点“定位订舱”后才写进路由 query，翻页始终沿用已生效的 query
const selectedRoute = ref(String(route.query.route ?? ''))
const selectedShipper = ref(String(route.query.shipper ?? ''))

const activeRoute = computed(() => String(route.query.route ?? ''))
const activeShipper = computed(() => String(route.query.shipper ?? ''))
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))
const activeScope = computed(() => {
  const parts = [
    activeRoute.value ? `航线「${activeRoute.value}」` : '',
    activeShipper.value ? `托运人「${shipperLabel(activeShipper.value)}」` : '',
  ].filter(Boolean)
  return parts.join('，')
})

function shipperLabel(code: string) {
  return shipperOptions.value.find((item) => item.value === code)?.label ?? code
}

function detailLink(id: number) {
  // 把当前条件与页码原样带给明细页，返回时恢复
  return { path: `/booking/${id}`, query: { ...route.query } }
}

function syncFormFromQuery() {
  selectedRoute.value = activeRoute.value
  selectedShipper.value = activeShipper.value
  page.value = Number(route.query.page) || 1
}

async function applyFilters() {
  await updateQuery({
    route: selectedRoute.value || undefined,
    shipper: selectedShipper.value || undefined,
    page: undefined,
  })
}

async function clearScope() {
  selectedRoute.value = ''
  selectedShipper.value = ''
  await updateQuery({ route: undefined, shipper: undefined, page: undefined })
}

async function goPage(target: number) {
  await updateQuery({ page: String(Math.max(1, target)) })
}

async function updateQuery(patch: Record<string, string | undefined>) {
  const query: Record<string, string> = {}
  for (const [key, value] of Object.entries(route.query)) {
    if (typeof value === 'string' && value) query[key] = value
  }
  for (const [key, value] of Object.entries(patch)) {
    if (value) query[key] = value
    else delete query[key]
  }
  await router.replace({ path: '/booking', query })
}

function buildListUrl() {
  const params = new URLSearchParams()
  params.set('page', String(page.value))
  params.set('size', String(PAGE_SIZE))
  if (activeRoute.value) params.set('route', activeRoute.value)
  if (activeShipper.value) params.set('shipper', activeShipper.value)
  return `${ENDPOINT}?${params.toString()}`
}

async function loadOptions() {
  try {
    const response = await request(`${ENDPOINT}/options`)
    if (!response.ok) throw new Error('定位选项读取失败')
    const payload = (await response.json()) as { routes: Option[]; shippers: Option[] }
    routeOptions.value = payload.routes ?? []
    shipperOptions.value = payload.shippers ?? []
  } catch (error) {
    // 选项拿不到不阻塞列表，受理员仍可重试列表请求
    loadError.value = error instanceof Error ? error.message : '定位选项读取失败，请重试'
  }
}

async function reload(restoreScroll = false) {
  syncFormFromQuery()
  loading.value = true
  loadError.value = ''
  try {
    const response = await request(buildListUrl())
    if (!response.ok) throw new Error(`接口返回 ${response.status}，订舱数据没有取到`)
    const payload = (await response.json()) as ListPayload
    rows.value = payload.items ?? []
    excluded.value = payload.excluded ?? []
    total.value = payload.total ?? 0
    pendingTotal.value = payload.pending_total ?? 0
    page.value = payload.page || page.value
    if (restoreScroll) {
      await nextTickRestore()
    }
  } catch (error) {
    loadError.value = error instanceof Error ? `${error.message}，请点击重试让受理员重新加载` : '订舱数据未取到，请重试'
  } finally {
    loading.value = false
  }
}

async function nextTickRestore() {
  // 等表格渲染完再恢复离开前的滚动位置
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)))
  const y = Number(sessionStorage.getItem(SCROLL_KEY) || '0')
  window.scrollTo({ top: y })
  sessionStorage.removeItem(SCROLL_KEY)
}

// 进入明细前记下当前滚动位置，返回后恢复到刚才的位置
watch(
  () => route.fullPath,
  (fullPath) => {
    if (fullPath.match(/^\/booking\/\d+/)) {
      sessionStorage.setItem(SCROLL_KEY, String(window.scrollY))
    }
  },
)

// 路由 query（航线/托运人/页码）变化即重新取数，翻页时条件保持不变
watch(
  () => [route.query.route, route.query.shipper, route.query.page],
  () => {
    if (route.name !== 'booking') return
    if (returningFromDetail) {
      // 从明细页返回引起的 query 还原已由 onActivated 处理，避免重复请求
      returningFromDetail = false
      return
    }
    // 主动改条件或翻页：回到列表顶部，不恢复旧滚动位置
    void reload(false)
    window.scrollTo({ top: 0 })
  },
)

onMounted(() => {
  void loadOptions()
  void reload(false)
})

// KeepAlive 缓存下从明细页返回：刷新数据（可能刚受理过）并恢复到刚才的位置
onActivated(() => {
  if (route.name !== 'booking') return
  if (firstActivation) {
    // 组件首次挂载时 onMounted 已取过数，这里不重复请求
    firstActivation = false
    return
  }
  returningFromDetail = true
  void reload(true)
})
</script>

<style scoped>
.scope-tip {
  color: var(--brand);
  font-size: 12px;
}
.retry-banner {
  display: flex;
  gap: 12px;
  align-items: center;
  background: #fff5f4;
  border: 1px solid #f2c4c0;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.excluded-box {
  margin-top: 12px;
  background: #fff;
  border: 1px dashed #d9a14a;
  border-radius: 8px;
  padding: 10px 14px;
}
.excluded-box h3 {
  margin: 0 0 6px;
  font-size: 13px;
  color: #9a6412;
}
.excluded-box ul {
  margin: 0;
  padding-left: 18px;
  font-size: 12px;
  line-height: 1.9;
}
.exclude-reason {
  color: #b45309;
}
.muted {
  color: var(--muted);
}
.pager {
  align-items: center;
}
.pager-btns {
  display: inline-flex;
  gap: 8px;
}
.filter-item select {
  min-width: 200px;
  padding: 5px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
</style>
