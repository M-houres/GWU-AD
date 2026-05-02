const { request, uploadFile } = require("../../utils/request")
const { ensureLogin } = require("../../utils/auth")
const { requireAuth } = require("../../utils/authFlow")
const { getUser, setUser } = require("../../utils/storage")
const env = require("../../config/env")

const TAB_CONTENT_KEYS = ["invite", "like", "create", "partner"]

function createDefaultPromoConfig() {
  return {
    enabled: true,
    nav_cards: [],
    pages: {
      invite: {
        title: "邀请有奖",
        subtitle: "",
        rule_lines: [],
        quick_actions_title: "快捷操作",
        bind_code_label: "填写邀请码",
        bind_code_placeholder: "请输入好友邀请码",
        bind_code_button_text: "绑定邀请码",
        share_copy_title: "分享文案",
        share_copy_text: "",
        miniapp_guide_title: "邀请步骤",
        miniapp_steps: [],
      },
      partner: {
        title: "渠道合作",
        subtitle: "",
        description: "",
        benefits: [],
        contacts: [],
      },
    },
    reward_rules: {
      invite: {
        invitee_bind_reward_points: 0,
        inviter_valid_invite_reward_points: 0,
        milestones: [],
      },
      like: {
        tiers: [],
      },
      create: {
        tiers: [],
      },
    },
  }
}

function createEmptyInviteState() {
  return {
    inviteCode: "",
    inviteLink: "",
    boundRelation: null,
    validInviteCount: 0,
    totalRewardPoints: 0,
    inviteeRewardPoints: 0,
    inviterRewardPoints: 0,
    nextMilestoneLabel: "暂无",
    nextMilestoneHint: "活动配置更新后会在这里显示",
    earnedMilestones: [],
  }
}

function toArray(value) {
  return Array.isArray(value) ? value : []
}

function formatPoints(value = 0) {
  return `${Number(value || 0)}积分`
}

function formatInviteMilestone(item = {}) {
  const threshold = Math.max(Number(item.threshold || 0), 0)
  const rewardPoints = Math.max(Number(item.reward_points || 0), 0)
  if (!threshold || !rewardPoints) return ""
  return `满${threshold}人额外+${rewardPoints}积分`
}

function formatTierLabel(item = {}, zeroLabel = "参与即得") {
  const threshold = Math.max(Number(item.threshold || 0), 0)
  const rewardPoints = Math.max(Number(item.reward_points || 0), 0)
  if (!rewardPoints) return ""
  if (!threshold) return `${zeroLabel}${rewardPoints}积分`
  return `${threshold}赞${rewardPoints}积分`
}

function formatCreateTierBusinessLabel(item = {}) {
  const threshold = Math.max(Number(item.threshold || 0), 0)
  const rewardPoints = Math.max(Number(item.reward_points || 0), 0)
  const fallback = rewardPoints ? `${rewardPoints}积分` : "奖励待配置"
  if (!threshold) return rewardPoints ? `发布通过可得${rewardPoints}积分` : fallback
  return rewardPoints ? `达到${threshold}赞可得${rewardPoints}积分` : fallback
}

function createFallbackCards() {
  return [
    { key: "invite", title: "邀请有奖", badge: "推荐", sort_order: 1 },
    { key: "like", title: "集赞有奖", badge: "活动", sort_order: 2 },
    { key: "create", title: "创作有奖", badge: "活动", sort_order: 3 },
    { key: "partner", title: "渠道合作", badge: "合作", sort_order: 4 },
  ]
}

function getSiteBaseUrl() {
  const apiBaseUrl = String(env.apiBaseUrl || "").trim()
  if (!apiBaseUrl) return ""
  return apiBaseUrl.replace(/\/api\/v1\/?$/i, "")
}

