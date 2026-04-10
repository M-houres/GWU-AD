<template>
  <section class="scholar-panel">
    <div class="scholar-panel__header">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="scholar-kicker">Credits Packages</div>
          <h3 class="scholar-subtitle">积分套餐</h3>
          <p class="scholar-lead">
            充值页套餐实时同步，当前支持微信支付和联调模式。
          </p>
        </div>
        <span class="scholar-badge" :class="paymentTestMode ? 'scholar-badge--warn' : 'scholar-badge--info'">
          {{ paymentTipText }}
        </span>
      </div>
    </div>

    <div class="scholar-panel__body">
      <p v-if="paymentTestMode" class="scholar-note scholar-note--warn">
        当前为联调支付模式，二维码仅用于测试链路，不代表真实扣款。
      </p>

      <div class="scholar-option-grid md:grid-cols-2" style="margin-top: 18px">
        <button
          v-for="item in packages"
          :key="item.name"
          type="button"
          class="scholar-option-card"
          :disabled="loading"
          @click="openPay(item)"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="text-lg font-bold tracking-[0.01em] text-[var(--ink)]">{{ item.name }}</div>
            <span v-if="item.badge" class="scholar-badge scholar-badge--success">{{ item.badge }}</span>
          </div>
          <div class="mt-3 text-sm leading-7 text-[var(--ink-soft)]">
            {{ packageDescription(item) }}
          </div>
          <div class="mt-5 flex items-end justify-between gap-3">
            <div class="text-3xl font-semibold text-[var(--ink)]">¥{{ Number(item.price).toFixed(2) }}</div>
            <div class="text-sm font-medium text-[var(--accent)]">
              {{ Number(item.credits).toLocaleString() }} 积分
            </div>
          </div>
        </button>
      </div>

      <p v-if="errorText" class="scholar-note scholar-note--danger" style="margin-top: 18px">
        {{ errorText }}
      </p>
      <p v-if="okText" class="scholar-note scholar-note--success" style="margin-top: 18px">
        {{ okText }}
      </p>
    </div>

    <div v-if="showModal" class="scholar-modal" @click.self="closeModal">
      <div class="scholar-modal__dialog buy-credits-modal">
        <div class="scholar-panel__header">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div class="scholar-kicker">Payment Order</div>
              <h3 class="scholar-subtitle">支付订单</h3>
              <p class="scholar-lead">
                {{ selectedPackage?.name || "-" }} / ¥{{ selectedPackage?.price || "-" }}
              </p>
            </div>
            <button class="scholar-button scholar-button--secondary" type="button" @click="closeModal">
              关闭
            </button>
          </div>
        </div>

        <div class="scholar-panel__body">
          <div class="scholar-inline-actions buy-credits__providers">
            <button
              v-for="p in providers"
              :key="p.value"
              type="button"
              class="scholar-chip"
              :class="{ 'is-active': provider === p.value }"
              @click="switchProvider(p.value)"
            >
              {{ p.label }}
            </button>
          </div>

          <div v-if="isGuest" class="scholar-note" style="margin-top: 18px">
            <div>游客可先查看套餐与支付方式，真正创建订单时再登录。</div>
            <div class="scholar-inline-actions" style="margin-top: 14px">
              <button class="scholar-button" type="button" @click="goLoginForOrder">登录后创建订单</button>
              <button class="scholar-button scholar-button--secondary" type="button" @click="closeModal">
                继续浏览
              </button>
            </div>
          </div>

          <div v-else class="buy-credits-paydesk">
            <section class="buy-credits-summary">
              <div class="buy-credits-summary__head">
                <span class="buy-credits-summary__eyebrow">订单摘要</span>
                <span class="scholar-badge" :class="orderStatusBadgeClass">{{ orderStatusText }}</span>
              </div>

              <div class="buy-credits-summary__package">
                <div class="buy-credits-summary__title">{{ selectedPackage?.name || "-" }}</div>
                <p class="buy-credits-summary__desc">
                  订单创建后系统会自动轮询支付状态，到账后立即刷新积分，无需手动提交回执。
                </p>
              </div>

              <div class="buy-credits-summary__amount">
                <span class="buy-credits-summary__amount-label">应付金额</span>
                <strong>¥{{ selectedPackage?.price || "-" }}</strong>
              </div>

              <div class="buy-credits-summary__facts">
                <article class="buy-credits-summary__fact">
                  <span>支付方式</span>
                  <strong>{{ providerMeta.label }}</strong>
                </article>
                <article class="buy-credits-summary__fact">
                  <span>到账积分</span>
                  <strong>{{ selectedPackage ? Number(selectedPackage.credits).toLocaleString() : "-" }}</strong>
                </article>
                <article class="buy-credits-summary__fact">
                  <span>订单号</span>
                  <strong>{{ orderNo || "-" }}</strong>
                </article>
                <article class="buy-credits-summary__fact">
                  <span>剩余时间</span>
                  <strong>{{ formattedRemain }}</strong>
                </article>
              </div>

              <div class="buy-credits-summary__timeline">
                <div class="buy-credits-summary__timeline-label">
                  <span>支付时效</span>
                  <span>{{ remainSeconds }} 秒</span>
                </div>
                <div class="buy-credits-summary__timeline-track">
                  <div class="buy-credits-summary__timeline-fill" :style="{ width: `${countdownProgress}%` }"></div>
                </div>
              </div>

              <div class="buy-credits-summary__notice">
                <div class="buy-credits-summary__notice-title">支付说明</div>
                <p>{{ providerMeta.notice }}</p>
              </div>
            </section>

            <section class="buy-credits-qrpanel" :class="providerMeta.themeClass">
              <div class="buy-credits-qrpanel__top">
                <div>
                  <div class="buy-credits-qrpanel__brand">{{ providerMeta.panelLabel }}</div>
                  <h4 class="buy-credits-qrpanel__title">请使用{{ providerMeta.scanWith }}扫码支付</h4>
                  <p class="buy-credits-qrpanel__desc">{{ providerMeta.description }}</p>
                </div>
                <div class="buy-credits-qrpanel__signal">
                  <span class="buy-credits-qrpanel__signal-dot"></span>
                  <span>{{ qrStatusText }}</span>
                </div>
              </div>

              <div class="buy-credits-qrpanel__stage">
                <div class="buy-credits-qrpanel__frame" :class="{ 'is-loading': loading && !qrCodeDataUrl }">
                  <span class="buy-credits-qrpanel__corner buy-credits-qrpanel__corner--lt"></span>
                  <span class="buy-credits-qrpanel__corner buy-credits-qrpanel__corner--rt"></span>
                  <span class="buy-credits-qrpanel__corner buy-credits-qrpanel__corner--lb"></span>
                  <span class="buy-credits-qrpanel__corner buy-credits-qrpanel__corner--rb"></span>

                  <img
                    v-if="qrCodeDataUrl"
                    :src="qrCodeDataUrl"
                    alt="payment qrcode"
                    class="buy-credits-qrpanel__image"
                  />
                  <div v-else class="buy-credits-qrpanel__placeholder">
                    <span class="buy-credits-qrpanel__spinner"></span>
                    <span>{{ loading ? "正在生成支付码..." : "支付码待生成" }}</span>
                  </div>
                </div>

                <div class="buy-credits-qrpanel__caption">
                  <strong>{{ providerMeta.caption }}</strong>
                  <span>{{ providerMeta.captionSubtext }}</span>
                </div>
              </div>

              <ol class="buy-credits-steps">
                <li v-for="step in providerMeta.steps" :key="step.title" class="buy-credits-steps__item">
                  <span class="buy-credits-steps__index">{{ step.index }}</span>
                  <div class="buy-credits-steps__content">
                    <strong>{{ step.title }}</strong>
                    <span>{{ step.text }}</span>
                  </div>
                </li>
              </ol>

              <div class="buy-credits-qrpanel__actions">
                <button class="scholar-button scholar-button--secondary" type="button" @click="refreshOrder">
                  刷新二维码
                </button>
                <button
                  v-if="paymentTestMode"
                  class="scholar-button"
                  type="button"
                  @click="mockPay"
                >
                  模拟已支付
                </button>
              </div>
            </section>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { userHttp } from "../lib/http"
