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

export async function fetchAllUserTasks(params = {}, options = {}) {
  return fetchAllPages(
    (page, pageSize) =>
      userHttp.get("/tasks/my", {
        params: {
          ...params,
          page,
          page_size: pageSize,
        },
      }),
    options
  )
}

export async function fetchAllUserCreditTransactions(params = {}, options = {}) {
  return fetchAllPages(
    (page, pageSize) =>
      userHttp.get("/users/me/credit-transactions", {
        params: {
          ...params,
          page,
          page_size: pageSize,
        },
      }),
    options
  )
}
