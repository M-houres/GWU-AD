const TASK_PLATFORM_LABELS = Object.freeze({
  cnki: "仿知网",
  vip: "仿维普",
  paperpass: "仿PaperPass",
})

export const TASK_PLATFORM_OPTIONS = Object.freeze([
  { value: "cnki", label: TASK_PLATFORM_LABELS.cnki },
  { value: "vip", label: TASK_PLATFORM_LABELS.vip },
  { value: "paperpass", label: TASK_PLATFORM_LABELS.paperpass },
])

export function mapTaskPlatform(platform) {
  const key = String(platform || "").trim().toLowerCase()
  return TASK_PLATFORM_LABELS[key] || platform || "-"
}
