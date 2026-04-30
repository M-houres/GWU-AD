const { request, downloadFile } = require("../../utils/request")
const { ensureLogin } = require("../../utils/auth")
const { requireAuth, getPendingAuth, clearPendingAuth } = require("../../utils/authFlow")
const { getTaskStatusText, toFriendlyError } = require("../../utils/status")
const {
  getTaskTypeLabel,
  getPlatformLabel,
  getTaskStatusTone,
  formatDateTime,
} = require("../../utils/display")

function buildFilterOptions(records = []) {
  const summary = {
    all: records.length,
    active: records.filter((item) => ["pending", "running"].includes(String(item.status).toLowerCase())).length,
    completed: records.filter((item) => String(item.status).toLowerCase() === "completed").length,
    failed: records.filter((item) => ["failed", "closed"].includes(String(item.status).toLowerCase())).length,
  }

  return [
    { label: "全部", value: "all", count: summary.all },
    { label: "处理中", value: "active", count: summary.active },
    { label: "已完成", value: "completed", count: summary.completed },
    { label: "异常/关闭", value: "failed", count: summary.failed },
  ]
}

function filterRecords(records = [], currentFilter = "all") {
  if (currentFilter === "active") {
    return records.filter((item) => ["pending", "running"].includes(String(item.status).toLowerCase()))
  }
  if (currentFilter === "completed") {
    return records.filter((item) => String(item.status).toLowerCase() === "completed")
  }
  if (currentFilter === "failed") {
    return records.filter((item) => ["failed", "closed"].includes(String(item.status).toLowerCase()))
  }
  return records
}

function collectResultEntries(node, bucket = [], prefix = "") {
  if (!node || typeof node !== "object" || bucket.length >= 40) return bucket

  Object.keys(node).forEach((key) => {
    if (bucket.length >= 40) return
    const value = node[key]
    const path = prefix ? `${prefix}.${key}` : key

    if (value && typeof value === "object" && !Array.isArray(value)) {
      collectResultEntries(value, bucket, path)
      return
    }

    if (Array.isArray(value)) {
      if (value.length && ["string", "number", "boolean"].includes(typeof value[0])) {
        bucket.push({ key: path.toLowerCase(), value: value.join(", ") })
      }
      return
    }

    if (["string", "number", "boolean"].includes(typeof value)) {
      bucket.push({ key: path.toLowerCase(), value })
    }
  })

  return bucket
}

function formatMetricValue(metricKey, value) {
  if (value === null || value === undefined || value === "") return null
  if (typeof value === "boolean") return value ? "是" : "否"

  if (typeof value === "number") {
    const lowerKey = String(metricKey || "").toLowerCase()
    const shouldPercent =
      lowerKey.includes("rate") ||
      lowerKey.includes("ratio") ||
      lowerKey.includes("percent") ||
      lowerKey.includes("score") ||
      lowerKey.includes("probability")

    if (shouldPercent) {
      const percent = value <= 1 ? value * 100 : value
      const text = percent % 1 === 0 ? String(percent.toFixed(0)) : percent.toFixed(2)
      return `${text}%`
    }
    return String(value)
  }

  return String(value)
}

function pickMetric(entries, label, aliases = []) {
  const match = entries.find((item) => aliases.some((alias) => item.key.includes(alias)))
  if (!match) return null
  const value = formatMetricValue(match.key, match.value)
  return value ? { label, value } : null
}

function buildReportCards(task = {}) {
  const entries = collectResultEntries(task.result_json || {})
  const cards = [
    pickMetric(entries, "AIGC风险", ["aigc", "ai_rate", "ai_score", "ai_probability", "risk"]),
    pickMetric(entries, "总相似比", ["similarity", "duplicate", "duplication", "repeat", "ratio", "rate"]),
    pickMetric(entries, "自写率", ["original", "self_write", "selfwrite", "原创", "自写"]),
    pickMetric(entries, "命中片段", ["segment", "match_count", "hit_count", "片段"]),
  ].filter(Boolean)

  if (cards.length) return cards.slice(0, 4)

  return [
    { label: "平台", value: getPlatformLabel(task.platform) },
    { label: "字数", value: String(Number(task.char_count || 0)) },
    { label: "消耗积分", value: String(Number(task.cost_credits || 0)) },
    { label: "状态", value: getTaskStatusText(task.status) },
  ]
}

function stringifyResult(resultJson) {
  if (typeof resultJson === "string" && resultJson.trim()) return resultJson.trim()
  if (!resultJson || typeof resultJson !== "object") return "暂无结构化结果"

  try {
    return JSON.stringify(resultJson, null, 2).slice(0, 2200)
  } catch (_) {
    return "结果解析失败"
  }
}

async function fetchAllTasks() {
  const pageSize = 50
  const maxPages = 6
  let page = 1
  let totalPages = 1
  const items = []

  while (page <= totalPages && page <= maxPages) {
    const data = await request({
      url: `/tasks/my?page=${page}&page_size=${pageSize}`,
      method: "GET",
      silent: true,
    })
    const pageItems = Array.isArray(data && data.items) ? data.items : []
    items.push(...pageItems)

    const nextTotal = Number(data && data.pagination ? data.pagination.total_pages : 0)
    if (Number.isFinite(nextTotal) && nextTotal > 0) {
      totalPages = nextTotal
    } else if (pageItems.length < pageSize) {
      totalPages = page
    } else {
      totalPages = page + 1
    }
    page += 1
  }

  return items
}

