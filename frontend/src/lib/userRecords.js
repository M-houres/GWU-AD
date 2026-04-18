import { userHttp } from "./http"

async function fetchAllPages(loader, { pageSize = 100, maxPages = 20 } = {}) {
  const size = Math.max(1, Number(pageSize) || 100)
  const limit = Math.max(1, Number(maxPages) || 20)
  const items = []
  let page = 1
  let totalPages = 1

  while (page <= totalPages && page <= limit) {
    const data = await loader(page, size)
    const pageItems = Array.isArray(data?.items) ? data.items : []
    items.push(...pageItems)

    const pagination = data?.pagination || {}
    const nextTotalPages = Number(pagination.total_pages || 0)
    if (Number.isFinite(nextTotalPages) && nextTotalPages > 0) {
      totalPages = nextTotalPages
    } else if (pageItems.length < size) {
      totalPages = page
    } else {
      totalPages = page + 1
    }
    page += 1
  }

  return items
}

function toPositiveInt(value, fallback) {
  const num = Number(value)
  return Number.isFinite(num) && num > 0 ? Math.floor(num) : fallback
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase()
}

function taskMatchesParams(task, params = {}) {
  if (!task || typeof task !== "object") {
    return false
  }
  if (params.task_type && normalizeText(task.task_type) !== normalizeText(params.task_type)) {
    return false
  }
  if (params.platform && normalizeText(task.platform) !== normalizeText(params.platform)) {
    return false
  }
  if (params.status && normalizeText(task.status) !== normalizeText(params.status)) {
    return false
  }
  return true
}

function sortTasksByNewest(items) {
  return [...items].sort((a, b) => String(b?.created_at || "").localeCompare(String(a?.created_at || "")))
}

export function mergeTaskLists(...lists) {
  const map = new Map()
  for (const list of lists) {
    for (const item of list || []) {
      if (!item?.id) continue
      map.set(item.id, item)
    }
  }
  return sortTasksByNewest([...map.values()])
}

export async function fetchUserTasksPage(params = {}, options = {}) {
  const { page = 1, pageSize = 100, requestConfig } = options || {}
  return userHttp.get("/tasks/my", {
    params: {
      ...params,
      page: toPositiveInt(page, 1),
      page_size: toPositiveInt(pageSize, 100),
    },
    ...(requestConfig || {}),
  })
}

export async function fetchUserTaskDetail(taskId, options = {}) {
  const id = toPositiveInt(taskId, 0)
  if (!id) return null
  const { requestConfig } = options || {}
  try {
    return await userHttp.get(`/tasks/${id}`, requestConfig || {})
  } catch {
    return null
  }
}

export function shouldPollTaskRecords({ tasks = [], focusTaskId = null, submitted = false } = {}) {
  const focusId = toPositiveInt(focusTaskId, 0)
  if (focusId > 0) {
    const focusTask = (tasks || []).find((item) => Number(item?.id) === focusId)
    if (!focusTask) {
      return true
    }
    const focusStatus = normalizeText(focusTask?.status)
    if (focusStatus === "pending" || focusStatus === "preprocessing" || focusStatus === "queued" || focusStatus === "running") {
      return true
    }
  } else if (submitted) {
    return true
  }
  return (tasks || []).some((item) => {
    const status = normalizeText(item?.status)
    return status === "pending" || status === "preprocessing" || status === "queued" || status === "running"
  })
}

export async function fetchUserTasksFast(params = {}, options = {}) {
  const { focusTaskId = null, pageSize = 100, maxPages = 20, requestConfig } = options || {}
  const firstPage = await fetchUserTasksPage(params, { page: 1, pageSize, requestConfig })
  const firstItems = Array.isArray(firstPage?.items) ? firstPage.items : []
  let initialItems = sortTasksByNewest(firstItems)

  const focusId = toPositiveInt(focusTaskId, 0)
  if (focusId && !initialItems.some((item) => item?.id === focusId)) {
    const focusTask = await fetchUserTaskDetail(focusId, { requestConfig })
    if (focusTask && taskMatchesParams(focusTask, params)) {
      initialItems = mergeTaskLists([focusTask], initialItems)
    }
  }

  const totalPages = Math.min(
    toPositiveInt(firstPage?.pagination?.total_pages, 1),
    toPositiveInt(maxPages, 20)
  )

  const restPromise = (async () => {
    if (totalPages <= 1) {
      return initialItems
    }
    const requests = []
    for (let page = 2; page <= totalPages; page += 1) {
      requests.push(fetchUserTasksPage(params, { page, pageSize, requestConfig }))
    }
    const results = await Promise.all(requests)
    const restItems = results.flatMap((result) => (Array.isArray(result?.items) ? result.items : []))
    return mergeTaskLists(initialItems, restItems)
  })()

  return {
    items: initialItems,
    totalPages,
    restPromise,
  }
}

export async function fetchAllUserTasks(params = {}, options = {}) {
  const { requestConfig, ...pageOptions } = options || {}
  return fetchAllPages(
    (page, pageSize) =>
      userHttp.get("/tasks/my", {
        params: {
          ...params,
          page,
          page_size: pageSize,
        },
        ...(requestConfig || {}),
      }),
    pageOptions
  )
}

export async function fetchAllUserCreditTransactions(params = {}, options = {}) {
  const { requestConfig, ...pageOptions } = options || {}
  return fetchAllPages(
    (page, pageSize) =>
      userHttp.get("/users/me/credit-transactions", {
        params: {
          ...params,
          page,
          page_size: pageSize,
        },
        ...(requestConfig || {}),
      }),
    pageOptions
  )
}
