import axios from "axios"

import {
  clearAdminSession,
  clearUserSession,
  getAdminToken,
  getUserToken,
} from "./session"

function resolveBaseURL() {
  const explicit = import.meta.env.VITE_API_BASE_URL
  if (explicit) {
    return explicit
  }
  // Local fallback: make API target explicit so both `vite dev` and `vite preview`
  // can work without depending on proxy configuration.
  if (typeof window !== "undefined") {
    const { hostname } = window.location
    if (hostname === "127.0.0.1" || hostname === "localhost") {
      return "http://127.0.0.1:8000/api/v1"
    }
  }
  return "/api/v1"
}

const baseURL = resolveBaseURL()
const refreshClient = axios.create({ baseURL, timeout: 20000, withCredentials: true })

function looksLikeJwt(value) {
  return /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(String(value || "").trim())
}

function unwrapResponse(response) {
  const responseType = response?.config?.responseType
  if (responseType === "blob" || responseType === "arraybuffer") {
    return response
  }
  const payload = response.data
  if (payload && typeof payload.code === "number") {
    if (payload.code !== 0) {
      const err = new Error(payload.message || "请求失败")
      err.code = payload.code
      throw err
    }
    return payload.data
  }
  return payload
}

async function normalizeBlobError(data) {
  if (typeof Blob === "undefined" || !(data instanceof Blob)) {
    return null
  }
  const rawText = await data.text()
  const text = String(rawText || "").trim()
  if (!text) {
    return null
  }
  try {
    const payload = JSON.parse(text)
    if (payload && typeof payload === "object" && payload.message) {
      return {
        message: payload.message,
        code: payload.code,
      }
    }
  } catch {}
  return { message: text }
}

async function normalizeError(error) {
  const blobError = await normalizeBlobError(error?.response?.data)
  if (blobError?.message) {
    const err = new Error(blobError.message)
    err.code = blobError.code
    return Promise.reject(err)
  }
  const rawMessage = String(error?.message || "").trim()
  if (error?.code === "ECONNABORTED" || /timeout/i.test(rawMessage)) {
    const err = new Error("请求超时，请稍后重试")
    err.code = error?.code || "ECONNABORTED"
    return Promise.reject(err)
  }
  if (!error?.response) {
    const err = new Error("网络连接异常，请稍后重试")
    err.code = error?.code || "NETWORK_ERROR"
    return Promise.reject(err)
  }
  if (error?.response?.data?.message) {
    const err = new Error(error.response.data.message)
    err.code = error.response.data.code
    return Promise.reject(err)
  }
  if ([502, 503, 504].includes(Number(error?.response?.status))) {
    const err = new Error("服务暂时不可用，请稍后重试")
    err.code = error?.response?.status
    return Promise.reject(err)
  }
  return Promise.reject(error)
}

let userRefreshPromise = null
let adminRefreshPromise = null

async function refreshUserSession() {
  if (!userRefreshPromise) {
    userRefreshPromise = refreshClient
      .post("/auth/refresh")
      .then((resp) => unwrapResponse(resp))
      .finally(() => {
        userRefreshPromise = null
      })
  }
  return userRefreshPromise
}

async function refreshAdminSession() {
  if (!adminRefreshPromise) {
    adminRefreshPromise = refreshClient
      .post("/admin/auth/refresh")
      .then((resp) => unwrapResponse(resp))
      .finally(() => {
        adminRefreshPromise = null
      })
  }
  return adminRefreshPromise
}

export const userHttp = axios.create({ baseURL, timeout: 20000, withCredentials: true })
userHttp.interceptors.request.use((config) => {
  config.headers["X-Client-Source"] = "web"
  const token = getUserToken()
  if (looksLikeJwt(token)) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
userHttp.interceptors.response.use(
  (resp) => unwrapResponse(resp),
  async (error) => {
    const originalRequest = error?.config || {}
    const isRefreshEndpoint = String(originalRequest.url || "").includes("/auth/refresh")
    if (error?.response?.status === 401 && !originalRequest._retry && !isRefreshEndpoint) {
      originalRequest._retry = true
      try {
        await refreshUserSession()
        return userHttp(originalRequest)
      } catch {}
    }
    if (error?.response?.status === 401) {
      const hadToken = Boolean(getUserToken())
      clearUserSession()
      if (hadToken) {
        const redirect = encodeURIComponent(`${location.pathname}${location.search}`)
        location.href = `/login?redirect=${redirect}`
      }
    }
    return normalizeError(error)
  }
)

export const adminHttp = axios.create({ baseURL, timeout: 20000, withCredentials: true })
adminHttp.interceptors.request.use((config) => {
  config.headers["X-Client-Source"] = "web"
  const token = getAdminToken()
  if (looksLikeJwt(token)) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
adminHttp.interceptors.response.use(
  (resp) => unwrapResponse(resp),
  async (error) => {
    const originalRequest = error?.config || {}
    const isRefreshEndpoint = String(originalRequest.url || "").includes("/admin/auth/refresh")
    if (error?.response?.status === 401 && !originalRequest._retry && !isRefreshEndpoint) {
      originalRequest._retry = true
      try {
        await refreshAdminSession()
        return adminHttp(originalRequest)
      } catch {}
    }
    if (error?.response?.status === 401) {
      const hadToken = Boolean(getAdminToken())
      clearAdminSession()
      if (hadToken) {
        const redirect = encodeURIComponent(`${location.pathname}${location.search}`)
        location.href = `/admin/login?redirect=${redirect}`
      }
    }
    return normalizeError(error)
  }
)
