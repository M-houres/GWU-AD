<template>
  <AdminShell title="后台总览" subtitle="每 30 秒自动刷新一次，关注任务、收入与模式状态。">
    <section
      v-if="switchStatus.current_mode === 'ALGO_ONLY'"
      class="scholar-note scholar-note--danger dashboard-alert"
    >
      <div class="dashboard-alert__text">当前系统处于算法降级模式，原因：{{ switchStatus.last_switch_reason || "大模型异常" }}。</div>
      <button class="scholar-button scholar-button--danger" type="button" @click="recoverMode">手动恢复大模型模式</button>
    </section>

    <section class="scholar-grid scholar-grid--stats">
      <article class="scholar-stat" v-for="item in statCards" :key="item.label">
        <div class="scholar-stat__label">{{ item.label }}</div>
        <div class="scholar-stat__value">{{ item.value }}</div>
        <div class="scholar-stat__hint">{{ item.hint }}</div>
      </article>
    </section>

    <section class="scholar-grid md:grid-cols-3" style="margin-top: 14px">
      <article class="scholar-stat" v-for="item in sourceCards" :key="item.label">
        <div class="scholar-stat__label">{{ item.label }}</div>
        <div class="scholar-stat__value">{{ item.value }}</div>
        <div class="scholar-stat__hint">{{ item.hint }}</div>
      </article>
    </section>

    <section class="scholar-grid dashboard-ops-grid" style="margin-top: 14px">
      <article class="scholar-chart-card dashboard-chart-card">
        <div class="dashboard-chart-head">
          <div>
            <div class="scholar-kicker">MVP Baseline</div>
            <h3 class="scholar-subtitle">后台运营基线状态</h3>
          </div>
          <span class="dashboard-chip" :class="`dashboard-chip--${baselineStatus.status}`">{{ baselineStatus.label }}</span>
        </div>
        <p class="dashboard-section-lead">{{ baselineLead }}</p>
        <div class="dashboard-baseline-list">
          <article v-for="item in baselineItems" :key="item.key" class="dashboard-baseline-item">
            <div class="dashboard-baseline-item__head">
              <strong>{{ item.label }}</strong>
              <span class="dashboard-chip" :class="`dashboard-chip--${item.status}`">{{ statusLabel(item.status) }}</span>
            </div>
            <p>{{ item.message }}</p>
          </article>
        </div>
      </article>

      <article class="scholar-chart-card dashboard-chart-card">
        <div class="dashboard-chart-head">
          <div>
            <div class="scholar-kicker">Ops Alerts</div>
            <h3 class="scholar-subtitle">待处理事项</h3>
          </div>
          <span class="dashboard-chip dashboard-chip--neutral">{{ opsAlertCount }} 项</span>
        </div>
        <div v-if="operationalAlerts.length" class="dashboard-alert-list">
          <article v-for="item in operationalAlerts" :key="item.key" class="dashboard-alert-item" :class="`dashboard-alert-item--${item.level}`">
            <strong>{{ item.level === 'error' ? '高优先级' : '提醒' }}</strong>
            <p>{{ item.message }}</p>
          </article>
        </div>
        <div v-else class="dashboard-empty-note">当前没有待处理异常，后台主链路可继续运行。</div>

        <div class="dashboard-ops-metrics">
          <article v-for="item in opsMetrics" :key="item.label" class="dashboard-ops-metric">
            <div class="dashboard-ops-metric__label">{{ item.label }}</div>
            <div class="dashboard-ops-metric__value">{{ item.value }}</div>
            <div class="dashboard-ops-metric__hint">{{ item.hint }}</div>
          </article>
        </div>
      </article>
    </section>

    <section class="scholar-hero-grid dashboard-grid">
      <article class="scholar-chart-card dashboard-chart-card">
        <div class="dashboard-chart-head">
          <div>
            <div class="scholar-kicker">Task Trend</div>
            <h3 class="scholar-subtitle">近 7 天任务趋势</h3>
          </div>
          <button class="scholar-button scholar-button--secondary" type="button" @click="loadData">刷新</button>
        </div>
        <div ref="taskChartEl" class="mt-4 h-72 w-full dashboard-chart-area"></div>
      </article>

      <article class="scholar-chart-card dashboard-chart-card">
        <div class="dashboard-chart-head">
          <div>
            <div class="scholar-kicker">Revenue Trend</div>
            <h3 class="scholar-subtitle">近 7 天收入趋势</h3>
          </div>
          <button class="scholar-button scholar-button--secondary" type="button" @click="loadData">刷新</button>
        </div>
        <div ref="revenueChartEl" class="mt-4 h-72 w-full dashboard-chart-area"></div>
      </article>
    </section>

    <section class="scholar-grid scholar-grid--halves">
      <article class="scholar-chart-card dashboard-chart-card">
        <div class="scholar-kicker">Usage Distribution</div>
        <h3 class="scholar-subtitle">功能使用占比</h3>
        <div ref="taskTypeChartEl" class="mt-4 h-60 w-full dashboard-chart-area dashboard-chart-area--short"></div>
      </article>

      <article class="scholar-chart-card dashboard-chart-card">
        <div class="scholar-kicker">Platform Distribution</div>
        <h3 class="scholar-subtitle">平台使用量对比</h3>
        <div ref="platformChartEl" class="mt-4 h-60 w-full dashboard-chart-area dashboard-chart-area--short"></div>
      </article>
    </section>

    <section class="scholar-chart-card dashboard-chart-card">
      <div class="scholar-kicker">Conversion Funnel</div>
      <h3 class="scholar-subtitle">用户转化对比</h3>
      <div ref="funnelChartEl" class="mt-4 h-56 w-full dashboard-chart-area dashboard-chart-area--compact"></div>
    </section>
  </AdminShell>
