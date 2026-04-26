<template>
  <div class="gw-auth-page">
    <main class="gw-auth-page__main">
      <section class="gw-auth-card" aria-label="登录面板">
        <header class="gw-auth-card__head">
          <div class="gw-auth-card__brand" role="img" aria-label="格物学术">
            <span class="gw-auth-card__brand-mark">
              <img src="/brand-logo.png" alt="格物学术 Logo" />
            </span>
            <span class="gw-auth-card__brand-name">格物学术</span>
          </div>
        </header>

        <h2 class="gw-auth-card__title">{{ panelTitle }}</h2>
        <p class="gw-auth-card__hint">{{ authHintText }}</p>

        <div v-if="showLoginTypeTabs" class="gw-auth-card__tabs" role="tablist" aria-label="登录方式切换">
          <button type="button" :class="{ 'is-active': mode === 'phone' }" @click="switchMode('phone')">手机号</button>
          <button type="button" :class="{ 'is-active': mode === 'wx' }" @click="switchMode('wx')">微信扫码</button>
        </div>

        <form v-if="mode === 'phone'" class="gw-auth-card__form" @submit.prevent="submitPhoneAuth">
          <label class="gw-auth-card__field">
            <span>手机号</span>
            <input v-model.trim="phone" type="tel" maxlength="11" placeholder="请输入手机号" />
          </label>

          <label class="gw-auth-card__field">
            <span>验证码</span>
            <div class="gw-auth-card__code-row">
              <input v-model.trim="code" maxlength="8" placeholder="请输入验证码" />
              <button type="button" :disabled="sending || countdown > 0" @click="sendCode">
                {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
              </button>
            </div>
          </label>

          <button class="gw-auth-card__submit" :disabled="loading">
            {{ loading ? '处理中...' : primaryButtonText }}
          </button>

          <button v-if="hasWechatEntry" type="button" class="gw-auth-card__secondary" @click="switchMode('wx')">
            改用微信扫码登录
          </button>
        </form>

        <div v-else class="gw-auth-card__wechat">
          <div class="gw-auth-card__qrcode" role="img" aria-label="微信二维码">
            <img v-if="wxQrcodeDataUrl" :src="wxQrcodeDataUrl" alt="微信登录二维码" />
            <span v-else>二维码生成中...</span>
          </div>

          <p class="gw-auth-card__wechat-status">{{ wxStatusText }} · {{ wxCountdown }} 秒</p>

          <div class="gw-auth-card__wechat-actions">
            <button type="button" @click="loadWxQrcode">刷新二维码</button>
            <button v-if="wxMockEnabled" type="button" @click="mockWxAuthorize">模拟授权</button>
          </div>
        </div>

        <label class="gw-auth-card__policy">
          <input v-model="agreedPolicy" type="checkbox" />
          <span>
            我已阅读并同意
            <RouterLink to="/terms" target="_blank">《服务协议》</RouterLink>
            与
            <RouterLink to="/privacy" target="_blank">《隐私政策》</RouterLink>
          </span>
        </label>

        <p v-if="errorText" class="gw-auth-card__msg gw-auth-card__msg--error">{{ errorText }}</p>
        <p v-if="hintText" class="gw-auth-card__msg gw-auth-card__msg--ok">{{ hintText }}</p>

        <div class="gw-auth-card__footer">
          <button type="button" class="gw-auth-card__guest" @click="enterGuest">立即开始</button>
        </div>
      </section>
    </main>
    <footer v-if="hasSiteFiling" class="gw-site-filing" aria-label="网站备案信息">
      <a
        v-if="siteFiling.icp_filing_no"
        class="gw-site-filing__link"
        :href="siteFiling.icp_filing_url"
        target="_blank"
        rel="noreferrer"
      >
        {{ siteFiling.icp_filing_no }}
      </a>
      <a
        v-if="siteFiling.police_filing_no"
        class="gw-site-filing__link"
        :href="siteFiling.police_filing_url"
        target="_blank"
        rel="noreferrer"
      >
        {{ siteFiling.police_filing_no }}
      </a>
    </footer>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { getDeviceFingerprint } from "../../../lib/device"
import { userHttp } from "../../../lib/http"
import { resolveUserRedirect } from "../../../lib/redirect"
import { setUserInfo, setUserRefreshToken, setUserToken } from "../../../lib/session"

const props = defineProps({
  entryType: {
    type: String,
    default: "login",
  },
})

const route = useRoute()
const router = useRouter()
const envWechatLoginEnabled = String(import.meta.env.VITE_ENABLE_WECHAT_LOGIN || "false").toLowerCase() === "true"

const wechatLoginEnabled = ref(false)
const wxMockEnabled = ref(false)
const phoneLoginEnabled = ref(true)

const mode = ref("phone")
const phone = ref("")
const code = ref("")
const agreedPolicy = ref(false)
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)
const errorText = ref("")
const hintText = ref("")