import { ensureUserLogin } from "../lib/requireLogin"
import { getUserToken } from "../lib/session"

const emit = defineEmits(["paid"])
const router = useRouter()
const route = useRoute()

const packages = ref([])
const loading = ref(false)
const errorText = ref("")
const okText = ref("")
const paymentTestMode = ref(false)
const supportedProviderValues = ref([])

const showModal = ref(false)
const selectedPackage = ref(null)
const provider = ref("mock")
const orderNo = ref("")
const qrCodeDataUrl = ref("")
const remainSeconds = ref(0)
const expireSecondsTotal = ref(300)
const orderStatus = ref("created")

let countdownTimer = null
let pollTimer = null

const isGuest = computed(() => !getUserToken())
const frontendVisibleProviders = new Set(["mock", "wechat"])
const allProviders = [
  { value: "mock", label: "测试支付" },
  { value: "wechat", label: "微信支付" },
  { value: "alipay", label: "支付宝" },
]
const providers = computed(() => {
  const visibleProviders = allProviders.filter((item) => frontendVisibleProviders.has(item.value))
  if (supportedProviderValues.value.length > 0) {
    return visibleProviders.filter((item) => supportedProviderValues.value.includes(item.value))
  }
  return paymentTestMode.value ? visibleProviders.filter((item) => item.value === "mock") : visibleProviders.filter((item) => item.value === "wechat")
})

