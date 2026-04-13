<template>
  <div class="gw-auth-page">
    <main class="gw-auth-page__main">
      <section class="gw-auth-card" :aria-label="isRegisterPage ? '注册面板' : '登录面板'">
        <header class="gw-auth-card__head">
          <div class="gw-auth-card__brand" role="img" aria-label="格物学术">
            <span class="gw-auth-card__brand-mark">GW</span>
            <span class="gw-auth-card__brand-name">格物学术</span>
          </div>

          <RouterLink class="gw-auth-card__entry-link" :to="alternateEntryLink">
            {{ alternateEntryText }}
          </RouterLink>
        </header>

        <h1 class="gw-auth-card__title">{{ panelTitle }}</h1>
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

          <label class="gw-auth-card__policy">
            <input v-model="agreedPolicy" type="checkbox" />
            <span>我已阅读并同意服务协议与隐私条款</span>
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

        <p v-if="errorText" class="gw-auth-card__msg gw-auth-card__msg--error">{{ errorText }}</p>
        <p v-if="hintText" class="gw-auth-card__msg gw-auth-card__msg--ok">{{ hintText }}</p>

        <div class="gw-auth-card__footer">
          <button type="button" class="gw-auth-card__guest" @click="enterGuest">立即开始</button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { getDeviceFingerprint } from "../../../lib/device"
import { userHttp } from "../../../lib/http"
import { resolveUserRedirect } from "../../../lib/redirect"
import { setUserInfo, setUserToken } from "../../../lib/session"

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
const agreedPolicy = ref(true)
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)
const errorText = ref("")
const hintText = ref("")
const alternateEntryLink = ref("/register")
const referrerCode = ref("")

const wxKey = ref("")
const wxQrcodeDataUrl = ref("")
const wxCountdown = ref(0)
const wxStatus = ref("pending")

let smsCountdownTimer = null
let wxCountTimer = null
let wxPollTimer = null

const isRegisterPage = computed(() => props.entryType === "register")
const panelTitle = computed(() => (isRegisterPage.value ? "账号注册" : "账号登录"))
const primaryButtonText = computed(() => (isRegisterPage.value ? "注册并进入工作台" : "登录并进入工作台"))
const alternateEntryText = computed(() => (isRegisterPage.value ? "已有账号，去登录" : "没有账号，去注册"))
const authHintText = computed(() => {
  if (mode.value === "wx") return "请使用微信扫码完成授权登录"
  return isRegisterPage.value ? "使用手机号验证码快速注册" : "请输入手机号与验证码登录"
})
const wxStatusText = computed(() => {
  if (wxStatus.value === "authorized") return "已授权，正在登录"
  if (wxStatus.value === "expired") return "二维码已过期"
  return "等待微信授权"
})
const showLoginTypeTabs = computed(() => phoneLoginEnabled.value && wechatLoginEnabled.value)
const hasWechatEntry = computed(() => wechatLoginEnabled.value)

watch(
  () => route.fullPath,
  () => {
    syncRouteParams()
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
  syncRouteParams()
  if (String(route.query.mode || "").toLowerCase() === "wx" && wechatLoginEnabled.value) {
    await switchMode("wx")
  }
})

onUnmounted(() => {
  stopSmsCountdown()
  stopWxTimers()
})

function syncRouteParams() {
  const params = new URLSearchParams()
  const redirect = resolveUserRedirect(route.query.redirect, "")
  if (redirect) params.set("redirect", redirect)

  const queryRef = route.query.ref
  if (typeof queryRef === "string" && queryRef.trim()) {
    referrerCode.value = queryRef.trim().toUpperCase()
    localStorage.setItem("wuhong_referrer_code", referrerCode.value)
    params.set("ref", referrerCode.value)
  } else {
    const cachedRef = localStorage.getItem("wuhong_referrer_code")
    referrerCode.value = cachedRef ? cachedRef.toUpperCase() : ""
    if (referrerCode.value) params.set("ref", referrerCode.value)
  }

  const targetPath = isRegisterPage.value ? "/login" : "/register"
  alternateEntryLink.value = params.toString() ? `${targetPath}?${params.toString()}` : targetPath
}

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
  if (!envWechatLoginEnabled) {
    wechatLoginEnabled.value = false
    wxMockEnabled.value = false
    return
  }
  try {
    const data = await userHttp.get("/auth/options")
    wechatLoginEnabled.value = Boolean(data.wechat_login_enabled)
    wxMockEnabled.value = Boolean(data.wx_mock_enabled)
    phoneLoginEnabled.value = data.phone_login_enabled !== false
    if (!phoneLoginEnabled.value && wechatLoginEnabled.value) mode.value = "wx"
    if (!wechatLoginEnabled.value && phoneLoginEnabled.value) mode.value = "phone"
  } catch {
    wechatLoginEnabled.value = false
    wxMockEnabled.value = false
    phoneLoginEnabled.value = true
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
    await userHttp.post("/auth/send-code", { phone: phone.value })
    countdown.value = 60
    stopSmsCountdown()
    smsCountdownTimer = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) {
        countdown.value = 0
        stopSmsCountdown()
      }
    }, 1000)
    hintText.value = "验证码已发送"
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
      referrer_code: referrerCode.value || undefined,
      device_fingerprint: getDeviceFingerprint(),
    })
    completeLogin(data.token, data.user)
  } catch (error) {
    errorText.value = error.message || "登录失败，请稍后再试"
  } finally {
    loading.value = false
  }
}

