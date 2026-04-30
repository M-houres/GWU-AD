import axios from "axios"

import {
  clearAdminSession,
  clearPartnerSession,
  clearUserSession,
  getAdminRefreshToken,
  getAdminToken,
  getPartnerRefreshToken,
  getPartnerToken,
  getUserRefreshToken,
  getUserToken,
  setAdminRefreshToken,
  setPartnerInfo,
  setPartnerRefreshToken,
  setPartnerToken,
  setAdminToken,
  setUserRefreshToken,
  setUserToken,
} from "./session"

function resolveBaseURL() {
  const explicit = import.meta.env.VITE_API_BASE_URL
  if (explicit) {
    return explicit
  }
  // Local fallback: talk to the backend directly during dev.
  // The Vite proxy adds severe latency to multipart task uploads on localhost.
  if (typeof window !== "undefined") {
    const { hostname } = window.location
    if (hostname === "127.0.0.1" || hostname === "localhost") {
      return "http://127.0.0.1:8001/api/v1"
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
  const status = Number(error?.response?.status || 0)
  const requestId = String(
    error?.response?.headers?.["x-request-id"] ||
      error?.response?.headers?.["X-Request-Id"] ||
      ""
  ).trim()
  if (blobError?.message) {
    const message =
      status >= 500 && requestId && !String(blobError.message).includes(requestId)
        ? `${blobError.message}（请求ID: ${requestId}）`
        : blobError.message
    const err = new Error(message)
    err.code = blobError.code
    err.status = status
    err.requestId = requestId
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
    err.code = error?.code || "ERR_NETWORK"
    return Promise.reject(err)
  }
  if (error?.response?.data?.message) {
    const baseMessage = String(error.response.data.message || "").trim() || "请求失败"
    const message =
      status >= 500 && requestId && !baseMessage.includes(requestId)
        ? `${baseMessage}（请求ID: ${requestId}）`
        : baseMessage
    const err = new Error(message)
    err.code = error.response.data.code
    err.status = status
    err.requestId = requestId
    return Promise.reject(err)
  }
  if ([502, 503, 504].includes(status)) {
    const err = new Error("服务暂时不可用，请稍后重试")
    err.code = String(status || "GATEWAY_ERROR")
    err.status = status
    err.requestId = requestId
    return Promise.reject(err)
  }
  if (status === 413) {
    const err = new Error("上传文件过大，请控制在 20MB 以内后重试")
    err.code = "PAYLOAD_TOO_LARGE"
    err.status = status
    err.requestId = requestId
    return Promise.reject(err)
  }
  if (status >= 500) {
    const err = new Error(
      requestId ? `服务器内部错误（请求ID: ${requestId}）` : "服务器内部错误，请稍后重试"
    )
    err.code = "SERVER_ERROR"
    err.status = status
    err.requestId = requestId
    return Promise.reject(err)
  }
  return Promise.reject(error)
}

let userRefreshPromise = null
let adminRefreshPromise = null
let partnerRefreshPromise = null
let userAuthRedirecting = false
let adminAuthRedirecting = false
let partnerAuthRedirecting = false

function hasWindowLocation() {
  return typeof window !== "undefined" && typeof location !== "undefined"
}

function buildCurrentPath() {
  if (!hasWindowLocation()) return "/"
  return `${location.pathname || "/"}${location.search || ""}`
}

function redirectUserToLogin() {
  if (!hasWindowLocation() || userAuthRedirecting) return
  userAuthRedirecting = true
  const redirect = encodeURIComponent(buildCurrentPath())
  location.replace(`/login?redirect=${redirect}`)
}

function redirectAdminToLogin() {
  if (!hasWindowLocation() || adminAuthRedirecting) return
  adminAuthRedirecting = true
  const redirect = encodeURIComponent(buildCurrentPath())
  location.replace(`/admin/login?redirect=${redirect}`)
}

function redirectPartnerToLogin() {
  if (!hasWindowLocation() || partnerAuthRedirecting) return
  partnerAuthRedirecting = true
  const redirect = encodeURIComponent(buildCurrentPath())
  location.replace(`/app/partner/login?redirect=${redirect}`)
}

async function refreshUserSession() {
  const refreshToken = getUserRefreshToken()
  if (!looksLikeJwt(refreshToken)) {
    const err = new Error("refresh token missing")
    err.code = "NO_REFRESH_TOKEN"
    return Promise.reject(err)
  }
  if (!userRefreshPromise) {
    userRefreshPromise = refreshClient
      .post("/auth/refresh", {
        refresh_token: refreshToken,
      })
      .then((resp) => unwrapResponse(resp))
      .then((data) => {
        if (data?.token) setUserToken(data.token)
        if (data?.refresh_token) setUserRefreshToken(data.refresh_token)
        return data
      })
      .finally(() => {
        userRefreshPromise = null
      })
  }
  return userRefreshPromise
}

async function refreshAdminSession() {
  const refreshToken = getAdminRefreshToken()
  if (!looksLikeJwt(refreshToken)) {
    const err = new Error("refresh token missing")
    err.code = "NO_REFRESH_TOKEN"
    return Promise.reject(err)
  }
  if (!adminRefreshPromise) {
    adminRefreshPromise = refreshClient
      .post("/admin/auth/refresh", {
        refresh_token: refreshToken,
      })
      .then((resp) => unwrapResponse(resp))
      .then((data) => {
        if (data?.token) setAdminToken(data.token)
        if (data?.refresh_token) setAdminRefreshToken(data.refresh_token)
        return data
      })
      .finally(() => {
        adminRefreshPromise = null
      })
  }
  return adminRefreshPromise
}

async function refreshPartnerSession() {
  const refreshToken = getPartnerRefreshToken()
  if (!looksLikeJwt(refreshToken)) {
    const err = new Error("refresh token missing")
    err.code = "NO_REFRESH_TOKEN"
    return Promise.reject(err)
  }
  if (!partnerRefreshPromise) {
    partnerRefreshPromise = refreshClient
      .post("/partners/portal/auth/refresh", {
        refresh_token: refreshToken,
      })
      .then((resp) => unwrapResponse(resp))
      .then((data) => {
        if (data?.token) setPartnerToken(data.token)
        if (data?.refresh_token) setPartnerRefreshToken(data.refresh_token)
        if (data?.channel) setPartnerInfo(data.channel)
        return data
      })
      .finally(() => {
        partnerRefreshPromise = null
      })
  }
  return partnerRefreshPromise
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
      } catch (refreshError) {
        const hadToken = Boolean(getUserToken())
        clearUserSession()
        if (hadToken) {
          redirectUserToLogin()
        }
        return normalizeError(refreshError)
      }
    }
    if (error?.response?.status === 401) {
      const hadToken = Boolean(getUserToken())
      clearUserSession()
      if (hadToken) {
        redirectUserToLogin()
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
      } catch (refreshError) {
        const hadToken = Boolean(getAdminToken())
        clearAdminSession()
        if (hadToken) {
          redirectAdminToLogin()
        }
        return normalizeError(refreshError)
      }
    }
    if (error?.response?.status === 401) {
      const hadToken = Boolean(getAdminToken())
      clearAdminSession()
      if (hadToken) {
        redirectAdminToLogin()
      }
    }
    return normalizeError(error)
  }
)

