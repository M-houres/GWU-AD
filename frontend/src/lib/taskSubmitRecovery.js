import { fetchAllUserTasks } from "./userRecords"

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      const error = new Error("request canceled")
      error.code = "ERR_CANCELED"
      reject(error)
      return
    }
    const timer = window.setTimeout(() => {
      if (signal) {
        signal.removeEventListener("abort", handleAbort)
      }
      resolve()
    }, ms)
    const handleAbort = () => {
      window.clearTimeout(timer)
      signal?.removeEventListener("abort", handleAbort)
      const error = new Error("request canceled")
      error.code = "ERR_CANCELED"
      reject(error)
    }
    signal?.addEventListener("abort", handleAbort, { once: true })
  })
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

function hashTextToHex(value) {
  const text = String(value || "")
  let hash = 2166136261
  for (let i = 0; i < text.length; i += 1) {
    hash ^= text.charCodeAt(i)
    hash = Math.imul(hash, 16777619)
  }
  return (hash >>> 0).toString(16).padStart(8, "0")
}

function toHeaderSafeSegment(value, { maxLen = 24 } = {}) {
  const normalized = String(value || "").trim().toLowerCase()
  if (!normalized) return ""
  const ascii = normalized.replace(/[^a-z0-9._-]/g, "")
  if (ascii.length >= 6) {
    return ascii.slice(0, maxLen)
  }
  return hashTextToHex(normalized)
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
    /timeout|timed out|exceeded|请求超时/i.test(message) ||
    code === "ECONNABORTED" ||
    code === "ETIMEDOUT"
  )
}

export function isTaskSubmitNetworkError(error) {
  const message = String(error?.message || "").trim()
  const code = String(error?.code || "").trim().toUpperCase()
  const numericCode = Number(code || 0)
  const status = Number(error?.response?.status || 0)
  return (
    /network error|failed to fetch|fetch failed|load failed|err_network|connection closed|empty response|socket hang up|网络连接异常|连接异常|服务暂时不可用|网关异常/i.test(
      message
    ) ||
    [
      "ERR_NETWORK",
      "NETWORK_ERROR",
      "ERR_CONNECTION_CLOSED",
      "ERR_CONNECTION_RESET",
      "ERR_EMPTY_RESPONSE",
      "GATEWAY_ERROR",
      "502",
      "503",
      "504",
      "520",
      "522",
      "524",
    ].includes(code) ||
    [502, 503, 504, 520, 522, 524].includes(numericCode) ||
    (!error?.response && Boolean(error?.request)) ||
    [502, 503, 504, 520, 522, 524].includes(status)
  )
}

export function isTaskSubmitCanceledError(error) {
  const code = String(error?.code || "").trim().toUpperCase()
  const message = String(error?.message || "").trim()
  return code === "ERR_CANCELED" || /canceled|cancelled|aborted/i.test(message)
}

async function probeBackendReachability({ signal, timeoutMs = 3500 } = {}) {
  if (typeof fetch !== "function" || typeof window === "undefined") {
    return { reachable: true, reason: "unsupported" }
  }
  if (signal?.aborted) {
    return { reachable: false, reason: "aborted" }
  }
  const controller = typeof AbortController !== "undefined" ? new AbortController() : null
  const timer = controller ? window.setTimeout(() => controller.abort(), timeoutMs) : null
  let detachAbort = null
  if (controller && signal) {
    const handleAbort = () => controller.abort()
    signal.addEventListener("abort", handleAbort, { once: true })
    detachAbort = () => signal.removeEventListener("abort", handleAbort)
  }
  try {
    const resp = await fetch(`/api/v1/auth/options?_ts=${Date.now()}`, {
      method: "GET",
      cache: "no-store",
      credentials: "include",
      signal: controller?.signal,
      headers: {
        "X-Client-Source": "web",
      },
    })
    if (resp.ok) {
      return { reachable: true, reason: "ok", status: resp.status }
    }
    if ([502, 503, 504, 520, 522, 524].includes(Number(resp.status))) {
      return { reachable: false, reason: "gateway", status: resp.status }
    }
    // 401/403/404 still means backend is reachable.
    return { reachable: true, reason: "http", status: resp.status }
  } catch (error) {
    if (isTaskSubmitCanceledError(error)) {
      return { reachable: false, reason: "aborted" }
    }
    return { reachable: false, reason: "network" }
  } finally {
    if (timer) {
      window.clearTimeout(timer)
    }
    detachAbort?.()
  }
}

