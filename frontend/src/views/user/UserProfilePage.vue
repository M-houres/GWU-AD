<template>
  <UserShell title="个人中心" subtitle="账户、任务和点数都在这里统一查看。" :credits="userBalanceFen">
    <section v-if="isGuest" class="scholar-panel scholar-panel--soft">
      <div class="scholar-panel__body">
        <h3 class="scholar-subtitle">登录后查看个人数据</h3>
        <p class="scholar-lead">个人中心会统一归档任务记录、通用点数流水和账户信息。提交任务或查看个人数据时再登录即可。</p>
        <button class="scholar-button" type="button" style="margin-top: 18px" @click="goLogin">登录后进入个人中心</button>
      </div>
    </section>

    <template v-else>
      <section class="profile-page">
        <section class="profile-hero">
          <article class="profile-hero__main">
            <div class="profile-hero__eyebrow">账户中心</div>
            <h2>{{ displayName }}</h2>
            <p>常用信息集中到一个页面，充值、查看任务和核对点数都更直接。</p>
          </article>
          <article class="profile-hero__stat">
            <span>当前点数</span>
            <strong>{{ formatCredits(userBalanceFen || 0) }}</strong>
            <em>可直接用于提交任务</em>
          </article>
          <article class="profile-hero__stat">
            <span>今日免费</span>
            <strong>{{ aigcQuota.free_remaining_today }} / {{ aigcQuota.daily_free_limit }}</strong>
            <em>AIGC 检测剩余额度</em>
          </article>
          <article class="profile-hero__stat">
            <span>累计任务</span>
            <strong>{{ summaryState.task_counts?.total || 0 }}</strong>
            <em>最近动态实时更新</em>
          </article>
        </section>

        <div class="profile-layout">
          <aside class="profile-sidebar">
            <ul class="profile-nav">
              <li v-for="tab in tabs" :key="tab.key">
                <button type="button" :class="{ 'is-active': activeTab === tab.key }" @click="switchTab(tab.key)">
                  {{ tab.label }}
                </button>
              </li>
            </ul>
          </aside>

          <div class="profile-main">
            <section v-if="activeTab === 'buy'" class="scholar-panel">
              <div class="scholar-panel__header">
                <div>
                  <h3 class="scholar-subtitle">充值入口</h3>
                  <p class="scholar-lead">先补充点数，再按需要提交检测、降重或改写任务。</p>
                </div>
              </div>
              <div class="scholar-panel__body">
                <BuyCreditsPanel @paid="afterPaid" />
              </div>
            </section>

            <section v-else-if="activeTab === 'overview'" class="profile-stack">
              <section class="profile-top-grid profile-top-grid--single">
                <article class="scholar-panel">
                  <div class="scholar-panel__body">
                    <div class="profile-head">
                      <div>
                        <h3 class="scholar-subtitle">{{ displayName }}</h3>
                        <p class="scholar-lead">账户情况、任务活跃度和近期数据在这里快速查看。</p>
                      </div>
                      <div class="profile-head__chips">
                        <span class="profile-chip">已登录</span>
                        <span class="profile-chip profile-chip--soft">AIGC 今日免费剩余 {{ aigcQuota.free_remaining_today }} / {{ aigcQuota.daily_free_limit }}</span>
                      </div>
                    </div>

                    <div class="profile-metric-grid">
                      <article v-for="card in overviewCards" :key="card.label" class="profile-metric">
                        <div class="profile-metric__label">{{ card.label }}</div>
                        <div class="profile-metric__value">{{ card.value }}</div>
                        <div class="profile-metric__hint">{{ card.hint }}</div>
                      </article>
                    </div>
                  </div>
                </article>
              </section>
            </section>

            <section v-else-if="activeTab === 'history'" class="scholar-panel">
              <div class="scholar-panel__header">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 class="scholar-subtitle">任务记录</h3>
                    <p class="scholar-lead">按时间查看全部任务，处理状态和下载入口都集中在这里。</p>
                  </div>
                  <button class="scholar-button scholar-button--secondary" type="button" @click="loadTasks">刷新</button>
                </div>
              </div>
              <div class="scholar-panel__body">
                <div class="scholar-inline-actions" style="margin-bottom: 16px">
                  <button
                    v-for="item in historyTypeFilters"
                    :key="item.key"
                    type="button"
                    class="scholar-chip"
                    :class="{ 'is-active': historyTypeFilter === item.key }"
                    @click="historyTypeFilter = item.key"
                  >
                    {{ item.label }}
                  </button>
                  <span class="scholar-pill">共 {{ filteredTasks.length }} 条</span>
                </div>
                <div class="overflow-x-auto profile-table-shell">
                  <table class="scholar-table">
                    <thead>
                      <tr><th>任务 ID</th><th>标题</th><th>类型</th><th>平台</th><th>状态</th><th>字符数</th><th>通用点数</th><th>时间</th><th>操作</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="item in pagedTasks" :key="item.id">
                        <td>{{ item.id }}</td>
                        <td>
                          <div>{{ taskLabel(item) }}</div>
                          <div class="profile-file-pair">{{ taskFilenamePair(item) }}</div>
                        </td>
                        <td>{{ mapTaskType(item.task_type) }}</td>
                        <td>{{ mapPlatform(item.platform, item.task_type) }}</td>
                        <td><span class="scholar-badge" :class="statusClass(item.status)">{{ mapStatus(item.status) }}</span></td>
                        <td>{{ item.char_count || 0 }}</td>
                        <td>{{ formatCredits(taskCostFen(item)) }}</td>
                        <td>{{ formatTime(item.created_at) }}</td>
                        <td>
                          <div class="scholar-inline-actions">
                            <button class="scholar-button scholar-button--secondary" type="button" @click="openResult(item)">查看</button>
                            <button class="scholar-button" type="button" :disabled="item.status !== 'completed'" @click="download(item)">下载</button>
                          </div>
                        </td>
                      </tr>
                      <tr v-if="pagedTasks.length === 0"><td colspan="9"><div class="scholar-empty">暂无任务记录</div></td></tr>
                    </tbody>
                  </table>
                </div>
                <div class="profile-mobile-list">
                  <article v-for="item in pagedTasks" :key="`mobile-task-${item.id}`" class="profile-mobile-card">
                    <div class="profile-mobile-card__head">
                      <div>
                        <div class="profile-mobile-card__eyebrow">任务 #{{ item.id }}</div>
                        <strong class="profile-mobile-card__title">{{ taskLabel(item) }}</strong>
                        <div class="profile-file-pair">{{ taskFilenamePair(item) }}</div>
                      </div>
                      <span class="scholar-badge" :class="statusClass(item.status)">{{ mapStatus(item.status) }}</span>
                    </div>
                    <div class="profile-mobile-grid">
                      <div><span>类型</span><strong>{{ mapTaskType(item.task_type) }}</strong></div>
                      <div><span>平台</span><strong>{{ mapPlatform(item.platform, item.task_type) }}</strong></div>
                      <div><span>字符数</span><strong>{{ item.char_count || 0 }}</strong></div>
                      <div><span>通用点数</span><strong>{{ formatCredits(taskCostFen(item)) }}</strong></div>
                      <div><span>时间</span><strong>{{ formatTime(item.created_at) }}</strong></div>
                    </div>
                    <div class="profile-mobile-actions">
                      <button class="scholar-button scholar-button--secondary" type="button" @click="openResult(item)">查看</button>
                      <button class="scholar-button" type="button" :disabled="item.status !== 'completed'" @click="download(item)">下载</button>
                    </div>
                  </article>
                  <div v-if="pagedTasks.length === 0" class="scholar-empty">暂无任务记录</div>
                </div>
                <div v-if="historyTotalPages > 1" class="profile-pagination">
                  <button class="scholar-button scholar-button--secondary" type="button" :disabled="historyPage <= 1" @click="historyPage -= 1">上一页</button>
                  <span class="scholar-pill">第 {{ historyPage }} / {{ historyTotalPages }} 页</span>
                  <button class="scholar-button scholar-button--secondary" type="button" :disabled="historyPage >= historyTotalPages" @click="historyPage += 1">下一页</button>
                </div>
              </div>
            </section>

            <section v-else class="scholar-panel">
              <div class="scholar-panel__header">
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 class="scholar-subtitle">通用点数流水</h3>
                    <p class="scholar-lead">点数收入和支出按时间排列，方便核对每一次变动。</p>
                  </div>
                  <button class="scholar-button scholar-button--secondary" type="button" @click="loadTransactions">刷新</button>
                </div>
              </div>
              <div class="scholar-panel__body">
                <div class="scholar-inline-actions" style="margin-bottom: 16px">
                  <span class="scholar-pill">共 {{ txRows.length }} 条</span>
                  <span class="scholar-pill">累计入账 {{ formatCredits(creditOverview.income_total_fen ?? creditOverview.income_total ?? 0) }}</span>
                  <span class="scholar-pill">累计支出 {{ formatCredits(creditOverview.outcome_total_fen ?? creditOverview.outcome_total ?? 0) }}</span>
                </div>
                <div class="overflow-x-auto profile-table-shell">
                  <table class="scholar-table">
                    <thead>
                      <tr><th>时间</th><th>类型</th><th>变化</th><th>前点数</th><th>后点数</th><th>备注</th></tr>
                    </thead>
                    <tbody>
                      <tr v-for="row in pagedTransactions" :key="row.id">
                        <td>{{ formatTime(row.created_at) }}</td>
                        <td>{{ mapCreditType(row.tx_type) }}</td>
                        <td :style="{ color: txDeltaFen(row) >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }">{{ signedCredits(txDeltaFen(row)) }}</td>
                        <td>{{ formatCredits(txBalanceBeforeFen(row)) }}</td>
                        <td>{{ formatCredits(txBalanceAfterFen(row)) }}</td>
                        <td>{{ row.reason || "-" }}</td>
                      </tr>
                      <tr v-if="pagedTransactions.length === 0"><td colspan="6"><div class="scholar-empty">暂无流水</div></td></tr>
                    </tbody>
                  </table>
                </div>
                <div class="profile-mobile-list">
                  <article v-for="row in pagedTransactions" :key="`mobile-tx-${row.id}`" class="profile-mobile-card">
                    <div class="profile-mobile-card__head">
                      <div>
                        <div class="profile-mobile-card__eyebrow">流水 #{{ row.id }}</div>
                        <strong class="profile-mobile-card__title">{{ mapCreditType(row.tx_type) }}</strong>
                      </div>
                      <strong :class="['profile-mobile-delta', txDeltaFen(row) >= 0 ? 'is-plus' : 'is-minus']">{{ signedCredits(txDeltaFen(row)) }}</strong>
                    </div>
                    <div class="profile-mobile-grid">
                      <div><span>前点数</span><strong>{{ formatCredits(txBalanceBeforeFen(row)) }}</strong></div>
                      <div><span>后点数</span><strong>{{ formatCredits(txBalanceAfterFen(row)) }}</strong></div>
                      <div><span>时间</span><strong>{{ formatTime(row.created_at) }}</strong></div>
                      <div><span>备注</span><strong>{{ row.reason || "-" }}</strong></div>
                    </div>
                  </article>
                  <div v-if="pagedTransactions.length === 0" class="scholar-empty">暂无流水</div>
                </div>
                <div v-if="creditsTotalPages > 1" class="profile-pagination">
                  <button class="scholar-button scholar-button--secondary" type="button" :disabled="creditsPage <= 1" @click="creditsPage -= 1">上一页</button>
                  <span class="scholar-pill">第 {{ creditsPage }} / {{ creditsTotalPages }} 页</span>
                  <button class="scholar-button scholar-button--secondary" type="button" :disabled="creditsPage >= creditsTotalPages" @click="creditsPage += 1">下一页</button>
                </div>
              </div>
            </section>
          </div>
        </div>
      </section>

      <div v-if="selectedTask" class="scholar-modal" @click.self="closeResult">
        <div class="scholar-modal__dialog">
          <div class="scholar-panel__header">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h3 class="scholar-subtitle">{{ mapTaskType(selectedTask.task_type) }}结果摘要</h3>
                <p class="scholar-lead">{{ resultSummary(selectedTask) }}</p>
              </div>
              <button class="scholar-button scholar-button--secondary" type="button" @click="closeResult">关闭</button>
            </div>
          </div>
          <div class="scholar-panel__body">
            <div class="scholar-grid scholar-grid--stats">
              <article v-for="metric in resultMetrics(selectedTask)" :key="metric.label" class="scholar-stat">
                <div class="scholar-stat__label">{{ metric.label }}</div>
                <div class="scholar-stat__value" style="font-size: 26px">{{ metric.value }}</div>
              </article>
            </div>
            <section v-if="resultReviewPoints(selectedTask).length" class="scholar-panel scholar-panel--soft" style="margin-top: 18px">
              <div class="scholar-panel__body">
                <h4 class="scholar-subtitle">复核建议</h4>
                <div class="scholar-list" style="margin-top: 16px">
                  <div v-for="point in resultReviewPoints(selectedTask)" :key="point" class="scholar-list-item">{{ point }}</div>
                </div>
              </div>
            </section>
            <section v-if="resultOutputPreview(selectedTask)" class="scholar-panel scholar-panel--soft" style="margin-top: 18px">
              <div class="scholar-panel__body">
                <h4 class="scholar-subtitle">结果预览</h4>
                <div class="scholar-note" style="margin-top: 16px; white-space: pre-wrap">{{ resultOutputPreview(selectedTask) }}</div>
              </div>
            </section>
            <div class="scholar-inline-actions" style="margin-top: 18px">
              <button class="scholar-button" type="button" :disabled="selectedTask.status !== 'completed'" @click="download(selectedTask)">下载结果文件</button>
              <button class="scholar-button scholar-button--secondary" type="button" @click="closeResult">返回列表</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </UserShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { downloadAxiosBlobResponse } from "../../lib/download"
