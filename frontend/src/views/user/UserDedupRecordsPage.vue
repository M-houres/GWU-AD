<template>
  <UserShell
    title="降重复率"
    subtitle="任务按时间倒序展示，最新提交优先在顶部显示。"
    :credits="userBalanceFen"
    :hide-topbar="true"
    :disable-notice-dialog="true"
    @buy="showBuy = !showBuy"
  >
    <section class="aigc-record-hero">
      <div class="aigc-record-hero__main">
        <div class="aigc-record-hero__eyebrow">任务记录</div>
        <div class="aigc-record-hero__title">降重复率</div>
        <p class="aigc-record-hero__desc">上传正文后自动进入处理队列，完成后可直接下载改写文档。</p>
      </div>

      <div class="aigc-record-hero__stats">
        <div class="aigc-record-hero__stat">
          <span>全部任务</span>
          <strong>{{ counts.all }}</strong>
          <em>按最新时间排序</em>
        </div>
        <div class="aigc-record-hero__stat">
          <span>已完成</span>
          <strong>{{ counts.completed }}</strong>
          <em>结果可下载</em>
        </div>
        <div class="aigc-record-hero__stat">
          <span>处理中</span>
          <strong>{{ counts.processing }}</strong>
          <em>系统自动刷新进度</em>
        </div>
        <div class="aigc-record-hero__stat">
          <span>累计消耗</span>
          <strong>{{ formatCredits(totalCreditsFen) }}</strong>
          <em>{{ latestTaskTime }}</em>
        </div>
      </div>
    </section>

    <section class="aigc-record-toolbar">
      <div class="aigc-record-toolbar__filters">
        <label class="aigc-search">
          <svg viewBox="0 0 24 24">
            <path
              d="M11 4.5a6.5 6.5 0 1 1 0 13a6.5 6.5 0 0 1 0-13Zm0 0v0m8.5 13.5L17 15.5"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-width="1.8"
            />
          </svg>
          <input v-model.trim="keyword" type="text" placeholder="请输入关键词" />
        </label>

        <div class="aigc-status-tabs">
          <button
            v-for="tab in statusTabs"
            :key="tab.key"
            type="button"
            class="aigc-status-tabs__item"
            :class="{ 'is-active': statusFilter === tab.key }"
            @click="statusFilter = tab.key"
          >
            {{ tab.label }}（{{ tab.count }}）
          </button>
        </div>
      </div>

      <div class="aigc-record-toolbar__actions">
        <button class="scholar-button aigc-record-toolbar__upload" type="button" @click="goUpload">新建任务</button>
      </div>
    </section>

    <p class="aigc-record-retain">结果文件将保留 30 天，请及时下载与归档。</p>

    <section v-if="initialLoading" class="scholar-note">正在加载记录...</section>

    <section v-else-if="pagedTasks.length === 0" class="aigc-empty">
      <div class="aigc-empty__icon">D</div>
      <h3>暂无降重记录</h3>
      <p>提交任务后，这里会显示处理进度与结果下载入口。</p>
      <button class="scholar-button" type="button" @click="goUpload">立即上传</button>
    </section>

    <section v-else class="aigc-record-list">
      <div v-if="refreshing" class="aigc-record-list__refreshing">正在同步最新进度...</div>
      <article
        v-for="item in pagedTasks"
        :id="`dedup-task-${item.id}`"
        :key="item.id"
        class="aigc-record-item"
        :class="{ 'is-focused': focusTaskId === item.id }"
      >
        <div class="aigc-record-item__left">
          <div class="aigc-record-item__title-row">
            <div class="aigc-record-item__title">{{ taskLabel(item) }}</div>
            <div class="aigc-record-item__badges">
              <span class="aigc-record-item__service">{{ mapTaskPlatform(item.platform, item.task_type) }}</span>
              <span v-if="focusTaskId === item.id" class="aigc-record-item__service aigc-record-item__service--focus">
                当前查看
              </span>
            </div>
          </div>

          <div class="aigc-record-item__meta">
            <div>作者：{{ safeText(item.result_json?.authors) }}</div>
            <div>提交时间：{{ formatTime(item.created_at) }}</div>
            <div>文档字数：{{ item.char_count || 0 }}</div>
            <div>消耗通用点数：{{ formatCredits(taskCostFen(item)) }}</div>
            <div class="aigc-record-item__meta-wide">文件：{{ filenamePair(item) }}</div>
          </div>
        </div>

        <div class="aigc-record-item__mid">
          <template v-if="item.status === 'completed'">
            <span class="service-status-tag service-status-tag--success">已完成</span>
          </template>
          <template v-else-if="isTaskProcessingStatus(item.status)">
            <span class="service-status-tag service-status-tag--processing">处理中</span>
            <div class="service-dot-loading"><span /><span /><span /></div>
            <div class="aigc-record-item__score-note">预计 3-10 分钟完成</div>
          </template>
          <template v-else>
            <span class="service-status-tag service-status-tag--failed">处理异常</span>
            <div class="aigc-record-item__score-note">{{ refundHint(item) }}</div>
          </template>
        </div>

        <div class="aigc-record-item__right">
          <button
            class="aigc-record-item__delete"
            type="button"
            :disabled="isTaskProcessingStatus(item.status) || removingId === item.id"
            @click="removeTask(item)"
          >
            删除
          </button>

          <template v-if="item.status === 'completed'">
            <button class="scholar-button scholar-button--secondary" type="button" @click="downloadResult(item.id)">
              下载改写文档
            </button>
            <p class="aigc-record-item__deadline">有效期至：{{ reportDeadline(item.created_at) }}</p>
          </template>
          <template v-else>
            <p class="aigc-record-item__waiting">
              {{ item.status === "failed" ? refundHint(item) : "处理完成后可下载" }}
            </p>
          </template>
        </div>
      </article>
    </section>

    <nav v-if="totalPages > 1" class="aigc-pagination">
      <button type="button" :disabled="page <= 1" @click="page -= 1">上一页</button>
      <button
        v-for="num in visiblePages"
        :key="num"
        type="button"
        :class="{ 'is-active': page === num }"
        @click="page = num"
      >
        {{ num }}
      </button>
      <button type="button" :disabled="page >= totalPages" @click="page += 1">下一页</button>
    </nav>

    <BuyCreditsPanel v-if="showBuy" @paid="afterPaid" />
  </UserShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { downloadAxiosBlobResponse } from "../../lib/download"
