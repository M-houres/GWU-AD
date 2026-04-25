const { getPartnerTracking, setPartnerTracking } = require("./storage")

function normalizeQueryValue(value) {
  if (Array.isArray(value)) return String(value[0] || "").trim()
  return String(value || "").trim()
}

function capturePartnerTracking(options = {}) {
  const channelCode = normalizeQueryValue(options.ch).toUpperCase().replace(/[^A-Z0-9_-]/g, "").slice(0, 32)
  const channelToken = normalizeQueryValue(options.ck).slice(0, 128)
  if (channelCode && channelToken) {
    const payload = {
      channel_code: channelCode,
      channel_token: channelToken,
    }
    setPartnerTracking(payload)
    return payload
  }
  return getPartnerTracking()
}

module.exports = {
  capturePartnerTracking,
}
