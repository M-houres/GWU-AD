const USER_TOKEN_KEY = "wuhong_user_access_token"
const USER_REFRESH_TOKEN_KEY = "wuhong_user_refresh_token"
const ADMIN_TOKEN_KEY = "wuhong_admin_access_token"
const ADMIN_REFRESH_TOKEN_KEY = "wuhong_admin_refresh_token"
const USER_INFO_KEY = "wuhong_user_info"
const ADMIN_INFO_KEY = "wuhong_admin_info"
const USER_NAVIGATION_KEY = "wuhong_user_navigation"

function normalizeToken(value) {
  const token = String(value || "").trim()
  return /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(token) ? token : ""
}

export function getUserToken() {
  return normalizeToken(localStorage.getItem(USER_TOKEN_KEY))
}

export function setUserToken(token) {
  const normalized = normalizeToken(token)
  if (!normalized) {
    localStorage.removeItem(USER_TOKEN_KEY)
    return
  }
  localStorage.setItem(USER_TOKEN_KEY, normalized)
}

export function getUserRefreshToken() {
  return normalizeToken(localStorage.getItem(USER_REFRESH_TOKEN_KEY))
}

export function setUserRefreshToken(token) {
  const normalized = normalizeToken(token)
  if (!normalized) {
    localStorage.removeItem(USER_REFRESH_TOKEN_KEY)
    return
  }
  localStorage.setItem(USER_REFRESH_TOKEN_KEY, normalized)
}

export function clearUserSession() {
  localStorage.removeItem(USER_TOKEN_KEY)
  localStorage.removeItem(USER_REFRESH_TOKEN_KEY)
  localStorage.removeItem(USER_INFO_KEY)
  localStorage.removeItem(USER_NAVIGATION_KEY)
}

export function getAdminToken() {
  return normalizeToken(localStorage.getItem(ADMIN_TOKEN_KEY))
}

export function setAdminToken(token) {
  const normalized = normalizeToken(token)
  if (!normalized) {
    localStorage.removeItem(ADMIN_TOKEN_KEY)
    return
  }
  localStorage.setItem(ADMIN_TOKEN_KEY, normalized)
}

export function getAdminRefreshToken() {
  return normalizeToken(localStorage.getItem(ADMIN_REFRESH_TOKEN_KEY))
}

export function setAdminRefreshToken(token) {
  const normalized = normalizeToken(token)
  if (!normalized) {
    localStorage.removeItem(ADMIN_REFRESH_TOKEN_KEY)
    return
  }
  localStorage.setItem(ADMIN_REFRESH_TOKEN_KEY, normalized)
}

export function clearAdminSession() {
  localStorage.removeItem(ADMIN_TOKEN_KEY)
  localStorage.removeItem(ADMIN_REFRESH_TOKEN_KEY)
  localStorage.removeItem(ADMIN_INFO_KEY)
}

export function setUserInfo(user) {
  if (!user) {
    localStorage.removeItem(USER_INFO_KEY)
    return
  }
  localStorage.setItem(USER_INFO_KEY, JSON.stringify(user))
}

export function getUserInfo() {
  const raw = localStorage.getItem(USER_INFO_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setUserNavigationConfig(config) {
  if (!config) {
    localStorage.removeItem(USER_NAVIGATION_KEY)
    return
  }
  localStorage.setItem(USER_NAVIGATION_KEY, JSON.stringify(config))
}

export function getUserNavigationConfig() {
  const raw = localStorage.getItem(USER_NAVIGATION_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

export function setAdminInfo(admin) {
  if (!admin) {
    localStorage.removeItem(ADMIN_INFO_KEY)
    return
  }
  localStorage.setItem(ADMIN_INFO_KEY, JSON.stringify(admin))
}

export function getAdminInfo() {
  const raw = localStorage.getItem(ADMIN_INFO_KEY)
  if (!raw) {
    return null
  }
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

function normalizePermissions(admin) {
  const values = admin?.permissions
  if (!Array.isArray(values)) {
    return []
  }
  return values
    .map((item) => String(item || "").trim())
    .filter(Boolean)
}

export function getAdminPermissions() {
  return normalizePermissions(getAdminInfo())
}

export function adminHasPermission(permission) {
  if (!permission) {
    return true
  }
  const admin = getAdminInfo()
  if (!admin) {
    return false
  }
  if (admin.role === "super_admin") {
    return true
  }
  const permissions = new Set(normalizePermissions(admin))
  // Backward compatibility:
  // old operator accounts may only have config permissions.
  if (permissions.has("configs:manage")) {
    permissions.add("configs:view")
    permissions.add("algo:view")
    permissions.add("algo:manage")
  } else if (permissions.has("configs:view")) {
    permissions.add("algo:view")
  }
  if (permissions.has("*") || permissions.has(permission)) {
    return true
  }
  const [scope] = String(permission).split(":")
  if (scope && permissions.has(`${scope}:*`)) {
    return true
  }
  return false
}