import { userHttp } from "../../lib/http"
import { ensureUserLogin } from "../../lib/requireLogin"
import { getUserToken } from "../../lib/session"
import { mapTaskPlatform } from "../../lib/taskPlatform"
import { mapTaskStatus, taskStatusClass } from "../../lib/taskStatus"
import { taskResultMetrics, taskResultOutputPreview, taskResultReviewPoints, taskResultSummary } from "../../lib/taskResult"
import { fetchAllUserCreditTransactions, fetchAllUserTasks } from "../../lib/userRecords"

const router = useRouter()
const route = useRoute()
const { user, refreshUser } = useUserProfile()

const tabs = [
  { key: "buy", label: "充值入口" },
  { key: "overview", label: "账户总览" },
  { key: "history", label: "任务记录" },
  { key: "credits", label: "点数流水" },
]
const historyTypeFilters = [
  { key: "all", label: "全部任务" },
  { key: "aigc_detect", label: "AIGC 检测" },
  { key: "dedup", label: "降重复率" },
  { key: "rewrite", label: "降AIGC率" },
]

const activeTab = ref("buy")
const tasks = ref([])
const txRows = ref([])
const selectedTask = ref(null)
const historyTypeFilter = ref("all")
const historyPage = ref(1)
const creditsPage = ref(1)
const summaryState = ref({
  task_counts: { total: 0, recent_7d: 0, by_type: { aigc_detect: 0, dedup: 0, rewrite: 0 }, by_status: { pending: 0, running: 0, completed: 0, failed: 0 }, last_created_at: null },
  credit_overview: { transaction_count: 0, income_total_fen: 0, outcome_total_fen: 0, income_total: 0, outcome_total: 0 },
  aigc_quota: { daily_free_limit: 0, submitted_today: 0, free_used_today: 0, free_remaining_today: 0 },
  recent_tasks: [],
  recent_transactions: [],
})

