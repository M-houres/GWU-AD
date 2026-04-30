const {
  getToken,
  setPendingAuth,
  getPendingAuth,
  clearPendingAuth,
} = require("./storage")

let loginOpening = false

function isLoggedIn() {
  return !!getToken()
}

function getCurrentRoute() {
  const pages = getCurrentPages()
  return pages.length ? String(pages[pages.length - 1].route || "") : ""
}

function openLogin(pending = {}) {
  setPendingAuth({
    ...pending,
    createdAt: Date.now(),
  })

  if (getCurrentRoute() === "pages/login/index" || loginOpening) {
    return false
  }

  loginOpening = true
  wx.navigateTo({
    url: "/pages/login/index",
    complete: () => {
      loginOpening = false
    },
  })
  return true
}

function requireAuth(pending = {}) {
  if (isLoggedIn()) return true
  openLogin(pending)
  return false
}

function finishLoginNavigation() {
  const pending = getPendingAuth() || {}
  const targetTab = ["records", "profile"].includes(pending.targetTab) ? pending.targetTab : "home"
  const sourceRoute = String(pending.sourceRoute || "").trim()
  if (sourceRoute && sourceRoute !== "pages/login/index" && sourceRoute.startsWith("pages/") && !sourceRoute.includes("?")) {
    clearPendingAuth()
    wx.reLaunch({ url: `/${sourceRoute}` })
    return
  }
  clearPendingAuth()
  wx.switchTab({ url: `/pages/${targetTab}/index` })
}

module.exports = {
  isLoggedIn,
  getCurrentRoute,
  openLogin,
  requireAuth,
  finishLoginNavigation,
  getPendingAuth,
  clearPendingAuth,
}
