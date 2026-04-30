const { request } = require("../../utils/request")
const { loginWithMiniProgram, loginWithMiniProgramInternalTest, loginWithMiniProgramPhone, ensureLogin } = require("../../utils/auth")
const { finishLoginNavigation, getPendingAuth } = require("../../utils/authFlow")
const { getReferrerCode, setReferrerCode, clearReferrerCode } = require("../../utils/storage")

const DEFAULT_RUNTIME_COPY = {
  login: {
    brand_name: "格物学术",
    brand_subtitle: "论文检测与处理服务",
    agreement_text: "我已阅读并同意服务协议与隐私条款",
    login_unavailable_title: "暂时无法完成登录",
    login_unavailable_desc: "当前登录服务正在维护，请稍后重试或联系管理员处理。",
    formal_mode_label: "当前为正式微信登录",
    internal_test_mode_label: "当前为内测登录",
    mock_mode_label: "当前为本地开发调试登录",
    prefer_phone_title: "请使用手机号快捷登录",
    prefer_phone_content: "为了统一 Web 端和小程序端账号、积分、订单和邀请关系，正式环境请优先使用微信手机号快捷登录。",
    policy_required_title: "请先同意协议",
    policy_required_content: "继续登录前，请先勾选左侧同意框，并完成隐私授权。",
    phone_auth_missing_title: "未完成授权",
  },
}

function pickText(value, fallback = "") {
  const text = String(value || "").trim()
  return text && !looksLikeMojibake(text) ? text : fallback
}

function looksLikeMojibake(text) {
  if (!text) return false
  const suspiciousTokens = ["æ", "ç", "è", "é", "å", "ä", "ã", "ï¼", "�"]
  if (suspiciousTokens.some((token) => text.includes(token))) return true
  const latin1Count = Array.from(text).filter((char) => char >= "\u00c0" && char <= "\u00ff").length
  return latin1Count >= 2 && latin1Count / Math.max(text.length, 1) > 0.1
}

function sanitizeReviewText(value, fallback = "") {
  const text = pickText(value, fallback)
  if (!text) return fallback
  const riskyWords = ["AppSecret", "生产环境", "未配置", "暂未开通", "微信学术工作台"]
  if (riskyWords.some((word) => text.includes(word))) {
    return fallback
  }
  return text
}

function normalizeRuntimeCopy(raw) {
  const source = raw && typeof raw === "object" ? raw : {}
  const login = source.login && typeof source.login === "object" ? source.login : {}
  return {
    login: {
      brand_name: sanitizeReviewText(login.brand_name, DEFAULT_RUNTIME_COPY.login.brand_name),
      brand_subtitle: sanitizeReviewText(login.brand_subtitle, DEFAULT_RUNTIME_COPY.login.brand_subtitle),
      agreement_text: pickText(login.agreement_text, DEFAULT_RUNTIME_COPY.login.agreement_text),
      login_unavailable_title: sanitizeReviewText(login.login_unavailable_title, DEFAULT_RUNTIME_COPY.login.login_unavailable_title),
      login_unavailable_desc: sanitizeReviewText(login.login_unavailable_desc, DEFAULT_RUNTIME_COPY.login.login_unavailable_desc),
      formal_mode_label: sanitizeReviewText(login.formal_mode_label, DEFAULT_RUNTIME_COPY.login.formal_mode_label),
      internal_test_mode_label: sanitizeReviewText(login.internal_test_mode_label, DEFAULT_RUNTIME_COPY.login.internal_test_mode_label),
      mock_mode_label: sanitizeReviewText(login.mock_mode_label, DEFAULT_RUNTIME_COPY.login.mock_mode_label),
      prefer_phone_title: pickText(login.prefer_phone_title, DEFAULT_RUNTIME_COPY.login.prefer_phone_title),
      prefer_phone_content: pickText(login.prefer_phone_content, DEFAULT_RUNTIME_COPY.login.prefer_phone_content),
      policy_required_title: pickText(login.policy_required_title, DEFAULT_RUNTIME_COPY.login.policy_required_title),
      policy_required_content: pickText(login.policy_required_content, DEFAULT_RUNTIME_COPY.login.policy_required_content),
      phone_auth_missing_title: pickText(login.phone_auth_missing_title, DEFAULT_RUNTIME_COPY.login.phone_auth_missing_title),
    },
  }
}

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

  if (errMsg.includes("privacy") || errMsg.includes("agree")) {
    return "请先同意微信隐私授权后再继续登录"
  }
  if (errno === 1400001) {
    return "当前小程序手机号快捷验证暂不可用，请稍后重试"
  }
  if (errMsg.includes("cancel") || errMsg.includes("deny")) {
    return "你已取消手机号授权，请重新授权后继续"
  }
  return "未拿到手机号授权，请重试"
}

