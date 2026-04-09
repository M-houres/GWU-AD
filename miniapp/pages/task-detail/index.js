const env = require("../../config/env")
const { request } = require("../../utils/request")
const { getToken } = require("../../utils/storage")
const { ensureLogin } = require("../../utils/auth")
const { getTaskStatusText, toFriendlyError } = require("../../utils/status")

Page({
  data: {
    taskId: 0,
    task: {},
    statusText: "未知状态",
    resultText: "暂无结果",
  },

  pollTimer: null,

  onLoad(options) {
    const taskId = Number(options.id || 0)
    this.setData({ taskId })
  },

  onShow() {
    if (!ensureLogin()) {
      wx.reLaunch({ url: "/pages/login/index" })
      return
    }
    this.loadTask(true)
  },

  onHide() {
    this.stopPolling()
  },

  onUnload() {
    this.stopPolling()
  },

  async onRefresh() {
    await this.loadTask(false)
  },

  async loadTask(initial) {
    const taskId = Number(this.data.taskId || 0)
    if (!taskId) return
    try {
      const data = await request({
        url: `/tasks/${taskId}`,
        method: "GET",
        silent: !initial,
      })
      const status = String(data.status || "").toLowerCase()
      const resultText = this.stringifyResult(data.result_json)
      this.setData({
        task: data || {},
        statusText: getTaskStatusText(status),
        resultText,
      })
      if (status === "pending" || status === "running") {
        this.startPolling()
      } else {
        this.stopPolling()
      }
    } catch (error) {
      if (initial) {
        wx.showToast({ title: toFriendlyError(error, "加载任务失败"), icon: "none" })
      }
    }
  },

  stringifyResult(resultJson) {
    if (!resultJson || typeof resultJson !== "object") return "暂无结构化结果"
    try {
      return JSON.stringify(resultJson, null, 2).slice(0, 1800)
    } catch (_) {
      return "结果解析失败"
    }
  },

  startPolling() {
    if (this.pollTimer) return
    this.pollTimer = setInterval(() => {
      this.loadTask(false)
    }, 3000)
  },

  stopPolling() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
    }
  },

  onDownloadResult() {
    const taskId = Number(this.data.taskId || 0)
    const status = String(this.data.task.status || "").toLowerCase()
    if (!taskId) return
    if (status !== "completed") {
      wx.showToast({ title: "任务未完成，无法下载", icon: "none" })
      return
    }
    const token = getToken()
    wx.downloadFile({
      url: `${env.apiBaseUrl}/tasks/${taskId}/download`,
      header: {
        "X-Client-Source": "miniprogram",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: (res) => {
        if (res.statusCode !== 200 || !res.tempFilePath) {
          wx.showToast({ title: "下载失败", icon: "none" })
          return
        }
        wx.openDocument({
          filePath: res.tempFilePath,
          showMenu: true,
          fail: () => wx.showToast({ title: "文件打开失败", icon: "none" }),
        })
      },
      fail: () => wx.showToast({ title: "下载失败", icon: "none" }),
    })
  },
})
