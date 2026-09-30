<template>
  <section class="page" data-module="booking-detail">
    <header class="page-head">
      <div>
        <h2>订舱明细</h2>
        <p class="page-desc">单票订舱的全部提交信息；若该票未进入受理列表，这里会说明过滤原因。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回订舱列表</button>
      </div>
    </header>

    <div v-if="errorMessage" class="error-banner" role="alert">
      <span>{{ errorMessage }}</span>
      <button class="btn primary" type="button" @click="loadDetail">重新加载</button>
    </div>

    <template v-else-if="entry">
      <div v-if="!entry.可受理" class="warn-banner">
        <strong>该票订舱当前不在可受理列表：</strong>
        <span v-for="reason in entry.过滤原因" :key="reason" class="reason-chip">{{ reason }}</span>
        <span v-if="!entry.过滤原因?.length">不是该票订舱的首次受理记录</span>
      </div>

      <div class="detail-grid">
        <article v-for="field in fields" :key="field.key" class="detail-item">
          <span class="detail-label">{{ field.label }}</span>
          <strong class="detail-value">{{ formatValue(field.key, entry[field.key]) }}</strong>
        </article>
      </div>

      <footer class="page-foot">
        <button
          v-if="entry.可受理 && entry.status === '待受理'"
          class="btn primary"
          type="button"
          :disabled="submitting"
          @click="accept"
        >
          {{ submitting ? '受理中…' : '受理该订舱' }}
        </button>
        <span v-if="actionMessage" :class="actionOk ? 'ok-text' : 'error-text'">{{ actionMessage }}</span>
      </footer>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type BookingDetail = {
  id: number
  status: string
  可受理: boolean
  过滤原因: string[]
  首次受理记录: number | null
  [key: string]: string | number | boolean | null | string[]
}

const route = useRoute()
const router = useRouter()

const fields = [
  { key: '订舱号', label: '订舱号' },
  { key: 'status', label: '订舱状态' },
  { key: '托运人名称', label: '托运人名称' },
  { key: '托运人联系人', label: '托运人联系人' },
  { key: '托运人联系电话', label: '托运人联系电话' },
  { key: '航线', label: '航线' },
  { key: '起运港', label: '起运港' },
  { key: '目的港', label: '目的港' },
  { key: '船名航次', label: '船名航次' },
  { key: '箱型箱量', label: '箱型箱量' },
  { key: '截关时间', label: '截关时间' },
  { key: '提交时间', label: '提交时间' },
] as const

const entry = ref<BookingDetail | null>(null)
const errorMessage = ref('')
const actionMessage = ref('')
const actionOk = ref(false)
const submitting = ref(false)

function formatTime(value: unknown): string {
  return typeof value === 'string' && value ? value.replace('T', ' ') : '—'
}

function formatValue(key: string, value: unknown): string {
  if (key === '截关时间' || key === '提交时间') return formatTime(value)
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

async function loadDetail() {
  errorMessage.value = ''
  actionMessage.value = ''
  const id = Number(route.params.id)
  try {
    const response = await request(`/api/booking/${id}`)
    if (!response.ok) {
      const detail = await response.json().catch(() => null)
      throw new Error(detail?.detail || `订舱 ${id} 读取失败（接口返回 ${response.status}），请重试`)
    }
    entry.value = (await response.json()) as BookingDetail
  } catch (error) {
    entry.value = null
    errorMessage.value = error instanceof Error ? error.message : '订舱数据没取到，请重新加载'
  }
}

async function accept() {
  if (!entry.value) return
  submitting.value = true
  actionMessage.value = ''
  try {
    const response = await request(`/api/booking/${entry.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '受理' } }),
    })
    const payload = await response.json()
    actionOk.value = Boolean(response.ok && payload.ok)
    actionMessage.value = payload.message || (actionOk.value ? '已受理' : '受理未生效，请重试')
    if (actionOk.value) {
      await loadDetail()
    }
  } catch (error) {
    actionOk.value = false
    actionMessage.value = error instanceof Error ? error.message : '受理操作失败，请重试'
  } finally {
    submitting.value = false
  }
}

function goBack() {
  // 列表页的航线/托运人/页码/滚动位置都存在 booking store 里，直接回退即可还原
  if (window.history.state?.back) {
    router.back()
  } else {
    void router.push('/booking')
  }
}

onMounted(loadDetail)
</script>

<style scoped>
.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
}
.detail-item {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
}
.detail-label {
  display: block;
  color: var(--muted);
  font-size: 12px;
  margin-bottom: 4px;
}
.detail-value {
  font-size: 14px;
}
.warn-banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 12px;
  background: #fff4e5;
  border: 1px solid #f5c27a;
  border-radius: 8px;
  color: #8a4b00;
  font-size: 13px;
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
.ok-text {
  color: #027a48;
}
</style>
