const PARTNER_TRACKING_KEY = "wuhong_partner_tracking_v1"

function normalizeQueryValue(value) {
  if (Array.isArray(value)) {
    return String(value[0] || "").trim()
  }
  return String(value || "").trim()
}

function normalizeChannelCode(value) {
  const raw = String(value || "").trim().toUpperCase()
  return raw.replace(/[^A-Z0-9_-]/g, "").slice(0, 32)
}

function normalizeChannelToken(value) {
  return String(value || "").trim().slice(0, 128)
}

export function getPartnerTracking() {
  if (typeof window === "undefined") return null
  let raw = ""
  try {
    raw = String(window.localStorage.getItem(PARTNER_TRACKING_KEY) || "").trim()
  } catch {
    return null
  }
  if (!raw) return null
  try {
    const data = JSON.parse(raw)
    const channelCode = normalizeChannelCode(data?.channel_code)
    const channelToken = normalizeChannelToken(data?.channel_token)
    if (!channelCode || !channelToken) return null
    return { channel_code: channelCode, channel_token: channelToken }
  } catch {
    return null
  }
}

export function capturePartnerTrackingFromQuery(query) {
  const channelCode = normalizeChannelCode(normalizeQueryValue(query?.ch))
  const channelToken = normalizeChannelToken(normalizeQueryValue(query?.ck))
  if (!channelCode || !channelToken || typeof window === "undefined") {
    return getPartnerTracking()
  }
  try {
    window.localStorage.setItem(
      PARTNER_TRACKING_KEY,
      JSON.stringify({
        channel_code: channelCode,
        channel_token: channelToken,
        captured_at: new Date().toISOString(),
      })
    )
  } catch {}
  return { channel_code: channelCode, channel_token: channelToken }
}
