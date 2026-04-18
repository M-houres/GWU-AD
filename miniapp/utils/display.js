function normalizeKey(value) {
  return String(value || "").trim().toLowerCase()
}

const TASK_TYPE_LABELS = {
  rewrite: "降AIGC",
  dedup: "降重复率",
  aigc_detect: "AIGC 检测",
}

const PLATFORM_LABELS = {
  cnki: "知网",
  vip: "维普",
}

function getTaskTypeLabel(value) {
  const key = normalizeKey(value)
  return TASK_TYPE_LABELS[key] || String(value || "-")
}

function getPlatformLabel(value) {
  const key = normalizeKey(value)
  return PLATFORM_LABELS[key] || String(value || "-")
}

function getTaskStatusTone(status) {
  const key = normalizeKey(status)
  if (key === "pending") return "status-pending"
  if (key === "running") return "status-running"
  if (key === "completed") return "status-completed"
  if (key === "failed") return "status-failed"
  return "status-closed"
}

function getOrderStatusTone(status) {
  const key = normalizeKey(status)
  if (key === "created") return "status-pending"
  if (key === "paid") return "status-completed"
  if (key === "refunded") return "status-running"
  return "status-closed"
}

function pad(value) {
  const number = Number(value || 0)
  return number < 10 ? `0${number}` : String(number)
}

function formatDateTime(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

module.exports = {
  getTaskTypeLabel,
  getPlatformLabel,
  getTaskStatusTone,
  getOrderStatusTone,
  formatDateTime,
}