const historyPageSize = 10
const creditsPageSize = 10
const isGuest = computed(() => !getUserToken())
const userBalanceFen = computed(() => {
  if (typeof user.value?.balance_fen === "number") return user.value.balance_fen
  if (typeof user.value?.credits === "number") return user.value.credits
  return 0
})
const displayName = computed(() => user.value?.nickname || `用户 ${String(user.value?.phone || "").slice(-4) || ""}`)
const creditOverview = computed(() => summaryState.value.credit_overview || {})
const aigcQuota = computed(() => summaryState.value.aigc_quota || {})
const filteredTasks = computed(() => (historyTypeFilter.value === "all" ? tasks.value : tasks.value.filter((item) => item.task_type === historyTypeFilter.value)))
const pagedTasks = computed(() => filteredTasks.value.slice((historyPage.value - 1) * historyPageSize, historyPage.value * historyPageSize))
const pagedTransactions = computed(() => txRows.value.slice((creditsPage.value - 1) * creditsPageSize, creditsPage.value * creditsPageSize))
const historyTotalPages = computed(() => Math.max(1, Math.ceil(filteredTasks.value.length / historyPageSize)))
const creditsTotalPages = computed(() => Math.max(1, Math.ceil(txRows.value.length / creditsPageSize)))

const overviewCards = computed(() => [
  { label: "当前通用点数", value: formatCredits(userBalanceFen.value || 0), hint: "账户可用通用点数" },
  { label: "累计任务", value: String(summaryState.value.task_counts?.total || 0), hint: "所有检测、降重、润色记录" },
  { label: "近 7 天任务", value: String(summaryState.value.task_counts?.recent_7d || 0), hint: "最近一周提交活跃度" },
  { label: "点数流水", value: String(creditOverview.value.transaction_count || 0), hint: "账户全部变动记录数" },
])