export async function buildTaskSubmitNetworkHint({ signal } = {}) {
  const probe = await probeBackendReachability({ signal })
  if (!probe.reachable && probe.reason === "network") {
    return "提交失败：前端无法连接后端服务，请确认后端已启动（127.0.0.1:8000）后重试"
  }
  if (!probe.reachable && probe.reason === "gateway") {
    return "提交失败：后端服务暂不可用（网关异常），请稍后重试；也可到记录页确认任务是否已创建"
  }
  return "提交未收到有效响应，请稍后到记录页确认任务是否已创建"
}

export function createTaskSubmitIdempotencyKey({
  taskType,
  platform,
  paperTitle,
  authors,
  sourceFilename,
  submittedAt = Date.now(),
}) {
  const randomSuffix =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().replace(/-/g, "").slice(0, 12)
      : Math.random().toString(36).slice(2, 14)
  return [
    toHeaderSafeSegment(taskType, { maxLen: 24 }),
    toHeaderSafeSegment(platform, { maxLen: 24 }),
    toHeaderSafeSegment(paperTitle, { maxLen: 24 }),
    toHeaderSafeSegment(authors, { maxLen: 24 }),
    toHeaderSafeSegment(normalizeFilename(sourceFilename), { maxLen: 24 }),
    String(submittedAt),
    randomSuffix,
  ]
    .filter(Boolean)
    .join(":")
    .slice(0, 96)
}

export async function submitTaskWithRetry({
  submitOnce,
  signal,
  maxAttempts = 4,
  retryDelayMs = 1200,
}) {
  const totalAttempts = Math.max(1, Number(maxAttempts || 1))
  let lastError = null
  for (let attempt = 0; attempt < totalAttempts; attempt += 1) {
    try {
      return await submitOnce()
    } catch (error) {
      lastError = error
      if (isTaskSubmitCanceledError(error)) {
        throw error
      }
      const retryable = isTaskSubmitTimeoutError(error) || isTaskSubmitNetworkError(error)
      if (!retryable || attempt >= totalAttempts - 1) {
        throw error
      }
      const waitMs = retryDelayMs * (attempt + 1)
      await sleep(waitMs, signal)
    }
  }
  throw lastError || new Error("提交失败")
}

export async function recoverSubmittedTaskByIdempotency({
  userHttp,
  taskType,
  platform,
  sourceFilename,
  idempotencyKey,
  signal,
}) {
  if (!userHttp || !taskType || !sourceFilename || !idempotencyKey) {
    return null
  }
  try {
    const data = await userHttp.post(
      "/tasks/submit/recover",
      {
        task_type: taskType,
        platform: platform || "cnki",
        source_filename: sourceFilename,
      },
      {
        timeout: 15000,
        signal,
        headers: {
          "X-Idempotency-Key": idempotencyKey,
        },
      }
    )
    return data?.id ? data : null
  } catch (error) {
    if (isTaskSubmitCanceledError(error)) {
      throw error
    }
    const status = Number(error?.response?.status || 0)
    const code = Number(error?.code || 0)
    if (status === 404 || code === 4041) {
      return null
    }
    return null
  }
}

export async function recoverSubmittedTask({
  taskType,
  paperTitle,
  authors,
  sourceFilename,
  submittedAt = Date.now(),
  attempts = 3,
  retryDelayMs = 900,
  signal,
}) {
  if (!taskType || signal?.aborted) {
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
        { pageSize: 100, maxPages: 10, requestConfig: signal ? { signal } : undefined }
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
      if (isTaskSubmitCanceledError(error)) {
        return null
      }
      console.warn("recover_submitted_task_failed", error)
    }

    if (attempt < attempts - 1) {
      try {
        await sleep(retryDelayMs, signal)
      } catch (error) {
        if (isTaskSubmitCanceledError(error)) {
          return null
        }
        throw error
      }
    }
  }

  return null
}