</template>

<script setup>
import * as echarts from "echarts/core"
import { BarChart, LineChart } from "echarts/charts"
import { GridComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

echarts.use([LineChart, BarChart, TooltipComponent, GridComponent, CanvasRenderer])

const dashboard = ref(null)
const taskChartEl = ref(null)
const revenueChartEl = ref(null)
const taskTypeChartEl = ref(null)
const platformChartEl = ref(null)
const funnelChartEl = ref(null)

let timer = null
let taskChart = null
let revenueChart = null
let taskTypeChart = null
let platformChart = null
let funnelChart = null

const statCards = computed(() => {
  const overview = dashboard.value?.overview || {}
  const totalUsers = typeof overview.total_users === "number" ? overview.total_users : 0
  const totalTasks = typeof overview.total_tasks === "number" ? overview.total_tasks : 0
  const totalOrders = typeof overview.total_orders === "number" ? overview.total_orders : 0
  const totalRevenue = typeof overview.total_revenue === "number" ? overview.total_revenue : 0
  return [
    { label: "累计用户", value: formatNumber(totalUsers), hint: "注册用户总量" },
    { label: "累计任务", value: formatNumber(totalTasks), hint: "含检测、降重、降AIGC率" },
    { label: "支付订单", value: formatNumber(totalOrders), hint: "已创建订单总数" },
    { label: "累计收入", value: `¥${formatNumber(totalRevenue)}`, hint: "订单支付后的累计金额" },
  ]
})

const switchStatus = computed(() => dashboard.value?.switch_status || {})
const sourceCards = computed(() => {
  const sourceStats = dashboard.value?.source_stats || {}
  const taskStats = sourceStats.tasks || {}
  const orderStats = sourceStats.paid_orders || {}
  const revenueStats = sourceStats.revenue || {}
  return [
    {
      label: "Web 来源任务",
      value: formatNumber(taskStats.web || 0),
      hint: `支付单 ${formatNumber(orderStats.web || 0)} / 收入 ¥${formatNumber(revenueStats.web || 0)}`,
    },
    {
      label: "小程序来源任务",
      value: formatNumber(taskStats.miniapp || 0),
      hint: `支付单 ${formatNumber(orderStats.miniapp || 0)} / 收入 ¥${formatNumber(revenueStats.miniapp || 0)}`,
    },
    {
      label: "其他来源任务",
      value: formatNumber(taskStats.other || 0),
      hint: `支付单 ${formatNumber(orderStats.other || 0)} / 收入 ¥${formatNumber(revenueStats.other || 0)}`,
    },
  ]
})
const baselineItems = computed(() => dashboard.value?.mvp_baseline?.items || [])
const operationalAlerts = computed(() => dashboard.value?.operational_alerts || [])
const opsSummary = computed(() => dashboard.value?.ops_summary || {})
const opsAlertCount = computed(() => operationalAlerts.value.length)
const baselineStatus = computed(() => {
  const status = dashboard.value?.mvp_baseline?.status || "warning"
  return { status, label: statusLabel(status) }
})
const baselineLead = computed(() => {
  const reasons = dashboard.value?.mvp_baseline?.reasons || []
  if (!reasons.length) {
    return "当前后台六个 MVP 入口已具备可运行基线，可继续做日常运营与验收。"
  }
  return `当前需关注：${reasons.join("；")}`
})
const opsMetrics = computed(() => {
  const taskStatus = opsSummary.value.task_status || {}
  return [
    {
      label: "失败任务",
      value: formatNumber(taskStatus.failed || 0),
      hint: "需要复核失败原因",
    },
    {
      label: "待退款任务",
      value: formatNumber(opsSummary.value.refund_pending_count || 0),
      hint: "失败后尚未完成退款",
    },
    {
      label: "近24h LLM异常",
      value: formatNumber(opsSummary.value.llm_error_24h || 0),
      hint: "用于判断是否频繁降级",
    },
    {
      label: "已支付订单",
      value: formatNumber(opsSummary.value.paid_order_count || 0),
      hint: "当前累计已支付订单数",
    },
  ]
})
const trendRows = computed(() => {
  const rows = dashboard.value?.trend_30d || []
  return rows.slice(-7)
})

watch(
  dashboard,
  async () => {
    await nextTick()
    renderCharts()
  },
  { deep: true }
)

onMounted(async () => {
  await loadData()
  timer = setInterval(loadData, 30000)
  window.addEventListener("resize", handleResize)
})

onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
  window.removeEventListener("resize", handleResize)
  disposeCharts()
})