watch(() => route.query.tab, (value) => { activeTab.value = normalizeTab(value) })
watch(historyTypeFilter, () => { historyPage.value = 1 })
watch(historyTotalPages, (value) => { if (historyPage.value > value) historyPage.value = value })
watch(creditsTotalPages, (value) => { if (creditsPage.value > value) creditsPage.value = value })

onMounted(async () => {
  activeTab.value = normalizeTab(route.query.tab)
  if (getUserToken()) {
    await refreshUser()
    await Promise.all([loadSummary(), loadTasks(), loadTransactions()])
  }
})

function normalizeTab(tab) {
  return tab === "buy" || tab === "overview" || tab === "history" || tab === "credits" ? tab : "buy"
}

function switchTab(tab) {
  activeTab.value = normalizeTab(tab)
  router.replace({ path: "/app/profile", query: activeTab.value === "buy" ? {} : { tab: activeTab.value } })
}

async function loadSummary() {
  if (!getUserToken()) return
  summaryState.value = { ...summaryState.value, ...(await userHttp.get("/users/me/summary")) }
}

async function loadTasks() {
  if (!getUserToken()) return
  const items = await fetchAllUserTasks({}, { pageSize: 100, maxPages: 20 })
  tasks.value = [...items].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
}

async function loadTransactions() {
  if (!getUserToken()) return
  txRows.value = await fetchAllUserCreditTransactions({}, { pageSize: 100, maxPages: 20 })
}

