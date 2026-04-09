const TASK_PLATFORM_LABELS = Object.freeze({
  cnki: "知网",
  vip: "维普",
  paperpass: "PaperPass",
})

const AIGC_PLATFORM_LABELS = Object.freeze({
  cnki: "模拟知网",
  vip: "模拟维普",
  paperpass: "模拟PaperPass",
})

const AIGC_TASK_TYPES = new Set(["aigc_detect"])

export const TASK_PLATFORM_OPTIONS = Object.freeze([
  { value: "cnki", label: TASK_PLATFORM_LABELS.cnki },
  { value: "vip", label: TASK_PLATFORM_LABELS.vip },
  { value: "paperpass", label: TASK_PLATFORM_LABELS.paperpass },
])

export const AIGC_PLATFORM_OPTIONS = Object.freeze([
  { value: "cnki", label: AIGC_PLATFORM_LABELS.cnki },
  { value: "vip", label: AIGC_PLATFORM_LABELS.vip },
  { value: "paperpass", label: AIGC_PLATFORM_LABELS.paperpass },
])

function isAigcTaskType(taskType) {
  const key = String(taskType || "").trim().toLowerCase()
  return AIGC_TASK_TYPES.has(key)
}

export function mapTaskPlatform(platform, taskType) {
  const key = String(platform || "").trim().toLowerCase()
  const labels = isAigcTaskType(taskType) ? AIGC_PLATFORM_LABELS : TASK_PLATFORM_LABELS
  return labels[key] || platform || "-"
}
