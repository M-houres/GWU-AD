const env = require("../config/env")
const { getToken, clearToken, clearUser } = require("./storage")
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
  const pages = getCurrentPages()
  const currentRoute = pages.length ? pages[pages.length - 1].route : ""
  if (currentRoute !== "pages/login/index") {
    wx.reLaunch({ url: "/pages/login/index" })
  }
}

function request(options) {
  const { url, method = "GET", data = {}, header = {}, silent = false } = options
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${env.apiBaseUrl}${url}`,
      method,
      data,
      header: buildHeaders(header),
      success(res) {
        const body = res.data
        if (res.statusCode === 401) {
          handleUnauthorized()
          reject(new Error(getBizMessage(body, "登录状态已失效")))
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const message = getBizMessage(body, "请求失败")
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(new Error(message))
          return
        }
        if (!body || typeof body !== "object") {
          const message = "响应格式异常"
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(new Error(message))
          return
        }
        if (Number(body.code) !== 0) {
          const message = getBizMessage(body, "业务处理失败")
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(new Error(message))
          return
        }
        resolve(body.data)
      },
      fail(err) {
        if (!silent) wx.showToast({ title: "网络异常，请稍后重试", icon: "none" })
        reject(err)
      },
    })
  })
}

function uploadFile(options) {
  const { url, filePath, name = "paper", formData = {}, header = {}, silent = false } = options
  return new Promise((resolve, reject) => {
    wx.uploadFile({
      url: `${env.apiBaseUrl}${url}`,
      filePath,
      name,
      formData,
      header: buildHeaders(header),
      success(res) {
        if (res.statusCode === 401) {
          handleUnauthorized()
          reject(new Error("登录状态已失效"))
          return
        }
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const message = "上传失败"
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(new Error(message))
          return
        }
        let body = {}
        try {
          body = JSON.parse(res.data || "{}")
        } catch (_) {
          reject(new Error("响应格式异常"))
          return
        }
        if (Number(body.code) !== 0) {
          const message = getBizMessage(body, "业务处理失败")
          if (!silent) wx.showToast({ title: message, icon: "none" })
          reject(new Error(message))
          return
        }
        resolve(body.data)
      },
      fail(err) {
        if (!silent) wx.showToast({ title: "上传失败，请稍后重试", icon: "none" })
        reject(err)
      },
    })
  })
}

module.exports = {
  request,
  uploadFile,
}