const wxKey = ref("")
const wxQrcodeDataUrl = ref("")
const wxCountdown = ref(0)
const wxStatus = ref("pending")
const siteFiling = ref({
  icp_filing_no: "",
  icp_filing_url: "https://beian.miit.gov.cn",
  police_filing_no: "",
  police_filing_url: "https://beian.mps.gov.cn/#/query/webSearch",
})

let smsCountdownTimer = null
let wxCountTimer = null
let wxPollTimer = null

const isRegister = computed(() => props.entryType === "register")
const panelTitle = computed(() => (isRegister.value ? "注册并开始使用" : "账号登录"))
const primaryButtonText = computed(() => (isRegister.value ? "注册并进入工作台" : "登录并进入工作台"))
const authHintText = computed(() => {
  if (mode.value === "wx") return "请使用微信扫码完成授权登录"
  return isRegister.value ? "输入手机号和验证码即可完成注册" : "请输入手机号与验证码登录"
})
const wxStatusText = computed(() => {
  if (wxStatus.value === "authorized") return "已授权，正在登录"
  if (wxStatus.value === "expired") return "二维码已过期"
  return "等待微信授权"
})
const showLoginTypeTabs = computed(() => phoneLoginEnabled.value && wechatLoginEnabled.value)
const hasWechatEntry = computed(() => wechatLoginEnabled.value)
const hasSiteFiling = computed(() => Boolean(siteFiling.value.icp_filing_no || siteFiling.value.police_filing_no))

watch(
  () => route.fullPath,
  () => {
  }
)

watch([phoneLoginEnabled, wechatLoginEnabled], ([phoneEnabled, wxEnabled]) => {
  if (mode.value === "wx" && !wxEnabled) {
    mode.value = "phone"
    return
  }
  if (mode.value === "phone" && !phoneEnabled && wxEnabled) {
    mode.value = "wx"
  }
})

onMounted(async () => {
  await loadAuthOptions()
  if (String(route.query.mode || "").toLowerCase() === "wx" && wechatLoginEnabled.value) {
    await switchMode("wx")
  }
})

onUnmounted(() => {
  stopSmsCountdown()
  stopWxTimers()
})

function stopSmsCountdown() {
  if (smsCountdownTimer) {
    clearInterval(smsCountdownTimer)
    smsCountdownTimer = null
  }
}

function stopWxTimers() {
  if (wxCountTimer) {
    clearInterval(wxCountTimer)
    wxCountTimer = null
  }
  if (wxPollTimer) {
    clearInterval(wxPollTimer)
    wxPollTimer = null
  }
}

function validatePhone() {
  return /^1\d{10}$/.test(phone.value)
}

async function loadAuthOptions() {
  try {
    const data = await userHttp.get("/auth/options")
    wechatLoginEnabled.value = envWechatLoginEnabled && Boolean(data.wechat_login_enabled)
    wxMockEnabled.value = Boolean(data.wx_mock_enabled)
    phoneLoginEnabled.value = data.phone_login_enabled !== false
    siteFiling.value = normalizeSiteFiling(data.site_filing)
    if (!phoneLoginEnabled.value && wechatLoginEnabled.value) mode.value = "wx"
    if (!wechatLoginEnabled.value && phoneLoginEnabled.value) mode.value = "phone"
  } catch {
    wechatLoginEnabled.value = false
    wxMockEnabled.value = false
    phoneLoginEnabled.value = true
    siteFiling.value = normalizeSiteFiling(null)
  }
}

