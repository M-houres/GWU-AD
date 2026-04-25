const { request, uploadFile } = require("../../utils/request")
const { ensureLogin } = require("../../utils/auth")
const { requireAuth, getPendingAuth, clearPendingAuth } = require("../../utils/authFlow")
const {
  getUser,
  setUser,
  setHomeDraft,
  getHomeDraft,
  clearHomeDraft,
  setReferrerCode,
} = require("../../utils/storage")
const { capturePartnerTracking } = require("../../utils/partnerTracking")
const {
  isTaskSubmitRecoverableError,
  recoverSubmittedTask,
  getTaskSubmitFallbackMessage,
} = require("../../utils/taskRecovery")

const DEFAULT_AIGC_DAILY_FREE_LIMIT = 6
const MAX_FILE_SIZE = 20 * 1024 * 1024

const TASK_OPTIONS = [
  {
    value: "aigc_detect",
    label: "AIGC检测",
    helper: "提交后生成全文检测结果与报告，并自动优先抵扣每日免费额度。",
    note: "全文检测",
    badge: "每日免费",
    uploadHint: "支持 .docx / .pdf / .txt，默认从微信聊天记录选择。",
  },
  {
    value: "rewrite",
    label: "降AIGC",
    helper: "围绕疑似 AI 表达做改写优化，尽量降低生成痕迹并保持论文语气稳定。",
    note: "降AIGC改写",
    badge: "重点优化",
    uploadHint: "仅支持 .docx，默认从微信聊天记录选择。",
  },
  {
    value: "dedup",
    label: "降重复率",
    helper: "围绕重复内容做改写降重，尽量保留原意与论文结构。",
    note: "降重改写",
    badge: "降重",
    uploadHint: "仅支持 .docx，默认从微信聊天记录选择。",
  },
]

const BASE_PLATFORM_OPTIONS = [
  {
    value: "cnki",
    label: "知网",
    detectLabel: "模拟知网",
    desc: "适合主流论文场景，结果展示更接近期刊与学位论文常用口径。",
    detectDesc: "按模拟知网的展示方式输出 AIGC 全文检测结果。",
  },
  {
    value: "vip",
    label: "维普",
    detectLabel: "模拟维普",
    desc: "适合交叉校验另一套平台视角，流程直观，结果清晰。",
    detectDesc: "按模拟维普的展示方式输出 AIGC 全文检测结果。",
  },
]

function getPlatformOptions(taskType = "") {
  return BASE_PLATFORM_OPTIONS.map((item) => ({
    value: item.value,
    label: taskType === "aigc_detect" ? item.detectLabel : item.label,
    desc: taskType === "aigc_detect" ? item.detectDesc : item.desc,
  }))
}

function getAllowedExtensions(taskType = "") {
  if (taskType === "aigc_detect") return [".docx", ".pdf", ".txt"]
  return [".docx"]
}

function getFilename(path = "") {
  const normalized = String(path || "").replace(/\\/g, "/")
  const segments = normalized.split("/")
  return segments[segments.length - 1] || ""
}

function deriveTitleFromFilename(filename = "") {
  return String(filename || "")
    .replace(/\.[^.]+$/, "")
    .trim()
}

function buildQuotaView(quota = {}) {
  const limit = Math.max(Number(quota.daily_free_limit || DEFAULT_AIGC_DAILY_FREE_LIMIT), DEFAULT_AIGC_DAILY_FREE_LIMIT)
  const remainingRaw = Number(quota.free_remaining_today)
  const usedRaw = Number(quota.free_used_today)
  const remaining = Number.isFinite(remainingRaw) ? Math.max(remainingRaw, 0) : null
  const used = Number.isFinite(usedRaw) ? Math.max(usedRaw, 0) : null

  if (remaining === null || used === null) {
    return {
      quotaChipText: `AIGC 每日免费 ${limit} 篇`,
      quotaPanelTitle: `今日可免费检测 ${limit} 篇`,
      quotaPanelDesc: "AIGC 检测每日前 6 篇免费，超出免费次数后再按字数计费。",
    }
  }

  if (remaining <= 0) {
    return {
      quotaChipText: `AIGC 今日 0 / ${limit}`,
      quotaPanelTitle: "今日免费次数已用完",
      quotaPanelDesc: "当前继续提交仍可检测，但会按字数计费，记录页会保留完整任务链。",
    }
  }

  return {
    quotaChipText: `AIGC 今日 ${remaining} / ${limit}`,
    quotaPanelTitle: `今日还可免费检测 ${remaining} 篇`,
    quotaPanelDesc: `今日已免费使用 ${used} 篇，当前提交会优先抵扣剩余免费额度。`,
  }
}

