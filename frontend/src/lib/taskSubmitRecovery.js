import { fetchAllUserTasks } from "./userRecords"

function normalizeText(value) {
  return String(value || "").trim().toLowerCase()
}

function parseTimestamp(value) {
  const timestamp = Date.parse(String(value || ""))
  return Number.isFinite(timestamp) ? timestamp : null
}

function scoreCandidate(task, matcher) {
  let score = 0
  const taskTitle = normalizeText(task?.result_json?.paper_title)
  const taskAuthors = normalizeText(task?.result_json?.authors)
  const sourceFilename = normalizeText(task?.source_filename)

  if (matcher.paperTitle && taskTitle === matcher.paperTitle) {
    score += 5
  }
  if (matcher.sourceFilename && sourceFilename === matcher.sourceFilename) {
    score += 4
  }
  if (matcher.authors && taskAuthors === matcher.authors) {
    score += 2
  }
  return score
}

export function isTaskSubmitTimeoutError(error) {
  const message = String(error?.message || "").trim()
  return /timeout|timed out|exceeded/i.test(message)
}

export function isTaskSubmitNetworkError(error) {
  const message = String(error?.message || "").trim()
  return /network error|failed to fetch|fetch failed|load failed|err_network/i.test(message)
}

export async function recoverSubmittedTask({
  taskType,
  paperTitle,
  authors,
  sourceFilename,
  submittedAt = Date.now(),
}) {
  if (!taskType) {
    return null
  }

  const matcher = {
    paperTitle: normalizeText(paperTitle),
    authors: normalizeText(authors),
    sourceFilename: normalizeText(sourceFilename),
  }

  try {
    const items = await fetchAllUserTasks(
      { task_type: taskType },
      { pageSize: 100, maxPages: 6 }
    )
    const windowStart = submittedAt - 2 * 60 * 1000
    const windowEnd = Date.now() + 60 * 1000

    const recentCandidates = items
      .map((task) => ({ task, createdAt: parseTimestamp(task?.created_at) }))
      .filter((item) => item.createdAt !== null && item.createdAt >= windowStart && item.createdAt <= windowEnd)
      .map((item) => ({ ...item, score: scoreCandidate(item.task, matcher) }))
      .filter((item) => item.score > 0)
      .sort((left, right) => right.score - left.score || right.createdAt - left.createdAt)

    if (recentCandidates.length > 0) {
      return recentCandidates[0].task
    }

    const veryRecentTasks = items
      .map((task) => ({ task, createdAt: parseTimestamp(task?.created_at) }))
      .filter((item) => item.createdAt !== null && item.createdAt >= submittedAt - 15 * 1000)
      .sort((left, right) => right.createdAt - left.createdAt)

    if (veryRecentTasks.length === 1) {
      return veryRecentTasks[0].task
    }
  } catch (error) {
    console.warn("recover_submitted_task_failed", error)
  }

  return null
}
