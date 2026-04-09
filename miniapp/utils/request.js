const env = require("../config/env")
const { getToken, clearToken, clearUser } = require("./storage")
const { openLogin, getCurrentRoute } = require("./authFlow")
const { getBizMessage } = require("./status")

function buildHeaders(extra = {}) {
  const token = getToken()
  const headers = {
    "content-type": "application/json",
    "X-Client-Source": "miniprogram",
    ...extra,
  }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

function handleUnauthorized() {
  clearToken()
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
  const { url, method = "GET", data = {}, header = {}, silent = false, timeout = 20000 } = options
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${env.apiBaseUrl}${url}`,
      method,
      data,
      timeout,
      header: buildHeaders(header),
      success(res) {
        const { body, rawText } = parseResponseBody(res.data)

        if (res.statusCode === 401) {
          handleUnauthorized()
          reject(
            createError(getBizMessage(body, "登录状态已失效"), {
              statusCode: res.statusCode,
              body,
            })
          )
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
  } = options

  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${env.apiBaseUrl}${url}`,
      filePath,
      name,
      formData,
      timeout,
      header: buildHeaders(header),
      success(res) {
        const { body, rawText } = parseResponseBody(res.data)

        if (res.statusCode === 401) {
          handleUnauthorized()
          reject(createError("登录状态已失效", { statusCode: res.statusCode, body }))
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
    })
  })
}

module.exports = {
  request,
  uploadFile,
}