function normalizeSiteFiling(raw) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    icp_filing_no: String(source.icp_filing_no || "").trim(),
    icp_filing_url: String(source.icp_filing_url || "https://beian.miit.gov.cn").trim(),
    police_filing_no: String(source.police_filing_no || "").trim(),
    police_filing_url: String(source.police_filing_url || "https://beian.mps.gov.cn/#/query/webSearch").trim(),
  }
}

async function switchMode(nextMode) {
  if (nextMode === "wx" && !wechatLoginEnabled.value) {
    errorText.value = "当前环境未开启微信登录"
    return
  }
  mode.value = nextMode
  errorText.value = ""
  hintText.value = ""
  if (nextMode === "wx") {
    if (!agreedPolicy.value) {
      errorText.value = "请先同意服务协议与隐私条款"
      return
    }
    await loadWxQrcode()
    return
  }
  stopWxTimers()
}

async function sendCode() {
  errorText.value = ""
  hintText.value = ""
  if (!phoneLoginEnabled.value) {
    errorText.value = "当前已关闭手机号验证码登录"
    return
  }
  if (!validatePhone()) {
    errorText.value = "请输入正确的11位手机号"
    return
  }

  sending.value = true
  try {
    const data = await userHttp.post("/auth/send-code", { phone: phone.value })
    countdown.value = 60
    stopSmsCountdown()
    smsCountdownTimer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        countdown.value = 0
        stopSmsCountdown()
      }
    }, 1000)
    const debugCode = String(data?.debug_code || "").trim()
    hintText.value = debugCode ? `短信通道未命中，调试验证码：${debugCode}` : "验证码已发送"
  } catch (error) {
    errorText.value = error.message || "验证码发送失败"
  } finally {
    sending.value = false
  }
}

async function submitPhoneAuth() {
  errorText.value = ""
  hintText.value = ""
  if (!phoneLoginEnabled.value) {
    errorText.value = "当前已关闭手机号验证码登录"
    return
  }
  if (!validatePhone()) {
    errorText.value = "请输入正确的11位手机号"
    return
  }
  if (!code.value) {
    errorText.value = "请输入验证码"
    return
  }
  if (!agreedPolicy.value) {
    errorText.value = "请先同意服务协议与隐私条款"
    return
  }

  loading.value = true
  try {
    const data = await userHttp.post("/auth/login", {
      phone: phone.value,
      code: code.value,
      device_fingerprint: getDeviceFingerprint(),
    })
    completeLogin(data.token, data.user, data.refresh_token)
  } catch (error) {
    errorText.value = error.message || "登录失败，请稍后再试"
  } finally {
    loading.value = false
  }
}

async function loadWxQrcode() {
  if (!agreedPolicy.value) {
    errorText.value = "请先同意服务协议与隐私条款"
    return
  }
  stopWxTimers()
  wxStatus.value = "pending"
  errorText.value = ""
  try {
    const data = await userHttp.get("/auth/wx/qrcode")
    wxKey.value = data.key
    wxQrcodeDataUrl.value = data.qrcode_data_url
    wxCountdown.value = Number(data.expire_seconds || 120)

    wxCountTimer = setInterval(() => {
      wxCountdown.value -= 1
      if (wxCountdown.value <= 0) {
        wxCountdown.value = 0
        wxStatus.value = "expired"
        stopWxTimers()
      }
    }, 1000)

    wxPollTimer = setInterval(pollWxStatus, Number(data.poll_interval_seconds || 2) * 1000)
  } catch (error) {
    errorText.value = error.message || "微信二维码加载失败"
  }
}

async function pollWxStatus() {
  if (!wxKey.value) return
  try {
    const data = await userHttp.get(`/auth/wx/poll/${wxKey.value}`)
    wxStatus.value = data.status || "pending"
    if (wxStatus.value === "authorized" && data.token && data.user) {
      stopWxTimers()
      completeLogin(data.token, data.user, data.refresh_token)
      return
    }
    if (wxStatus.value === "expired") stopWxTimers()
  } catch {
    // keep polling
  }
}

