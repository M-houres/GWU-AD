const TOKEN_KEY = "gw_user_token"
const USER_KEY = "gw_user_profile"
const AUTH_PENDING_KEY = "gw_auth_pending"
const HOME_DRAFT_KEY = "gw_home_draft"
const REFERRER_CODE_KEY = "gw_referrer_code"

function setToken(token) {
  wx.setStorageSync(TOKEN_KEY, token || "")
}

function getToken() {
  return wx.getStorageSync(TOKEN_KEY) || ""
}

function clearToken() {
  wx.removeStorageSync(TOKEN_KEY)
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

module.exports = {
  setToken,
  getToken,
  clearToken,
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
}
