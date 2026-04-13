import { fetchAllUserTasks } from "./userRecords"

function sleep(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

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
  if (!Number.isFinite(createdAt) || !Number.isFinite(submittedAt)) {
    return 0
  }
  const delta = Math.abs(createdAt - submittedAt)
  if (delta <= 15 * 1000) return 8
  if (delta <= 60 * 1000) return 6
  if (delta <= 3 * 60 * 1000) return 4
  if (delta <= 10 * 60 * 1000) return 2
  return 0
}

function scoreCandidate(task, matcher, submittedAt, createdAt) {
  let score = 0
  const taskTitle = normalizeText(task?.result_json?.paper_title)
  const taskAuthors = normalizeText(task?.result_json?.authors)
  const sourceFilename = normalizeFilename(task?.source_filename)

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

export function isTaskSubmitTimeoutError(error) {
  const message = String(error?.message || "").trim()
  const code = String(error?.code || "").trim()
  return (
    /timeout|timed out|exceeded/i.test(message) ||
    code === "ECONNABORTED" ||
    code === "ETIMEDOUT"
  )
}

export function isTaskSubmitNetworkError(error) {
  const message = String(error?.message || "").trim()
  const code = String(error?.code || "").trim().toUpperCase()
  const status = Number(error?.response?.status || 0)
  return (
    /network error|failed to fetch|fetch failed|load failed|err_network|connection closed|empty response|socket hang up/i.test(
      message
    ) ||
    [
      "ERR_NETWORK",
      "ERR_CONNECTION_CLOSED",
      "ERR_CONNECTION_RESET",
      "ERR_EMPTY_RESPONSE",
    ].includes(code) ||
    (!error?.response && Boolean(error?.request)) ||
    [502, 503, 504, 520, 522, 524].includes(status)
  )
}

export async function recoverSubmittedTask({
  taskType,
  paperTitle,
  authors,
  sourceFilename,
  submittedAt = Date.now(),
  attempts = 3,
  retryDelayMs = 900,
}) {
  if (!taskType) {
    return null
  }

  const matcher = {
    paperTitle: normalizeText(paperTitle),
    authors: normalizeText(authors),
    sourceFilename: normalizeFilename(sourceFilename),
    derivedTitle: deriveTitleFromFilename(sourceFilename),
  }

  for (let attempt = 0; attempt < Math.max(1, attempts); attempt += 1) {
    try {
      const items = await fetchAllUserTasks(
        { task_type: taskType },
        { pageSize: 100, maxPages: 10 }
      )
      const windowStart = submittedAt - 10 * 60 * 1000
      const windowEnd = Date.now() + 2 * 60 * 1000

      const recentCandidates = items
        .map((task) => ({ task, createdAt: parseTimestamp(task?.created_at) }))
        .filter((item) => item.createdAt !== null && item.createdAt >= windowStart && item.createdAt <= windowEnd)
        .map((item) => ({ ...item, score: scoreCandidate(item.task, matcher, submittedAt, item.createdAt) }))
        .filter((item) => item.score >= 6)
        .sort((left, right) => right.score - left.score || right.createdAt - left.createdAt)

      if (recentCandidates.length > 0 && recentCandidates[0].score >= 10) {
        return recentCandidates[0].task
      }

      const nearTasks = items
        .map((task) => ({ task, createdAt: parseTimestamp(task?.created_at) }))
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
      console.warn("recover_submitted_task_failed", error)
    }

    if (attempt < attempts - 1) {
      await sleep(retryDelayMs)
    }
  }

  return null
}
