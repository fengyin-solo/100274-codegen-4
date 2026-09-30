<template>
  <section class="page" data-module="booking-detail">
    <header class="page-head">
      <div>
        <h2>订舱明细 · #{{ bookingId }}</h2>
        <p class="page-desc">核对一票订舱的完整信息后再受理；该票若不在受理口径内，页面会写明过滤原因。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn ghost" :to="backLink">返回订舱列表</RouterLink>
      </div>
    </header>

    <div v-if="loadError" class="retry-banner">
      <span class="error-text">{{ loadError }}</span>
      <button class="btn" type="button" @click="loadDetail">重试</button>
    </div>

    <div v-else-if="loading" class="hint-box">正在读取订舱明细…</div>

    <template v-else-if="entry">
      <div class="detail-status">
        <span class="status-tag" :class="{ accepted: entry.status === '已受理' }">{{ entry.status }}</span>
        <span v-if="excludeReason" class="exclude-tag">不在受理口径：{{ excludeReason }}</span>
      </div>

      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in fields" :key="field">
            <th>{{ field }}</th>
            <td>{{ entry[field] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>

      <p v-if="actionMessage" class="action-msg" :class="{ 'error-text': !actionOk }">{{ actionMessage }}</p>

      <div class="detail-actions">
        <button
          v-if="entry.status === '待受理' && !excludeReason"
          class="btn primary"
          type="button"
          :disabled="acting"
          @click="accept"
        >
          {{ acting ? '受理中…' : '受理该订舱' }}
        </button>
        <RouterLink class="btn" :to="backLink">返回刚才的位置</RouterLink>
      </div>    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Entry = Record<string, string | number | boolean | null>

const fields = ['订舱号', '航线', '托运人代码', '托运人名称', '联系人', '联系电话', '船名航次', '箱型尺寸', '箱量', '截关时间', '提交时间', '舱位状态']

const route = useRoute()
const router = useRouter()

const entry = ref<Entry | null>(null)
const loading = ref(false)
const acting = ref(false)
const loadError = ref('')
const actionMessage = ref('')
const actionOk = ref(true)

const bookingId = computed(() => String(route.params.id))
// 返回列表时带上离开前的航线、托运人与页码，停在刚才的位置
const backLink = computed(() => ({ path: '/booking', query: { ...route.query } }))

// 以后端口径为准（舱位释放 / 信息不全 / 重复提交），前端不重复维护规则
const excludeReason = computed(() => String(entry.value?.['不可受理原因'] ?? ''))

async function loadDetail() {
  loading.value = true
  loadError.value = ''
  try {
    const response = await request(`/api/booking/${bookingId.value}`)
    if (response.status === 404) {
      throw new Error('该订舱不存在或已归档')
    }
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}，订舱明细没有取到`)
    }
    entry.value = (await response.json()) as Entry
  } catch (error) {
    entry.value = null
    loadError.value = error instanceof Error ? `${error.message}，请点击重试` : '订舱明细未取到，请重试'
  } finally {
    loading.value = false
  }
}

async function accept() {
  acting.value = true
  actionMessage.value = ''
  try {
    const response = await request(`/api/booking/${bookingId.value}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '受理订舱' } }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string; entry?: Entry }
    if (!response.ok || !payload.ok) {
      actionOk.value = false
      actionMessage.value = payload.message || '受理未生效，请重试'
      return
    }
    actionOk.value = true
    actionMessage.value = payload.message || '订舱已受理'
    if (payload.entry) entry.value = payload.entry
    // 受理后停留 0.8 秒，带受理员回到列表原来的位置
    setTimeout(() => { void router.push(backLink.value) }, 800)
  } catch (error) {
    actionOk.value = false
    actionMessage.value = error instanceof Error ? error.message : '受理请求失败，请重试'
  } finally {
    acting.value = false
  }
}

watch(
  () => route.params.id,
  () => { void loadDetail() },
  { immediate: true },
)
</script>

<style scoped>
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
.hint-box {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  color: var(--muted);
  font-size: 13px;
}
.detail-status {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
.status-tag {
  background: #eaf1fe;
  color: var(--brand);
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
}
.status-tag.accepted {
  background: #e9f7ee;
  color: #157347;
}
.exclude-tag {
  color: #b45309;
  font-size: 12px;
}
.detail-table th {
  width: 140px;
  background: #f8fafc;
}
.detail-actions {
  display: flex;
  gap: 10px;
  margin-top: 14px;
}
.action-msg {
  margin-top: 10px;
  font-size: 13px;
}
</style>