async function loadWxQrcode() {
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
      completeLogin(data.token, data.user)
      return
    }
    if (wxStatus.value === "expired") stopWxTimers()
  } catch {
    // keep polling
  }
}

async function mockWxAuthorize() {
  if (!wxKey.value) return
  try {
    await userHttp.post("/auth/wx/mock-authorize", { key: wxKey.value, openid: "demo_view_user_001" })
    hintText.value = "模拟授权成功"
    await pollWxStatus()
  } catch (error) {
    errorText.value = error.message || "模拟授权失败"
  }
}

function completeLogin(token, user) {
  setUserToken(token)
  setUserInfo(user)
  localStorage.removeItem("wuhong_referrer_code")
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
  background: #ffffff;
  color: #111111;
}

.gw-auth-page__main {
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: 20px 16px;
}

.gw-auth-card {
  width: min(100%, 420px);
  border: 1px solid #d9d9d9;
  border-radius: 16px;
  background: #ffffff;
  padding: 22px;
  display: grid;
  gap: 12px;
}

.gw-auth-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  display: grid;
  place-items: center;
  background: #111111;
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.gw-auth-card__brand-name {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.gw-auth-card__entry-link {
  min-height: 34px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid #111111;
  background: #111111;
  color: #ffffff;
  text-decoration: none;
  font-size: 12px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.gw-auth-card__title {
  margin: 2px 0 0;
  font-size: 24px;
  line-height: 1.2;
  letter-spacing: 0.01em;
}

.gw-auth-card__hint {
  margin: 0;
  font-size: 13px;
  color: #3f3f3f;
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
  border: 1px solid #111111;
  border-radius: 10px;
  background: #111111;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background-color 0.18s ease, color 0.18s ease, border-color 0.18s ease;
}

.gw-auth-card__tabs button {
  background: #ffffff;
  color: #111111;
}

.gw-auth-card__tabs button.is-active {
  background: #111111;
  color: #ffffff;
}

.gw-auth-card__tabs button:hover,
.gw-auth-card__code-row button:hover,
.gw-auth-card__submit:hover,
.gw-auth-card__secondary:hover,
.gw-auth-card__wechat-actions button:hover,
.gw-auth-card__entry-link:hover {
  background: #2b2b2b;
  border-color: #2b2b2b;
  color: #ffffff;
}

.gw-auth-card__tabs button:active,
.gw-auth-card__code-row button:active,
.gw-auth-card__submit:active,
.gw-auth-card__secondary:active,
.gw-auth-card__wechat-actions button:active,
.gw-auth-card__entry-link:active {
  background: #ffffff;
  border-color: #111111;
  color: #111111;
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
  color: #333333;
}

.gw-auth-card__field input,
.gw-auth-card__code-row input {
  width: 100%;
  height: 40px;
  border: 1px solid #d0d0d0;
  border-radius: 10px;
  padding: 0 12px;
  background: #ffffff;
  color: #111111;
  font-size: 14px;
}

.gw-auth-card__field input::placeholder,
.gw-auth-card__code-row input::placeholder {
  color: #777777;
}

.gw-auth-card__field input:focus,
.gw-auth-card__code-row input:focus {
  outline: none;
  border-color: #111111;
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
  color: #333333;
  font-size: 12px;
  line-height: 1.6;
}

.gw-auth-card__policy input {
  margin-top: 2px;
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
  background: #ffffff;
  color: #111111;
}

.gw-auth-card__secondary:hover {
  background: #f5f5f5;
  color: #111111;
  border-color: #111111;
}

.gw-auth-card__secondary:active {
  background: #111111;
  color: #ffffff;
}

.gw-auth-card__wechat {
  display: grid;
  gap: 10px;
}

.gw-auth-card__qrcode {
  min-height: 220px;
  border: 1px solid #d9d9d9;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: #333333;
  font-size: 13px;
}

.gw-auth-card__qrcode img {
  width: min(220px, 90%);
  height: auto;
  border-radius: 10px;
  background: #ffffff;
  padding: 8px;
  border: 1px solid #d9d9d9;
}

.gw-auth-card__wechat-status {
  margin: 0;
  color: #333333;
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
  border: 1px solid #d9d9d9;
}

.gw-auth-card__msg--error {
  color: #8f2424;
}

.gw-auth-card__msg--ok {
  color: #245542;
}

.gw-auth-card__footer {
  padding-top: 6px;
  border-top: 1px solid #e5e5e5;
}

.gw-auth-card__guest {
  width: 100%;
  background: #ffffff;
  color: #111111;
}

.gw-auth-card__guest:hover {
  background: #f5f5f5;
  border-color: #111111;
  color: #111111;
}

@media (max-width: 480px) {
  .gw-auth-page__main {
    padding: 12px;
    align-items: start;
  }

  .gw-auth-card__head {
    flex-direction: column;
    align-items: stretch;
  }

  .gw-auth-card__entry-link {
    width: 100%;
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