async function loadData() {
  dashboard.value = await adminHttp.get("/admin/dashboard")
}

async function recoverMode() {
  if (!adminHasPermission("system:manage")) {
    window.alert("当前账号没有系统模式切换权限")
    return
  }
  const confirmed = window.confirm("确认切换回大模型 + 算法模式吗？")
  if (!confirmed) {
    return
  }
  await adminHttp.post("/admin/switch/mode", { mode: "LLM_PLUS_ALGO" })
  await loadData()
}

function initChart(el, chartRef) {
  if (!el) {
    return null
  }
  if (chartRef) {
    return chartRef
  }
  return echarts.init(el)
}

function formatNumber(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return "0"
  return num.toLocaleString("zh-CN")
}

function statusLabel(status) {
  if (status === "ready") return "已就绪"
  if (status === "error") return "未就绪"
  if (status === "warning") return "待确认"
  return "待确认"
}

function baseAxisStyle() {
  return {
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { lineStyle: { color: "rgba(107, 119, 130, 0.12)" } },
    axisLabel: { color: "#6a7782" },
  }
}

function renderCharts() {
  const rows = trendRows.value
  const dates = rows.map((r) => r.date.slice(5))
  const taskSeries = rows.map((r) => r.tasks)
  const revenueSeries = rows.map((r) => r.revenue)
  const taskTypeDist = dashboard.value?.task_type_dist || []
  const platformDist = dashboard.value?.platform_dist || []
  const funnel = dashboard.value?.funnel || {}

  taskChart = initChart(taskChartEl.value, taskChart)
  revenueChart = initChart(revenueChartEl.value, revenueChart)
  taskTypeChart = initChart(taskTypeChartEl.value, taskTypeChart)
  platformChart = initChart(platformChartEl.value, platformChart)
  funnelChart = initChart(funnelChartEl.value, funnelChart)

  if (taskChart) {
    taskChart.setOption({
      grid: { left: 36, right: 16, top: 16, bottom: 28 },
      xAxis: { type: "category", data: dates, ...baseAxisStyle(), splitLine: { show: false } },
      yAxis: { type: "value", ...baseAxisStyle() },
      tooltip: { trigger: "axis" },
      series: [
        {
          type: "line",
          smooth: true,
          data: taskSeries,
          areaStyle: { color: "rgba(23, 74, 82, 0.14)" },
          lineStyle: { width: 3, color: "#174a52" },
          symbol: "circle",
          symbolSize: 8,
          itemStyle: { color: "#174a52" },
        },
      ],
    })
  }
  if (revenueChart) {
    revenueChart.setOption({
      grid: { left: 36, right: 16, top: 16, bottom: 28 },
      xAxis: { type: "category", data: dates, ...baseAxisStyle(), splitLine: { show: false } },
      yAxis: { type: "value", ...baseAxisStyle() },
      tooltip: { trigger: "axis" },
      series: [
        {
          type: "line",
          smooth: true,
          data: revenueSeries,
          areaStyle: { color: "rgba(138, 100, 53, 0.16)" },
          lineStyle: { width: 3, color: "#8a6435" },
          symbol: "circle",
          symbolSize: 8,
          itemStyle: { color: "#8a6435" },
        },
      ],
    })
  }
  if (taskTypeChart) {
    taskTypeChart.setOption({
      grid: { left: 72, right: 16, top: 12, bottom: 24 },
      xAxis: { type: "value", ...baseAxisStyle() },
      yAxis: {
        type: "category",
        data: taskTypeDist.map((r) => r.task_type),
        ...baseAxisStyle(),
        splitLine: { show: false },
      },
      tooltip: { trigger: "axis" },
      series: [
        {
          type: "bar",
          data: taskTypeDist.map((r) => r.count),
          itemStyle: { color: "#174a52", borderRadius: [0, 8, 8, 0] },
          barWidth: 18,
        },
      ],
    })
  }
  if (platformChart) {
    platformChart.setOption({
      grid: { left: 36, right: 16, top: 12, bottom: 28 },
      xAxis: { type: "category", data: platformDist.map((r) => r.platform), ...baseAxisStyle(), splitLine: { show: false } },
      yAxis: { type: "value", ...baseAxisStyle() },
      tooltip: { trigger: "axis" },
      series: [
        {
          type: "bar",
          data: platformDist.map((r) => r.count),
          itemStyle: { color: "#4e7283", borderRadius: [8, 8, 0, 0] },
          barWidth: 34,
        },
      ],
    })
  }
  if (funnelChart) {
    const visitors = funnel.visitors || 0
    const registered = funnel.registered || 0
    const paidUsers = funnel.paid_users || 0
    const taskUsers = funnel.task_users || 0
    funnelChart.setOption({
      grid: { left: 70, right: 16, top: 12, bottom: 24 },
      xAxis: { type: "value", ...baseAxisStyle() },
      yAxis: {
        type: "category",
        data: ["访问用户", "注册用户", "支付用户", "任务用户"],
        ...baseAxisStyle(),
        splitLine: { show: false },
      },
      tooltip: { trigger: "axis" },
      series: [
        {
          type: "bar",
          data: [visitors, registered, paidUsers, taskUsers],
          itemStyle: { color: "#8a6435", borderRadius: [0, 8, 8, 0] },
          barWidth: 20,
        },
      ],
    })
  }
}

