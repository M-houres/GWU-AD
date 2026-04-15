const { request } = require("../../utils/request")
const { loginWithMiniProgram, loginWithMiniProgramPhone, ensureLogin } = require("../../utils/auth")
const { finishLoginNavigation, getPendingAuth } = require("../../utils/authFlow")
const { getReferrerCode, setReferrerCode, clearReferrerCode } = require("../../utils/storage")

function getLoginCopy(pending = {}) {
  switch (pending.action) {
    case "choose_file":
      return {
        title: "登录后继续上传文件",
        desc: "为了继续从微信聊天记录选择文件，需要先完成账号登录。",
      }
    case "submit_task":
      return {
        title: "登录后继续提交任务",
        desc: "登录后会保留你刚才已填写的内容，可继续完成任务提交。",
      }
    case "create_order":
      return {
        title: "登录后继续充值",
        desc: "登录成功后会回到刚才选择的套餐，并继续当前充值动作。",
      }
    case "open_records":
      return {
        title: "登录后查看任务记录",
        desc: "登录后可查看检测、降AIGC和降重任务的完整处理链路。",
      }
    case "copy_invite":
      return {
        title: "登录后生成邀请码",
        desc: "邀请码和邀请链接会在登录后自动生成，并记录邀请关系。",
      }
    case "session_expired":
      return {
        title: "登录状态已失效",
        desc: "请重新完成微信登录，系统会带你回到刚才的操作位置。",
      }
    default:
      return {
        title: "微信登录",
        desc: "",
      }
  }
}

function getPhoneQuickLoginError(detail = {}) {
  const errno = Number(detail.errno || 0)
  const errMsg = String(detail.errMsg || "").toLowerCase()

  if (errno === 1400001) {
    return "当前小程序手机号快捷登录次数不足，请先使用微信一键登录"
  }
  if (errMsg.includes("cancel") || errMsg.includes("deny")) {
    return "你已取消手机号授权，可改用微信一键登录"
  }
  return "未拿到手机号授权，请重试或改用微信一键登录"
}

Page({
  data: {
    loading: false,
    referrerCode: "",
    agreedPolicy: false,
    loginTitle: "微信登录",
    loginDesc: "",
    phoneQuickLoginReady: false,
  },

  onLoad(options = {}) {
    const pending = getPendingAuth() || {}
    const copy = getLoginCopy(pending)
    const sharedRef = String(options.ref || options.invite_code || getReferrerCode()).trim().toUpperCase()
    if (sharedRef) {
      setReferrerCode(sharedRef)
    }
    this.setData({
      referrerCode: sharedRef,
      loginTitle: copy.title,
      loginDesc: copy.desc,
    })
    this.loadAuthOptions()
  },

  onShow() {
    if (ensureLogin()) {
      finishLoginNavigation()
    }
  },

  onInputReferrer(e) {
    const referrerCode = String(e.detail.value || "").trim().toUpperCase()
    this.setData({ referrerCode })
    setReferrerCode(referrerCode)
  },

  onTogglePolicy() {
    this.setData({ agreedPolicy: !this.data.agreedPolicy })
  },

  async loadAuthOptions() {
    const canUsePhoneNumber =
      typeof wx.canIUse === "function" ? wx.canIUse("button.open-type.getPhoneNumber") : true

    try {
      const data = await request({ url: "/auth/options", method: "GET", silent: true })
      this.setData({
        phoneQuickLoginReady:
          canUsePhoneNumber && !!(data && data.wechat_miniprogram_phone_quick_login_enabled),
      })
    } catch (_) {
      this.setData({ phoneQuickLoginReady: false })
    }
  },

  async onTapWeChatLogin() {
    if (this.data.loading) return
    if (!this.data.agreedPolicy) {
      wx.showModal({
        title: "请先同意协议",
        content: "继续登录前，请先勾选服务协议与隐私条款。",
        showCancel: false,
      })
      return
    }
    this.setData({ loading: true })
    try {
      await loginWithMiniProgram({ referrerCode: this.data.referrerCode })
      clearReferrerCode()
      wx.showToast({ title: "登录成功", icon: "success" })
      finishLoginNavigation()
    } catch (error) {
      wx.showModal({
        title: "登录失败",
        content: error.message || "请稍后重试",
        showCancel: false,
      })
    } finally {
      this.setData({ loading: false })
    }
  },

  async onTapPhoneQuickLogin(e) {
    if (this.data.loading) return
    if (!this.data.agreedPolicy) {
      wx.showModal({
        title: "请先同意协议",
        content: "继续登录前，请先勾选服务协议与隐私条款。",
        showCancel: false,
      })
      return
    }

    const phoneCode = String((e && e.detail && e.detail.code) || "").trim()
    if (!phoneCode) {
      wx.showModal({
        title: "未完成授权",
        content: getPhoneQuickLoginError((e && e.detail) || {}),
        showCancel: false,
      })
      return
    }

    this.setData({ loading: true })
    try {
      await loginWithMiniProgramPhone({
        phoneCode,
        referrerCode: this.data.referrerCode,
      })
      clearReferrerCode()
      wx.showToast({ title: "登录成功", icon: "success" })
      finishLoginNavigation()
    } catch (error) {
      wx.showModal({
        title: "登录失败",
        content: error.message || "请稍后重试",
        showCancel: false,
      })
    } finally {
      this.setData({ loading: false })
    }
  },
})