const orderStatusText = computed(() => {
  const map = {
    created: "待支付",
    paid: "已支付",
    closed: "已过期",
    refunded: "已退款",
  }
  return map[orderStatus.value] || orderStatus.value
})

const orderStatusBadgeClass = computed(() => {
  const map = {
    created: "scholar-badge--warn",
    paid: "scholar-badge--success",
    closed: "scholar-badge--danger",
    refunded: "scholar-badge--info",
  }
  return map[orderStatus.value] || "scholar-badge--info"
})

const paymentTipText = computed(() =>
  paymentTestMode.value ? "联调支付模式" : "支持微信支付"
)

const providerMeta = computed(() => {
  const map = {
    wechat: {
      label: "微信支付",
      panelLabel: "微信收银台",
      scanWith: "微信",
      description: "打开微信扫一扫完成支付，支付成功后页面会自动确认到账。",
      notice: "请在当前设备保持本页打开，扫码完成后通常会在数秒内自动完成入账。",
      caption: "请使用微信扫一扫",
      captionSubtext: "推荐在手机端完成支付，支付成功后自动回到当前页面。",
      themeClass: "is-wechat",
      steps: [
        { index: "01", title: "打开微信", text: "进入微信首页或聊天页，点击右上角扫一扫。" },
        { index: "02", title: "扫描二维码", text: "对准右侧支付码，确认订单金额与套餐信息。" },
        { index: "03", title: "等待到账", text: "支付成功后页面自动轮询，无需手动刷新列表。" },
      ],
    },
    alipay: {
      label: "支付宝",
      panelLabel: "支付宝收银台",
      scanWith: "支付宝",
      description: "使用支付宝扫一扫完成支付，系统会持续检查订单状态并自动更新。",
      notice: "如二维码过期，直接刷新即可生成新的支付码，原订单不会重复扣款。",
      caption: "请使用支付宝扫一扫",
      captionSubtext: "支付完成后保持页面停留片刻，系统会自动同步支付结果。",
      themeClass: "is-alipay",
      steps: [
        { index: "01", title: "打开支付宝", text: "进入支付宝首页，点击扫一扫。" },
        { index: "02", title: "确认订单", text: "核对当前套餐金额后完成支付。" },
        { index: "03", title: "自动到账", text: "状态更新后系统会自动发放对应积分。" },
      ],
    },
    mock: {
      label: "测试支付",
      panelLabel: "联调收银台",
      scanWith: "测试工具",
      description: "当前为联调模式，二维码仅用于验证支付链路与前端流程，不会真实扣款。",
      notice: "你可以直接点击“模拟已支付”验证充值到账流程，也可以刷新二维码重测下单链路。",
      caption: "联调二维码",
      captionSubtext: "仅用于联调与验收，不会触发真实支付。",
      themeClass: "is-mock",
      steps: [
        { index: "01", title: "创建测试单", text: "系统先生成一笔测试订单并显示二维码。" },
        { index: "02", title: "验证链路", text: "可扫码验证页面展示，或直接点击模拟支付。" },
        { index: "03", title: "确认到账", text: "支付成功后检查积分到账与页面回调是否正常。" },
      ],
    },
  }
  return map[provider.value] || map.mock
})

