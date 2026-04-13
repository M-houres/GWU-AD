<template>
  <section class="pricing-stage">
    <div class="pricing-stage__intro">
      <div class="pricing-stage__top-tags">
        <span class="pricing-stage__tag pricing-stage__tag--solid">微信支付</span>
        <span class="pricing-stage__tag" :class="paymentTestMode ? 'pricing-stage__tag--warn' : 'pricing-stage__tag--soft'">
          {{ paymentTipText }}
        </span>
      </div>
    </div>

    <p v-if="paymentTestMode" class="scholar-note scholar-note--warn" style="margin-top: 18px">
      当前为联调支付模式，二维码仅用于测试链路，不代表真实扣款。
    </p>
    <p v-if="errorText" class="scholar-note scholar-note--danger" style="margin-top: 18px">
      {{ errorText }}
    </p>
    <p v-if="okText" class="scholar-note scholar-note--success" style="margin-top: 18px">
      {{ okText }}
    </p>

    <div v-if="featuredPackages.length" class="pricing-stage__grid">
      <button
        v-for="item in featuredPackages"
        :key="item.packageName"
        type="button"
        class="pricing-card"
        :class="[`is-${item.theme}`, { 'is-selected': selectedPackage?.packageName === item.packageName, 'is-recommended': item.recommended }]"
        :disabled="loading && selectedPackage?.packageName !== item.packageName"
        @click="selectPackage(item)"
      >
        <div class="pricing-card__flag-row">
          <span class="pricing-card__flag">{{ item.badge }}</span>
          <span v-if="item.recommended" class="pricing-card__flag pricing-card__flag--dark">主推</span>
        </div>

        <div class="pricing-card__head">
          <div class="pricing-card__name">{{ item.displayName }}</div>
          <div class="pricing-card__audience">{{ item.audience }}</div>
        </div>

        <div class="pricing-card__price">
          <strong>¥{{ item.priceLabel }}</strong>
          <span>{{ item.creditsLabel }}</span>
        </div>

        <p class="pricing-card__summary">{{ item.summary }}</p>

        <div class="pricing-card__estimate">
          <div class="pricing-card__estimate-label">按约 12000 字论文估算</div>
          <div class="pricing-card__estimate-grid">
            <div v-for="estimate in item.estimates" :key="estimate.label" class="pricing-card__estimate-item">
              <span>{{ estimate.label }}</span>
              <strong>{{ estimate.value }}</strong>
            </div>
          </div>
        </div>

        <div class="pricing-card__footer">
          <span class="pricing-card__cta">{{ selectedPackage?.packageName === item.packageName ? "当前方案" : "选择方案" }}</span>
        </div>
      </button>
    </div>

    <section v-if="selectedPackage" class="pricing-checkout">
      <div class="pricing-checkout__payment pricing-checkout__payment--solo">
        <div class="pricing-checkout__mini-head">
          <strong class="pricing-checkout__mini-name">{{ selectedPackage.displayName }}</strong>
          <span class="pricing-checkout__mini-method">{{ providerMeta.label }}</span>
        </div>

        <div v-if="isGuest" class="pricing-checkout__guest">
          <div class="pricing-checkout__qr-wrap">
            <div class="pricing-checkout__qr-frame">
              <div class="pricing-checkout__qr-placeholder">
                <span class="pricing-checkout__qr-spinner"></span>
                <span>登录后生成二维码</span>
              </div>
            </div>
            <div class="pricing-checkout__qr-caption">
              <span class="pricing-checkout__qr-method">{{ providerMeta.label }}</span>
              <strong>¥{{ selectedPackage.priceLabel }}</strong>
            </div>
          </div>
          <button class="scholar-button" type="button" @click="goLoginForOrder">登录后购买</button>
        </div>

        <div v-else class="pricing-checkout__pay-body">
          <div class="pricing-checkout__qr-wrap">
            <div class="pricing-checkout__qr-frame" :class="{ 'is-loading': loading && !qrCodeDataUrl }">
              <img v-if="qrCodeDataUrl" :src="qrCodeDataUrl" alt="微信支付二维码" class="pricing-checkout__qr-image" />
              <div v-else class="pricing-checkout__qr-placeholder">
                <span class="pricing-checkout__qr-spinner"></span>
                <span>{{ loading ? "正在生成支付码..." : "支付码待生成" }}</span>
              </div>
            </div>
            <div class="pricing-checkout__qr-caption">
              <span class="pricing-checkout__qr-method">{{ providerMeta.label }}</span>
              <strong>¥{{ selectedPackage.priceLabel }}</strong>
            </div>
          </div>

          <div class="pricing-checkout__actions">
            <button class="scholar-button scholar-button--secondary" type="button" @click="refreshOrder">刷新二维码</button>
            <button v-if="paymentTestMode" class="scholar-button" type="button" @click="mockPay">模拟已支付</button>
          </div>
        </div>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { userHttp } from "../lib/http"
