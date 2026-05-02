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
  if (getCurrentRoute() === "pages/login/index" || loginOpening) {
    return false
  }

  setPendingAuth({
    ...pending,
    createdAt: Date.now(),
  })

  loginOpening = true
  wx.navigateTo({
    url: "/pages/login/index",
    complete: () => {
      loginOpening = false
    },
  })
  return true
}

const VALID_SOURCE_ROUTES = [
  "pages/home/index",
  "pages/records/index",
  "pages/profile/index",
  "pages/promo-center/index",
]

function finishLoginNavigation() {
  const pending = getPendingAuth() || {}
  const targetTab = ["records", "profile"].includes(pending.targetTab) ? pending.targetTab : "home"
  const sourceRoute = String(pending.sourceRoute || "").trim()
  if (sourceRoute && VALID_SOURCE_ROUTES.includes(sourceRoute)) {
    clearPendingAuth()
    wx.reLaunch({ url: `/${sourceRoute}` })
    return
  }
  clearPendingAuth()
  wx.switchTab({ url: `/pages/${targetTab}/index` })
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