const formattedRemain = computed(() => {
  const total = Math.max(0, Number(remainSeconds.value || 0))
  const minutes = Math.floor(total / 60)
  const seconds = total % 60
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`
})

const countdownProgress = computed(() => {
  const total = Math.max(1, Number(expireSecondsTotal.value || 300))
  const remain = Math.max(0, Math.min(total, Number(remainSeconds.value || 0)))
  return Math.round((remain / total) * 100)
})

const qrStatusText = computed(() => {
  if (orderStatus.value === "paid") return "已到账"
  if (orderStatus.value === "closed") return "二维码已过期"
  if (loading.value && !qrCodeDataUrl.value) return "支付码生成中"
  return `有效期 ${formattedRemain.value}`
})

onMounted(loadPackages)
onUnmounted(stopTimers)

async function loadPackages() {
  errorText.value = ""
  try {
    const data = await userHttp.get("/billing/packages", { timeout: 30000 })
    packages.value = data.items || []
    if (typeof data.payment_test_mode === "boolean") {
      paymentTestMode.value = data.payment_test_mode
    }
    if (Array.isArray(data.supported_providers)) {
      supportedProviderValues.value = data.supported_providers
    }
    const defaultProvider = providers.value[0]?.value
    if (defaultProvider) {
      provider.value = defaultProvider
    }
  } catch (error) {
    packages.value = []
    errorText.value = resolvePaymentError(error, "加载套餐失败，请稍后重试")
  }
}

function packageDescription(item) {
  const text = String(item?.description || "").trim()
  if (text) {
    return text
  }
  return "适合常规论文处理场景，可用于 AIGC 检测、降重复率和降AIGC任务。"
}

async function openPay(item) {
  errorText.value = ""
  okText.value = ""
  selectedPackage.value = item
  provider.value = providers.value[0]?.value || "mock"
  orderNo.value = ""
  qrCodeDataUrl.value = ""
  remainSeconds.value = 0
  expireSecondsTotal.value = 300
  orderStatus.value = "created"
  showModal.value = true
  stopTimers()
  if (isGuest.value) {
    return
  }
  await createOrder()
}

async function switchProvider(nextProvider) {
  if (provider.value === nextProvider) return
  provider.value = nextProvider
  if (isGuest.value) {
    return
  }
  await createOrder()
}

async function refreshOrder() {
  if (!ensureUserLogin(router, route, "/app/buy")) {
    return
  }
  await createOrder()
}

async function createOrder() {
  if (!selectedPackage.value) return
  loading.value = true
  errorText.value = ""
  try {
    const data = await userHttp.post("/billing/create-order", {
      package_name: selectedPackage.value.name,
      provider: provider.value,
    }, { timeout: 45000 })
    orderNo.value = data.order_no
    qrCodeDataUrl.value = data.qrcode_data_url
    expireSecondsTotal.value = Number(data.expire_seconds || 300)
    remainSeconds.value = expireSecondsTotal.value
    orderStatus.value = data.status || "created"
    startTimers()
  } catch (error) {
    errorText.value = resolvePaymentError(error, "创建订单失败")
  } finally {
    loading.value = false
  }
}

function startTimers() {
  stopTimers()
  countdownTimer = setInterval(() => {
    remainSeconds.value -= 1
    if (remainSeconds.value <= 0) {
      remainSeconds.value = 0
      stopTimers()
      orderStatus.value = "closed"
    }
  }, 1000)
  pollTimer = setInterval(checkOrderStatus, 3000)
}

function stopTimers() {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

async function checkOrderStatus() {
  if (!orderNo.value) return
  try {
    const data = await userHttp.get(`/billing/order-status/${orderNo.value}`)
    orderStatus.value = data.status || "created"
    const remain = Number(data.remain_seconds)
    if (Number.isFinite(remain) && remain >= 0) {
      remainSeconds.value = remain
    }
    if (orderStatus.value === "paid") {
      onPaySuccess(data)
    }
    if (orderStatus.value === "closed") {
      stopTimers()
    }
  } catch {
    // Ignore polling failures to avoid interrupting the checkout flow.
  }
}

async function mockPay() {
  if (!ensureUserLogin(router, route, "/app/buy")) {
    errorText.value = "请先登录后再支付"
    return
  }
  if (!orderNo.value) return
  try {
    const data = await userHttp.post(`/billing/order-pay/${orderNo.value}`)
    onPaySuccess(data)
  } catch (error) {
    errorText.value = resolvePaymentError(error, "支付失败")
  }
}

function resolvePaymentError(error, fallback = "操作失败") {
  const message = String(error?.message || "").trim()
  if (!message) {
    return fallback
  }
  if (message.includes("网络连接异常")) {
    return "支付链路连接短暂波动，请稍候重试。若订单可能已创建，请先刷新二维码，避免重复支付。"
  }
  if (message.includes("请求超时")) {
    return "支付通道响应较慢，请稍候重试。若订单已创建，可直接刷新二维码继续支付。"
  }
  if (message.includes("服务暂时不可用")) {
    return "支付服务暂时繁忙，请稍后再试。"
  }
  return message
}

function onPaySuccess(data) {
  stopTimers()
  orderStatus.value = "paid"
  showModal.value = false
  okText.value = `支付成功，订单号 ${orderNo.value}`
  emit("paid", data)
}

function closeModal() {
  showModal.value = false
  stopTimers()
}

function goLoginForOrder() {
  ensureUserLogin(router, route, "/app/buy")
}
</script>

<style scoped>
.buy-credits-modal {
  max-width: 1040px;
  background:
    linear-gradient(180deg, rgba(250, 253, 255, 0.99), rgba(244, 249, 255, 0.98)),
    rgba(248, 252, 255, 0.97);
}

.buy-credits__providers {
  gap: 10px;
}

.buy-credits-paydesk {
  display: grid;
  grid-template-columns: minmax(280px, 0.92fr) minmax(360px, 1.08fr);
  gap: 18px;
  margin-top: 18px;
  align-items: stretch;
}

.buy-credits-summary,
.buy-credits-qrpanel {
  position: relative;
  overflow: hidden;
  border-radius: 28px;
}

.buy-credits-summary {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px;
  border: 1px solid rgba(46, 94, 179, 0.12);
  background:
    radial-gradient(circle at top left, rgba(53, 120, 231, 0.12), transparent 36%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(245, 249, 255, 0.92));
  box-shadow:
    0 22px 44px rgba(23, 60, 121, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
}

.buy-credits-summary__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.buy-credits-summary__eyebrow {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(38, 110, 225, 0.1);
  color: rgba(22, 66, 135, 0.92);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.buy-credits-summary__package {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.buy-credits-summary__title {
  color: #112a4d;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.buy-credits-summary__desc {
  margin: 0;
  color: #5a6a7d;
  font-size: 14px;
  line-height: 1.75;
}

.buy-credits-summary__amount {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px 20px;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(46, 94, 179, 0.1);
}

.buy-credits-summary__amount-label {
  color: #6b7b8f;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.buy-credits-summary__amount strong {
  color: #102746;
  font-size: 40px;
  line-height: 1;
  font-weight: 700;
  letter-spacing: -0.04em;
}

.buy-credits-summary__facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.buy-credits-summary__fact {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 94px;
  padding: 16px 18px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(46, 94, 179, 0.1);
}

.buy-credits-summary__fact span {
  color: #7a8796;
  font-size: 12px;
  line-height: 1.3;
}

.buy-credits-summary__fact strong {
  color: #193457;
  font-size: 15px;
  line-height: 1.45;
  font-weight: 700;
  word-break: break-word;
}

.buy-credits-summary__timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.buy-credits-summary__timeline-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #5f7187;
  font-size: 13px;
  font-weight: 600;
}

.buy-credits-summary__timeline-track {
  width: 100%;
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(57, 108, 189, 0.12);
}

.buy-credits-summary__timeline-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #33b879 0%, #21a868 45%, #198754 100%);
  box-shadow: 0 0 18px rgba(33, 168, 104, 0.32);
  transition: width 0.32s ease;
}

.buy-credits-summary__notice {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 22px;
  background: rgba(16, 39, 70, 0.92);
  color: rgba(242, 248, 255, 0.96);
}

.buy-credits-summary__notice-title {
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.buy-credits-summary__notice p {
  margin: 0;
  color: rgba(230, 238, 247, 0.9);
  font-size: 13px;
  line-height: 1.75;
}

.buy-credits-qrpanel {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 100%;
  padding: 24px;
  border: 1px solid rgba(26, 62, 122, 0.12);
  box-shadow:
    0 26px 52px rgba(16, 53, 110, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.78);
}

.buy-credits-qrpanel::before {
  content: "";
  position: absolute;
  top: -80px;
  right: -70px;
  width: 220px;
  height: 220px;
  border-radius: 999px;
  opacity: 0.8;
  pointer-events: none;
}

.buy-credits-qrpanel.is-wechat {
  background:
    linear-gradient(180deg, rgba(239, 252, 245, 0.98), rgba(248, 255, 251, 0.96)),
    #f7fff9;
}

.buy-credits-qrpanel.is-wechat::before {
  background: radial-gradient(circle, rgba(21, 187, 107, 0.2), transparent 72%);
}

.buy-credits-qrpanel.is-alipay {
  background:
    linear-gradient(180deg, rgba(240, 249, 255, 0.98), rgba(247, 252, 255, 0.96)),
    #f6fbff;
}

.buy-credits-qrpanel.is-alipay::before {
  background: radial-gradient(circle, rgba(36, 149, 255, 0.2), transparent 72%);
}

.buy-credits-qrpanel.is-mock {
  background:
    linear-gradient(180deg, rgba(247, 244, 255, 0.98), rgba(252, 250, 255, 0.96)),
    #fbf8ff;
}

.buy-credits-qrpanel.is-mock::before {
  background: radial-gradient(circle, rgba(115, 90, 255, 0.18), transparent 72%);
}

.buy-credits-qrpanel__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.buy-credits-qrpanel__brand {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.76);
  color: #21456f;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.buy-credits-qrpanel__title {
  margin: 12px 0 8px;
  color: #11294a;
  font-size: 28px;
  line-height: 1.15;
  font-weight: 700;
  letter-spacing: -0.03em;
}

.buy-credits-qrpanel__desc {
  margin: 0;
  max-width: 420px;
  color: #607187;
  font-size: 14px;
  line-height: 1.75;
}

.buy-credits-qrpanel__signal {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: #274a74;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.buy-credits-qrpanel__signal-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #21a868;
  box-shadow: 0 0 0 6px rgba(33, 168, 104, 0.14);
}

.buy-credits-qrpanel__stage {
  display: grid;
  justify-items: center;
  gap: 14px;
}

.buy-credits-qrpanel__frame {
  position: relative;
  display: grid;
  place-items: center;
  width: min(100%, 312px);
  aspect-ratio: 1;
  padding: 24px;
  border-radius: 34px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(253, 255, 255, 0.98));
  border: 1px solid rgba(31, 72, 141, 0.12);
  box-shadow:
    0 18px 44px rgba(15, 43, 89, 0.1),
    inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.buy-credits-qrpanel__frame.is-loading {
  animation: buy-credits-pulse 1.8s ease-in-out infinite;
}

.buy-credits-qrpanel__corner {
  position: absolute;
  width: 34px;
  height: 34px;
  border-color: rgba(25, 98, 210, 0.72);
}

.buy-credits-qrpanel__corner--lt {
  top: 16px;
  left: 16px;
  border-top: 3px solid currentColor;
  border-left: 3px solid currentColor;
  border-top-left-radius: 18px;
}

.buy-credits-qrpanel__corner--rt {
  top: 16px;
  right: 16px;
  border-top: 3px solid currentColor;
  border-right: 3px solid currentColor;
  border-top-right-radius: 18px;
}

.buy-credits-qrpanel__corner--lb {
  bottom: 16px;
  left: 16px;
  border-bottom: 3px solid currentColor;
  border-left: 3px solid currentColor;
  border-bottom-left-radius: 18px;
}

.buy-credits-qrpanel__corner--rb {
  right: 16px;
  bottom: 16px;
  border-right: 3px solid currentColor;
  border-bottom: 3px solid currentColor;
  border-bottom-right-radius: 18px;
}

.buy-credits-qrpanel__image {
  width: min(100%, 224px);
  height: min(100%, 224px);
  border-radius: 24px;
  background: #fff;
  object-fit: contain;
}

.buy-credits-qrpanel__placeholder {
  display: grid;
  justify-items: center;
  gap: 12px;
  color: #6d7b8d;
  font-size: 14px;
  font-weight: 600;
}

.buy-credits-qrpanel__spinner {
  width: 36px;
  height: 36px;
  border: 3px solid rgba(37, 99, 235, 0.14);
  border-top-color: rgba(37, 99, 235, 0.86);
  border-radius: 999px;
  animation: buy-credits-spin 1s linear infinite;
}

.buy-credits-qrpanel__caption {
  display: grid;
  justify-items: center;
  gap: 6px;
  text-align: center;
}

.buy-credits-qrpanel__caption strong {
  color: #143152;
  font-size: 16px;
  font-weight: 700;
}

.buy-credits-qrpanel__caption span {
  color: #67788e;
  font-size: 13px;
  line-height: 1.65;
}

.buy-credits-steps {
  display: grid;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.buy-credits-steps__item {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(31, 72, 141, 0.08);
}

.buy-credits-steps__index {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 14px;
  background: rgba(34, 104, 223, 0.1);
  color: #17488d;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.buy-credits-steps__content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.buy-credits-steps__content strong {
  color: #183556;
  font-size: 14px;
  font-weight: 700;
}

.buy-credits-steps__content span {
  color: #6a7b90;
  font-size: 13px;
  line-height: 1.65;
}

.buy-credits-qrpanel__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

@keyframes buy-credits-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes buy-credits-pulse {
  0%,
  100% {
    box-shadow:
      0 18px 44px rgba(15, 43, 89, 0.1),
      inset 0 1px 0 rgba(255, 255, 255, 0.8);
  }

  50% {
    box-shadow:
      0 22px 52px rgba(15, 43, 89, 0.14),
      inset 0 1px 0 rgba(255, 255, 255, 0.9);
  }
}

@media (max-width: 960px) {
  .buy-credits-paydesk {
    grid-template-columns: 1fr;
  }

  .buy-credits-modal {
    max-width: 760px;
  }
}

@media (max-width: 640px) {
  .buy-credits-modal {
    max-width: none;
  }

  .buy-credits-summary,
  .buy-credits-qrpanel {
    padding: 18px;
    border-radius: 24px;
  }

  .buy-credits-summary__title {
    font-size: 22px;
  }

  .buy-credits-summary__amount strong {
    font-size: 34px;
  }

  .buy-credits-summary__facts {
    grid-template-columns: 1fr;
  }

  .buy-credits-qrpanel__top {
    flex-direction: column;
  }

  .buy-credits-qrpanel__title {
    font-size: 23px;
  }

  .buy-credits-qrpanel__frame {
    width: 100%;
    max-width: 276px;
    border-radius: 28px;
  }
}
</style>