function resolveAssetUrl(value = "") {
  const raw = String(value || "").trim()
  if (!raw) return ""
  if (/^https?:\/\//i.test(raw)) return raw
  if (!raw.startsWith("/")) return ""
  const siteBaseUrl = getSiteBaseUrl()
  return siteBaseUrl ? `${siteBaseUrl}${raw}` : ""
}

function normalizePromoConfig(raw = {}) {
  const defaults = createDefaultPromoConfig()
  const pages = raw && raw.pages ? raw.pages : {}
  const rewardRules = raw && raw.reward_rules ? raw.reward_rules : {}
  return {
    enabled: raw && raw.enabled !== false,
    nav_cards: toArray(raw && raw.nav_cards).length ? toArray(raw.nav_cards) : createFallbackCards(),
    pages: {
      invite: {
        ...defaults.pages.invite,
        ...(pages.invite || {}),
        rule_lines: toArray(pages.invite && pages.invite.rule_lines),
        miniapp_steps: toArray(pages.invite && pages.invite.miniapp_steps),
      },
      like: {
        ...(pages.like || {}),
        rule_lines: toArray(pages.like && pages.like.rule_lines),
      },
      create: {
        ...(pages.create || {}),
        rule_lines: toArray(pages.create && pages.create.rule_lines),
      },
      partner: {
        ...defaults.pages.partner,
        ...(pages.partner || {}),
        benefits: toArray(pages.partner && pages.partner.benefits),
        contacts: toArray(pages.partner && pages.partner.contacts)
          .filter((item) => item && item.enabled !== false)
          .map((item) => ({
            ...item,
            qrcode_url_resolved: resolveAssetUrl(item.qrcode_url),
          })),
      },
    },
    reward_rules: {
      invite: {
        ...defaults.reward_rules.invite,
        ...(rewardRules.invite || {}),
        milestones: toArray(rewardRules.invite && rewardRules.invite.milestones),
      },
      like: {
        ...defaults.reward_rules.like,
        ...(rewardRules.like || {}),
        tiers: toArray(rewardRules.like && rewardRules.like.tiers).map((item, index) => ({
          ...item,
          tier_key: String(item && (item.key || item.tier_key) ? item.key || item.tier_key : `like-tier-${index + 1}`),
          display_label: String(item && item.label ? item.label : `${Number(item && item.threshold ? item.threshold : 0)}赞`),
        })),
      },
      create: {
        ...defaults.reward_rules.create,
        ...(rewardRules.create || {}),
        tiers: toArray(rewardRules.create && rewardRules.create.tiers).map((item, index) => ({
          ...item,
          tier_key: String(item && (item.key || item.tier_key) ? item.key || item.tier_key : `tier-${index + 1}`),
          display_label: String(item && item.label ? item.label : (Number(item && item.threshold ? item.threshold : 0) ? `${Number(item.threshold)}赞` : "发帖即得")),
          business_label: formatCreateTierBusinessLabel(item),
        })),
      },
    },
  }
}

function buildInviteState(inviteInfo = {}, promoConfig = createDefaultPromoConfig()) {
  const summary = inviteInfo && inviteInfo.invite_summary ? inviteInfo.invite_summary : {}
  const nextMilestone = summary && summary.next_milestone ? summary.next_milestone : null
  const inviteRules = promoConfig.reward_rules && promoConfig.reward_rules.invite ? promoConfig.reward_rules.invite : {}
  return {
    inviteCode: String(inviteInfo.invite_code || "").trim(),
    inviteLink: String(inviteInfo.invite_link || "").trim(),
    boundRelation: inviteInfo.bound_relation || null,
    validInviteCount: Number(summary.valid_invite_count || 0),
    totalRewardPoints: Number(summary.total_reward_points || 0),
    inviteeRewardPoints: Number(inviteRules.invitee_bind_reward_points || 0),
    inviterRewardPoints: Number(inviteRules.inviter_valid_invite_reward_points || 0),
    nextMilestoneLabel: nextMilestone && nextMilestone.label ? String(nextMilestone.label).trim() : "暂无",
    nextMilestoneHint: nextMilestone
      ? `再邀请 ${Math.max(Number(nextMilestone.remaining_count || 0), 0)} 人可解锁 ${nextMilestone.reward_points || 0} 积分`
      : "当前已到最高档，继续邀请仍可累计有效人数",
    earnedMilestones: toArray(summary.earned_milestones),
  }
}

function buildCardHighlights(key, promoConfig, inviteState) {
  const inviteRules = promoConfig.reward_rules.invite || {}
  const likeRules = promoConfig.reward_rules.like || {}
  const createRules = promoConfig.reward_rules.create || {}
  const partnerPage = promoConfig.pages.partner || {}

  if (key === "invite") {
    const firstMilestone = toArray(inviteRules.milestones)[0] || {}
    return [
      { label: "每邀1人", value: formatPoints(inviteRules.inviter_valid_invite_reward_points || 0) },
      { label: "满员加奖", value: formatInviteMilestone(firstMilestone) || "按配置发放" },
    ]
  }

  if (key === "like") {
    const tiers = toArray(likeRules.tiers)
    return [
      { label: "首档奖励", value: formatTierLabel(tiers[0], "参与即得") || "后台配置" },
      { label: "最高奖励", value: formatTierLabel(tiers[tiers.length - 1], "参与即得") || "后台配置" },
    ]
  }

  if (key === "create") {
    const tiers = toArray(createRules.tiers)
    return [
      { label: "起步奖励", value: (tiers[0] && tiers[0].business_label) || "后台配置" },
      { label: "最高奖励", value: (tiers[tiers.length - 1] && tiers[tiers.length - 1].business_label) || "后台配置" },
    ]
  }

  const contacts = toArray(partnerPage.contacts).filter((item) => item && item.enabled !== false)
  return [
    { label: "联系入口", value: `${contacts.length}个` },
    { label: "合作场景", value: contacts[0] && contacts[0].title ? String(contacts[0].title).trim() : "校园 / 机构" },
  ]
}

function buildEnabledCards(promoConfig, inviteState) {
  const rawCards = toArray(promoConfig.nav_cards)
    .filter((item) => item && item.enabled !== false && TAB_CONTENT_KEYS.includes(String(item.key || "").trim()))
    .sort((a, b) => Number(a.sort_order || 0) - Number(b.sort_order || 0))

  return rawCards.map((item) => ({
    key: String(item.key || "").trim(),
    title: String(item.title || "").trim(),
    badge: String(item.badge || "").trim(),
    highlights: buildCardHighlights(String(item.key || "").trim(), promoConfig, inviteState),
  }))
}

function buildHeroCard(activeTab, promoConfig, inviteState) {
  const invitePage = promoConfig.pages.invite || {}
  const likePage = promoConfig.pages.like || {}
  const createPage = promoConfig.pages.create || {}
  const partnerPage = promoConfig.pages.partner || {}
  const inviteRules = promoConfig.reward_rules.invite || {}
  const likeRules = promoConfig.reward_rules.like || {}
  const createRules = promoConfig.reward_rules.create || {}

  if (activeTab === "invite") {
    const firstMilestone = toArray(inviteRules.milestones)[0] || {}
    return {
      kicker: "邀请有奖",
      title: invitePage.title || "邀请有奖",
      subtitle: invitePage.subtitle || "邀请好友完成绑定后，奖励按后台配置发放。",
      facts: [
        { label: "好友绑定奖励", value: formatPoints(inviteRules.invitee_bind_reward_points || 0) },
        { label: "每个有效邀请", value: formatPoints(inviteRules.inviter_valid_invite_reward_points || 0) },
        { label: "里程碑加奖", value: formatInviteMilestone(firstMilestone) || "按后台配置" },
      ],
    }
  }

  if (activeTab === "like") {
    const tiers = toArray(likeRules.tiers)
    return {
      kicker: "集赞有奖",
      title: likePage.title || "集赞有奖",
      subtitle: likePage.subtitle || "活动奖励按后台配置展示，提交流程后续补齐。",
      facts: [
        { label: "首档", value: formatTierLabel(tiers[0], "参与即得") || "后台配置" },
        { label: "最高档", value: formatTierLabel(tiers[tiers.length - 1], "参与即得") || "后台配置" },
      ],
    }
  }

  if (activeTab === "create") {
    const tiers = toArray(createRules.tiers)
    return {
      kicker: "创作有奖",
      title: createPage.title || "创作有奖",
      subtitle: createPage.subtitle || "选择发布平台并提交作品链接，审核通过后发放对应奖励。",
      facts: [
        { label: "起步奖励", value: (tiers[0] && tiers[0].business_label) || "后台配置" },
        { label: "最高奖励", value: (tiers[tiers.length - 1] && tiers[tiers.length - 1].business_label) || "后台配置" },
      ],
    }
  }

  const contacts = toArray(partnerPage.contacts).filter((item) => item && item.enabled !== false)
  return {
    kicker: "渠道合作",
    title: partnerPage.title || "渠道合作",
    subtitle: partnerPage.description || partnerPage.subtitle || "校园、机构、社群合作统一从这里接入。",
    facts: [
      { label: "联系卡片", value: `${contacts.length}个` },
      { label: "主联系人", value: contacts[0] && contacts[0].title ? String(contacts[0].title).trim() : "合作顾问" },
    ],
  }
}

function resolveActiveTab(cards = [], current = "") {
  const target = String(current || "").trim()
  if (cards.some((item) => item.key === target)) return target
  return cards[0] ? cards[0].key : "invite"
}

function formatSubmissionStatus(status = "") {
  const key = String(status || "").trim().toLowerCase()
  return {
    pending: "待审核",
    submitted: "已提交",
    approved: "已通过",
    rejected: "已驳回",
  }[key] || "待处理"
}

function getStatusClass(status = "") {
  const key = String(status || "").trim().toLowerCase()
  return `promo-status--${key || "default"}`
}

function formatDateTime(value = "") {
  if (!value) return "--"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function resolveCreatePlatformLabelFromConfig(promoConfig = {}, platform = "") {
  const page = promoConfig && promoConfig.pages ? promoConfig.pages.create || {} : {}
  const platforms = Array.isArray(page.platforms) ? page.platforms : []
  const matched = platforms.find((item) => String(item.key || "") === String(platform || ""))
  return matched && matched.label ? String(matched.label).trim() : String(platform || "创作活动")
}

function resolveCreateTierLabelFromConfig(promoConfig = {}, tierKey = "") {
  const rules = promoConfig && promoConfig.reward_rules ? promoConfig.reward_rules.create || {} : {}
  const tiers = Array.isArray(rules.tiers) ? rules.tiers : []
  const matched = tiers.find((item) => String(item.tier_key || "") === String(tierKey || ""))
  return matched && matched.business_label ? String(matched.business_label).trim() : String(tierKey || "默认档位")
}

function normalizeLikeSubmissions(items = []) {
  return (Array.isArray(items) ? items : []).map((item) => ({
    ...item,
    status_text: formatSubmissionStatus(item && item.status),
    status_class: getStatusClass(item && item.status),
    updated_at_text: formatDateTime((item && (item.updated_at || item.created_at)) || ""),
  }))
}

function normalizeCreateSubmissions(items = [], promoConfig = {}) {
  return (Array.isArray(items) ? items : []).map((item) => ({
    ...item,
    status_text: formatSubmissionStatus(item && item.status),
    status_class: getStatusClass(item && item.status),
    updated_at_text: formatDateTime((item && (item.updated_at || item.created_at)) || ""),
    platform_label: resolveCreatePlatformLabelFromConfig(promoConfig, item && item.platform),
    tier_label: resolveCreateTierLabelFromConfig(promoConfig, item && item.tier_key),
  }))
}

Page({
  data: {
    guestMode: true,
    loading: false,
    submittingBind: false,
    errorText: "",
    hintText: "",
    user: {},
    userCredits: 0,
    enabledCards: [],
    activeTab: "invite",
    promoConfig: createDefaultPromoConfig(),
    heroCard: {
      kicker: "推广中心",
      title: "推广中心",
      subtitle: "",
      facts: [],
    },
    inviteState: createEmptyInviteState(),
    inviteBindCode: "",
    likeShareText: "",
    likeScreenshotPath: "",
    likeScreenshotName: "",
    likeSubmitting: false,
    likeSubmissions: [],
    createSubmitting: false,
    createSubmissions: [],
    createForm: {
      platform: "",
      tierKey: "",
      shareLink: "",
    },
    currentTemplateIndex: 0,
    currentTemplate: "",
  },

  onShow() {
    if (!ensureLogin()) {
      this.setData({
        guestMode: true,
        loading: false,
        user: {},
        userCredits: 0,
        enabledCards: [],
        activeTab: "invite",
        promoConfig: createDefaultPromoConfig(),
        heroCard: {
          kicker: "推广中心",
          title: "推广中心",
          subtitle: "",
          facts: [],
        },
        inviteState: createEmptyInviteState(),
        inviteBindCode: "",
        likeShareText: "",
        likeScreenshotPath: "",
        likeScreenshotName: "",
        likeSubmitting: false,
        likeSubmissions: [],
        createSubmitting: false,
        createSubmissions: [],
        createForm: {
          platform: "",
          tierKey: "",
          shareLink: "",
        },
        currentTemplateIndex: 0,
        currentTemplate: "",
        errorText: "",
        hintText: "",
      })
      return
    }

    const cachedUser = getUser() || {}
    this.setData({
      guestMode: false,
      user: cachedUser,
      userCredits: Number(cachedUser.credits || 0),
    })
    this.loadData()
  },

  async loadData() {
    if (!ensureLogin()) return
    this.setData({ loading: true, errorText: "", hintText: "" })
    try {
      const [options, profile, inviteInfo, likeResp, createResp] = await Promise.all([
        request({ url: "/auth/options", method: "GET", silent: true }),
        request({ url: "/users/me", method: "GET", silent: true }),
        request({ url: "/users/me/invite", method: "GET", silent: true }),
        request({ url: "/users/me/promo/like-submissions", method: "GET", silent: true }).catch(() => ({ items: [] })),
        request({ url: "/users/me/promo/create-submissions", method: "GET", silent: true }).catch(() => ({ items: [] })),
      ])

      const promoConfig = normalizePromoConfig(options && options.promo_center ? options.promo_center : {})
      const inviteState = buildInviteState(inviteInfo || {}, promoConfig)
      const enabledCards = buildEnabledCards(promoConfig, inviteState)
      const activeTab = resolveActiveTab(enabledCards, this.data.activeTab)
      const heroCard = buildHeroCard(activeTab, promoConfig, inviteState)
      const createDefaults = this.buildCreateFormDefaults(promoConfig, this.data.createForm)
      const likeSubmissions = normalizeLikeSubmissions(likeResp && likeResp.items)
      const createSubmissions = normalizeCreateSubmissions(createResp && createResp.items, promoConfig)

      this.setData({
        guestMode: false,
        user: profile || {},
        userCredits: Number((profile && profile.credits) || 0),
        promoConfig,
        enabledCards,
        activeTab,
        heroCard,
        inviteState,
        likeSubmissions,
        createSubmissions,
        createForm: createDefaults,
        currentTemplate: this.getCurrentTemplate(promoConfig, this.data.currentTemplateIndex),
      })
      setUser(profile || {})
    } catch (error) {
      this.setData({
        errorText: String((error && error.message) || "加载推广中心失败"),
      })
    } finally {
      this.setData({ loading: false })
    }
  },

  async refreshInviteState(forceReload = false) {
    const currentCode = String(this.data.inviteState && this.data.inviteState.inviteCode ? this.data.inviteState.inviteCode : "").trim()
    if (currentCode && !forceReload) return this.data.inviteState
    if (!ensureLogin()) return this.data.inviteState

    const inviteInfo = await request({ url: "/users/me/invite", method: "GET", silent: true })
    const nextInviteState = buildInviteState(inviteInfo || {}, this.data.promoConfig)
    const nextCards = buildEnabledCards(this.data.promoConfig, nextInviteState)
    this.setData({
      inviteState: nextInviteState,
      enabledCards: nextCards,
      heroCard: buildHeroCard(this.data.activeTab, this.data.promoConfig, nextInviteState),
    })
    return nextInviteState
  },

  copyText(value, emptyMessage, successMessage) {
    const text = String(value || "").trim()
    if (!text) {
      wx.showToast({ title: emptyMessage || "暂无可复制内容", icon: "none" })
      return
    }
    wx.setClipboardData({
      data: text,
      success: () => {
        wx.showToast({ title: successMessage || "已复制", icon: "success" })
      },
      fail: () => {
        wx.showToast({ title: "复制失败", icon: "none" })
      },
    })
  },

  onSelectTab(e) {
    const nextTab = String((e.currentTarget.dataset.key || "")).trim()
    if (!nextTab) return
    this.setData({
      activeTab: nextTab,
      hintText: "",
      heroCard: buildHeroCard(nextTab, this.data.promoConfig, this.data.inviteState),
    })
  },

  onInputInviteCode(e) {
    this.setData({
      inviteBindCode: String((e.detail && e.detail.value) || "")
        .trim()
        .toUpperCase()
        .slice(0, 16),
    })
  },

  getCurrentTemplate(promoConfig = {}, index = 0) {
    const page = promoConfig && promoConfig.pages ? promoConfig.pages.create || {} : {}
    const templates = Array.isArray(page.templates) ? page.templates.filter((item) => String(item || "").trim()) : []
    if (!templates.length) return ""
    return String(templates[index % templates.length] || "").trim()
  },

  buildCreateFormDefaults(promoConfig = {}, current = {}) {
    const createPage = promoConfig && promoConfig.pages ? promoConfig.pages.create || {} : {}
    const createRules = promoConfig && promoConfig.reward_rules ? promoConfig.reward_rules.create || {} : {}
    const platforms = Array.isArray(createPage.platforms) ? createPage.platforms.filter((item) => item && item.enabled !== false) : []
    const tiers = Array.isArray(createRules.tiers) ? createRules.tiers : []
    const platform = platforms.some((item) => String(item.key || "") === current.platform)
      ? current.platform
      : String((platforms[0] && platforms[0].key) || "")
    const tierKey = tiers.some((item) => String(item.tier_key || "") === current.tierKey)
      ? current.tierKey
      : String((tiers[0] && tiers[0].tier_key) || "")
    return {
      platform,
      tierKey,
      shareLink: String(current.shareLink || ""),
    }
  },

  upsertSubmission(items = [], row = {}, keyField = "id") {
    const list = Array.isArray(items) ? items.slice() : []
    const key = String(row && row[keyField] ? row[keyField] : "")
    if (!key) return list
    const next = [row, ...list.filter((item) => String(item && item[keyField] ? item[keyField] : "") !== key)]
    return next
  },

  onChooseLikeScreenshot() {
    if (this.data.likeSubmitting) return
    wx.chooseMedia({
      count: 1,
      mediaType: ["image"],
      sizeType: ["compressed"],
      success: (res) => {
        const file = (res.tempFiles || [])[0]
        if (!file || !file.tempFilePath) {
          wx.showToast({ title: "未选择截图", icon: "none" })
          return
        }
        this.setData({
          likeScreenshotPath: file.tempFilePath,
          likeScreenshotName: String(file.originalFileObj && file.originalFileObj.name ? file.originalFileObj.name : file.tempFilePath.split("/").pop() || "已选截图"),
        })
      },
      fail: () => {
        wx.showToast({ title: "选择截图失败", icon: "none" })
      },
    })
  },

  onInputLikeShareText(e) {
    this.setData({ likeShareText: String((e.detail && e.detail.value) || "").slice(0, 500) })
  },

  async onSubmitLikeSubmission() {
    if (!this.data.likeScreenshotPath || this.data.likeSubmitting) {
      wx.showToast({ title: "请先选择截图", icon: "none" })
      return
    }
    this.setData({ likeSubmitting: true, errorText: "", hintText: "" })
    try {
      const data = await uploadFile({
        url: "/users/me/promo/like-submissions",
        filePath: this.data.likeScreenshotPath,
        name: "screenshot",
        formData: {
          platform: "wechat",
          share_text: this.data.likeShareText || "",
          screenshot_name: this.data.likeScreenshotName || "",
        },
      })
      const nextItems = normalizeLikeSubmissions(this.upsertSubmission(this.data.likeSubmissions, data && data.item ? data.item : {}, "id"))
      this.setData({
        likeSubmissions: nextItems,
        likeShareText: "",
        likeScreenshotPath: "",
        likeScreenshotName: "",
        hintText: "截图已提交，等待审核",
      })
    } catch (error) {
      this.setData({ errorText: String((error && error.message) || "截图提交失败") })
    } finally {
      this.setData({ likeSubmitting: false })
    }
  },

  onSelectCreatePlatform(e) {
    if (this.data.createSubmitting) return
    const platform = String((e.currentTarget.dataset.value || "")).trim()
    this.setData({
      createForm: {
        ...this.data.createForm,
        platform,
      },
    })
  },

  onSelectCreateTier(e) {
    if (this.data.createSubmitting) return
    const tierKey = String((e.currentTarget.dataset.value || "")).trim()
    this.setData({
      createForm: {
        ...this.data.createForm,
        tierKey,
      },
    })
  },

  onInputCreateField(e) {
    const field = String((e.currentTarget.dataset.field || "")).trim()
    if (!field) return
    const value = String((e.detail && e.detail.value) || "")
    this.setData({
      createForm: {
        ...this.data.createForm,
        [field]: value,
      },
    })
  },

  onRotateTemplate() {
    if (this.data.createSubmitting) return
    const page = this.data.promoConfig && this.data.promoConfig.pages ? this.data.promoConfig.pages.create || {} : {}
    const templates = Array.isArray(page.templates) ? page.templates.filter((item) => String(item || "").trim()) : []
    if (!templates.length) return
    const nextIndex = (Number(this.data.currentTemplateIndex || 0) + 1) % templates.length
    this.setData({
      currentTemplateIndex: nextIndex,
      currentTemplate: this.getCurrentTemplate(this.data.promoConfig, nextIndex),
    })
  },

  onCopyCurrentTemplate() {
    const value = String(this.data.currentTemplate || "").trim()
    this.copyText(value, "暂无创作文案", "创作文案已复制")
  },

  async onSubmitCreateSubmission() {
    const form = this.data.createForm || {}
    if (!form.platform || !form.shareLink || this.data.createSubmitting) {
      wx.showToast({ title: "请先补全平台和作品链接", icon: "none" })
      return
    }
    this.setData({ createSubmitting: true, errorText: "", hintText: "" })
    try {
      const data = await request({
        url: "/users/me/promo/create-submissions",
        method: "POST",
        data: {
          platform: form.platform,
          tier_key: form.tierKey,
          share_link: form.shareLink,
        },
      })
      const nextItems = normalizeCreateSubmissions(this.upsertSubmission(this.data.createSubmissions, data && data.item ? data.item : {}, "id"), this.data.promoConfig)
      const nextForm = this.buildCreateFormDefaults(this.data.promoConfig, {
        ...form,
        shareLink: "",
      })
      this.setData({
        createSubmissions: nextItems,
        createForm: nextForm,
        hintText: "作品链接已提交，等待审核",
      })
    } catch (error) {
      this.setData({ errorText: String((error && error.message) || "作品提交失败") })
    } finally {
      this.setData({ createSubmitting: false })
    }
  },

  async onSubmitInviteBind() {
    if (!ensureLogin()) {
      requireAuth({ targetTab: "profile", action: "open_profile" })
      return
    }
    if (this.data.submittingBind || this.data.inviteState.boundRelation) return

    const inviteCode = String(this.data.inviteBindCode || "").trim().toUpperCase()
    if (!inviteCode) {
      wx.showToast({ title: "请输入邀请码", icon: "none" })
      return
    }

    this.setData({ submittingBind: true, errorText: "", hintText: "" })
    try {
      const data = await request({
        url: "/users/me/invite/bind",
        method: "POST",
        data: { invite_code: inviteCode },
      })
      const nextInviteState = {
        ...this.data.inviteState,
        boundRelation: data && data.bound_relation ? data.bound_relation : null,
        validInviteCount: Number(data && data.invite_summary ? data.invite_summary.valid_invite_count || 0 : this.data.inviteState.validInviteCount),
        totalRewardPoints: Number(data && data.invite_summary ? data.invite_summary.total_reward_points || 0 : this.data.inviteState.totalRewardPoints),
      }
      const nextCards = buildEnabledCards(this.data.promoConfig, nextInviteState)
      this.setData({
        inviteState: nextInviteState,
        enabledCards: nextCards,
        heroCard: buildHeroCard(this.data.activeTab, this.data.promoConfig, nextInviteState),
        inviteBindCode: "",
        hintText: "邀请码绑定成功",
      })
      wx.showToast({ title: "绑定成功", icon: "success" })
    } catch (error) {
      this.setData({ errorText: String((error && error.message) || "绑定失败，请稍后重试") })
    } finally {
      this.setData({ submittingBind: false })
    }
  },

  async onCopyInviteCode() {
    try {
      const inviteState = await this.refreshInviteState(false)
      this.copyText(inviteState && inviteState.inviteCode, "邀请码暂未生成", "邀请码已复制")
    } catch (_) {
      wx.showToast({ title: "邀请码加载失败", icon: "none" })
    }
  },

  async onCopyInviteLink() {
    try {
      const inviteState = await this.refreshInviteState(false)
      this.copyText(inviteState && inviteState.inviteLink, "邀请链接暂未生成", "邀请链接已复制")
    } catch (_) {
      wx.showToast({ title: "邀请链接加载失败", icon: "none" })
    }
  },

  onCopyShareText() {
    const pageConfig = this.data.promoConfig.pages.invite || {}
    const shareText = String(pageConfig.share_copy_text || "").trim()
    this.copyText(shareText, "分享文案暂未配置", "分享文案已复制")
  },

  onCopyWechatId(e) {
    const wechatId = String((e.currentTarget.dataset.value || "")).trim()
    this.copyText(wechatId, "微信号暂未配置", "微信号已复制")
  },

  onReload() {
    if (this.data.loading) return
    this.loadData()
  },

  onGoLogin() {
    requireAuth({ targetTab: "profile", action: "open_profile" })
  },

  onShareAppMessage() {
    const inviteCode = String(this.data.inviteState.inviteCode || "").trim()
    const query = inviteCode ? `?ref=${encodeURIComponent(inviteCode)}` : ""
    return {
      title: "格物学术 | 邀请好友领取积分奖励",
      path: `/pages/home/index${query}`,
    }
  },
})