function createEmptyInviteInfo() {
  return {
    inviteCode: "",
    inviteLink: "",
  }
}

function buildCreditChipText(user = null, guestMode = false) {
  if (guestMode) return "登录后查看积分"
  return `当前积分 ${Number((user && user.credits) || 0)}`
}

Page({
  data: {
    guestMode: true,
    user: {},
    inviteInfo: createEmptyInviteInfo(),
    taskOptions: TASK_OPTIONS,
    platformOptions: getPlatformOptions("aigc_detect"),
    selectedTaskType: "aigc_detect",
    selectedPlatform: "cnki",
    selectedTaskMeta: TASK_OPTIONS[0],
    selectedPlatformMeta: getPlatformOptions("aigc_detect")[0],
    uploadRuleText: TASK_OPTIONS[0].uploadHint,
    paperPath: "",
    paperName: "",
    paperTitle: "",
    authors: "",
    submitting: false,
    creditChipText: "登录后查看积分",
    quotaChipText: `AIGC 每日免费 ${DEFAULT_AIGC_DAILY_FREE_LIMIT} 篇`,
    quotaPanelTitle: `今日可免费检测 ${DEFAULT_AIGC_DAILY_FREE_LIMIT} 篇`,
    quotaPanelDesc: "AIGC 检测每日前 6 篇免费，超出免费次数后再按字数计费。",
  },

  onLoad(options = {}) {
    const sharedRef = String(options.ref || options.invite_code || "").trim().toUpperCase()
    if (sharedRef) {
      setReferrerCode(sharedRef)
    }
    capturePartnerTracking(options)
    this.restoreDraft()
    this.syncSelectedMeta()
  },

  onShow() {
    this.restoreDraft()

    const cachedTaskType = wx.getStorageSync("gw_pending_task_type")
    if (cachedTaskType) {
      this.setData({ selectedTaskType: cachedTaskType })
      wx.removeStorageSync("gw_pending_task_type")
    }

    this.syncSelectedMeta()
    if (ensureLogin()) {
      const currentUser = getUser() || {}
      this.setData({
        guestMode: false,
        user: currentUser,
        creditChipText: buildCreditChipText(currentUser, false),
      })
      this.reloadProfile()
      this.loadInviteInfo()
      this.loadSummary()
      this.consumePendingAction()
    } else {
      this.applyGuestState()
    }

    if (typeof wx.showShareMenu === "function") {
      try {
        wx.showShareMenu({ menus: ["shareAppMessage"] })
      } catch (_) {
        // ignore share menu failure
      }
    }
  },

  onHide() {
    this.persistDraft()
  },

  onUnload() {
    this.persistDraft()
  },

  applyGuestState() {
    this.setData({
      guestMode: true,
      user: {},
      inviteInfo: createEmptyInviteInfo(),
      creditChipText: buildCreditChipText(null, true),
      ...buildQuotaView({}),
    })
  },

  getDraftPayload() {
    return {
      selectedTaskType: this.data.selectedTaskType,
      selectedPlatform: this.data.selectedPlatform,
      paperPath: this.data.paperPath,
      paperName: this.data.paperName,
      paperTitle: this.data.paperTitle,
      authors: this.data.authors,
    }
  },

  persistDraft() {
    const payload = this.getDraftPayload()
    const hasValue = Object.keys(payload).some((key) => String(payload[key] || "").trim())
    if (!hasValue) {
      clearHomeDraft()
      return
    }
    setHomeDraft(payload)
  },

  restoreDraft() {
    const draft = getHomeDraft()
    if (!draft) return
    this.setData({
      selectedTaskType: draft.selectedTaskType || this.data.selectedTaskType,
      selectedPlatform: draft.selectedPlatform || this.data.selectedPlatform,
      paperPath: draft.paperPath || "",
      paperName: draft.paperName || "",
      paperTitle: draft.paperTitle || "",
      authors: draft.authors || "",
    })
  },

  consumePendingAction() {
    const pending = getPendingAuth()
    if (!pending || pending.targetTab !== "home") return

    clearPendingAuth()

    if (pending.action === "choose_file") {
      wx.nextTick(() => this.chooseFileDirect())
      return
    }

    if (pending.action === "copy_invite") {
      wx.nextTick(() => this.onCopyInviteCode())
      return
    }

    if (pending.action === "submit_task") {
      wx.showToast({ title: "已登录，请继续提交任务", icon: "none" })
      return
    }

    if (pending.action === "session_expired") {
      wx.showToast({ title: "登录状态已更新，请继续操作", icon: "none" })
    }
  },

  syncSelectedMeta() {
    const selectedTaskMeta =
      TASK_OPTIONS.find((item) => item.value === this.data.selectedTaskType) || TASK_OPTIONS[0]
    const platformOptions = getPlatformOptions(this.data.selectedTaskType)

    let selectedPlatform = this.data.selectedPlatform || "cnki"
    if (!platformOptions.some((item) => item.value === selectedPlatform)) {
      selectedPlatform = platformOptions[0] ? platformOptions[0].value : "cnki"
    }

    const selectedPlatformMeta =
      platformOptions.find((item) => item.value === selectedPlatform) || platformOptions[0]

    this.setData({
      platformOptions,
      selectedTaskMeta,
      selectedPlatform,
      selectedPlatformMeta,
      uploadRuleText: selectedTaskMeta.uploadHint,
    })
  },

  async reloadProfile() {
    try {
      const profile = await request({ url: "/users/me", method: "GET", silent: true })
      if (!profile) return

      this.setData({
        user: profile,
        creditChipText: buildCreditChipText(profile, false),
      })
      setUser(profile)
    } catch (_) {
      // keep current UI state
    }
  },

  async loadInviteInfo() {
    try {
      const inviteInfo = await request({ url: "/users/me/invite-code", method: "GET", silent: true })
      this.setData({
        inviteInfo: {
          inviteCode: String(inviteInfo.invite_code || "").trim(),
          inviteLink: String(inviteInfo.invite_link || "").trim(),
        },
      })
    } catch (_) {
      // keep invite area quiet if endpoint fails
    }
  },

  async loadSummary() {
    try {
      const summary = await request({ url: "/users/me/summary", method: "GET", silent: true })
      this.setData(buildQuotaView((summary && summary.aigc_quota) || {}))
    } catch (_) {
      this.setData(buildQuotaView({}))
    }
  },

  onSelectTaskType(e) {
    this.setData({ selectedTaskType: e.currentTarget.dataset.value || "aigc_detect" })
    this.syncSelectedMeta()
    this.persistDraft()
  },

  onSelectPlatform(e) {
    this.setData({ selectedPlatform: e.currentTarget.dataset.value || "cnki" })
    this.syncSelectedMeta()
    this.persistDraft()
  },

  onInputPaperTitle(e) {
    this.setData({ paperTitle: (e.detail.value || "").trim() })
    this.persistDraft()
  },

  onInputAuthors(e) {
    this.setData({ authors: (e.detail.value || "").trim() })
    this.persistDraft()
  },

  validateFile(file) {
    if (!file || !file.path) return "请选择正文文件"
    const ext = file.name && file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")).toLowerCase() : ""
    const allowed = getAllowedExtensions(this.data.selectedTaskType)
    if (!allowed.includes(ext)) {
      return `当前服务仅支持 ${allowed.join(" / ")} 文件`
    }
    if (Number(file.size || 0) > MAX_FILE_SIZE) {
      return "文件超过 20MB 限制"
    }
    return ""
  },

  chooseFileDirect() {
    wx.chooseMessageFile({
      count: 1,
      type: "file",
      success: (res) => {
        const file = (res.tempFiles || [])[0]
        if (!file) return

        const errorMessage = this.validateFile(file)
        if (errorMessage) {
          wx.showToast({ title: errorMessage, icon: "none" })
          return
        }

        const nextName = file.name || getFilename(file.path)
        const nextTitle = this.data.paperTitle.trim() || deriveTitleFromFilename(nextName)

        this.setData({
          paperPath: file.path,
          paperName: nextName,
          paperTitle: nextTitle,
        })
        this.persistDraft()
      },
      fail: () => {
        wx.showToast({ title: "文件选择失败", icon: "none" })
      },
    })
  },

  onChooseFile() {
    this.persistDraft()
    if (!requireAuth({ targetTab: "home", action: "choose_file" })) return
    this.chooseFileDirect()
  },

  onCopyInviteCode() {
    if (!ensureLogin()) {
      if (!requireAuth({ targetTab: "home", action: "copy_invite" })) return
    }
    const inviteCode = String(this.data.inviteInfo.inviteCode || "").trim()
    if (!inviteCode) {
      wx.showToast({ title: "邀请码暂未生成", icon: "none" })
      return
    }
    wx.setClipboardData({
      data: inviteCode,
      success: () => wx.showToast({ title: "邀请码已复制", icon: "success" }),
      fail: () => wx.showToast({ title: "复制失败", icon: "none" }),
    })
  },

  resetForm() {
    this.setData({
      paperTitle: "",
      authors: "",
      paperPath: "",
      paperName: "",
    })
    clearHomeDraft()
  },

  showLongMessage(title, content, callback) {
    wx.showModal({
      title,
      content,
      showCancel: false,
      success: () => {
        if (typeof callback === "function") {
          callback()
        }
      },
    })
  },

  async onSubmitTask() {
    if (this.data.submitting) return
    this.persistDraft()

    if (!requireAuth({ targetTab: "home", action: "submit_task" })) return

    const file = {
      path: this.data.paperPath,
      name: this.data.paperName,
    }
    const fileError = this.validateFile(file)
    if (fileError) {
      wx.showToast({ title: fileError, icon: "none" })
      return
    }
    if (!this.data.paperTitle.trim()) {
      wx.showToast({ title: "请填写篇名", icon: "none" })
      return
    }
    if (!this.data.authors.trim()) {
      wx.showToast({ title: "请填写作者", icon: "none" })
      return
    }

    this.setData({ submitting: true })
    const submittedAt = Date.now()

    try {
      const result = await uploadFile({
        url: "/tasks/submit",
        filePath: this.data.paperPath,
        name: "paper",
        formData: {
          task_type: this.data.selectedTaskType,
          platform: this.data.selectedPlatform,
          paper_title: this.data.paperTitle.trim(),
          authors: this.data.authors.trim(),
        },
      })

      this.resetForm()
      await Promise.all([this.reloadProfile(), this.loadSummary()])
      wx.switchTab({ url: "/pages/records/index" })
    } catch (error) {
      if (isTaskSubmitRecoverableError(error)) {
        const recoveredTask = await recoverSubmittedTask({
          taskType: this.data.selectedTaskType,
          paperTitle: this.data.paperTitle.trim(),
          authors: this.data.authors.trim(),
          sourceFilename: this.data.paperName,
          submittedAt,
        })

        if (recoveredTask && recoveredTask.id) {
          await Promise.all([this.reloadProfile(), this.loadSummary()])
          wx.switchTab({ url: "/pages/records/index" })
          return
        }
      }

      this.showLongMessage("提交失败", getTaskSubmitFallbackMessage(error, this.data.selectedTaskType))
    } finally {
      this.setData({ submitting: false })
    }
  },

  onShareAppMessage() {
    const inviteCode = String(this.data.inviteInfo.inviteCode || "").trim()
    const query = inviteCode ? `?ref=${encodeURIComponent(inviteCode)}` : ""
    return {
      title: "格物学术 | 检测、降AIGC与降重",
      path: `/pages/home/index${query}`,
    }
  },
})
