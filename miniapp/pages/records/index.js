const env = require("../../config/env")
const { request } = require("../../utils/request")
const { getToken } = require("../../utils/storage")
const { ensureLogin } = require("../../utils/auth")
const { getTaskStatusText, toFriendlyError } = require("../../utils/status")

Page({
  data: {
    records: [],
    loading: false,
  },

  onShow() {
    if (!ensureLogin()) {
      wx.reLaunch({ url: "/pages/login/index" })
      return
    }
    this.loadRecords()
  },

  onPullDownRefresh() {
    this.loadRecords().finally(() => wx.stopPullDownRefresh())
  },

  async loadRecords() {
    if (this.data.loading) return
    this.setData({ loading: true })
    try {
      const data = await request({
        url: "/tasks/my?page=1&page_size=20",
        method: "GET",
      })
      const records = (data.items || []).map((item) => ({
        ...item,
        statusText: getTaskStatusText(item.status),
      }))
      this.setData({ records })
    } catch (error) {
      wx.showToast({ title: toFriendlyError(error, "加载记录失败"), icon: "none" })
    } finally {
      this.setData({ loading: false })
    }
  },

  onTapDetail(e) {
    const taskId = Number(e.currentTarget.dataset.id || 0)
    if (!taskId) return
    wx.navigateTo({ url: `/pages/task-detail/index?id=${taskId}` })
  },

  onTapDownload(e) {
    const taskId = Number(e.currentTarget.dataset.id || 0)
    const status = String(e.currentTarget.dataset.status || "").toLowerCase()
    if (!taskId) return
    if (status !== "completed") {
      wx.showToast({ title: "任务未完成，暂不可下载", icon: "none" })
      return
    }

    const token = getToken()
    wx.downloadFile({
      url: `${env.apiBaseUrl}/tasks/${taskId}/download`,
      header: token ? { Authorization: `Bearer ${token}` } : {},
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
