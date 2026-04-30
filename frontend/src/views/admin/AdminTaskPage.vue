<template>
  <AdminShell title="任务管理" subtitle="多维筛选与任务详情查看。">
    <section class="gw-admin-task-overview">
      <article class="gw-admin-task-overview__hero">
        <div class="gw-admin-task-overview__eyebrow">任务工作台</div>
        <h2>任务管理</h2>
        <p>筛选、查看详情和下载结果都集中处理，减少后台重复点开任务的成本。</p>
      </article>
      <article class="gw-admin-task-overview__stat">
        <span>当前结果</span>
        <strong>{{ rows.length }}</strong>
        <em>按筛选条件展示</em>
      </article>
      <article class="gw-admin-task-overview__stat">
        <span>处理中</span>
        <strong>{{ processingCount }}</strong>
        <em>等待、排队和处理中任务</em>
      </article>
      <article class="gw-admin-task-overview__stat">
        <span>已完成</span>
        <strong>{{ completedCount }}</strong>
        <em>结果可进一步复核</em>
      </article>
    </section>

    <section class="gw-admin-task-panel">
      <div class="gw-admin-task-filters">
        <div class="grid gap-2 md:grid-cols-3">
          <input v-model.trim="filters.qPhone" class="gw-admin-task-input" placeholder="用户手机号" />
          <input v-model="filters.startDate" type="date" class="gw-admin-task-input" />
          <input v-model="filters.endDate" type="date" class="gw-admin-task-input" />
        </div>

        <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <div class="mb-2 text-xs font-semibold tracking-[0.08em] text-[#6b7a86]">任务类型</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="item in taskTypeOptions" :key="item.value || 'all-task'" type="button" :class="chipClass(filters.taskType, item.value)" @click="filters.taskType = item.value">
                {{ item.label }}
              </button>
            </div>
          </div>

          <div>
            <div class="mb-2 text-xs font-semibold tracking-[0.08em] text-[#6b7a86]">平台</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="item in platformOptions" :key="item.value || 'all-platform'" type="button" :class="chipClass(filters.platform, item.value)" @click="filters.platform = item.value">
                {{ item.label }}
              </button>
            </div>
          </div>

          <div>
            <div class="mb-2 text-xs font-semibold tracking-[0.08em] text-[#6b7a86]">状态</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="item in statusOptions" :key="item.value || 'all-status'" type="button" :class="chipClass(filters.status, item.value)" @click="filters.status = item.value">
                {{ item.label }}
              </button>
            </div>
          </div>

          <div>
            <div class="mb-2 text-xs font-semibold tracking-[0.08em] text-[#6b7a86]">来源</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="item in sourceOptions" :key="item.value || 'all-source'" type="button" :class="chipClass(filters.source, item.value)" @click="filters.source = item.value">
                {{ item.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="scholar-button" @click="loadData">查询</button>
          <button class="scholar-button scholar-button--secondary" @click="resetFilters">重置</button>
        </div>

        <div class="flex flex-wrap gap-4 text-xs text-[#4b5965]">
          <span>Web: {{ sourceStats.web || 0 }}</span>
          <span>小程序: {{ sourceStats.miniapp || 0 }}</span>
          <span>其他: {{ sourceStats.other || 0 }}</span>
          <span>总计: {{ sourceStats.total || 0 }}</span>
        </div>
      </div>

      <div class="overflow-x-auto gw-admin-task-table-shell">
        <table class="scholar-table gw-admin-task-table">
          <thead>
            <tr class="border-b border-[#e1e6eb] text-left text-[#5a6671]">
              <th class="px-2 py-2">任务ID</th>
              <th class="px-2 py-2">用户ID</th>
              <th class="px-2 py-2">类型</th>
              <th class="px-2 py-2">平台</th>
              <th class="px-2 py-2">来源</th>
              <th class="px-2 py-2">状态</th>
              <th class="px-2 py-2">字符数</th>
              <th class="px-2 py-2">通用点数</th>
              <th class="px-2 py-2">创建时间</th>
              <th class="px-2 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.id" class="border-b border-[#eef2f5]">
              <td class="px-2 py-2">{{ row.id }}</td>
              <td class="px-2 py-2">{{ row.user_id }}</td>
              <td class="px-2 py-2">{{ mapTaskType(row.task_type) }}</td>
              <td class="px-2 py-2">{{ mapPlatform(row.platform, row.task_type) }}</td>
              <td class="px-2 py-2">{{ mapSource(row.source) }}</td>
              <td class="px-2 py-2">
                <span :class="statusClass(row.status)" class="inline-flex items-center rounded-full border px-2 py-1 text-xs">{{ mapStatus(row.status) }}</span>
              </td>
              <td class="px-2 py-2">{{ row.char_count }}</td>
              <td class="px-2 py-2">{{ formatCredits(rowCostFen(row)) }}</td>
              <td class="px-2 py-2">{{ formatTime(row.created_at) }}</td>
              <td class="px-2 py-2">
                <button class="scholar-button scholar-button--compact" @click="openDetail(row.id)">查看详情</button>
              </td>
            </tr>
            <tr v-if="rows.length === 0">
              <td class="px-2 py-3 text-[#5b6771]" colspan="10">暂无任务</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="gw-admin-task-mobile-list">
        <article v-for="row in rows" :key="`task-mobile-${row.id}`" class="gw-admin-task-card">
          <div class="gw-admin-task-card__head">
            <div>
              <div class="gw-admin-task-card__eyebrow">任务 #{{ row.id }}</div>
              <strong class="gw-admin-task-card__title">{{ mapTaskType(row.task_type) }} / {{ mapPlatform(row.platform, row.task_type) }}</strong>
              <div class="gw-admin-task-card__sub">用户 {{ row.user_id }} · {{ mapSource(row.source) }}</div>
            </div>
            <span :class="statusClass(row.status)" class="inline-flex items-center rounded-full border px-2 py-1 text-xs">
              {{ mapStatus(row.status) }}
            </span>
          </div>

          <div class="gw-admin-task-card__grid">
            <div><span>字符数</span><strong>{{ row.char_count }}</strong></div>
            <div><span>通用点数</span><strong>{{ formatCredits(rowCostFen(row)) }}</strong></div>
            <div><span>创建时间</span><strong>{{ formatTime(row.created_at) }}</strong></div>
          </div>

          <div class="gw-admin-task-card__actions">
            <button class="scholar-button scholar-button--compact" @click="openDetail(row.id)">查看详情</button>
          </div>
        </article>
        <div v-if="rows.length === 0" class="scholar-empty">暂无任务</div>
      </div>
    </section>

    <section v-if="taskDetail" class="gw-admin-task-detail">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div class="text-[11px] uppercase tracking-[0.18em] text-[#73808b]">任务洞察</div>
          <h3 class="mt-2 text-base font-semibold">任务详情 #{{ taskDetail.id }}</h3>
          <p class="mt-1 text-sm leading-6 text-[#5c6872]">{{ resultSummary(taskDetail) }}</p>
        </div>
        <div class="flex flex-wrap gap-2">
          <button class="scholar-button" :disabled="taskDetail.status !== 'completed'" @click="downloadResult(taskDetail.id)">下载结果</button>
          <button class="scholar-button scholar-button--secondary" @click="openDetail(taskDetail.id)">刷新</button>
          <button class="scholar-button scholar-button--secondary" @click="closeDetail">关闭</button>
        </div>
      </div>

      <div class="grid gap-2 text-sm md:grid-cols-2 xl:grid-cols-3">
        <div>用户：{{ taskDetail.user_id }} {{ taskDetail.user_phone ? `(${taskDetail.user_phone})` : '' }}</div>
        <div>类型：{{ mapTaskType(taskDetail.task_type) }}</div>
        <div>平台：{{ mapPlatform(taskDetail.platform, taskDetail.task_type) }}</div>
        <div>来源：{{ mapSource(taskDetail.source) }}</div>
        <div>状态：{{ mapStatus(taskDetail.status) }}</div>
        <div>字符数：{{ taskDetail.char_count }}</div>
        <div>通用点数：{{ formatCredits(rowCostFen(taskDetail)) }}</div>
        <div>退款状态：{{ taskDetail.refund_done ? '已退回' : '未退款' }}</div>
        <div>原文件：{{ taskDetail.source_filename || '-' }}</div>
        <div>创建时间：{{ formatTime(taskDetail.created_at) }}</div>
        <div>更新时间：{{ formatTime(taskDetail.updated_at) }}</div>
        <div class="xl:col-span-3">结果文件：{{ taskDetail.output_path || '-' }}</div>
        <div class="xl:col-span-3">错误信息：{{ taskDetail.error_message || '-' }}</div>
      </div>

      <div v-if="resultMetrics(taskDetail).length" class="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <article v-for="metric in resultMetrics(taskDetail)" :key="metric.label" class="rounded-2xl border border-[#dce3e9] bg-white p-4">
          <div class="text-xs tracking-[0.1em] text-[#6d7a86]">{{ metric.label }}</div>
          <div class="mt-2 text-lg font-semibold text-[#16222a]">{{ metric.value }}</div>
        </article>
      </div>

      <section v-if="resultRiskParagraphs(taskDetail).length" class="mt-5 rounded-2xl border border-[#dce3e9] bg-white p-4">
        <h4 class="text-sm font-semibold text-[#1c2831]">高风险段落</h4>
        <div class="mt-3 space-y-3">
          <div v-for="item in resultRiskParagraphs(taskDetail)" :key="`${item.index}-${item.score}`" class="rounded-xl border border-[#e4eaf0] bg-white p-3">
            <div class="text-xs text-[#6b7884]">段落 {{ item.index }} · 风险 {{ item.score }}%</div>
            <div class="mt-2 text-sm leading-6 text-[#31404b]">{{ item.excerpt }}</div>
          </div>
        </div>
      </section>

      <section v-if="resultReviewPoints(taskDetail).length" class="mt-5 rounded-2xl border border-[#dce3e9] bg-white p-4">
        <h4 class="text-sm font-semibold text-[#1c2831]">复核建议</h4>
        <div class="mt-3 space-y-2">
          <div v-for="point in resultReviewPoints(taskDetail)" :key="point" class="flex items-start gap-2 rounded-xl border border-[#e4eaf0] bg-white px-3 py-2">
            <span class="mt-1 h-1.5 w-1.5 rounded-full bg-[#111111]"></span>
            <span class="text-sm leading-6 text-[#3c4b56]">{{ point }}</span>
          </div>
        </div>
      </section>

      <section v-if="resultOutputPreview(taskDetail)" class="mt-5 rounded-2xl border border-[#dce3e9] bg-white p-4">
        <h4 class="text-sm font-semibold text-[#1c2831]">结果预览</h4>
        <div class="mt-3 whitespace-pre-wrap rounded-xl border border-[#e4eaf0] bg-white p-3 text-sm leading-6 text-[#2f3d48]">
          {{ resultOutputPreview(taskDetail) }}
        </div>
      </section>

      <section v-if="taskDetail.result_json" class="mt-5 rounded-2xl border border-[#dce3e9] bg-white p-4">
        <h4 class="text-sm font-semibold text-[#1c2831]">原始结果 JSON</h4>
        <pre class="mt-3 overflow-x-auto rounded-xl border border-[#e4eaf0] bg-white p-3 text-xs leading-6 text-[#31404b]">{{ formatJson(taskDetail.result_json) }}</pre>
      </section>
    </section>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import AdminShell from "../../components/AdminShell.vue"
import { formatBeijingDateTime } from "../../lib/dateTime"
import { downloadAxiosBlobResponse } from "../../lib/download"
import { adminHttp } from "../../lib/http"
import { TASK_PLATFORM_OPTIONS, mapTaskPlatform } from "../../lib/taskPlatform"
import {
  taskResultMetrics,
  taskResultOutputPreview,
  taskResultReviewPoints,
  taskResultRiskParagraphs,
  taskResultSummary,
} from "../../lib/taskResult"

const rows = ref([])
const sourceStats = ref({ web: 0, miniapp: 0, other: 0, total: 0 })
const taskDetail = ref(null)
const route = useRoute()
const router = useRouter()
const filters = reactive({
  qPhone: "",
  taskType: "",
  platform: "",
  status: "",
  source: "",
  startDate: "",
  endDate: "",
})
let syncingRouteTask = false

const taskTypeOptions = [
  { value: "", label: "全部" },
  { value: "aigc_detect", label: "AIGC检测" },
  { value: "dedup", label: "降重" },
  { value: "rewrite", label: "降AIGC率" },
]
const platformOptions = [
  { value: "", label: "全部" },
  ...TASK_PLATFORM_OPTIONS,
]
const statusOptions = [
  { value: "", label: "全部" },
  { value: "preprocessing", label: "预处理中" },
  { value: "queued", label: "排队中" },
  { value: "pending", label: "等待中" },
  { value: "running", label: "处理中" },
  { value: "completed", label: "已完成" },
  { value: "failed", label: "失败" },
]
const sourceOptions = [
  { value: "", label: "全部" },
  { value: "web", label: "Web" },
  { value: "miniapp", label: "小程序" },
  { value: "other", label: "其他" },
]
const completedCount = computed(() => rows.value.filter((row) => row.status === "completed").length)
const processingCount = computed(() =>
  rows.value.filter((row) => ["preprocessing", "queued", "pending", "running"].includes(String(row.status || ""))).length
)

watch(
  () => route.query.task_id,
  async (value) => {
    if (syncingRouteTask) return
    const taskId = Number(value || 0)
    if (Number.isInteger(taskId) && taskId > 0) {
      await openDetail(taskId, { syncRoute: false })
      return
    }
    taskDetail.value = null
  }
)

onMounted(async () => {
  await loadData()
  await syncTaskFromRoute()
})

async function loadData() {
  const params = {
    page: 1,
    page_size: 100,
    q_phone: filters.qPhone || undefined,
    task_type: filters.taskType || undefined,
    platform: filters.platform || undefined,
    status: filters.status || undefined,
    source: filters.source || undefined,
    start_date: filters.startDate || undefined,
    end_date: filters.endDate || undefined,
  }
  const data = await adminHttp.get("/admin/tasks", { params })
  rows.value = data.items || []
  sourceStats.value = data.source_stats || { web: 0, miniapp: 0, other: 0, total: 0 }
}

function resetFilters() {
  filters.qPhone = ""
  filters.taskType = ""
  filters.platform = ""
  filters.status = ""
  filters.source = ""
  filters.startDate = ""
  filters.endDate = ""
  loadData()
}

async function syncTaskFromRoute() {
  const taskId = Number(route.query.task_id || 0)
  if (Number.isInteger(taskId) && taskId > 0) {
    await openDetail(taskId, { syncRoute: false })
  }
}

async function openDetail(taskId, options = {}) {
  taskDetail.value = await adminHttp.get(`/admin/tasks/${taskId}/detail`)
  if (options.syncRoute === false) return
  syncingRouteTask = true
  try {
    await router.replace({ path: "/admin/tasks", query: { task_id: String(taskId) } })
  } finally {
    syncingRouteTask = false
  }
}

async function downloadResult(taskId) {
  const resp = await adminHttp.get(`/admin/tasks/${taskId}/download`, { responseType: "blob" })
  downloadAxiosBlobResponse(resp, `admin_task_${taskId}_result`)
}

async function closeDetail() {
  taskDetail.value = null
  if (!route.query.task_id) return
  syncingRouteTask = true
  try {
    await router.replace({ path: "/admin/tasks" })
  } finally {
    syncingRouteTask = false
  }
}

function mapTaskType(type) {
  const mapping = {
    aigc_detect: "AIGC检测",
    dedup: "降重",
    rewrite: "降AIGC率",
  }
  return mapping[type] || type
}

function mapPlatform(platform, taskType) {
  return mapTaskPlatform(platform, taskType)
}

function mapSource(source) {
  const mapping = {
    web: "Web",
    miniapp: "小程序",
    other: "其他",
  }
  return mapping[source] || "其他"
}

function mapStatus(status) {
  const mapping = {
    preprocessing: "预处理中",
    queued: "排队中",
    pending: "等待中",
    running: "处理中",
    completed: "已完成",
    failed: "失败",
  }
  return mapping[status] || status
}

function statusClass(status) {
  if (status === "completed") return "border-[#111111] bg-[#111111] text-white"
  if (status === "failed") return "border-[#111111] bg-white text-[#111111]"
  return "border-[#111111] bg-white text-[#111111]"
}

function chipClass(current, value) {
  const active = current === value
  if (active) {
    return "is-active rounded-xl border border-[#111111] bg-[#111111] px-3 py-1.5 text-sm font-medium text-white"
  }
  return "rounded-xl border border-[#111111] bg-white px-3 py-1.5 text-sm text-[#111111]"
}

function formatTime(value) {
  return formatBeijingDateTime(value)
}

function rowCostFen(row) {
  if (typeof row?.cost_fen === "number") return row.cost_fen
  if (typeof row?.cost_credits === "number") return row.cost_credits
  return 0
}

function formatCredits(value) {
  return `${Number(value || 0).toLocaleString()} 通用点数`
}

function resultSummary(task) {
  return taskResultSummary(task)
}

function resultMetrics(task) {
  return taskResultMetrics(task)
}

function resultRiskParagraphs(task) {
  return taskResultRiskParagraphs(task)
}

function resultReviewPoints(task) {
  return taskResultReviewPoints(task)
}

function resultOutputPreview(task) {
  return taskResultOutputPreview(task)
}

function formatJson(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value || "")
  }
}
</script>

<style scoped>
.gw-admin-task-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) repeat(3, minmax(0, 0.62fr));
  gap: 14px;
  margin-bottom: 16px;
}