async function openResult(item) {
  if (item.status === "completed") {
    try {
      selectedTask.value = { ...item, ...(await userHttp.get(`/tasks/${item.id}`)) }
      return
    } catch {}
  }
  selectedTask.value = item
}

function closeResult() {
  selectedTask.value = null
}

async function download(taskOrId) {
  const taskId = Number(typeof taskOrId === "object" ? taskOrId?.id : taskOrId)
  if (!taskId) return
  if (!ensureUserLogin(router, route, "/app/profile?tab=history")) return
  const resp = await userHttp.get(`/tasks/${taskId}/download`, { responseType: "blob" })
  const task = typeof taskOrId === "object" ? taskOrId : tasks.value.find((item) => item.id === taskId)
  downloadAxiosBlobResponse(resp, task?.result_filename || `task_${taskId}_result`)
}

function taskLabel(item) {
  return String(item?.result_json?.paper_title || "").trim() || item?.source_filename || `任务 #${item?.id}`
}

function taskFilenamePair(item) {
  const sourceName = String(item?.source_filename || "-").trim() || "-"
  const resultName = String(item?.result_filename || "").trim() || `task_${item?.id || ""}_result`
  return `${sourceName} + ${resultName}`
}

function mapCreditType(type) {
  return { init: "初始化点数", task_consume: "任务消费", task_refund: "任务退款", package_pay: "点数充值", admin_adjust: "系统调整" }[type] || type
}

function mapTaskType(type) {
  return { aigc_detect: "AIGC 检测", dedup: "降重复率", rewrite: "降AIGC率" }[type] || type
}