function getPrivacyAuthorizationErrorMessage(err) {
  const errMsg = String(err && err.errMsg ? err.errMsg : "").trim().toLowerCase()
  if (!errMsg) return "请先完成微信隐私授权"
  if (errMsg.includes("cancel")) return "你已取消微信隐私授权，请重新确认"
  if (errMsg.includes("deny") || errMsg.includes("disagree")) return "你还没有同意微信隐私授权，请重新确认"
  if (errMsg.includes("privacyagreement")) return "小程序隐私声明未完整配置，当前微信授权未生效"
  return "请先完成微信隐私授权"
}

function isPrivacyAuthorizationAccepted(detail = {}) {
  const errMsg = String(detail && detail.errMsg ? detail.errMsg : "").trim().toLowerCase()
  if (!errMsg) return true
  return errMsg.endsWith(":ok") || errMsg === "ok"
}

Page({
  data: {
    loading: false,
    referrerCode: "",
    agreedPolicy: false,
    loginTitle: "微信登录",
    loginDesc: "",
    miniProgramLoginReady: false,
    miniProgramInternalTestReady: false,
    phoneQuickLoginReady: false,
    miniProgramMockReady: false,
    loginModeLabel: "",
    loginAvailable: false,
    loginUnavailableTitle: "暂时无法完成登录",
    loginUnavailableDesc: "当前登录服务正在维护，请稍后重试或联系管理员处理。",
    loginLoadFailed: false,
    primaryLoginMode: "wechat",
    phoneQuickLoginFailed: false,
    showWeChatLoginButton: false,
    wechatPrivacyReady: false,
    needWechatPrivacyAuthorization: true,
    runtimeCopy: DEFAULT_RUNTIME_COPY,
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
    this.loadPrivacySetting()
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

  loadPrivacySetting() {
    if (typeof wx.getPrivacySetting !== "function") {
      this.setData({
        wechatPrivacyReady: true,
        needWechatPrivacyAuthorization: false,
      })
      return
    }
    wx.getPrivacySetting({
      success: (res) => {
        const needAuthorization = !!res.needAuthorization
        this.setData({
          wechatPrivacyReady: !needAuthorization,
          needWechatPrivacyAuthorization: needAuthorization,
        })
      },
      fail: () => {
        this.setData({
          wechatPrivacyReady: false,
          needWechatPrivacyAuthorization: true,
        })
      },
    })
  },

  onTogglePolicy() {
    this.setData({ agreedPolicy: !this.data.agreedPolicy })
  },

  markPolicyAgreed() {
    if (this.data.agreedPolicy) return
    this.setData({ agreedPolicy: true })
  },

  onAgreePrivacyAuthorization(e) {
    const detail = (e && e.detail) || {}
    if (!isPrivacyAuthorizationAccepted(detail)) {
      wx.showModal({
        title: "需要微信隐私授权",
        content: getPrivacyAuthorizationErrorMessage(detail),
        showCancel: false,
      })
      return
    }
    this.setData({
      agreedPolicy: true,
      wechatPrivacyReady: true,
      needWechatPrivacyAuthorization: false,
    })
    this.loadPrivacySetting()
  },

  ensureWechatPrivacyReady(action = "login", onGranted) {
    if (typeof onGranted !== "function") return
    if (this.data.wechatPrivacyReady && !this.data.needWechatPrivacyAuthorization) {
      onGranted()
      return
    }
    const app = getApp()
    if (app && typeof app.ensurePrivacyAuthorization === "function") {
      app.ensurePrivacyAuthorization((granted, err) => {
        if (!granted) {
          wx.showModal({
            title: "请先同意微信隐私授权",
            content: getPrivacyAuthorizationErrorMessage(err),
            showCancel: false,
          })
          return
        }
        this.setData({
          agreedPolicy: true,
          wechatPrivacyReady: true,
          needWechatPrivacyAuthorization: false,
        })
        onGranted()
      })
      return
    }
    onGranted()
  },

  openTermsPage() {
    this.markPolicyAgreed()
    wx.navigateTo({ url: "/pages/legal/terms/index" })
  },

  openPrivacyPage() {
    this.markPolicyAgreed()
    const app = getApp()
    if (app && typeof app.openPrivacyContract === "function") {
      app.openPrivacyContract()
      return
    }
    wx.navigateTo({ url: "/pages/legal/privacy/index" })
  },

  async loadAuthOptions() {
    const canUsePhoneNumber =
      typeof wx.canIUse === "function" ? wx.canIUse("button.open-type.getPhoneNumber") : true

    try {
      const data = await request({ url: "/auth/options", method: "GET", silent: true })
      const miniProgramLoginReady = !!(data && data.wechat_miniprogram_login_enabled)
      const miniProgramInternalTestReady = !!(data && data.miniapp_internal_test_login_enabled)
      const miniProgramMockReady = !!(data && data.wx_mock_enabled) && !miniProgramInternalTestReady
      const phoneQuickLoginReady =
        miniProgramLoginReady && canUsePhoneNumber && !!(data && data.wechat_miniprogram_phone_quick_login_enabled)
      const loginAvailable = miniProgramLoginReady || miniProgramInternalTestReady || miniProgramMockReady
      const showWeChatLoginButton = !!(
        this.data.loginLoadFailed ||
        miniProgramMockReady ||
        miniProgramInternalTestReady ||
        (miniProgramLoginReady && !phoneQuickLoginReady)
      )
      let loginModeLabel = ""
      if (miniProgramMockReady) {
        loginModeLabel = pickText(data?.miniapp_runtime?.login?.mock_mode_label, DEFAULT_RUNTIME_COPY.login.mock_mode_label)
      } else if (phoneQuickLoginReady) {
        loginModeLabel = pickText(data?.miniapp_runtime?.login?.formal_mode_label, DEFAULT_RUNTIME_COPY.login.formal_mode_label)
      } else if (miniProgramInternalTestReady) {
        loginModeLabel = pickText(data?.miniapp_runtime?.login?.internal_test_mode_label, DEFAULT_RUNTIME_COPY.login.internal_test_mode_label)
      }
      const runtimeCopy = normalizeRuntimeCopy(data && data.miniapp_runtime)
      let loginUnavailableTitle = runtimeCopy.login.login_unavailable_title
      let loginUnavailableDesc = runtimeCopy.login.login_unavailable_desc
      if (miniProgramInternalTestReady) {
        loginUnavailableTitle = "已切到小程序内测登录"
        loginUnavailableDesc = "当前版本正在进行体验验证，可继续使用当前登录入口完成流程体验。"
      } else if (miniProgramLoginReady && !phoneQuickLoginReady && !miniProgramMockReady) {
        loginUnavailableTitle = "当前环境不支持手机号快捷验证"
        loginUnavailableDesc = canUsePhoneNumber
          ? "当前小程序登录要求使用微信手机号快速验证组件，请检查配置后重试。"
          : "请升级微信客户端后，再使用微信手机号快速验证组件完成登录。"
      }
      this.setData({
        miniProgramLoginReady,
        miniProgramInternalTestReady,
        miniProgramMockReady,
        loginAvailable,
        loginLoadFailed: false,
        phoneQuickLoginReady,
        loginModeLabel,
        runtimeCopy,
        phoneQuickLoginFailed: false,
        loginUnavailableTitle,
        loginUnavailableDesc,
        primaryLoginMode: phoneQuickLoginReady ? "phone" : "wechat",
        showWeChatLoginButton,
      })
    } catch (_) {
      this.setData({
        miniProgramLoginReady: false,
        miniProgramInternalTestReady: false,
        phoneQuickLoginReady: false,
        miniProgramMockReady: false,
        loginAvailable: false,
        loginLoadFailed: true,
        loginModeLabel: "",
        loginUnavailableTitle: "登录配置加载失败",
        loginUnavailableDesc: "当前网络连接异常，请稍后重试。",
        primaryLoginMode: "wechat",
        showWeChatLoginButton: true,
        runtimeCopy: DEFAULT_RUNTIME_COPY,
      })
    }
  },

  async onTapWeChatLogin() {
    if (this.data.loading) return
    if (this.data.loginLoadFailed) {
      this.setData({ loading: true })
      try {
        await this.loadAuthOptions()
      } finally {
        this.setData({ loading: false })
      }
      if (this.data.loginLoadFailed) {
        wx.showModal({
          title: this.data.loginUnavailableTitle,
          content: this.data.loginUnavailableDesc,
          showCancel: false,
        })
      }
      return
    }
    if (this.data.phoneQuickLoginReady && !this.data.showWeChatLoginButton) {
      wx.showModal({
        title: this.data.runtimeCopy.login.prefer_phone_title,
        content: this.data.runtimeCopy.login.prefer_phone_content,
        showCancel: false,
      })
      return
    }
    if (!this.data.loginAvailable) {
      wx.showModal({
        title: this.data.loginUnavailableTitle,
        content: this.data.loginUnavailableDesc,
        showCancel: false,
      })
      return
    }
    if (!this.data.agreedPolicy) {
      wx.showModal({
        title: this.data.runtimeCopy.login.policy_required_title,
        content: this.data.runtimeCopy.login.policy_required_content,
        showCancel: false,
      })
      return
    }
    const proceed = async () => {
      this.setData({ loading: true })
      try {
        if (this.data.miniProgramLoginReady) {
          await loginWithMiniProgram({ referrerCode: this.data.referrerCode })
        } else {
          await loginWithMiniProgramInternalTest({ referrerCode: this.data.referrerCode })
        }
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
    }
    this.ensureWechatPrivacyReady("login", () => {
      void proceed()
    })
  },

  async onTapPhoneQuickLogin(e) {
    if (this.data.loading) return
    if (!this.data.phoneQuickLoginReady) {
      wx.showModal({
        title: this.data.loginUnavailableTitle,
        content: this.data.loginUnavailableDesc,
        showCancel: false,
      })
      return
    }
    if (!this.data.agreedPolicy) {
      wx.showModal({
        title: this.data.runtimeCopy.login.policy_required_title,
        content: this.data.runtimeCopy.login.policy_required_content,
        showCancel: false,
      })
      return
    }

    const detail = (e && e.detail) || {}
    console.info("[miniapp-login] getPhoneNumber detail", detail)
    if (String(detail.errMsg || "").toLowerCase().includes("privacy")) {
      this.ensureWechatPrivacyReady("phone", () => {
        wx.showToast({ title: "请再点一次登录", icon: "none" })
      })
      return
    }
    const phoneCode = String(detail.code || "").trim()
    if (!phoneCode) {
      this.setData({ phoneQuickLoginFailed: true })
      wx.showModal({
        title: this.data.runtimeCopy.login.phone_auth_missing_title,
        content: getPhoneQuickLoginError(detail),
        showCancel: false,
      })
      return
    }
    const proceed = async () => {
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
    }
    void proceed()
  },
})