.gw-admin-task-overview__hero,
.gw-admin-task-overview__stat,
.gw-admin-task-panel,
.gw-admin-task-detail,
.gw-admin-task-card {
  border: 1px solid rgba(30, 91, 223, 0.12);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 255, 0.94));
  box-shadow: 0 16px 30px rgba(30, 91, 223, 0.08);
}

.gw-admin-task-overview__hero {
  padding: 20px 22px;
  display: grid;
  gap: 8px;
}

.gw-admin-task-overview__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6c87ac;
}

.gw-admin-task-overview__hero h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.1;
  color: #1f3555;
}

.gw-admin-task-overview__hero p {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #607894;
}

.gw-admin-task-overview__stat {
  padding: 18px 18px 16px;
  display: grid;
  gap: 6px;
}

.gw-admin-task-overview__stat span {
  font-size: 12px;
  color: #6d84a2;
}

.gw-admin-task-overview__stat strong {
  font-size: 24px;
  line-height: 1.08;
  color: #1e5bdf;
}

.gw-admin-task-overview__stat em {
  font-style: normal;
  font-size: 12px;
  line-height: 1.6;
  color: #68809d;
}

.gw-admin-task-panel,
.gw-admin-task-detail {
  padding: 20px;
}

.gw-admin-task-filters {
  margin-bottom: 18px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid rgba(30, 91, 223, 0.12);
  background: #fff;
}