export const partnerHttp = axios.create({ baseURL, timeout: 20000, withCredentials: true })
partnerHttp.interceptors.request.use((config) => {
  config.headers["X-Client-Source"] = "web"
  const token = getPartnerToken()
  if (looksLikeJwt(token)) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
partnerHttp.interceptors.response.use(
  (resp) => unwrapResponse(resp),
  async (error) => {
    const originalRequest = error?.config || {}
    const isRefreshEndpoint = String(originalRequest.url || "").includes("/partners/portal/auth/refresh")
    const isLoginEndpoint = String(originalRequest.url || "").includes("/partners/portal/auth/login")
    if (error?.response?.status === 401 && !originalRequest._retry && !isRefreshEndpoint && !isLoginEndpoint) {
      originalRequest._retry = true
      try {
        await refreshPartnerSession()
        return partnerHttp(originalRequest)
      } catch (refreshError) {
        const hadToken = Boolean(getPartnerToken())
        clearPartnerSession()
        if (hadToken) {
          redirectPartnerToLogin()
        }
        return normalizeError(refreshError)
      }
    }
    if (error?.response?.status === 401 && !isLoginEndpoint) {
      const hadToken = Boolean(getPartnerToken())
      clearPartnerSession()
      if (hadToken) {
        redirectPartnerToLogin()
      }
    }
    return normalizeError(error)
  }
)
