const PROD_API_BASE_URL = "https://restin.top/api/v1"
const LOCAL_API_BASE_URL = "http://127.0.0.1:8000/api/v1"

const envMap = {
  develop: {
    // Local dev should hit the local backend first so miniapp config changes can be verified safely.
    apiBaseUrl: LOCAL_API_BASE_URL,
  },
  trial: {
    // Must be a filed HTTPS domain allowed in WeChat.
    apiBaseUrl: PROD_API_BASE_URL,
  },
  release: {
    // Must be a filed HTTPS domain allowed in WeChat.
    apiBaseUrl: PROD_API_BASE_URL,
  },
}

const forceEnvVersion = ""

function resolveEnvVersion() {
  if (forceEnvVersion && envMap[forceEnvVersion]) {
    return forceEnvVersion
  }

  try {
    const info = wx.getAccountInfoSync()
    const envVersion = info && info.miniProgram ? info.miniProgram.envVersion : ""
    if (envVersion && envMap[envVersion]) {
      return envVersion
    }
  } catch (_) {
    // Fallback for non-runtime tooling.
  }

  return "develop"
}

const currentEnv = resolveEnvVersion()

module.exports = {
  currentEnv,
  ...envMap[currentEnv],
}
