const TOKEN_KEY = "gw_user_token"
const REFRESH_TOKEN_KEY = "gw_user_refresh_token"
const USER_KEY = "gw_user_profile"
const AUTH_PENDING_KEY = "gw_auth_pending"
const HOME_DRAFT_KEY = "gw_home_draft"
const REFERRER_CODE_KEY = "gw_referrer_code"
const PARTNER_TRACKING_KEY = "gw_partner_tracking"

const ACCESS_TOKEN_TTL_MS = 2 * 60 * 60 * 1000
const REFRESH_TOKEN_TTL_MS = 30 * 24 * 60 * 60 * 1000

function setToken(token) {
  if (!token) {
    wx.removeStorageSync(TOKEN_KEY)
    return
  }
  wx.setStorageSync(TOKEN_KEY, {
    value: token,
    expiresAt: Date.now() + ACCESS_TOKEN_TTL_MS,
  })
}

function getToken() {
  const raw = wx.getStorageSync(TOKEN_KEY)
  if (!raw || typeof raw !== "object") return ""
  if (!raw.value || !raw.expiresAt) return ""
  if (Date.now() >= Number(raw.expiresAt)) {
    wx.removeStorageSync(TOKEN_KEY)
    return ""
  }
  return raw.value
}

function clearToken() {
  wx.removeStorageSync(TOKEN_KEY)
}

function setRefreshToken(token) {
  if (!token) {
    wx.removeStorageSync(REFRESH_TOKEN_KEY)
    return
  }
  wx.setStorageSync(REFRESH_TOKEN_KEY, {
    value: token,
    expiresAt: Date.now() + REFRESH_TOKEN_TTL_MS,
  })
}

function getRefreshToken() {
  const raw = wx.getStorageSync(REFRESH_TOKEN_KEY)
  if (!raw) return ""
  if (typeof raw === "string") return raw
  if (typeof raw !== "object" || !raw.value || !raw.expiresAt) {
    wx.removeStorageSync(REFRESH_TOKEN_KEY)
    return ""
  }
  if (Date.now() >= Number(raw.expiresAt)) {
    wx.removeStorageSync(REFRESH_TOKEN_KEY)
    return ""
  }
  return raw.value
}

function clearRefreshToken() {
  wx.removeStorageSync(REFRESH_TOKEN_KEY)
}

function setUser(user) {
  wx.setStorageSync(USER_KEY, user || null)
}

function getUser() {
  return wx.getStorageSync(USER_KEY) || null
}

function clearUser() {
  wx.removeStorageSync(USER_KEY)
}

function setPendingAuth(payload) {
  if (!payload || typeof payload !== "object") {
    wx.removeStorageSync(AUTH_PENDING_KEY)
    return
  }
  wx.setStorageSync(AUTH_PENDING_KEY, payload)
}

function getPendingAuth() {
  return wx.getStorageSync(AUTH_PENDING_KEY) || null
}

function clearPendingAuth() {
  wx.removeStorageSync(AUTH_PENDING_KEY)
}

function setHomeDraft(payload) {
  if (!payload || typeof payload !== "object") {
    wx.removeStorageSync(HOME_DRAFT_KEY)
    return
  }
  wx.setStorageSync(HOME_DRAFT_KEY, payload)
}

function getHomeDraft() {
  return wx.getStorageSync(HOME_DRAFT_KEY) || null
}

function clearHomeDraft() {
  wx.removeStorageSync(HOME_DRAFT_KEY)
}

function setReferrerCode(code = "") {
  const normalized = String(code || "").trim().toUpperCase()
  if (!normalized) {
    wx.removeStorageSync(REFERRER_CODE_KEY)
    return
  }
  wx.setStorageSync(REFERRER_CODE_KEY, normalized)
}

function getReferrerCode() {
  return String(wx.getStorageSync(REFERRER_CODE_KEY) || "").trim().toUpperCase()
}

function clearReferrerCode() {
  wx.removeStorageSync(REFERRER_CODE_KEY)
}

function normalizeChannelCode(value = "") {
  return String(value || "").trim().toUpperCase().replace(/[^A-Z0-9_-]/g, "").slice(0, 32)
}

function normalizeChannelToken(value = "") {
  return String(value || "").trim().slice(0, 128)
}

function normalizeChannelScene(value = "") {
  return String(value || "").trim().toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 64)
}

function setPartnerTracking(payload) {
  const channelCode = normalizeChannelCode(payload && payload.channel_code)
  const channelToken = normalizeChannelToken(payload && payload.channel_token)
  const channelScene = normalizeChannelScene(payload && payload.channel_scene)
  if ((!channelCode || !channelToken) && !channelScene) {
    wx.removeStorageSync(PARTNER_TRACKING_KEY)
    return
  }
  wx.setStorageSync(PARTNER_TRACKING_KEY, {
    channel_code: channelCode,
    channel_token: channelToken,
    channel_scene: channelScene,
    captured_at: Date.now(),
  })
}

function getPartnerTracking() {
  const raw = wx.getStorageSync(PARTNER_TRACKING_KEY)
  if (!raw || typeof raw !== "object") return null
  const channelCode = normalizeChannelCode(raw.channel_code)
  const channelToken = normalizeChannelToken(raw.channel_token)
  const channelScene = normalizeChannelScene(raw.channel_scene)
  if ((!channelCode || !channelToken) && !channelScene) return null
  return {
    channel_code: channelCode,
    channel_token: channelToken,
    channel_scene: channelScene,
  }
}

function clearPartnerTracking() {
  wx.removeStorageSync(PARTNER_TRACKING_KEY)
}

function clearAuthState() {
  clearToken()
  clearRefreshToken()
  clearUser()
  clearPendingAuth()
  clearHomeDraft()
}

function clearPartnerPortalAuth() {
  wx.removeStorageSync("gw_partner_portal_token")
  wx.removeStorageSync("gw_partner_portal_refresh_token")
  wx.removeStorageSync("gw_partner_portal_profile")
}

module.exports = {
  setToken,
  getToken,
  clearToken,
  setRefreshToken,
  getRefreshToken,
  clearRefreshToken,
  setUser,
  getUser,
  clearUser,
  setPendingAuth,
  getPendingAuth,
  clearPendingAuth,
  setHomeDraft,
  getHomeDraft,
  clearHomeDraft,
  setReferrerCode,
  getReferrerCode,
  clearReferrerCode,
  setPartnerTracking,
  getPartnerTracking,
  clearPartnerTracking,
  clearAuthState,
  clearPartnerPortalAuth,
}
