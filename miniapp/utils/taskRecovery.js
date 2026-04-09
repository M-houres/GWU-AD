const { request } = require("./request")

function normalizeText(value) {
  return String(value || "").trim().toLowerCase()
}

function normalizeFilename(value) {
  const normalized = String(value || "").trim().replace(/\\/g, "/")
  const parts = normalized.split("/")
  return normalizeText(parts[parts.length - 1] || "")
}

function deriveTitleFromFilename(filename) {
  return normalizeFilename(filename).replace(/\.[^.]+$/, "")
}

function parseTimestamp(value) {
  const timestamp = Date.parse(String(value || ""))
  return Number.isFinite(timestamp) ? timestamp : null
}

function hasLooseMatch(left, right) {
  if (!left || !right) return false
  return left.includes(right) || right.includes(left)
}

function scoreCreatedAt(createdAt, submittedAt) {
  if (!Number.isFinite(createdAt) || !Number.isFinite(submittedAt)) return 0
  const delta = Math.abs(createdAt - submittedAt)
  if (delta <= 15 * 1000) return 8
  if (delta <= 60 * 1000) return 6
  if (delta <= 3 * 60 * 1000) return 4
  if (delta <= 10 * 60 * 1000) return 2
  return 0
}

function scoreCandidate(task, matcher, submittedAt, createdAt) {
  let score = 0
  const taskTitle = normalizeText(task && task.result_json ? task.result_json.paper_title : "")
  const taskAuthors = normalizeText(task && task.result_json ? task.result_json.authors : "")
  const sourceFilename = normalizeFilename(task && task.source_filename)

  if (matcher.paperTitle && taskTitle === matcher.paperTitle) {
    score += 12
  } else if (matcher.paperTitle && hasLooseMatch(taskTitle, matcher.paperTitle)) {
    score += 7
  }

  if (matcher.sourceFilename && sourceFilename === matcher.sourceFilename) {
    score += 10
  } else if (matcher.sourceFilename && hasLooseMatch(sourceFilename, matcher.sourceFilename)) {
    score += 5
  }

  if (matcher.derivedTitle && taskTitle === matcher.derivedTitle) {
    score += 4
  } else if (matcher.derivedTitle && hasLooseMatch(taskTitle, matcher.derivedTitle)) {
    score += 2
  }

  if (matcher.authors && taskAuthors === matcher.authors) {
    score += 6
  } else if (matcher.authors && hasLooseMatch(taskAuthors, matcher.authors)) {
    score += 3
  }

  score += scoreCreatedAt(createdAt, submittedAt)
  return score
}

function isTaskSubmitRecoverableError(error) {
  const message = normalizeText((error && error.message) || (error && error.errMsg) || "")
  return (
    !!(error && (error.isNetworkError || error.isTimeout || error.isResponseParseError)) ||
    /timeout|network|connection|closed|reset|abort|未收到有效响应|响应格式异常/.test(message)
  )
}

function getTaskRecordLabel(taskType) {
  if (taskType === "aigc_detect") return "检测"
  if (taskType === "rewrite") return "降AIGC"
  if (taskType === "dedup") return "降重"
  return "任务"
}

function getTaskSubmitFallbackMessage(error, taskType) {
  const recordLabel = getTaskRecordLabel(taskType)
  if (error && error.isTimeout) {
    return `提交耗时较长，请稍后到${recordLabel}记录页确认任务是否已创建`
  }
  if (isTaskSubmitRecoverableError(error)) {
    return `提交未收到有效响应，请检查网络或后端服务；也可到${recordLabel}记录页查看任务是否已创建`
  }
  return String((error && error.message) || "").trim() || "提交失败，请稍后重试"
}

async function fetchRecentTasks(taskType) {
  const pageSize = 50
  const maxPages = 6
  let page = 1
  let totalPages = 1
  const items = []

  while (page <= totalPages && page <= maxPages) {
    const data = await request({
      url: `/tasks/my?page=${page}&page_size=${pageSize}&task_type=${encodeURIComponent(taskType)}`,
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

async function recoverSubmittedTask({
  taskType,
  paperTitle,
  authors,
  sourceFilename,
  submittedAt = Date.now(),
}) {
  if (!taskType) return null

  const matcher = {
    paperTitle: normalizeText(paperTitle),
    authors: normalizeText(authors),
    sourceFilename: normalizeFilename(sourceFilename),
    derivedTitle: deriveTitleFromFilename(sourceFilename),
  }

  try {
    const items = await fetchRecentTasks(taskType)
    const windowStart = submittedAt - 10 * 60 * 1000
    const windowEnd = Date.now() + 2 * 60 * 1000

    const recentCandidates = items
      .map((task) => ({ task, createdAt: parseTimestamp(task && task.created_at) }))
      .filter((item) => item.createdAt !== null && item.createdAt >= windowStart && item.createdAt <= windowEnd)
      .map((item) => ({
        task: item.task,
        createdAt: item.createdAt,
        score: scoreCandidate(item.task, matcher, submittedAt, item.createdAt),
      }))
      .filter((item) => item.score >= 6)
      .sort((left, right) => right.score - left.score || right.createdAt - left.createdAt)

    if (recentCandidates.length > 0 && recentCandidates[0].score >= 10) {
      return recentCandidates[0].task
    }

    const nearTasks = items
      .map((task) => ({ task, createdAt: parseTimestamp(task && task.created_at) }))
      .filter((item) => item.createdAt !== null)
      .filter((item) => Math.abs(item.createdAt - submittedAt) <= 45 * 1000)
      .sort(
        (left, right) =>
          Math.abs(left.createdAt - submittedAt) - Math.abs(right.createdAt - submittedAt) ||
          right.createdAt - left.createdAt
      )

    if (recentCandidates.length > 0 && nearTasks.length <= 2) {
      return recentCandidates[0].task
    }

    if (nearTasks.length === 1) {
      return nearTasks[0].task
    }
  } catch (error) {
    console.warn("miniapp_recover_submitted_task_failed", error)
  }

  return null
}

module.exports = {
  isTaskSubmitRecoverableError,
  recoverSubmittedTask,
  getTaskSubmitFallbackMessage,
}
