const env = require("../config/env")
const {
  clearRefreshToken,
  getRefreshToken,
  getToken,
  getTokenAge,
  setRefreshToken,
  setToken,
  clearToken,
  clearUser,
  setUser,
} = require("./storage")
const { openLogin, getCurrentRoute } = require("./authFlow")
const { getBizMessage } = require("./status")
let refreshPromise = null
const PROACTIVE_REFRESH_AGE_MS = 90 * 60 * 1000

async function ensureFreshToken() {
  if (!getToken()) return
  if (getTokenAge() >= PROACTIVE_REFRESH_AGE_MS) {
    await refreshMiniSession()
  }
}

function buildHeaders(extra = {}, options = {}) {
  const { includeJsonContentType = true } = options
  const token = getToken()
  const headers = {
    "X-Client-Source": "miniprogram",
    ...extra,
  }
  if (includeJsonContentType && !headers["content-type"] && !headers["Content-Type"]) {
    headers["content-type"] = "application/json"
  }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

function handleUnauthorized() {
  clearToken()
  clearRefreshToken()
  clearUser()
  const currentRoute = getCurrentRoute()
  if (currentRoute !== "pages/login/index") {
    const targetTab = currentRoute.startsWith("pages/records/")
      ? "records"
      : currentRoute.startsWith("pages/profile/")
        ? "profile"
        : "home"
    openLogin({
      targetTab,
      action: "session_expired",
      sourceRoute: currentRoute,
    })
  }
}

function rawRequest(options) {
  return new Promise((resolve, reject) => {
    wx.request({
      ...options,
      success: resolve,
      fail: reject,
    })
  })
}

async function refreshMiniSession() {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  if (!refreshPromise) {
    refreshPromise = rawRequest({
      url: `${env.apiBaseUrl}/auth/refresh`,
      method: "POST",
      timeout: 20000,
      header: {
        "content-type": "application/json",
        "X-Client-Source": "miniprogram",
      },
      data: {
        refresh_token: refreshToken,
      },
    })
      .then((res) => {
        const { body } = parseResponseBody(res.data)
        if (res.statusCode < 200 || res.statusCode >= 300 || !body || Number(body.code) !== 0) {
          throw new Error(getBizMessage(body, "登录已过期"))
        }
        const data = body.data || {}
        if (data.token) setToken(data.token)
        if (data.refresh_token) setRefreshToken(data.refresh_token)
        if (data.user) setUser(data.user)
        return true
      })
      .catch(() => false)
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

function createError(message, extra = {}) {
  const error = new Error(message)
  Object.keys(extra).forEach((key) => {
    error[key] = extra[key]
  })
  return error
}

function parseResponseBody(raw) {
  if (raw && typeof raw === "object") {
    return { body: raw, rawText: "" }
  }
  const rawText = String(raw || "").replace(/^\uFEFF/, "").trim()
  if (!rawText) {
    return { body: null, rawText: "" }
  }
  try {
    return {
      body: JSON.parse(rawText),
      rawText,
    }
  } catch {
    return { body: null, rawText }
  }
}

function getNetworkError(err, upload = false) {
  const errMsg = String(err && err.errMsg ? err.errMsg : "").toLowerCase()
  const isTimeout = /timeout/.test(errMsg)
  const message = isTimeout
    ? upload
      ? "上传超时，请稍后到记录页确认任务是否已创建"
      : "网络超时，请稍后重试"
    : upload
      ? "上传失败，请稍后重试"
      : "网络异常，请稍后重试"
  return createError(message, {
    originalError: err,
    isTimeout,
    isNetworkError: !isTimeout,
  })
}

function request(options) {
  const { url, method = "GET", data = {}, header = {}, silent = false, timeout = 20000, _retried = false } = options
  return new Promise((resolve, reject) => {
    ;(async () => {
      await ensureFreshToken()
      wx.request({
      url: `${env.apiBaseUrl}${url}`,
      method,
      data,
      timeout,
      header: buildHeaders(header),
      success(res) {
        const { body, rawText } = parseResponseBody(res.data)

        if (res.statusCode === 401) {
          ;(async () => {
            if (!_retried) {
              const refreshed = await refreshMiniSession()
              if (refreshed) {
                try {
                  const retried = await request({ ...options, silent: true, _retried: true })
                  resolve(retried)
                  return
                } catch (retryError) {
                  reject(retryError)
                  return
                }
              }
            }
            handleUnauthorized()
            reject(
              createError(getBizMessage(body, "登录状态已失效"), {
                statusCode: res.statusCode,
                body,
              })
            )
          })()
          return
        }

        if (res.statusCode < 200 || res.statusCode >= 300) {
          const message = getBizMessage(body, `请求失败（HTTP ${res.statusCode}）`)
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(createError(message, { statusCode: res.statusCode, body, rawBody: rawText }))
          return
        }

        if (!body || typeof body !== "object" || Array.isArray(body)) {
          const message = "响应格式异常"
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(
            createError(message, {
              statusCode: res.statusCode,
              rawBody: rawText,
              isResponseParseError: true,
            })
          )
          return
        }

        if (Number(body.code) !== 0) {
          const message = getBizMessage(body, "业务处理失败")
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(createError(message, { code: body.code, body, statusCode: res.statusCode }))
          return
        }

        resolve(body.data)
      },
      fail(err) {
        const error = getNetworkError(err)
        if (!silent) wx.showToast({ title: error.message, icon: "none" })
        reject(error)
      },
    })
    })()
  })
}

function uploadFile(options) {
  const {
    url,
    filePath,
    name = "paper",
    formData = {},
    header = {},
    silent = false,
    timeout = 120000,
    _retried = false,
    onProgress = null,
  } = options

  return new Promise((resolve, reject) => {
    const uploadOptions = {
      url: `${env.apiBaseUrl}${url}`,
      filePath,
      name,
      formData,
      timeout,
      header: buildHeaders(header, { includeJsonContentType: false }),
      success(res) {
        const { body, rawText } = parseResponseBody(res.data)

        if (res.statusCode === 401) {
          ;(async () => {
            if (!_retried) {
              const refreshed = await refreshMiniSession()
              if (refreshed) {
                try {
                  const retried = await uploadFile({ ...options, silent: true, _retried: true })
                  resolve(retried)
                  return
                } catch (retryError) {
                  reject(retryError)
                  return
                }
              }
            }
            handleUnauthorized()
            reject(createError("登录状态已失效", { statusCode: res.statusCode, body }))
          })()
          return
        }

        if (res.statusCode < 200 || res.statusCode >= 300) {
          const message = getBizMessage(body, `上传失败（HTTP ${res.statusCode}）`)
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(createError(message, { statusCode: res.statusCode, body, rawBody: rawText }))
          return
        }

        if (!body || typeof body !== "object" || Array.isArray(body)) {
          const message = "响应格式异常"
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(
            createError(message, {
              statusCode: res.statusCode,
              rawBody: rawText,
              isResponseParseError: true,
            })
          )
          return
        }

        if (Number(body.code) !== 0) {
          const message = getBizMessage(body, "业务处理失败")
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(createError(message, { code: body.code, body, statusCode: res.statusCode }))
          return
        }

        resolve(body.data)
      },
      fail(err) {
        const error = getNetworkError(err, true)
        if (!silent) wx.showToast({ title: error.message, icon: "none" })
        reject(error)
      },
    }
    if (typeof onProgress === "function") {
      uploadOptions.onProgressUpdate = (res) => {
        onProgress(res.progress || 0, res.totalBytesSent || 0, res.totalBytesExpectedToSend || 0)
      }
    }
    wx.uploadFile(uploadOptions)
  })
}

function downloadFile(options) {
  const { url, header = {}, timeout = 120000, _retried = false } = options

  return new Promise((resolve, reject) => {
    wx.downloadFile({
      url: `${env.apiBaseUrl}${url}`,
      timeout,
      header: buildHeaders(header, { includeJsonContentType: false }),
      success(res) {
        if (res.statusCode === 401) {
          ;(async () => {
            if (!_retried) {
              const refreshed = await refreshMiniSession()
              if (refreshed) {
                try {
                  const retried = await downloadFile({ ...options, _retried: true })
                  resolve(retried)
                  return
                } catch (retryError) {
                  reject(retryError)
                  return
                }
              }
            }
            handleUnauthorized()
            reject(createError("登录状态已失效", { statusCode: res.statusCode }))
          })()
          return
        }

        if (res.statusCode < 200 || res.statusCode >= 300 || !res.tempFilePath) {
          reject(createError(`下载失败（HTTP ${res.statusCode}）`, { statusCode: res.statusCode }))
          return
        }

        resolve(res.tempFilePath)
      },
      fail(err) {
        reject(getNetworkError(err, true))
      },
    })
  })
}

module.exports = {
  request,
  uploadFile,
  downloadFile,
}
