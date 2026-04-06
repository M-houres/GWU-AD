const { uploadFile } = require("../../utils/request")
const { ensureLogin } = require("../../utils/auth")

Page({
  data: {
    selectedTaskType: "rewrite",
    selectedPlatform: "cnki",
    paperPath: "",
    paperName: "",
    submitting: false,
  },

  onShow() {
    if (!ensureLogin()) {
      wx.reLaunch({ url: "/pages/login/index" })
      return
    }
    const cachedTaskType = wx.getStorageSync("gw_pending_task_type")
    if (cachedTaskType) {
      this.setData({ selectedTaskType: cachedTaskType })
      wx.removeStorageSync("gw_pending_task_type")
    }
  },

  onSelectTaskType(e) {
    this.setData({ selectedTaskType: e.currentTarget.dataset.value || "rewrite" })
  },

  onSelectPlatform(e) {
    this.setData({ selectedPlatform: e.currentTarget.dataset.value || "cnki" })
  },

  onChooseFile() {
    wx.chooseMessageFile({
      count: 1,
      type: "file",
      success: (res) => {
        const file = (res.tempFiles || [])[0]
        if (!file) return
        this.setData({
          paperPath: file.path,
          paperName: file.name || file.path.split("/").pop(),
        })
      },
      fail: () => {
        wx.showToast({ title: "文件选择失败", icon: "none" })
      },
    })
  },

  async onSubmitTask() {
    if (!this.data.paperPath || this.data.submitting) return
    this.setData({ submitting: true })
    try {
      const result = await uploadFile({
        url: "/tasks/submit",
        filePath: this.data.paperPath,
        name: "paper",
        formData: {
          task_type: this.data.selectedTaskType,
          platform: this.data.selectedPlatform,
        },
      })
      wx.showModal({
        title: "提交成功",
        content: `任务ID: ${result.id}\n扣除积分: ${result.cost_credits}`,
        showCancel: true,
        cancelText: "继续提交",
        confirmText: "查看记录",
        success: (modalRes) => {
          if (modalRes.confirm) {
            wx.switchTab({ url: "/pages/records/index" })
            return
          }
          this.setData({ paperPath: "", paperName: "" })
        },
      })
    } catch (error) {
      wx.showToast({ title: error.message || "提交失败", icon: "none" })
    } finally {
      this.setData({ submitting: false })
    }
  },
})