function handleResize() {
  if (taskChart) taskChart.resize()
  if (revenueChart) revenueChart.resize()
  if (taskTypeChart) taskTypeChart.resize()
  if (platformChart) platformChart.resize()
  if (funnelChart) funnelChart.resize()
}

function disposeCharts() {
  if (taskChart) taskChart.dispose()
  if (revenueChart) revenueChart.dispose()
  if (taskTypeChart) taskTypeChart.dispose()
  if (platformChart) platformChart.dispose()
  if (funnelChart) funnelChart.dispose()
  taskChart = null
  revenueChart = null
  taskTypeChart = null
  platformChart = null
  funnelChart = null
}
</script>

<style scoped>
.dashboard-alert {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.dashboard-alert__text {
  min-width: 0;
  flex: 1;
}

.dashboard-chart-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.dashboard-ops-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dashboard-chip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 74px;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12px;
  line-height: 1;
  background: #eef2f5;
  color: #5e6c78;
}

.dashboard-chip--ready {
  background: #e8f5ef;
  color: #106c4f;
}

.dashboard-chip--warning {
  background: #fff5df;
  color: #946200;
}

.dashboard-chip--error {
  background: #fff0ee;
  color: #b24439;
}

.dashboard-chip--neutral {
  background: #eef2f5;
  color: #5e6c78;
}

.dashboard-section-lead {
  margin-top: 12px;
  color: #51606b;
  line-height: 1.7;
}

.dashboard-baseline-list,
.dashboard-alert-list {
  margin-top: 16px;
  display: grid;
  gap: 12px;
}

.dashboard-baseline-item,
.dashboard-alert-item,
.dashboard-ops-metric {
  border: 1px solid #dde5eb;
  border-radius: 18px;
  background: #fbfcfd;
  padding: 14px;
}

.dashboard-baseline-item__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.dashboard-baseline-item p,
.dashboard-alert-item p {
  margin-top: 8px;
  color: #51606b;
  line-height: 1.7;
}

.dashboard-alert-item--error {
  border-color: #f1d0cb;
  background: #fff6f3;
}

.dashboard-alert-item--warning {
  border-color: #f1e0bf;
  background: #fffaf0;
}

.dashboard-empty-note {
  margin-top: 16px;
  border: 1px dashed #d8e0e7;
  border-radius: 18px;
  background: #fbfcfd;
  padding: 18px;
  color: #5e6c78;
}

.dashboard-ops-metrics {
  margin-top: 16px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.dashboard-ops-metric__label {
  font-size: 12px;
  color: #6b7884;
}

.dashboard-ops-metric__value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 600;
  color: #16222a;
}

.dashboard-ops-metric__hint {
  margin-top: 6px;
  font-size: 13px;
  color: #5d6973;
  line-height: 1.6;
}

@media (max-width: 768px) {
  .dashboard-alert {
    align-items: stretch;
  }

  .dashboard-alert .scholar-button,
  .dashboard-chart-head .scholar-button {
    width: 100%;
  }

  .dashboard-chart-head {
    flex-direction: column;
  }

  .dashboard-ops-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-ops-metrics {
    grid-template-columns: 1fr;
  }

  .dashboard-chart-area {
    height: 260px !important;
  }

  .dashboard-chart-area--short {
    height: 220px !important;
  }

  .dashboard-chart-area--compact {
    height: 200px !important;
  }
}
</style>
