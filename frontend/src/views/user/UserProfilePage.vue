<template>
  <UserShell title="个人中心" subtitle="统一管理账户信息、任务记录、积分流水与免费额度。" :credits="userCredits" @buy="goBuy">
    <section v-if="isGuest" class="scholar-panel scholar-panel--soft">
      <div class="scholar-panel__body">
        <h3 class="scholar-subtitle">登录后查看个人数据</h3>
        <p class="scholar-lead">个人中心会统一归档任务记录、积分流水和账户信息。提交任务或查看个人数据时再登录即可。</p>
        <button class="scholar-button" type="button" style="margin-top: 18px" @click="goLogin">登录后进入个人中心</button>
      </div>
    </section>

    <template v-else>
      <section class="scholar-panel scholar-panel--soft">
        <div class="scholar-panel__body">
          <div class="scholar-inline-actions">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              type="button"
              class="scholar-chip"
              :class="{ 'is-active': activeTab === tab.key }"
              @click="switchTab(tab.key)"
            >
              {{ tab.label }}
            </button>
          </div>
        </div>
      </section>

      <section v-if="activeTab === 'overview'" class="profile-stack">
        <section class="profile-top-grid profile-top-grid--single">
          <article class="scholar-panel">
            <div class="scholar-panel__body">
              <div class="profile-head">
                <div>
                  <h3 class="scholar-subtitle">{{ displayName }}</h3>
                  <p class="scholar-lead">账户资料、任务活跃度和最近记录都在这里统一查看。</p>
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
              <p class="scholar-lead">这里会连续拉取你的历史任务，刷新和重新登录后不会只剩一页数据。</p>
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
                <tr><th>任务 ID</th><th>标题</th><th>类型</th><th>平台</th><th>状态</th><th>字符数</th><th>积分</th><th>时间</th><th>操作</th></tr>
              </thead>
              <tbody>
                <tr v-for="item in pagedTasks" :key="item.id">
                  <td>{{ item.id }}</td>
                  <td>{{ taskLabel(item) }}</td>
                  <td>{{ mapTaskType(item.task_type) }}</td>
                  <td>{{ mapPlatform(item.platform, item.task_type) }}</td>
                  <td><span class="scholar-badge" :class="statusClass(item.status)">{{ mapStatus(item.status) }}</span></td>
                  <td>{{ item.char_count || 0 }}</td>
                  <td>{{ item.cost_credits || 0 }} 积分</td>
                  <td>{{ formatTime(item.created_at) }}</td>
                  <td>
                    <div class="scholar-inline-actions">
                      <button class="scholar-button scholar-button--secondary" type="button" @click="openResult(item)">查看</button>
                      <button class="scholar-button" type="button" :disabled="item.status !== 'completed'" @click="download(item.id)">下载</button>
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
                </div>
                <span class="scholar-badge" :class="statusClass(item.status)">{{ mapStatus(item.status) }}</span>
              </div>
              <div class="profile-mobile-grid">
                <div><span>类型</span><strong>{{ mapTaskType(item.task_type) }}</strong></div>
                <div><span>平台</span><strong>{{ mapPlatform(item.platform, item.task_type) }}</strong></div>
                <div><span>字符数</span><strong>{{ item.char_count || 0 }}</strong></div>
                <div><span>积分</span><strong>{{ item.cost_credits || 0 }} 积分</strong></div>
                <div><span>时间</span><strong>{{ formatTime(item.created_at) }}</strong></div>
              </div>
              <div class="profile-mobile-actions">
                <button class="scholar-button scholar-button--secondary" type="button" @click="openResult(item)">查看</button>
                <button class="scholar-button" type="button" :disabled="item.status !== 'completed'" @click="download(item.id)">下载</button>
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
              <h3 class="scholar-subtitle">积分流水</h3>
              <p class="scholar-lead">全部流水按时间连续展示，初始积分、消费、退款和充值都能在这里看到。</p>
            </div>
            <button class="scholar-button scholar-button--secondary" type="button" @click="loadTransactions">刷新</button>
          </div>
        </div>
        <div class="scholar-panel__body">
          <div class="scholar-inline-actions" style="margin-bottom: 16px">
            <span class="scholar-pill">共 {{ txRows.length }} 条</span>
            <span class="scholar-pill">累计入账 {{ creditOverview.income_total }} 积分</span>
            <span class="scholar-pill">累计支出 {{ creditOverview.outcome_total }} 积分</span>
          </div>
          <div class="overflow-x-auto profile-table-shell">
            <table class="scholar-table">
              <thead>
                <tr><th>时间</th><th>类型</th><th>变化</th><th>前余额</th><th>后余额</th><th>备注</th></tr>
              </thead>
              <tbody>
                <tr v-for="row in pagedTransactions" :key="row.id">
                  <td>{{ formatTime(row.created_at) }}</td>
                  <td>{{ mapCreditType(row.tx_type) }}</td>
                  <td :style="{ color: row.delta >= 0 ? 'var(--success)' : 'var(--danger)', fontWeight: 600 }">{{ row.delta >= 0 ? `+${row.delta}` : row.delta }} 积分</td>
                  <td>{{ row.balance_before }} 积分</td>
                  <td>{{ row.balance_after }} 积分</td>
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
                <strong :class="['profile-mobile-delta', row.delta >= 0 ? 'is-plus' : 'is-minus']">{{ row.delta >= 0 ? `+${row.delta}` : row.delta }} 积分</strong>
              </div>
              <div class="profile-mobile-grid">
                <div><span>前余额</span><strong>{{ row.balance_before }} 积分</strong></div>
                <div><span>后余额</span><strong>{{ row.balance_after }} 积分</strong></div>
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
              <button class="scholar-button" type="button" :disabled="selectedTask.status !== 'completed'" @click="download(selectedTask.id)">下载结果文件</button>
              <button class="scholar-button scholar-button--secondary" type="button" @click="closeResult">返回列表</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </UserShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
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
  { key: "overview", label: "账户总览" },
  { key: "history", label: "任务记录" },
  { key: "credits", label: "积分流水" },
]
const historyTypeFilters = [
  { key: "all", label: "全部任务" },
  { key: "aigc_detect", label: "AIGC 检测" },
  { key: "dedup", label: "降重复率" },
  { key: "rewrite", label: "降AIGC率" },
]