Page({
  data: {
    guestMode: true,
    allRecords: [],
    records: [],
    loading: false,
    currentFilter: "all",
    filterOptions: buildFilterOptions([]),
    summary: {
      total: 0,
      completed: 0,
      active: 0,
      failed: 0,
    },
    expandedId: 0,
    expandedDetail: null,
    detailLoadingId: 0,
    downloadingId: 0,
  },

  onShow() {
    if (!ensureLogin()) {
      this.applyGuestState()
      return
    }
    this.setData({ guestMode: false })
    this.consumePendingAction()
    this.loadRecords()
  },

  onPullDownRefresh() {
    this.loadRecords().finally(() => wx.stopPullDownRefresh())
  },

  applyFilter(currentFilter = this.data.currentFilter, records = this.data.allRecords) {
    this.setData({
      currentFilter,
      records: filterRecords(records, currentFilter),
      filterOptions: buildFilterOptions(records),
    })
  },

  applyGuestState() {
    this.setData({
      guestMode: true,
      allRecords: [],
      records: [],
      currentFilter: "all",
      filterOptions: buildFilterOptions([]),
      summary: {
        total: 0,
        completed: 0,
        active: 0,
        failed: 0,
      },
      expandedId: 0,
      expandedDetail: null,
      detailLoadingId: 0,
      downloadingId: 0,
      loading: false,
    })
  },

  onTapGuestLogin() {
    requireAuth({ targetTab: "records", action: "open_records" })
  },

  consumePendingAction() {
    const pending = getPendingAuth()
    if (!pending || pending.targetTab !== "records") return
    clearPendingAuth()
    if (pending.action === "session_expired") {
      wx.showToast({ title: "登录状态已更新，请继续查看记录", icon: "none" })
    }
  },

  async expandTaskDetail(taskId) {
    if (!taskId) return

    this.setData({ expandedId: taskId, expandedDetail: null, detailLoadingId: taskId })
    try {
      const task = await request({
        url: `/tasks/${taskId}`,
        method: "GET",
        silent: true,
      })

      if (this.data.expandedId !== taskId) return

      this.setData({
        expandedDetail: {
          reportCards: buildReportCards(task),
          resultText: stringifyResult(task.result_json),
          errorMessage: task.error_message || "",
          statusText: getTaskStatusText(task.status),
        },
      })
    } catch (error) {
      wx.showToast({ title: toFriendlyError(error, "加载报告失败"), icon: "none" })
    } finally {
      if (this.data.detailLoadingId === taskId) {
        this.setData({ detailLoadingId: 0 })
      }
    }
  },

  async loadRecords() {
    if (!ensureLogin()) {
      this.applyGuestState()
      return
    }
    if (this.data.loading) return

    this.setData({ loading: true })
    try {
      const rawRecords = await fetchAllTasks()
      const records = rawRecords
        .map((item) => {
          const resultJson = item && item.result_json && typeof item.result_json === "object" ? item.result_json : {}
          return {
            ...item,
            taskTypeText: getTaskTypeLabel(item.task_type),
            platformText: getPlatformLabel(item.platform),
            statusText: getTaskStatusText(item.status),
            statusClass: getTaskStatusTone(item.status),
            createdAtText: formatDateTime(item.created_at),
            charCount: Number(item.char_count || 0),
            costCredits: Number(item.cost_credits || 0),
            sourceFilenameText: item.source_filename || "未命名文件",
            paperTitle: String(resultJson.paper_title || "").trim() || item.source_filename || "未命名篇名",
            authorsText: String(resultJson.authors || "").trim() || "作者未填写",
          }
        })
        .sort((left, right) => Number(right.id || 0) - Number(left.id || 0))

      const completed = records.filter((item) => String(item.status).toLowerCase() === "completed").length
      const active = records.filter((item) => {
        const status = String(item.status).toLowerCase()
        return status === "pending" || status === "running"
      }).length
      const failed = records.filter((item) => {
        const status = String(item.status).toLowerCase()
        return status === "failed" || status === "closed"
      }).length

      this.setData({
        allRecords: records,
        summary: {
          total: records.length,
          completed,
          active,
          failed,
        },
      })
      this.applyFilter(this.data.currentFilter, records)

    } catch (error) {
      wx.showToast({ title: toFriendlyError(error, "加载记录失败"), icon: "none" })
    } finally {
      this.setData({ loading: false })
    }
  },

  onChangeFilter(e) {
    const nextFilter = e.currentTarget.dataset.value || "all"
    this.applyFilter(nextFilter)
  },

  async onToggleDetail(e) {
    const taskId = Number(e.currentTarget.dataset.id || 0)
    if (!taskId) return

    if (this.data.expandedId === taskId) {
      this.setData({ expandedId: 0, expandedDetail: null })
      return
    }

    await this.expandTaskDetail(taskId)
  },

  async onTapDownload(e) {
    const taskId = Number(e.currentTarget.dataset.id || 0)
    const status = String(e.currentTarget.dataset.status || "").toLowerCase()
    if (!taskId) return
    if (this.data.downloadingId) return
    if (status !== "completed") {
      wx.showToast({ title: "任务未完成，暂不可下载", icon: "none" })
      return
    }

    this.setData({ downloadingId: taskId })
    try {
      const tempFilePath = await downloadFile({
        url: `/tasks/${taskId}/download`,
      })
      wx.openDocument({
        filePath: tempFilePath,
        showMenu: true,
        fail: () => wx.showToast({ title: "文件打开失败", icon: "none" }),
      })
    } catch (error) {
      wx.showToast({ title: toFriendlyError(error, "下载失败"), icon: "none" })
    } finally {
      this.setData({ downloadingId: 0 })
    }
  },
})
