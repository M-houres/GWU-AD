const { getPartnerTracking, setPartnerTracking } = require("./storage")
const { request } = require("./request")

function normalizeQueryValue(value) {
  if (Array.isArray(value)) return String(value[0] || "").trim()
  return String(value || "").trim()
}

async function capturePartnerTracking(options = {}) {
  const channelCode = normalizeQueryValue(options.ch).toUpperCase().replace(/[^A-Z0-9_-]/g, "").slice(0, 32)
  const channelToken = normalizeQueryValue(options.ck).slice(0, 128)
  const channelScene = normalizeQueryValue(options.cs || options.scene).toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 64)
  if (channelCode && channelToken) {
    const payload = {
      channel_code: channelCode,
      channel_token: channelToken,
      channel_scene: channelScene,
    }
    setPartnerTracking(payload)
    return payload
  }
  if (channelScene) {
    const cached = getPartnerTracking()
    if (cached && cached.channel_scene === channelScene && cached.channel_code && cached.channel_token) {
      return cached
    }
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const data = await request({
          url: `/partners/miniapp/resolve-scene?scene=${encodeURIComponent(channelScene)}`,
          method: "GET",
          silent: true,
        })
        const payload = {
          channel_code: String(data && data.channel_code || ""),
          channel_token: String(data && data.channel_token || ""),
          channel_scene: String(data && data.channel_scene || channelScene),
        }
        setPartnerTracking(payload)
        return payload
      } catch (_) {
        if (attempt === 1) return getPartnerTracking()
        await new Promise(r => setTimeout(r, 1000))
      }
    }
  }
  return getPartnerTracking()
}

module.exports = {
  capturePartnerTracking,
}