const activeTab = ref("overview")
const nickname = ref("")
const tasks = ref([])
const txRows = ref([])
const selectedTask = ref(null)
const historyTypeFilter = ref("all")
const historyPage = ref(1)
const creditsPage = ref(1)
const savingNickname = ref(false)
const nicknameFeedback = reactive({ type: "", text: "" })
const summaryState = ref({
  task_counts: { total: 0, recent_7d: 0, by_type: { aigc_detect: 0, dedup: 0, rewrite: 0 }, by_status: { pending: 0, running: 0, completed: 0, failed: 0 }, last_created_at: null },
  credit_overview: { transaction_count: 0, income_total: 0, outcome_total: 0 },
  aigc_quota: { daily_free_limit: 0, submitted_today: 0, free_used_today: 0, free_remaining_today: 0 },
  recent_tasks: [],
  recent_transactions: [],
})

const historyPageSize = 10
const creditsPageSize = 10
const isGuest = computed(() => !getUserToken())
const userCredits = computed(() => (typeof user.value?.credits === "number" ? user.value.credits : null))
const displayName = computed(() => user.value?.nickname || `用户 ${String(user.value?.phone || "").slice(-4) || ""}`)
const creditOverview = computed(() => summaryState.value.credit_overview || {})
const aigcQuota = computed(() => summaryState.value.aigc_quota || {})
const recentTasks = computed(() => summaryState.value.recent_tasks || [])
const recentTransactions = computed(() => summaryState.value.recent_transactions || [])
const filteredTasks = computed(() => (historyTypeFilter.value === "all" ? tasks.value : tasks.value.filter((item) => item.task_type === historyTypeFilter.value)))
const pagedTasks = computed(() => filteredTasks.value.slice((historyPage.value - 1) * historyPageSize, historyPage.value * historyPageSize))
const pagedTransactions = computed(() => txRows.value.slice((creditsPage.value - 1) * creditsPageSize, creditsPage.value * creditsPageSize))
const historyTotalPages = computed(() => Math.max(1, Math.ceil(filteredTasks.value.length / historyPageSize)))
const creditsTotalPages = computed(() => Math.max(1, Math.ceil(txRows.value.length / creditsPageSize)))

