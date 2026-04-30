const env = require("../config/env")
const { request } = require("./request")
const { setRefreshToken, setToken, setUser, getToken, clearAuthState, getPartnerTracking } = require("./storage")

function buildLoginPayload({ referrerCode = "", deviceFingerprint = "" } = {}) {
  const tracking = getPartnerTracking() || {}
  return {
    referrer_code: referrerCode || undefined,
    device_fingerprint: deviceFingerprint || undefined,
    channel_code: tracking.channel_code || undefined,
    channel_token: tracking.channel_token || undefined,
    channel_scene: tracking.channel_scene || undefined,
  }
}

function shouldUseMockMiniLogin() {
  return env.currentEnv === "develop"
}

function loginWithMiniProgram({ referrerCode = "", deviceFingerprint = "" } = {}) {
  return new Promise((resolve, reject) => {
    const submitLogin = async (code) => {
      const data = await request({
        url: "/auth/wx/mini-login",
        method: "POST",
        data: { code, ...buildLoginPayload({ referrerCode, deviceFingerprint }) },
      })
      if (data && data.token) setToken(data.token)
      if (data && data.refresh_token) setRefreshToken(data.refresh_token)
      if (data && data.user) setUser(data.user)
      resolve(data)
    }

    if (shouldUseMockMiniLogin()) {
      submitLogin("mock_mini_login_001").catch(reject)
      return
    }

    wx.login({
      success: async (res) => {
        try {
          if (!res.code) {
            reject(new Error("未获取到微信登录 code"))
            return
          }
          await submitLogin(res.code)
        } catch (error) {
          reject(error)
        }
      },
      fail: reject,
    })
  })
}

function loginWithMiniProgramInternalTest({ referrerCode = "", deviceFingerprint = "" } = {}) {
  return new Promise((resolve, reject) => {
    request({
      url: "/auth/wx/mini-login",
      method: "POST",
      data: {
        code: `internal_test_${Date.now()}`,
        ...buildLoginPayload({ referrerCode, deviceFingerprint }),
      },
    })
      .then((data) => {
        if (data && data.token) setToken(data.token)
        if (data && data.refresh_token) setRefreshToken(data.refresh_token)
        if (data && data.user) setUser(data.user)
        resolve(data)
      })
      .catch(reject)
  })
}

function loginWithMiniProgramPhone({ phoneCode = "", referrerCode = "", deviceFingerprint = "" } = {}) {
  return new Promise((resolve, reject) => {
    if (!phoneCode) {
      reject(new Error("未获取到手机号授权信息"))
      return
    }

    const submitLogin = async (loginCode) => {
      const data = await request({
        url: "/auth/wx/mini-phone-login",
        method: "POST",
        data: {
          login_code: loginCode,
          phone_code: phoneCode,
          ...buildLoginPayload({ referrerCode, deviceFingerprint }),
        },
      })
      if (data && data.token) setToken(data.token)
      if (data && data.refresh_token) setRefreshToken(data.refresh_token)
      if (data && data.user) setUser(data.user)
      resolve(data)
    }

    wx.login({
      success: async (res) => {
        try {
          if (!res.code) {
            reject(new Error("未获取到微信登录 code"))
            return
          }
          await submitLogin(res.code)
        } catch (error) {
          reject(error)
        }
      },
      fail: reject,
    })
  })
}

function ensureLogin() {
  return !!getToken()
}

function logout() {
  request({ url: "/auth/logout", method: "POST", silent: true }).catch(() => null)
  clearAuthState()
}

module.exports = {
  loginWithMiniProgram,
  loginWithMiniProgramInternalTest,
  loginWithMiniProgramPhone,
  ensureLogin,
  logout,
}