function mapStatus(status) {
  return mapTaskStatus(status)
}

function statusClass(status) {
  const tone = taskStatusClass(status)
  if (tone === "success") return "scholar-badge--success"
  if (tone === "danger") return "scholar-badge--danger"
  if (tone === "info") return "scholar-badge--info"
  return "scholar-badge--warn"
}

function mapPlatform(platform, taskType) {
  return mapTaskPlatform(platform, taskType)
}

function resultSummary(task) {
  return taskResultSummary(task)
}

function resultMetrics(task) {
  return taskResultMetrics(task)
}

function resultReviewPoints(task) {
  return taskResultReviewPoints(task)
}

function resultOutputPreview(task) {
  return taskResultOutputPreview(task)
}

function formatTime(value) {
  return value ? String(value).slice(0, 19).replace("T", " ") : "-"
}

function formatCredits(value) {
  return `${Number(value || 0).toLocaleString()} 通用点数`
}

function signedCredits(value) {
  const points = Number(value || 0)
  const sign = points >= 0 ? "+" : ""
  return `${sign}${formatCredits(points)}`
}

function taskCostFen(task) {
  if (typeof task?.cost_fen === "number") return task.cost_fen
  if (typeof task?.cost_credits === "number") return task.cost_credits
  return 0
}

function txDeltaFen(row) {
  if (typeof row?.delta_fen === "number") return row.delta_fen
  if (typeof row?.delta === "number") return row.delta
  return 0
}

function txBalanceBeforeFen(row) {
  if (typeof row?.balance_before_fen === "number") return row.balance_before_fen
  if (typeof row?.balance_before === "number") return row.balance_before
  return 0
}

function txBalanceAfterFen(row) {
  if (typeof row?.balance_after_fen === "number") return row.balance_after_fen
  if (typeof row?.balance_after === "number") return row.balance_after
  return 0
}

async function afterPaid() {
  if (!getUserToken()) return
  await Promise.all([refreshUser(), loadSummary(), loadTransactions()])
}

function goLogin() {
  const redirect = encodeURIComponent(route.fullPath || "/app/profile")
  router.push(`/login?redirect=${redirect}`)
}
</script>

<style scoped>
.profile-page {
  display: grid;
  gap: 18px;
}

.profile-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) repeat(3, minmax(0, 0.62fr));
  gap: 14px;
}

.profile-hero__main,
.profile-hero__stat,
.profile-nav,
.profile-mobile-card {
  border: 1px solid rgba(30, 91, 223, 0.12);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 255, 0.94));
  box-shadow: 0 16px 30px rgba(30, 91, 223, 0.08);
}

.profile-hero__main {
  padding: 22px 24px;
  display: grid;
  gap: 8px;
}

.profile-hero__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6c87ac;
}

.profile-hero__main h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1.1;
  color: #1f3555;
}

.profile-hero__main p {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #617894;
}

.profile-hero__stat {
  padding: 18px 18px 16px;
  display: grid;
  gap: 6px;
}

.profile-hero__stat span {
  font-size: 12px;
  color: #6f86a5;
}

.profile-hero__stat strong {
  font-size: 24px;
  line-height: 1.08;
  color: #1e5bdf;
}

.profile-hero__stat em {
  font-style: normal;
  font-size: 12px;
  line-height: 1.6;
  color: #68809d;
}

.profile-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.profile-sidebar {
  position: sticky;
  top: 88px;
}

.profile-nav {
  list-style: none;
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
  margin: 0;
  padding: 12px;
}

.profile-nav li {
  min-width: 0;
}

.profile-nav button {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 46px;
  padding: 12px 15px;
  border-radius: 14px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #536d90;
  transition: all 0.18s ease;
  cursor: pointer;
  border: 1px solid transparent;
  background: transparent;
  text-align: left;
}

.profile-nav button:hover {
  background: rgba(30, 91, 223, 0.06);
  color: #163f76;
  border-color: rgba(30, 91, 223, 0.08);
}