const overviewCards = computed(() => [
  { label: "当前积分", value: `${userCredits.value || 0} 积分`, hint: "账户可用余额" },
  { label: "累计任务", value: String(summaryState.value.task_counts?.total || 0), hint: "所有检测、降重、润色记录" },
  { label: "近 7 天任务", value: String(summaryState.value.task_counts?.recent_7d || 0), hint: "最近一周提交活跃度" },
  { label: "积分流水", value: String(creditOverview.value.transaction_count || 0), hint: "账户全部变动记录数" },
])
const accountCards = computed(() => [
  { label: "手机号", value: user.value?.phone || "-", hint: "登录与通知使用该手机号" },
  { label: "昵称", value: user.value?.nickname || "未设置", hint: "支持随时修改并立即生效" },
  { label: "注册时间", value: formatTime(user.value?.created_at), hint: "按系统记录时间展示" },
  { label: "账户编号", value: user.value?.id ? `#${user.value.id}` : "-", hint: "用于后台排查与对账" },
  { label: "注册来源", value: mapUserSource(user.value?.source), hint: "区分 Web 与小程序入口" },
  { label: "最近任务时间", value: formatTime(summaryState.value.task_counts?.last_created_at), hint: "用于确认最近一次提交" },
])
const breakdownCards = computed(() => [
  { label: "AIGC 检测", value: summaryState.value.task_counts?.by_type?.aigc_detect || 0, hint: "功能累计任务数" },
  { label: "降重复率", value: summaryState.value.task_counts?.by_type?.dedup || 0, hint: "功能累计任务数" },
  { label: "降AIGC率", value: summaryState.value.task_counts?.by_type?.rewrite || 0, hint: "功能累计任务数" },
  {
    label: "处理中",
    value:
      (summaryState.value.task_counts?.by_status?.pending || 0) +
      (summaryState.value.task_counts?.by_status?.preprocessing || 0) +
      (summaryState.value.task_counts?.by_status?.queued || 0) +
      (summaryState.value.task_counts?.by_status?.running || 0),
    hint: "当前还在执行中的任务",
  },
  { label: "已完成", value: summaryState.value.task_counts?.by_status?.completed || 0, hint: "已产出结果的任务" },
  { label: "失败", value: summaryState.value.task_counts?.by_status?.failed || 0, hint: "需要重新提交或人工排查" },
])

watch(() => route.query.tab, (value) => { activeTab.value = normalizeTab(value) })
watch(() => user.value?.nickname, (value) => { nickname.value = value || "" }, { immediate: true })
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
  return tab === "history" || tab === "credits" ? tab : "overview"
}

