const TOKEN_KEY = "gw_user_token"
const USER_KEY = "gw_user_profile"

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

module.exports = {
  setToken,
  getToken,
  clearToken,
  setUser,
  getUser,
  clearUser,
}

