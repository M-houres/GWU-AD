const envMap = {
  develop: {
    // Development tools can point to local or test services.
    apiBaseUrl: "http://127.0.0.1:8000/api/v1",
  },
  trial: {
    // Replace before trial submission. Must be a filed HTTPS domain allowed in WeChat.
    apiBaseUrl: "https://your-domain.example.com/api/v1",
  },
  release: {
    // Replace before release submission. Must be a filed HTTPS domain allowed in WeChat.
    apiBaseUrl: "https://your-domain.example.com/api/v1",
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