import { ensureUserLogin } from "../lib/requireLogin"
import { getUserToken } from "../lib/session"

const FEATURE_PRESETS = [
  {
    displayName: "轻量自检包",
    audience: "适合初稿自查、先看 AI 风险",
    badge: "低门槛开始",
    summary: "先做一轮基础体检，快速判断论文当前的风险与修改方向。",
    note: "适合第一次购买、先小范围验证",
    theme: "slate",
    recommended: false,
  },
  {
    displayName: "毕业冲刺包",
    audience: "适合定稿前集中检测、降AIGC、降重复率",
    badge: "毕业季主推",
    summary: "覆盖最常见的论文处理路径，适合定稿前反复检测与集中优化。",
    note: "性价比最高，适合作为主力方案",
    theme: "azure",
    recommended: true,
  },
  {
    displayName: "团队共享包",
    audience: "适合同学拼单、多人共用、长期使用",
    badge: "长期高频",
    summary: "适合多人拼单或高频使用，覆盖多轮检测与反复修改。",
    note: "适合毕业季高频处理和长期储备",
    theme: "amber",
    recommended: false,
  },
  {
    displayName: "长期储备包",
    audience: "适合导师组、工作室、长期论文处理",
    badge: "大额储备",
    summary: "适合长期储备积分，单次成本最低，覆盖多篇论文连续处理。",
    note: "适合多篇论文和长期使用场景",
    theme: "graphite",
    recommended: false,
  },
]

const emit = defineEmits(["paid"])
const router = useRouter()
const route = useRoute()

