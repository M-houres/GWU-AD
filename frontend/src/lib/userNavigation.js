export const USER_NAV_GROUP_LABELS = {
  core: "核心功能",
}

export const USER_NAV_PRESETS = [
  {
    key: "detect",
    label: "AIGC检测",
    path: "/app/detect",
    group: "core",
    visible: true,
    order: 1,
    disabled: false,
    badge: "",
  },
  {
    key: "rewrite",
    label: "降AIGC率",
    path: "/app/rewrite",
    group: "core",
    visible: true,
    order: 2,
    disabled: false,
    badge: "",
  },
  {
    key: "dedup",
    label: "降重复率",
    path: "/app/dedup",
    group: "core",
    visible: true,
    order: 3,
    disabled: false,
    badge: "",
  },
]

const USER_NAV_INDEX = Object.fromEntries(USER_NAV_PRESETS.map((item, index) => [item.key, index]))

function asBool(value, defaultValue = false) {
  if (typeof value === "boolean") return value
  if (typeof value === "number") return value !== 0
  if (typeof value === "string") {
    const raw = value.trim().toLowerCase()
    if (["1", "true", "yes", "on", "y"].includes(raw)) return true
    if (["0", "false", "no", "off", "n", ""].includes(raw)) return false
  }
  return defaultValue
}

function asInt(value, defaultValue) {
  const num = Number.parseInt(value, 10)
  if (!Number.isFinite(num) || num < 1 || num > 1000) {
    return defaultValue
  }
  return num
}

export function normalizeUserNavigationConfig(raw) {
  const sourceItems = Array.isArray(raw?.items) ? raw.items : []
  const incomingMap = new Map()
  for (const item of sourceItems) {
    if (!item || typeof item !== "object") continue
    const key = String(item.key || "").trim()
    if (!key || incomingMap.has(key)) continue
    incomingMap.set(key, item)
  }

  const items = USER_NAV_PRESETS.map((preset, index) => {
    const current = incomingMap.get(preset.key) || {}
    return {
      ...preset,
      visible: asBool(current.visible, preset.visible !== false),
      order: preset.group === "core"
        ? (preset.order || index + 1)
        : asInt(current.order, preset.order || index + 1),
    }
  })
    .sort((left, right) => {
      if (left.order !== right.order) {
        return left.order - right.order
      }
      return (USER_NAV_INDEX[left.key] ?? 999) - (USER_NAV_INDEX[right.key] ?? 999)
    })
    .map((item, index) => ({ ...item, order: index + 1 }))

  return { items }
}