.gw-admin-task-input {
  width: 100%;
  min-height: 40px;
  border: 1px solid rgba(30, 91, 223, 0.14);
  border-radius: 12px;
  padding: 0 12px;
  font-size: 13px;
  color: #21416a;
  background: #fff;
}

.gw-admin-task-input:focus {
  outline: none;
  border-color: #1e5bdf;
  box-shadow: 0 0 0 3px rgba(30, 91, 223, 0.12);
}

.gw-admin-task-table-shell {
  margin-top: 0;
}

.gw-admin-task-table :deep(th) {
  white-space: nowrap;
}

.gw-admin-task-mobile-list {
  display: none;
  margin-top: 18px;
}

.gw-admin-task-card {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.gw-admin-task-card + .gw-admin-task-card {
  margin-top: 12px;
}

.gw-admin-task-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.gw-admin-task-card__eyebrow {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6b85a8;
}

.gw-admin-task-card__title {
  display: block;
  margin-top: 6px;
  font-size: 16px;
  line-height: 1.5;
  color: #1f3555;
}

.gw-admin-task-card__sub {
  margin-top: 4px;
  font-size: 13px;
  color: #607894;
}

.gw-admin-task-card__grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.gw-admin-task-card__grid div {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(30, 91, 223, 0.1);
  background: #fff;
}

.gw-admin-task-card__grid span {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6c85a8;
}

.gw-admin-task-card__grid strong {
  font-size: 13px;
  line-height: 1.6;
  color: #1f3555;
  word-break: break-word;
}

.gw-admin-task-card__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 980px) {
  .gw-admin-task-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .gw-admin-task-overview__hero {
    grid-column: 1 / -1;
  }
}

@media (max-width: 768px) {
  .gw-admin-task-overview {
    grid-template-columns: 1fr;
  }

  .gw-admin-task-panel,
  .gw-admin-task-detail {
    padding: 14px;
  }

  .gw-admin-task-table-shell {
    display: none;
  }

  .gw-admin-task-mobile-list {
    display: block;
  }

  .gw-admin-task-card__grid {
    grid-template-columns: 1fr;
  }
}
</style>
