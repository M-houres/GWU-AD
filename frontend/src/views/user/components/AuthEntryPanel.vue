<template>
  <div class="gw-auth-page">
    <main class="gw-auth-page__main">
      <aside class="gw-auth-side" aria-label="品牌介绍">
        <div class="gw-auth-side__eyebrow">格物学术</div>
        <h1 class="gw-auth-side__title">{{ heroTitle }}</h1>
        <p class="gw-auth-side__desc">{{ heroDesc }}</p>

        <div class="gw-auth-side__grid">
          <article v-for="item in heroStats" :key="item.label" class="gw-auth-side__stat">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <em>{{ item.desc }}</em>
          </article>
        </div>

        <div class="gw-auth-side__list">
          <div v-for="item in heroBullets" :key="item.title" class="gw-auth-side__item">
            <div class="gw-auth-side__dot">{{ item.tag }}</div>
            <div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
            </div>
          </div>
        </div>
      </aside>

      <section class="gw-auth-card" aria-label="登录面板">
        <header class="gw-auth-card__head">
          <div class="gw-auth-card__brand" role="img" aria-label="格物学术">
            <span class="gw-auth-card__brand-mark">
              <img src="/brand-logo.png" alt="格物学术 Logo" />
            </span>
            <span class="gw-auth-card__brand-name">格物学术</span>
          </div>

          <span class="gw-auth-card__entry-link">验证码登录</span>
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
const heroTitle = computed(() => (isRegister.value ? "几步完成注册，直接开始使用" : "更快进入工作台，继续处理任务"))
const heroDesc = computed(() =>
  isRegister.value
    ? "统一入口支持手机号验证码和微信扫码，注册完成后即可直接使用检测、降重和改写服务。"
    : "一个入口完成登录，进入后即可继续提交任务、查看记录和管理账户点数。"
)
const heroStats = computed(() => [
  { label: "登录方式", value: hasWechatEntry.value ? "双通道" : "手机号", desc: hasWechatEntry.value ? "手机号 + 微信扫码" : "验证码快速进入" },
  { label: "进入后可用", value: "全功能", desc: "检测、降重、改写统一管理" },
  { label: "设备体验", value: "移动优先", desc: "手机和桌面端都能顺手操作" },
])
const heroBullets = computed(() => [
  { tag: "01", title: "入口更直接", desc: "登录后直接进入主工作区，不绕路，不展示多余说明。" },
  { tag: "02", title: "账号更统一", desc: "任务记录、点数和账户信息全部跟随当前账号集中管理。" },
  { tag: "03", title: "操作更轻", desc: "验证码登录和扫码登录都保留，按你的使用习惯切换即可。" },
])

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
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(380px, 420px);
  align-items: center;
  gap: 24px;
  padding: 20px 16px;
}

.gw-auth-side {
  padding: 28px 8px 28px 4px;
  display: grid;
  gap: 18px;
}

.gw-auth-side__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #5e80b5;
}

.gw-auth-side__title {
  margin: 0;
  max-width: 520px;
  font-size: clamp(34px, 4vw, 54px);
  line-height: 1.04;
  color: #143a73;
}

.gw-auth-side__desc {
  margin: 0;
  max-width: 560px;
  font-size: 15px;
  line-height: 1.85;
  color: #52729f;
}

.gw-auth-side__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.gw-auth-side__stat {
  padding: 16px 16px 14px;
  border-radius: 18px;
  border: 1px solid rgba(30, 91, 223, 0.12);
  background: rgba(255, 255, 255, 0.74);
  box-shadow: 0 16px 28px rgba(30, 91, 223, 0.08);
  display: grid;
  gap: 6px;
}

.gw-auth-side__stat span {
  font-size: 12px;
  color: #6483ad;
}

.gw-auth-side__stat strong {
  font-size: 22px;
  line-height: 1.08;
  color: #1e5bdf;
}

.gw-auth-side__stat em {
  font-style: normal;
  font-size: 12px;
  line-height: 1.6;
  color: #6a84a5;
}

.gw-auth-side__list {
  display: grid;
  gap: 12px;
}

.gw-auth-side__item {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid rgba(30, 91, 223, 0.1);
  background: rgba(255, 255, 255, 0.64);
}

.gw-auth-side__dot {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, #5d92ff, #1e5bdf);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
}

.gw-auth-side__item h3 {
  margin: 0;
  font-size: 16px;
  color: #173b70;
}

.gw-auth-side__item p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.75;
  color: #5978a3;
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

.gw-auth-card__entry-link {
  min-height: 34px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid #1e5bdf;
  background: #1e5bdf;
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
.gw-auth-card__wechat-actions button:hover,
.gw-auth-card__entry-link:hover {
  background: #225be4;
  border-color: #225be4;
  color: #ffffff;
}

.gw-auth-card__tabs button:active,
.gw-auth-card__code-row button:active,
.gw-auth-card__submit:active,
.gw-auth-card__secondary:active,
.gw-auth-card__wechat-actions button:active,
.gw-auth-card__entry-link:active {
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

@media (max-width: 480px) {
  .gw-auth-page__main {
    padding: 12px;
    align-items: center;
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

@media (max-width: 980px) {
  .gw-auth-page__main {
    grid-template-columns: 1fr;
    width: min(100%, 560px);
    gap: 18px;
  }

  .gw-auth-side {
    padding: 6px 0 0;
  }

  .gw-auth-side__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .gw-auth-side__title {
    font-size: 30px;
  }

  .gw-auth-side__item {
    padding: 14px;
  }
}
</style>