function switchTab(tab) {
  activeTab.value = normalizeTab(tab)
  router.replace({ path: "/app/profile", query: activeTab.value === "overview" ? {} : { tab: activeTab.value } })
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

async function saveNickname() {
  if (!ensureUserLogin(router, { fullPath: "/app/profile" }, "/app/profile")) return
  if (savingNickname.value) return
  savingNickname.value = true
  nicknameFeedback.type = ""
  nicknameFeedback.text = ""
  try {
    await userHttp.patch("/users/me", { nickname: nickname.value })
    await refreshUser()
    nicknameFeedback.type = "success"
    nicknameFeedback.text = "昵称已保存并同步到账户信息。"
  } catch (error) {
    nicknameFeedback.type = "error"
    nicknameFeedback.text = String(error?.message || "昵称保存失败，请稍后重试")
  } finally {
    savingNickname.value = false
  }
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

async function download(taskId) {
  if (!ensureUserLogin(router, route, "/app/profile?tab=history")) return
  const resp = await userHttp.get(`/tasks/${taskId}/download`, { responseType: "blob" })
  downloadAxiosBlobResponse(resp, `task_${taskId}_result`)
}

function taskLabel(item) {
  return String(item?.result_json?.paper_title || "").trim() || item?.source_filename || `任务 #${item?.id}`
}

function mapCreditType(type) {
  return { init: "初始积分", task_consume: "任务消费", task_refund: "任务退款", package_pay: "积分充值", referral_invite: "邀请奖励", referral_bonus: "被邀请福利", referral_first_pay: "首充返佣", referral_recurring: "持续返利", share_reward: "分享奖励", admin_adjust: "系统调整" }[type] || type
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

function mapUserSource(source) {
  return { web: "Web 端", miniapp: "小程序", other: "其他来源" }[source] || source || "未记录"
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

function goBuy() {
  router.push("/app/buy")
}

function goLogin() {
  const redirect = encodeURIComponent(route.fullPath || "/app/profile")
  router.push(`/login?redirect=${redirect}`)
}
</script>

<style scoped>
.profile-stack,.profile-top-grid,.profile-two-col{display:grid;gap:18px}
.profile-top-grid{grid-template-columns:minmax(0,1.3fr) minmax(320px,.7fr)}
.profile-top-grid--single{grid-template-columns:minmax(0,1fr)}
.profile-two-col{grid-template-columns:repeat(2,minmax(0,1fr))}
.profile-head{display:flex;justify-content:space-between;gap:16px}
.profile-head__chips{display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start}
.profile-chip{display:inline-flex;align-items:center;min-height:32px;padding:0 12px;border-radius:999px;background:#111;color:#fff;font-size:12px;font-weight:600}
.profile-chip--soft{background:#f5f7f9;color:#33414d;border:1px solid rgba(17,17,17,.12)}
.profile-metric-grid,.profile-card-grid{display:grid;gap:12px;grid-template-columns:repeat(2,minmax(0,1fr));margin-top:18px}
.profile-metric,.profile-card{padding:16px;border:1px solid rgba(17,17,17,.08);border-radius:16px;background:linear-gradient(180deg,#fff 0%,#f7f8fa 100%)}
.profile-metric__label,.profile-card__label{font-size:12px;font-weight:600;color:#5a6773}
.profile-metric__value,.profile-card__value{margin-top:8px;font-size:24px;line-height:1.25;color:#111;word-break:break-word}
.profile-metric__hint,.profile-card__hint,.profile-tip{margin-top:8px;font-size:13px;line-height:1.7;color:#5a6773}
.profile-editor{display:flex;gap:12px;align-items:center}
.profile-feedback{margin:10px 0 0;font-size:13px}
.profile-feedback.is-success{color:#106c4f}
.profile-feedback.is-error{color:#b24439}
.profile-list{display:grid;gap:12px}
.profile-list__item{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:12px 0;border-bottom:1px solid rgba(17,17,17,.06)}
.profile-list__item:last-child{border-bottom:0;padding-bottom:0}
.profile-list__main{min-width:0;flex:1}
.profile-link{padding:0;border:0;background:transparent;color:#111;font-size:15px;font-weight:600;text-align:left;cursor:pointer}
.profile-link--static{cursor:default}
.profile-list__meta{margin-top:6px;font-size:12px;color:#5a6773}
.profile-list__side{display:flex;align-items:center;gap:10px;flex-shrink:0}
.profile-delta.is-plus{color:#106c4f}
.profile-delta.is-minus{color:#b24439}
.profile-pagination{margin-top:18px;display:flex;justify-content:center;align-items:center;gap:12px}
.profile-mobile-list{display:none}
.profile-mobile-card{display:grid;gap:14px;padding:16px;border:1px solid rgba(17,17,17,.08);border-radius:18px;background:linear-gradient(180deg,#fff 0%,#f7f8fa 100%)}
.profile-mobile-card + .profile-mobile-card{margin-top:12px}
.profile-mobile-card__head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}
.profile-mobile-card__eyebrow{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#6b7782}
.profile-mobile-card__title{display:block;margin-top:6px;font-size:16px;line-height:1.5;color:#111}
.profile-mobile-grid{display:grid;gap:10px;grid-template-columns:repeat(2,minmax(0,1fr))}
.profile-mobile-grid div{display:grid;gap:4px;padding:10px 12px;border-radius:14px;background:#fff;border:1px solid rgba(17,17,17,.06)}
.profile-mobile-grid span{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#6b7782}
.profile-mobile-grid strong{font-size:13px;line-height:1.6;color:#111;word-break:break-word}
.profile-mobile-actions{display:flex;gap:10px;flex-wrap:wrap}
.profile-mobile-delta{font-size:15px;line-height:1.4}
.profile-mobile-delta.is-plus{color:#106c4f}
.profile-mobile-delta.is-minus{color:#b24439}
@media (max-width:1100px){.profile-top-grid,.profile-two-col{grid-template-columns:1fr}}
@media (max-width:720px){.profile-head,.profile-editor,.profile-list__item,.profile-list__side,.profile-pagination{flex-direction:column;align-items:stretch}.profile-metric-grid,.profile-card-grid,.profile-mobile-grid{grid-template-columns:1fr}.profile-table-shell{display:none}.profile-mobile-list{display:block}}
</style>
