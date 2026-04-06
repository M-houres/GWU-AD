const env = require("./config/env")
const { getToken, getUser } = require("./utils/storage")

App({
  globalData: {
    apiBaseUrl: env.apiBaseUrl,
    token: "",
    user: null,
  },

  onLaunch() {
    this.globalData.token = getToken() || ""
    this.globalData.user = getUser() || null
  },
})

