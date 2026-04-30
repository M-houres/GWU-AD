const BARE_DATETIME_RE = /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/
const BARE_DATE_RE = /^\d{4}-\d{2}-\d{2}$/
const DAY_MS = 24 * 60 * 60 * 1000
const BEIJING_OFFSET_MS = 8 * 60 * 60 * 1000

function pad(value) {
  return String(value).padStart(2, "0")
}

export function parseBackendDateTime(value) {
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : new Date(value.getTime())
  }
  const text = String(value ?? "").trim()
  if (!text) return null

  let normalized = text
  if (BARE_DATETIME_RE.test(normalized)) {
    normalized = `${normalized.replace(" ", "T")}Z`
  } else if (BARE_DATE_RE.test(normalized)) {
    normalized = `${normalized}T00:00:00Z`
  }

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatBeijingParts(date, withSeconds) {
  const beijingDate = new Date(date.getTime() + BEIJING_OFFSET_MS)
  const yyyy = beijingDate.getUTCFullYear()
  const mm = pad(beijingDate.getUTCMonth() + 1)
  const dd = pad(beijingDate.getUTCDate())
  const hh = pad(beijingDate.getUTCHours())
  const mi = pad(beijingDate.getUTCMinutes())
  const ss = pad(beijingDate.getUTCSeconds())
  return withSeconds ? `${yyyy}-${mm}-${dd} ${hh}:${mi}:${ss}` : `${yyyy}-${mm}-${dd} ${hh}:${mi}`
}

export function formatBeijingDateTime(value, options = {}) {
  const { placeholder = "-", withSeconds = true } = options
  const date = parseBackendDateTime(value)
  if (!date) {
    const fallback = String(value ?? "").trim()
    return fallback || placeholder
  }
  return formatBeijingParts(date, withSeconds)
}

export function formatBeijingDateTimeAfterDays(value, days, options = {}) {
  const { placeholder = "-" } = options
  const date = parseBackendDateTime(value)
  if (!date) {
    const fallback = String(value ?? "").trim()
    return fallback || placeholder
  }
  return formatBeijingParts(new Date(date.getTime() + Number(days || 0) * DAY_MS), options.withSeconds !== false)
}
