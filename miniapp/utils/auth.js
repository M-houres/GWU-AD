const env = require("../config/env")
const { request } = require("./request")
const { setToken, setUser, getToken, clearToken, clearUser } = require("./storage")

function shouldUseMockMiniLogin() {
  return env.currentEnv === "develop"
}

function loginWithMiniProgram({ referrerCode = "", deviceFingerprint = "" } = {}) {
  return new Promise((resolve, reject) => {
    const submitLogin = async (code) => {
      const data = await request({
        url: "/auth/wx/mini-login",
        method: "POST",
        data: {
          code,
          referrer_code: referrerCode || undefined,
          device_fingerprint: deviceFingerprint || undefined,
        },
      })
      if (data && data.token) setToken(data.token)
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
          referrer_code: referrerCode || undefined,
          device_fingerprint: deviceFingerprint || undefined,
        },
      })
      if (data && data.token) setToken(data.token)
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
  clearToken()
  clearUser()
}

module.exports = {
  loginWithMiniProgram,
  loginWithMiniProgramPhone,
  ensureLogin,
  logout,
}