const rawPackages = ref([])
const featuredPackages = ref([])
const taskRates = ref({
  aigc_rate: 1,
  dedup_rate: 3,
  rewrite_rate: 2,
})
const loading = ref(false)
const errorText = ref("")
const okText = ref("")
const paymentTestMode = ref(false)
const supportedProviderValues = ref([])

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
const allProviders = [
  { value: "mock", label: "测试支付" },
  { value: "wechat", label: "微信支付" },
]
const providers = computed(() => {
  if (supportedProviderValues.value.length > 0) {
    return allProviders.filter((item) => supportedProviderValues.value.includes(item.value))
  }
  return paymentTestMode.value
    ? allProviders.filter((item) => item.value === "mock")
    : allProviders.filter((item) => item.value === "wechat")
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

const paymentTipText = computed(() => (paymentTestMode.value ? "联调支付模式" : "微信支付已开通"))

const providerMeta = computed(() => {
  const map = {
    wechat: {
      label: "微信支付",
      captionText: "请使用微信扫一扫，支付成功后自动到账。",
    },
    mock: {
      label: "测试支付",
      captionText: "当前为联调模式，仅用于验证支付链路。",
    },
  }
  return map[provider.value] || map.wechat
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

onMounted(loadPackages)
onUnmounted(stopTimers)

async function loadPackages() {
  errorText.value = ""
  try {
    const [packageData, rateData] = await Promise.all([
      userHttp.get("/billing/packages", { timeout: 30000 }),
      userHttp.get("/tasks/rates", { timeout: 30000 }).catch(() => null),
    ])
    rawPackages.value = Array.isArray(packageData?.items) ? packageData.items : []
    featuredPackages.value = buildFeaturedPackages(rawPackages.value, rateData || {})

    if (typeof packageData?.payment_test_mode === "boolean") {
      paymentTestMode.value = packageData.payment_test_mode
    }
    if (Array.isArray(packageData?.supported_providers)) {
      supportedProviderValues.value = packageData.supported_providers
    }
    if (rateData && typeof rateData === "object") {
      taskRates.value = {
        aigc_rate: Number(rateData.aigc_rate || 1),
        dedup_rate: Number(rateData.dedup_rate || 3),
        rewrite_rate: Number(rateData.rewrite_rate || 2),
      }
    }

    const defaultProvider = providers.value[0]?.value
    if (defaultProvider) {
      provider.value = defaultProvider
    }
    const defaultPackage = featuredPackages.value.find((item) => item.recommended) || featuredPackages.value[0] || null
    if (defaultPackage) {
      await selectPackage(defaultPackage, { silentWhenSame: false })
    }
  } catch (error) {
    featuredPackages.value = []
    rawPackages.value = []
    errorText.value = resolvePaymentError(error, "加载套餐失败，请稍后重试")
  }
}

function buildFeaturedPackages(items, rateData) {
  const source = Array.isArray(items) ? items.slice(0, 4) : []
  const rates = {
    aigc_rate: Number(rateData?.aigc_rate || taskRates.value.aigc_rate || 1),
    dedup_rate: Number(rateData?.dedup_rate || taskRates.value.dedup_rate || 3),
    rewrite_rate: Number(rateData?.rewrite_rate || taskRates.value.rewrite_rate || 2),
  }
  return source.map((pkg, index) => {
    const preset = FEATURE_PRESETS[index] || FEATURE_PRESETS[FEATURE_PRESETS.length - 1]
    return {
      packageName: pkg.name,
      displayName: preset.displayName,
      audience: preset.audience,
      badge: pkg.badge || preset.badge,
      summary: preset.summary,
      theme: preset.theme,
      recommended: preset.recommended,
      price: Number(pkg.price || 0),
      priceLabel: Number(pkg.price || 0).toFixed(2),
      credits: Number(pkg.credits || 0),
      creditsLabel: `${Number(pkg.credits || 0).toLocaleString()} 积分`,
      description: String(pkg.description || "").trim(),
      estimates: buildEstimateCards(Number(pkg.credits || 0), rates),
    }
  })
}

function buildEstimateCards(credits, rates) {
  const estimateCount = (rate) => {
    const cost = Math.max(1, Number(rate || 1) * 12000)
    const count = Math.floor(credits / cost)
    return count <= 0 ? "< 1 次" : `${count} 次`
  }
  return [
    { label: "AIGC检测", value: estimateCount(rates.aigc_rate) },
    { label: "降AIGC率", value: estimateCount(rates.rewrite_rate) },
    { label: "降重复率", value: estimateCount(rates.dedup_rate) },
  ]
}

async function selectPackage(item, { silentWhenSame = true } = {}) {
  if (!item) return
  if (silentWhenSame && selectedPackage.value?.packageName === item.packageName) return
  selectedPackage.value = item
  errorText.value = ""
  okText.value = ""
  resetOrderState()
  if (providers.value.length > 0) {
    provider.value = providers.value[0].value
  }
  if (isGuest.value || providers.value.length === 0) {
    return
  }
  await createOrder()
}

function resetOrderState() {
  stopTimers()
  orderNo.value = ""
  qrCodeDataUrl.value = ""
  remainSeconds.value = 0
  expireSecondsTotal.value = 300
  orderStatus.value = "created"
}

async function refreshOrder() {
  if (!ensureUserLogin(router, route, "/app/buy")) {
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

async function createOrder() {
  if (!selectedPackage.value) return
  loading.value = true
  errorText.value = ""
  try {
    const data = await userHttp.post(
      "/billing/create-order",
      {
        package_name: selectedPackage.value.packageName,
        provider: provider.value,
      },
      { timeout: 45000 }
    )
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
  countdownTimer = window.setInterval(() => {
    remainSeconds.value -= 1
    if (remainSeconds.value <= 0) {
      remainSeconds.value = 0
      stopTimers()
      orderStatus.value = "closed"
    }
  }, 1000)
  pollTimer = window.setInterval(checkOrderStatus, 3000)
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
    // Keep polling silently to avoid interrupting checkout.
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
  if (!message) return fallback
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
  okText.value = `支付成功，订单号 ${orderNo.value}`
  emit("paid", data)
}

function goLoginForOrder() {
  ensureUserLogin(router, route, "/app/buy")
}
</script>

<style scoped>
.pricing-stage {
  display: grid;
  gap: 16px;
}

.pricing-stage__intro {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.pricing-stage__top-tags {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-start;
  gap: 10px;
}

.pricing-stage__tag {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.pricing-stage__tag--solid {
  background: linear-gradient(135deg, #1c6be4 0%, #174fc5 100%);
  color: #ffffff;
}

.pricing-stage__tag--soft {
  background: rgba(226, 238, 255, 0.96);
  color: #184694;
}

.pricing-stage__tag--warn {
  background: rgba(255, 239, 214, 0.96);
  color: #9b641b;
}

.pricing-stage__grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.pricing-card {
  position: relative;
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 22px;
  border: 1px solid rgba(165, 184, 217, 0.2);
  background: rgba(255, 255, 255, 0.96);
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease;
}

.pricing-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 22px 42px rgba(23, 58, 116, 0.08);
}

.pricing-card.is-selected {
  border-color: rgba(22, 84, 182, 0.36);
  box-shadow: 0 26px 48px rgba(22, 84, 182, 0.12);
}

.pricing-card.is-slate {
  background: linear-gradient(180deg, #f5f8fd 0%, #fbfdff 100%);
}

.pricing-card.is-azure {
  background: linear-gradient(180deg, #eef5ff 0%, #fbfdff 100%);
}

.pricing-card.is-amber {
  background: linear-gradient(180deg, #fff7ee 0%, #fffdf9 100%);
}

.pricing-card.is-graphite {
  background: linear-gradient(180deg, #f4f7fb 0%, #fafcff 100%);
}

.pricing-card__flag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pricing-card__flag {
  min-height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.88);
  color: #2752a5;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.pricing-card__flag--dark {
  background: #11284b;
  color: #ffffff;
}

.pricing-card__name {
  font-size: 18px;
  line-height: 1.08;
  font-weight: 800;
  color: #122d50;
  letter-spacing: -0.04em;
}

.pricing-card__audience {
  margin-top: 4px;
  color: #5a6f90;
  font-size: 11px;
  line-height: 1.45;
}

.pricing-card__price {
  display: grid;
  gap: 4px;
}

.pricing-card__price strong {
  font-size: 28px;
  line-height: 1;
  color: #102848;
  letter-spacing: -0.05em;
}

.pricing-card__price span {
  color: #6b809f;
  font-size: 11px;
}

.pricing-card__summary {
  margin: 0;
  color: #455d80;
  font-size: 11px;
  line-height: 1.45;
}

.pricing-card__estimate {
  display: grid;
  gap: 6px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(157, 177, 214, 0.18);
}

.pricing-card__estimate-label {
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6b809f;
}

.pricing-card__estimate-grid {
  display: grid;
  gap: 6px;
}

.pricing-card__estimate-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.pricing-card__estimate-item span {
  color: #617796;
  font-size: 10px;
}

.pricing-card__estimate-item strong {
  color: #173b6d;
  font-size: 11px;
  font-weight: 800;
}

.pricing-card__footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 2px;
  border-top: 1px solid rgba(162, 180, 213, 0.18);
}

.pricing-card__cta {
  flex-shrink: 0;
  color: #2157ca;
  font-size: 11px;
  font-weight: 800;
}

.pricing-checkout {
  display: block;
}

.pricing-checkout__payment {
  max-width: 320px;
  margin: 0 auto;
  border-radius: 22px;
  overflow: hidden;
  border: 1px solid rgba(163, 182, 217, 0.18);
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 24px 46px rgba(18, 55, 113, 0.08);
}

.pricing-checkout__payment {
  display: grid;
  gap: 10px;
  padding: 14px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.12), transparent 34%),
    linear-gradient(180deg, rgba(247, 251, 255, 0.98), rgba(255, 255, 255, 0.98));
}

.pricing-checkout__payment--solo {
  align-items: start;
}

.pricing-checkout__mini-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  width: 100%;
}

.pricing-checkout__mini-name {
  color: #11294b;
  font-size: 18px;
  line-height: 1.15;
  font-weight: 800;
  letter-spacing: -0.03em;
}

.pricing-checkout__mini-method {
  min-height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(226, 238, 255, 0.96);
  color: #184694;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.pricing-checkout__guest {
  display: grid;
  gap: 12px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px dashed rgba(120, 143, 186, 0.26);
  background: rgba(255, 255, 255, 0.88);
}

.pricing-checkout__guest-copy strong {
  display: block;
  color: #122d50;
  font-size: 16px;
}

.pricing-checkout__guest-copy p {
  margin: 8px 0 0;
  color: #5f7392;
  font-size: 14px;
  line-height: 1.8;
}

.pricing-checkout__pay-body {
  display: grid;
  gap: 6px;
  justify-items: center;
}

.pricing-checkout__qr-wrap {
  display: grid;
  justify-items: center;
  gap: 6px;
}

.pricing-checkout__qr-frame {
  display: grid;
  place-items: center;
  width: min(100%, 190px);
  aspect-ratio: 1;
  padding: 10px;
  border-radius: 18px;
  background: #ffffff;
  border: 1px solid rgba(160, 181, 217, 0.18);
  box-shadow: 0 18px 40px rgba(17, 50, 101, 0.1);
}

.pricing-checkout__qr-frame.is-loading {
  animation: pricing-qr-pulse 1.8s ease-in-out infinite;
}

.pricing-checkout__qr-image {
  width: min(100%, 144px);
  height: min(100%, 144px);
  object-fit: contain;
  border-radius: 12px;
  background: #ffffff;
}

.pricing-checkout__qr-placeholder {
  display: grid;
  justify-items: center;
  gap: 8px;
  color: #6c809f;
  font-size: 12px;
  font-weight: 600;
}

.pricing-checkout__qr-spinner {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 3px solid rgba(37, 99, 235, 0.14);
  border-top-color: rgba(37, 99, 235, 0.88);
  animation: pricing-spin 1s linear infinite;
}

.pricing-checkout__qr-caption {
  display: grid;
  justify-items: center;
  gap: 4px;
  text-align: center;
}

.pricing-checkout__qr-method {
  color: #5f7392;
  font-size: 10px;
  font-weight: 700;
}

.pricing-checkout__qr-caption strong {
  color: #102746;
  font-size: 22px;
  line-height: 1;
  font-weight: 800;
}

.pricing-checkout__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  justify-content: center;
}

@keyframes pricing-spin {
  to {
    transform: rotate(360deg);
  }
}

@keyframes pricing-qr-pulse {
  0%,
  100% {
    box-shadow: 0 18px 40px rgba(17, 50, 101, 0.1);
  }

  50% {
    box-shadow: 0 24px 50px rgba(17, 50, 101, 0.14);
  }
}

@media (max-width: 1080px) {
  .pricing-stage__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .pricing-stage { gap: 14px; }

  .pricing-stage__intro,
  .pricing-checkout__mini-head {
    flex-direction: column;
    align-items: flex-start;
  }

  .pricing-stage__top-tags,
  .pricing-checkout__actions {
    justify-content: flex-start;
  }

  .pricing-stage__top-tags,
  .pricing-checkout__actions {
    width: 100%;
  }

  .pricing-card,
  .pricing-checkout__payment { padding: 16px 14px; border-radius: 22px; }

  .pricing-card__name,
  .pricing-checkout__payment-title { font-size: 22px; }

  .pricing-card__price strong,
  .pricing-checkout__qr-caption strong { font-size: 28px; }

  .pricing-stage__grid {
    grid-template-columns: 1fr;
  }

  .pricing-checkout__actions > * {
    width: 100%;
  }
}
</style>
