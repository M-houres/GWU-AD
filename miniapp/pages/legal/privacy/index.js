Page({
  openWechatPrivacyContract() {
    const app = getApp()
    if (app && typeof app.openPrivacyContract === "function") {
      app.openPrivacyContract()
    }
  },
})