import { userHttp } from "../../lib/http"
import { fetchUserTasksFast, shouldPollTaskRecords } from "../../lib/userRecords"
import { getUserToken } from "../../lib/session"
import { mapTaskPlatform } from "../../lib/taskPlatform"
import { isTaskProcessingStatus } from "../../lib/taskStatus"

const router = useRouter()
const route = useRoute()
const showBuy = ref(false)
const loading = ref(false)
const initialLoading = ref(true)
const refreshing = ref(false)
const removingId = ref(null)
const keyword = ref("")
const statusFilter = ref("all")
const page = ref(1)
const pageSize = 8
const tasks = ref([])
const pollTimer = ref(null)
let loadToken = 0

const { user, refreshUser } = useUserProfile()
const userBalanceFen = computed(() => {
  const value = user.value && (user.value.balance_fen ?? user.value.credits)
  return typeof value === "number" ? value : null
})
const focusTaskId = computed(() => {
  const raw = Number(route.query.focus)
  return Number.isFinite(raw) && raw > 0 ? raw : null
})
const justSubmitted = computed(() => String(route.query.submitted || "").trim() === "1")

const counts = computed(() => {
  const all = tasks.value.length
  const processing = tasks.value.filter((item) => isTaskProcessingStatus(item.status)).length
  const completed = tasks.value.filter((item) => item.status === "completed").length
  return { all, processing, completed }
})

const statusTabs = computed(() => [
  { key: "all", label: "全部", count: counts.value.all },
  { key: "processing", label: "处理中", count: counts.value.processing },
  { key: "completed", label: "已完成", count: counts.value.completed },
])
const totalCreditsFen = computed(() => tasks.value.reduce((sum, item) => sum + taskCostFen(item), 0))
const latestTaskTime = computed(() => (tasks.value[0]?.created_at ? `最近提交 ${formatTime(tasks.value[0].created_at)}` : "暂无记录"))

const filteredTasks = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return tasks.value.filter((item) => {
    if (statusFilter.value === "processing" && !isTaskProcessingStatus(item.status)) {
      return false
    }
    if (statusFilter.value === "completed" && item.status !== "completed") {
      return false
    }
    if (!text) {
      return true
    }
    const searchText = `${item.id} ${taskLabel(item)} ${mapTaskPlatform(item.platform, item.task_type)}`.toLowerCase()
    return searchText.includes(text)
  })
})

const totalPages = computed(() => Math.max(1, Math.ceil(filteredTasks.value.length / pageSize)))
const pagedTasks = computed(() => {
  const start = (page.value - 1) * pageSize
  return filteredTasks.value.slice(start, start + pageSize)
})
const visiblePages = computed(() => {
  const pages = []
  const start = Math.max(1, page.value - 2)
  const end = Math.min(totalPages.value, page.value + 2)
  for (let i = start; i <= end; i += 1) {
    pages.push(i)
  }
  return pages
})

