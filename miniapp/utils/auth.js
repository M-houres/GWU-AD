const { request } = require("./request")
const { setToken, setUser, getToken, clearToken, clearUser } = require("./storage")

function loginWithMiniProgram({ referrerCode = "", deviceFingerprint = "" } = {}) {
  return new Promise((resolve, reject) => {
    wx.login({
      success: async (res) => {
        try {
          if (!res.code) {
            reject(new Error("未获取到微信登录 code"))
            return
          }
          const data = await request({
            url: "/auth/wx/mini-login",
            method: "POST",
            data: {
              code: res.code,
              referrer_code: referrerCode || undefined,
              device_fingerprint: deviceFingerprint || undefined,
            },
          })
          if (data && data.token) setToken(data.token)
          if (data && data.user) setUser(data.user)
          resolve(data)
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
  ensureLogin,
  logout,
}