async function mockWxAuthorize() {
  if (!wxKey.value) return
  if (!agreedPolicy.value) {
    errorText.value = "请先同意服务协议与隐私条款"
    return
  }
  try {
    await userHttp.post("/auth/wx/mock-authorize", { key: wxKey.value, openid: "demo_view_user_001" })
    hintText.value = "模拟授权成功"
    await pollWxStatus()
  } catch (error) {
    errorText.value = error.message || "模拟授权失败"
  }
}

function completeLogin(token, user, refreshToken) {
  setUserToken(token)
  setUserRefreshToken(refreshToken)
  setUserInfo(user)
  router.push(resolveUserRedirect(route.query.redirect, "/app/detect"))
}

function enterGuest() {
  router.push("/app/detect")
}
</script>

<style scoped>
.gw-auth-page {
  min-height: 100vh;
  display: grid;
  background:
    radial-gradient(1200px 600px at 8% -10%, rgba(30, 91, 223, 0.2), rgba(30, 91, 223, 0) 60%),
    radial-gradient(900px 500px at 92% 110%, rgba(30, 91, 223, 0.12), rgba(30, 91, 223, 0) 62%),
    linear-gradient(180deg, #f5f9ff 0%, #eef4ff 100%);
  color: #173b70;
}

.gw-auth-page__main {
  min-height: 100svh;
  width: min(1120px, 100%);
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px 16px;
}

.gw-auth-card {
  width: min(100%, 420px);
  border: 1px solid #c8dafd;
  border-radius: 16px;
  background: #ffffff;
  padding: 22px;
  display: grid;
  gap: 12px;
  box-shadow: 0 20px 42px rgba(30, 91, 223, 0.12);
}

.gw-auth-card__head {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
}

.gw-auth-card__brand {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.gw-auth-card__brand-mark {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.gw-auth-card__brand-mark img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  border-radius: inherit;
}

.gw-auth-card__brand-name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #143a73;
}

.gw-auth-card__title {
  margin: 2px 0 0;
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: 0.01em;
  color: #143a73;
}

.gw-auth-card__hint {
  margin: 0;
  font-size: 13px;
  color: #5a77a4;
  line-height: 1.55;
}

.gw-auth-card__tabs {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.gw-auth-card__tabs button,
.gw-auth-card__code-row button,
.gw-auth-card__submit,
.gw-auth-card__secondary,
.gw-auth-card__wechat-actions button,
.gw-auth-card__guest {
  min-height: 40px;
  border: 1px solid #1e5bdf;
  border-radius: 10px;
  background: #1e5bdf;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}

.gw-auth-card__tabs button {
  background: #eef4ff;
  color: #244f91;
  border-color: #c8dafd;
}

.gw-auth-card__tabs button.is-active {
  background: #1e5bdf;
  color: #ffffff;
  border-color: #1e5bdf;
}

.gw-auth-card__tabs button:hover,
.gw-auth-card__code-row button:hover,
.gw-auth-card__submit:hover,
.gw-auth-card__secondary:hover,
.gw-auth-card__wechat-actions button:hover {
  background: #225be4;
  border-color: #225be4;
  color: #ffffff;
}

.gw-auth-card__tabs button:active,
.gw-auth-card__code-row button:active,
.gw-auth-card__submit:active,
.gw-auth-card__secondary:active,
.gw-auth-card__wechat-actions button:active {
  background: #eef4ff;
  border-color: #1e5bdf;
  color: #1e5bdf;
}

.gw-auth-card__form {
  display: grid;
  gap: 10px;
}

.gw-auth-card__field {
  display: grid;
  gap: 6px;
}

.gw-auth-card__field span {
  font-size: 12px;
  color: #3e6295;
}

.gw-auth-card__field input,
.gw-auth-card__code-row input {
  width: 100%;
  height: 40px;
  border: 1px solid #c8dafd;
  border-radius: 10px;
  padding: 0 12px;
  background: #ffffff;
  color: #173b70;
  font-size: 14px;
}

.gw-auth-card__field input::placeholder,
.gw-auth-card__code-row input::placeholder {
  color: #8aa3c9;
}

.gw-auth-card__field input:focus,
.gw-auth-card__code-row input:focus {
  outline: none;
  border-color: #1e5bdf;
  box-shadow: 0 0 0 3px rgba(30, 91, 223, 0.14);
}

.gw-auth-card__code-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.gw-auth-card__code-row button {
  min-width: 108px;
  padding: 0 10px;
}

.gw-auth-card__policy {
  display: inline-flex;
  align-items: flex-start;
  gap: 8px;
  color: #4f6a91;
  font-size: 12px;
  line-height: 1.6;
}

.gw-auth-card__policy input {
  margin-top: 2px;
}

.gw-auth-card__policy a {
  color: #1e5bdf;
  text-decoration: none;
}

.gw-auth-card__policy a:hover {
  color: #184ec8;
  text-decoration: underline;
}

.gw-auth-card__submit {
  min-height: 40px;
}

.gw-auth-card__submit:disabled,
.gw-auth-card__code-row button:disabled {
  opacity: 0.56;
  cursor: not-allowed;
}

.gw-auth-card__secondary {
  min-height: 38px;
  background: #eef4ff;
  color: #1e5bdf;
  border-color: #c8dafd;
}

.gw-auth-card__secondary:hover {
  background: #e2ecff;
  color: #1e5bdf;
  border-color: #1e5bdf;
}

.gw-auth-card__secondary:active {
  background: #1e5bdf;
  color: #ffffff;
}

.gw-auth-card__wechat {
  display: grid;
  gap: 10px;
}

.gw-auth-card__qrcode {
  min-height: 220px;
  border: 1px solid #c8dafd;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #4f6a91;
  font-size: 13px;
}

.gw-auth-card__qrcode img {
  width: min(220px, 90%);
  height: auto;
  border-radius: 10px;
  background: #ffffff;
  padding: 8px;
  border: 1px solid #d4e3fb;
}

.gw-auth-card__wechat-status {
  margin: 0;
  color: #4f6a91;
  font-size: 12px;
}

.gw-auth-card__wechat-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.gw-auth-card__wechat-actions button {
  min-height: 34px;
  padding: 0 12px;
}

.gw-auth-card__msg {
  padding: 8px 10px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  border: 1px solid #d4e3fb;
}

.gw-auth-card__msg--error {
  color: #b33349;
  background: #fff3f6;
  border-color: #f3c3cf;
}

.gw-auth-card__msg--ok {
  color: #1f6a42;
  background: #eefbf4;
  border-color: #bfe8ce;
}

.gw-auth-card__footer {
  padding-top: 6px;
  border-top: 1px solid #dce8ff;
}

.gw-auth-card__guest {
  width: 100%;
  background: #ffffff;
  color: #1e5bdf;
  border-color: #c8dafd;
}

.gw-auth-card__guest:hover {
  background: #eef4ff;
  border-color: #1e5bdf;
  color: #1e5bdf;
}

.gw-site-filing {
  padding: 8px 16px 18px;
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px 18px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.86);
}

.gw-site-filing__link {
  color: inherit;
  text-decoration: none;
}

.gw-site-filing__link:hover {
  text-decoration: underline;
}

@media (max-width: 480px) {
  .gw-auth-page__main {
    padding: 12px;
    align-items: center;
  }

  .gw-auth-card__head {
    align-items: flex-start;
  }

  .gw-auth-card__brand-name {
    font-size: 16px;
  }

  .gw-auth-card {
    border-radius: 12px;
    padding: 18px 14px;
    gap: 10px;
  }

  .gw-auth-card__code-row {
    grid-template-columns: 1fr;
  }

  .gw-auth-card__code-row button {
    width: 100%;
  }

  .gw-auth-card__wechat-actions {
    flex-direction: column;
  }

  .gw-auth-card__wechat-actions button {
    width: 100%;
  }

  .gw-auth-card__tabs {
    gap: 6px;
  }
}
</style>
