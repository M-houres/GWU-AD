const PROCESSING_STATUSES = new Set(["pending", "preprocessing", "queued", "running"])

export function normalizeTaskStatus(status) {
  return String(status || "").trim().toLowerCase()
}

export function isTaskProcessingStatus(status) {
  return PROCESSING_STATUSES.has(normalizeTaskStatus(status))
}

export function mapTaskStatus(status) {
  const key = normalizeTaskStatus(status)
  return {
    pending: "等待中",
    preprocessing: "预处理中",
    queued: "排队中",
    running: "处理中",
    completed: "已完成",
    failed: "失败",
  }[key] || status
}

export function taskStatusClass(status) {
  const key = normalizeTaskStatus(status)
  if (key === "completed") return "success"
  if (key === "failed") return "danger"
  if (key === "running") return "info"
  return "warn"
}