watch([keyword, statusFilter], () => {
  page.value = 1
})

watch(
  [filteredTasks, focusTaskId],
  () => {
    if (!focusTaskId.value) {
      return
    }
    const index = filteredTasks.value.findIndex((item) => item.id === focusTaskId.value)
    if (index >= 0) {
      page.value = Math.floor(index / pageSize) + 1
    }
  },
  { immediate: true }
)

watch(totalPages, (value) => {
  if (page.value > value) {
    page.value = value
  }
})

onMounted(async () => {
  const jobs = [loadTasks()]
  if (getUserToken()) {
    jobs.push(refreshUser())
  }
  await Promise.all(jobs)
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})

async function loadTasks() {
  if (!getUserToken()) {
    tasks.value = []
    initialLoading.value = false
    return
  }
  const token = ++loadToken
  const hasExistingTasks = tasks.value.length > 0
  loading.value = true
  if (hasExistingTasks) {
    refreshing.value = true
  } else {
    initialLoading.value = true
  }
  try {
    const { items, restPromise } = await fetchUserTasksFast(
      { task_type: "dedup" },
      { focusTaskId: focusTaskId.value, pageSize: 100, maxPages: 20 }
    )
    if (token !== loadToken) return
    tasks.value = items
    loading.value = false
    const mergedItems = await restPromise
    if (token !== loadToken) return
    tasks.value = mergedItems
  } finally {
    if (token === loadToken) {
      loading.value = false
      initialLoading.value = false
      refreshing.value = false
    }
  }
}

function startPolling() {
  stopPolling()
  if (!getUserToken()) {
    return
  }
  pollTimer.value = window.setInterval(() => {
    if (shouldPollTaskRecords({ tasks: tasks.value, focusTaskId: focusTaskId.value, submitted: justSubmitted.value })) {
      loadTasks()
    }
  }, 4000)
}

function stopPolling() {
  if (pollTimer.value) {
    window.clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

function safeText(value) {
  if (typeof value === "string" && value.trim()) {
    return value.trim()
  }
  return "-"
}

function taskLabel(item) {
  const paperTitle = String(item?.result_json?.paper_title || "").trim()
  if (paperTitle) {
    return paperTitle
  }
  return item?.source_filename || `任务 #${item?.id}`
}

function formatTime(value) {
  return value ? String(value).slice(0, 19).replace("T", " ") : "-"
}

function taskCostFen(item) {
  if (typeof item?.cost_fen === "number") return item.cost_fen
  if (typeof item?.cost_points === "number") return item.cost_points
  if (typeof item?.cost_credits === "number") return item.cost_credits
  return 0
}

function formatCredits(value) {
  return `${Number(value || 0).toLocaleString()} 通用点数`
}

function reportDeadline(value) {
  if (!value) {
    return "-"
  }
  const time = new Date(value)
  if (Number.isNaN(time.getTime())) {
    return "-"
  }
  time.setDate(time.getDate() + 30)
  const iso = time.toISOString()
  return iso.slice(0, 19).replace("T", " ")
}

function taskFailureMessage(item) {
  const message = String(item?.error_message || "").trim()
  return message || "任务处理失败，请稍后重试"
}

function taskFailureHint(item) {
  const message = taskFailureMessage(item)
  return message.length > 22 ? `${message.slice(0, 22)}...` : message
}

function refundHint(item) {
  if (item?.refund_done) return "处理失败，已退回通用点数"
  return taskFailureHint(item)
}

function goUpload() {
  router.push("/app/dedup")
}

async function removeTask(item) {
  if (item.status === "running") {
    return
  }
  const ok = window.confirm(`确认删除任务 #${item.id} 吗？`)
  if (!ok) {
    return
  }
  removingId.value = item.id
  try {
    await userHttp.delete(`/tasks/${item.id}`)
    tasks.value = tasks.value.filter((row) => row.id !== item.id)
  } finally {
    removingId.value = null
  }
}

async function downloadResult(taskId) {
  const item = tasks.value.find((row) => row.id === taskId)
  const resp = await userHttp.get(`/tasks/${taskId}/download`, { responseType: "blob" })
  downloadAxiosBlobResponse(resp, item?.result_filename || `dedup_result_${taskId}`)
}

function filenamePair(item) {
  const sourceName = String(item?.source_filename || "-").trim() || "-"
  const resultName = String(item?.result_filename || "").trim() || `dedup_result_${item?.id || ""}`
  return `${sourceName} + ${resultName}`
}

async function afterPaid() {
  await refreshUser()
}
</script>