.profile-nav button.is-active {
  background: linear-gradient(135deg, #5d92ff, #1e5bdf);
  color: #fff;
  border-color: rgba(30, 91, 223, 0.14);
  box-shadow: 0 14px 24px rgba(30, 91, 223, 0.18);
}

.profile-main {
  min-width: 0;
  display: grid;
  gap: 18px;
}

.profile-stack,
.profile-top-grid,
.profile-two-col {
  display: grid;
  gap: 18px;
}

.profile-top-grid {
  grid-template-columns: minmax(0, 1.3fr) minmax(320px, 0.7fr);
}

.profile-top-grid--single {
  grid-template-columns: minmax(0, 1fr);
}

.profile-two-col {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.profile-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.profile-head__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
}

.profile-chip {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: linear-gradient(135deg, #5d92ff, #1e5bdf);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.profile-chip--soft {
  background: rgba(30, 91, 223, 0.08);
  color: #35527d;
  border: 1px solid rgba(30, 91, 223, 0.12);
}

.profile-metric-grid,
.profile-card-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 18px;
}

.profile-metric,
.profile-card {
  padding: 16px;
  border: 1px solid rgba(30, 91, 223, 0.12);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(242, 247, 255, 0.94));
}

.profile-metric__label,
.profile-card__label {
  font-size: 12px;
  font-weight: 700;
  color: #67809f;
}

.profile-metric__value,
.profile-card__value {
  margin-top: 8px;
  font-size: 24px;
  line-height: 1.25;
  color: #1f3555;
  word-break: break-word;
}

.profile-metric__hint,
.profile-card__hint,
.profile-tip {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.7;
  color: #5f7896;
}

.profile-editor {
  display: flex;
  gap: 12px;
  align-items: center;
}

.profile-feedback {
  margin: 10px 0 0;
  font-size: 13px;
}

.profile-feedback.is-success,
.profile-delta.is-plus,
.profile-mobile-delta.is-plus {
  color: #106c4f;
}

.profile-feedback.is-error,
.profile-delta.is-minus,
.profile-mobile-delta.is-minus {
  color: #b24439;
}

.profile-file-pair {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #65809f;
  word-break: break-all;
}

.profile-list {
  display: grid;
  gap: 12px;
}

.profile-list__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(30, 91, 223, 0.08);
}

.profile-list__item:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.profile-list__main {
  min-width: 0;
  flex: 1;
}

.profile-link {
  padding: 0;
  border: 0;
  background: transparent;
  color: #1f3555;
  font-size: 15px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
}

.profile-link--static {
  cursor: default;
}

.profile-list__meta {
  margin-top: 6px;
  font-size: 12px;
  color: #5f7896;
}

.profile-list__side {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.profile-pagination {
  margin-top: 18px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
}

.profile-mobile-list {
  display: none;
}

.profile-mobile-card {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.profile-mobile-card + .profile-mobile-card {
  margin-top: 12px;
}

.profile-mobile-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.profile-mobile-card__eyebrow {
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #6b85a8;
}

.profile-mobile-card__title {
  display: block;
  margin-top: 6px;
  font-size: 16px;
  line-height: 1.5;
  color: #1f3555;
}

.profile-mobile-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.profile-mobile-grid div {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid rgba(30, 91, 223, 0.1);
}

.profile-mobile-grid span {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6b85a8;
}

.profile-mobile-grid strong {
  font-size: 13px;
  line-height: 1.6;
  color: #1f3555;
  word-break: break-word;
}

.profile-mobile-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.profile-mobile-delta {
  font-size: 15px;
  line-height: 1.4;
}

@media (max-width: 1200px) {
  .profile-hero {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .profile-hero__main {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1100px) {
  .profile-layout,
  .profile-top-grid,
  .profile-two-col {
    grid-template-columns: 1fr;
  }

  .profile-sidebar {
    position: static;
    top: auto;
  }

  .profile-nav {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .profile-hero {
    grid-template-columns: 1fr;
  }

  .profile-head,
  .profile-editor,
  .profile-list__item,
  .profile-list__side,
  .profile-pagination {
    flex-direction: column;
    align-items: stretch;
  }

  .profile-nav,
  .profile-metric-grid,
  .profile-card-grid,
  .profile-mobile-grid {
    grid-template-columns: 1fr;
  }

  .profile-table-shell {
    display: none;
  }

  .profile-mobile-list {
    display: block;
  }
}
</style>
