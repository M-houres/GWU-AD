<template>
  <section class="pricing-stage">
    <header class="pricing-hero">
      <div class="pricing-hero__copy">
        <div class="pricing-stage__top-tags">
          <span class="pricing-stage__tag pricing-stage__tag--solid">充值通用点数</span>
          <span class="pricing-stage__tag" :class="paymentTestMode ? 'pricing-stage__tag--warn' : 'pricing-stage__tag--soft'">
            {{ paymentTipText }}
          </span>
        </div>
        <h2 class="pricing-hero__title">按任务体量选择合适套餐</h2>
        <p class="pricing-hero__lead">
          当前按字符数扣减通用点数。以下估算统一按 8000 字 / 篇文稿计算，便于快速判断大致使用量。
        </p>
      </div>
      <div class="pricing-hero__hint">
        <strong>当前口径</strong>
        <span>1 字符约扣 1 点数</span>
      </div>
    </header>

    <p v-if="paymentTestMode" class="scholar-note scholar-note--warn">
      当前为联调支付模式，二维码仅用于测试链路，不代表真实扣款。
    </p>
    <p v-if="errorText" class="scholar-note scholar-note--danger">
      {{ errorText }}
    </p>
    <p v-if="okText" class="scholar-note scholar-note--success">
      {{ okText }}
    </p>

    <section v-if="packageOptions.length" class="pricing-card-grid" aria-label="通用点数套餐">
      <article
        v-for="item in packageOptions"
        :key="item.key"
        class="pricing-card"
        :class="[item.toneClass, { 'is-active': selectedPackage?.key === item.key }]"
      >
        <div class="pricing-card__header">
          <div>
            <div class="pricing-card__name">{{ item.displayName }}</div>
            <p class="pricing-card__subhead">{{ item.audienceText }}</p>
          </div>
          <span v-if="item.badge" class="pricing-card__badge">{{ item.badge }}</span>
        </div>

        <div class="pricing-card__price">
          <strong>¥{{ item.priceLabel }}</strong>
          <span>{{ item.priceHint }}</span>
        </div>

        <div class="pricing-card__points">
          <strong>{{ item.creditsLabel }}</strong>
          <span>{{ item.estimateHeadline }}</span>
        </div>

        <div class="pricing-card__estimate">
          <div class="pricing-card__estimate-kicker">使用估算</div>
          <p>{{ item.estimateText }}</p>
        </div>

        <p class="pricing-card__desc">{{ item.descriptionText }}</p>

        <button
          type="button"
          class="pricing-card__action"
          :disabled="loading && selectedPackage?.key === item.key && paymentModalOpen"
          @click="openPackageModal(item)"
        >
          立即充值
        </button>
      </article>
    </section>

    <p v-else class="scholar-note">
      当前暂无可购买套餐，请联系管理员在配置中心启用通用点数套餐。
    </p>

    <div v-if="paymentModalOpen && selectedPackage" class="pricing-modal" @click.self="closePaymentModal">
      <section class="pricing-modal__dialog" role="dialog" aria-modal="true" aria-label="扫码支付">
        <button type="button" class="pricing-modal__close" @click="closePaymentModal">关闭</button>

        <div class="pricing-modal__body">
          <div class="pricing-modal__summary">
            <div class="pricing-modal__eyebrow">扫码支付</div>
            <h3 class="pricing-modal__title">{{ selectedPackage.displayName }}</h3>
            <p class="pricing-modal__lead">{{ selectedPackage.descriptionText }}</p>

            <div class="pricing-modal__facts">
              <div class="pricing-modal__fact">
                <span>支付金额</span>
                <strong>¥{{ selectedPackage.priceLabel }}</strong>
              </div>
              <div class="pricing-modal__fact">
                <span>到账点数</span>
                <strong>{{ selectedPackage.creditsLabel }}</strong>
              </div>
              <div class="pricing-modal__fact">
                <span>使用场景</span>
                <strong>{{ selectedPackage.audienceText }}</strong>
              </div>
              <div class="pricing-modal__fact">
                <span>估算处理量</span>
                <strong>{{ selectedPackage.estimateHeadline }}</strong>
              </div>
            </div>

            <div class="pricing-modal__note">
              <strong>估算说明</strong>
              <span>{{ selectedPackage.estimateText }}</span>
            </div>
          </div>

          <div class="pricing-modal__checkout">
            <p v-if="errorText" class="pricing-modal__inline-note pricing-modal__inline-note--danger">
              {{ errorText }}
            </p>
            <p v-if="okText" class="pricing-modal__inline-note pricing-modal__inline-note--success">
              {{ okText }}
            </p>

            <div v-if="providers.length > 1" class="pricing-modal__providers">
              <button
                v-for="item in providers"
                :key="item.value"
                type="button"
                class="pricing-modal__provider"
                :class="{ 'is-active': provider === item.value }"
                @click="switchProvider(item.value)"
              >
                {{ item.label }}
              </button>
            </div>

            <div v-if="isGuest" class="pricing-modal__guest">
              <div class="pricing-modal__qr-shell">
                <div class="pricing-modal__qr-frame">
                  <div class="pricing-modal__qr-placeholder">
                    <span class="pricing-modal__qr-spinner"></span>
                    <span>登录后生成支付二维码</span>
                  </div>
                </div>
              </div>
              <p class="pricing-modal__guest-text">登录后即可生成当前套餐的支付二维码，支付成功后自动到账。</p>
              <button class="scholar-button" type="button" @click="goLoginForOrder">登录后充值</button>
            </div>

            <div v-else class="pricing-modal__pay">
              <div class="pricing-modal__status-row">
                <span class="pricing-modal__status" :class="`is-${orderStatus}`">{{ orderStatusText }}</span>
                <span class="pricing-modal__countdown">剩余 {{ formattedRemain }}</span>
              </div>

              <div class="pricing-modal__progress">
                <span class="pricing-modal__progress-bar" :style="{ width: `${countdownProgress}%` }"></span>
              </div>

              <div class="pricing-modal__qr-shell">
                <div class="pricing-modal__qr-frame" :class="{ 'is-loading': loading && !qrCodeDataUrl }">
                  <img v-if="qrCodeDataUrl" :src="qrCodeDataUrl" alt="支付二维码" class="pricing-modal__qr-image" />
                  <div v-else class="pricing-modal__qr-placeholder">
                    <span class="pricing-modal__qr-spinner"></span>
                    <span>{{ loading ? "正在生成支付二维码..." : "支付二维码待生成" }}</span>
                  </div>
                </div>
              </div>

              <div class="pricing-modal__caption">
                <strong>{{ providerMeta.label }}</strong>
                <span>{{ providerMeta.captionText }}</span>
              </div>

              <div class="pricing-modal__actions">
                <button class="scholar-button scholar-button--secondary" type="button" @click="refreshOrder">刷新二维码</button>
                <button v-if="paymentTestMode" class="scholar-button" type="button" @click="mockPay">模拟已支付</button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { useBuyCreditsCheckout } from "../composables/useBuyCreditsCheckout"
import { userHttp } from "../lib/http"
import { getPartnerTracking } from "../lib/partnerTracking"
import { normalizePackageOption, resolvePaymentError, resolveProviderOptions } from "../lib/buyCredits"
import { ensureUserLogin } from "../lib/requireLogin"
import { getUserToken } from "../lib/session"

const emit = defineEmits(["paid"])
const router = useRouter()
const route = useRoute()

const errorText = ref("")
const okText = ref("")
const paymentTestMode = ref(false)
const supportedProviderValues = ref([])

const packageOptions = ref([])
const selectedPackage = ref(null)
const paymentModalOpen = ref(false)
const provider = ref("mock")
const tracking = computed(() => getPartnerTracking())
const channelCode = computed(() => {
  const queryValue = normalizeQueryValue(route.query.ch).toUpperCase().slice(0, 32)
  if (queryValue) return queryValue
  return String(tracking.value?.channel_code || "")
})
const channelToken = computed(() => {
  const queryValue = normalizeQueryValue(route.query.ck).slice(0, 128)
  if (queryValue) return queryValue
  return String(tracking.value?.channel_token || "")
})
const {
  loading,
  orderNo,
  qrCodeDataUrl,
  orderStatus,
  orderStatusText,
  formattedRemain,
  countdownProgress,
  resetOrderState,
  createOrder,
  mockPay: runMockPay,
} = useBuyCreditsCheckout({
  userHttp,
  resolvePaymentError,
  onPaid(data, currentOrderNo) {
    okText.value = `支付成功，通用点数已到账（订单号 ${currentOrderNo}）`
    emit("paid", data)
  },
})

const isGuest = computed(() => !getUserToken())
const providers = computed(() => resolveProviderOptions(supportedProviderValues.value, paymentTestMode.value))

const paymentTipText = computed(() => (paymentTestMode.value ? "联调支付模式" : "微信支付已开通"))

const providerMeta = computed(() => {
  const map = {
    wechat: {
      label: "微信支付",
      captionText: "请使用微信扫一扫，支付成功后通用点数自动到账。",
    },
    mock: {
      label: "测试支付",
      captionText: "当前为联调模式，仅用于验证支付链路。",
    },
  }
  return map[provider.value] || map.wechat
})

function normalizeQueryValue(value) {
  if (Array.isArray(value)) {
    return String(value[0] || "").trim()
  }
  return String(value || "").trim()
}

onMounted(loadPackages)

async function loadPackages() {
  errorText.value = ""
  try {
    const packageData = await userHttp.get("/billing/packages", { timeout: 30000 })
    const items = Array.isArray(packageData?.items)
      ? packageData.items.map((item, index) => normalizePackageOption(item, index)).filter(Boolean)
      : []

    if (typeof packageData?.payment_test_mode === "boolean") {
      paymentTestMode.value = packageData.payment_test_mode
    }
    if (Array.isArray(packageData?.supported_providers)) {
      supportedProviderValues.value = packageData.supported_providers
    }
    packageOptions.value = items

    const defaultProvider = providers.value[0]?.value
    if (defaultProvider) {
      provider.value = defaultProvider
    }
    if (!items.length) {
      selectedPackage.value = null
      paymentModalOpen.value = false
      resetOrderState()
      errorText.value = "当前暂无可购买套餐"
    }
  } catch (error) {
    errorText.value = resolvePaymentError(error, "加载充值配置失败，请稍后重试")
  }
}

async function openPackageModal(item) {
  if (!item) return
  selectedPackage.value = item
  paymentModalOpen.value = true
  okText.value = ""
  errorText.value = ""
  resetOrderState()
  if (providers.value.length > 0) {
    provider.value = providers.value[0].value
  }
  if (isGuest.value || providers.value.length === 0) {
    return
  }
  await createCurrentOrder()
}

function closePaymentModal() {
  paymentModalOpen.value = false
  resetOrderState()
}

async function refreshOrder() {
  if (!ensureUserLogin(router, route, "/app/buy")) {
    return
  }
  await createCurrentOrder()
}

async function switchProvider(nextProvider) {
  if (provider.value === nextProvider) return
  provider.value = nextProvider
  if (isGuest.value) {
    return
  }
  await createCurrentOrder()
}

async function createCurrentOrder() {
  if (!selectedPackage.value) return
  errorText.value = ""
  const result = await createOrder({
    provider: provider.value,
    packageName: selectedPackage.value.packageName,
    channelCode: channelCode.value,
    channelToken: channelToken.value,
  })
  if (!result.ok) {
    errorText.value = result.error
  }
}

async function mockPay() {
  if (!ensureUserLogin(router, route, "/app/buy")) {
    errorText.value = "请先登录后再支付"
    return
  }
  if (!orderNo.value) return
  const result = await runMockPay()
  if (!result.ok) {
    errorText.value = result.error
  }
}

function goLoginForOrder() {
  ensureUserLogin(router, route, "/app/buy")
}
</script>

<style scoped>
.pricing-stage {
  display: grid;
  gap: 10px;
}

.pricing-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding: 2px 2px 0;
}

.pricing-hero__copy {
  max-width: 760px;
  display: grid;
  gap: 6px;
}

.pricing-stage__top-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.pricing-stage__tag {
  min-height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}

.pricing-stage__tag--solid {
  background: linear-gradient(135deg, #11335b 0%, #1c5ad7 100%);
  color: #fff;
}

.pricing-stage__tag--soft {
  background: #eaf2ff;
  color: #1f4d9c;
}

.pricing-stage__tag--warn {
  background: #fff0d9;
  color: #9b6112;
}

.pricing-hero__title {
  margin: 0;
  color: #10233b;
  font-size: 28px;
  line-height: 1.05;
  letter-spacing: -0.05em;
  font-weight: 800;
}

.pricing-hero__lead {
  margin: 0;
  color: #516174;
  font-size: 13px;
  line-height: 1.5;
}

.pricing-hero__hint {
  flex-shrink: 0;
  min-width: 180px;
  padding: 10px 12px;
  border-radius: 16px;
  background: linear-gradient(180deg, #f1f5fb 0%, #f8fbff 100%);
  border: 1px solid #d7e2ee;
  display: grid;
  gap: 2px;
}

.pricing-hero__hint strong {
  color: #10233b;
  font-size: 12px;
}

.pricing-hero__hint span {
  color: #5b6b7e;
  font-size: 12px;
  line-height: 1.45;
}

.pricing-card-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.pricing-card {
  min-height: 248px;
  padding: 15px;
  border-radius: 20px;
  border: 1px solid rgba(166, 182, 205, 0.26);
  display: grid;
  gap: 9px;
  background: #fff;
  box-shadow: 0 22px 48px rgba(18, 35, 59, 0.06);
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.pricing-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 28px 56px rgba(18, 35, 59, 0.1);
}

.pricing-card.is-active {
  border-color: rgba(30, 88, 215, 0.35);
  box-shadow: 0 30px 60px rgba(30, 88, 215, 0.12);
}

.pricing-card.is-slate {
  background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
}

.pricing-card.is-azure {
  background: linear-gradient(180deg, #eef5ff 0%, #ffffff 100%);
}

.pricing-card.is-amber {
  background: linear-gradient(180deg, #fff7ed 0%, #ffffff 100%);
}

.pricing-card.is-graphite {
  background: linear-gradient(180deg, #f4f7fb 0%, #ffffff 100%);
}

.pricing-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.pricing-card__name {
  color: #10233b;
  font-size: 20px;
  line-height: 1.08;
  font-weight: 800;
  letter-spacing: -0.04em;
}

.pricing-card__subhead {
  margin: 4px 0 0;
  color: #5d6e81;
  font-size: 11px;
  line-height: 1.4;
}

.pricing-card__badge {
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: rgba(17, 51, 91, 0.9);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  white-space: nowrap;
}

.pricing-card__price {
  display: grid;
  gap: 2px;
}

.pricing-card__price strong {
  color: #0f2440;
  font-size: 27px;
  line-height: 1;
  letter-spacing: -0.06em;
}

.pricing-card__price span {
  color: #728295;
  font-size: 10px;
}

.pricing-card__points {
  display: grid;
  gap: 4px;
  padding: 11px 13px;
  border-radius: 15px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(160, 176, 200, 0.2);
}

.pricing-card__points strong {
  color: #10233b;
  font-size: 18px;
  line-height: 1.2;
  letter-spacing: -0.04em;
}

.pricing-card__points span {
  color: #38506d;
  font-size: 12px;
  line-height: 1.4;
  font-weight: 600;
}

.pricing-card__estimate {
  display: grid;
  gap: 3px;
}

.pricing-card__estimate-kicker {
  color: #7b8a9d;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
}

.pricing-card__estimate p,
.pricing-card__desc {
  margin: 0;
  color: #556577;
  font-size: 11px;
  line-height: 1.45;
}

.pricing-card__action {
  margin-top: auto;
  min-height: 38px;
  border: 0;
  border-radius: 12px;
  background: #111827;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform 0.15s ease,
    opacity 0.15s ease,
    background 0.15s ease;
}

.pricing-card__action:hover {
  transform: translateY(-1px);
  background: #0f172a;
}

.pricing-card__action:disabled {
  opacity: 0.6;
  cursor: default;
  transform: none;
}

.pricing-modal {
  position: fixed;
  inset: 0;
  z-index: 1200;
  padding: 32px 20px;
  background: rgba(7, 16, 28, 0.56);
  backdrop-filter: blur(8px);
  display: grid;
  place-items: center;
}

.pricing-modal__dialog {
  position: relative;
  width: min(980px, 100%);
  max-height: calc(100vh - 64px);
  overflow: auto;
  padding: 28px;
  border-radius: 32px;
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  box-shadow: 0 36px 100px rgba(7, 16, 28, 0.28);
}

.pricing-modal__close {
  position: absolute;
  top: 18px;
  right: 18px;
  min-height: 36px;
  padding: 0 12px;
  border: 0;
  border-radius: 999px;
  background: #eef3f9;
  color: #314355;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.pricing-modal__body {
  display: grid;
  gap: 24px;
  grid-template-columns: minmax(0, 1.1fr) minmax(320px, 0.9fr);
}

.pricing-modal__summary {
  display: grid;
  gap: 18px;
}

.pricing-modal__eyebrow {
  color: #6f8094;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-weight: 700;
}

.pricing-modal__title {
  margin: 0;
  color: #0f223a;
  font-size: 34px;
  line-height: 1.04;
  letter-spacing: -0.05em;
  font-weight: 800;
}

.pricing-modal__lead {
  margin: 0;
  color: #556577;
  font-size: 15px;
  line-height: 1.75;
}

.pricing-modal__facts {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.pricing-modal__fact,
.pricing-modal__note {
  padding: 18px;
  border-radius: 22px;
  background: #f6f9fc;
  border: 1px solid #dbe4ee;
  display: grid;
  gap: 8px;
}

.pricing-modal__fact span,
.pricing-modal__note strong {
  color: #708196;
  font-size: 12px;
  font-weight: 700;
}

.pricing-modal__fact strong,
.pricing-modal__note span {
  color: #11263f;
  font-size: 15px;
  line-height: 1.65;
}

.pricing-modal__checkout {
  display: grid;
  gap: 16px;
  align-content: start;
  padding: 22px;
  border-radius: 28px;
  background: radial-gradient(circle at top, rgba(28, 90, 215, 0.08), transparent 50%), #f8fbff;
  border: 1px solid #dbe5ef;
}

.pricing-modal__providers {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pricing-modal__inline-note {
  margin: 0;
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 13px;
  line-height: 1.6;
}

.pricing-modal__inline-note--danger {
  background: #fff0ed;
  color: #a43d32;
  border: 1px solid #f4c9c2;
}

.pricing-modal__inline-note--success {
  background: #eaf7ef;
  color: #176d48;
  border: 1px solid #c7ebd5;
}

.pricing-modal__provider {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid #cfdae6;
  background: #fff;
  color: #3b4f63;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.pricing-modal__provider.is-active {
  border-color: #1d55c8;
  background: #eaf1ff;
  color: #184696;
}

.pricing-modal__guest,
.pricing-modal__pay {
  display: grid;
  gap: 14px;
  justify-items: center;
}

.pricing-modal__guest-text,
.pricing-modal__caption span {
  margin: 0;
  color: #5c6d80;
  font-size: 13px;
  line-height: 1.7;
  text-align: center;
}

.pricing-modal__status-row {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.pricing-modal__status {
  min-height: 28px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.pricing-modal__status.is-created {
  background: #fff0d8;
  color: #8b5b0b;
}

.pricing-modal__status.is-paid {
  background: #e5f7ed;
  color: #156b45;
}

.pricing-modal__status.is-closed,
.pricing-modal__status.is-refunded {
  background: #ffe7e5;
  color: #a73d33;
}

.pricing-modal__countdown {
  color: #5f7083;
  font-size: 12px;
  font-weight: 700;
}

.pricing-modal__progress {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: #e4ebf3;
  overflow: hidden;
}

.pricing-modal__progress-bar {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2c68e2 0%, #10233b 100%);
  transition: width 0.2s ease;
}

.pricing-modal__qr-shell {
  width: 100%;
  display: grid;
  place-items: center;
}

.pricing-modal__qr-frame {
  width: min(100%, 232px);
  aspect-ratio: 1;
  padding: 16px;
  border-radius: 24px;
  background: #fff;
  border: 1px solid #d8e1eb;
  box-shadow: 0 22px 48px rgba(16, 35, 59, 0.1);
  display: grid;
  place-items: center;
}

.pricing-modal__qr-frame.is-loading {
  animation: pricing-qr-pulse 1.8s ease-in-out infinite;
}

.pricing-modal__qr-image {
  width: min(100%, 180px);
  height: min(100%, 180px);
  object-fit: contain;
  border-radius: 14px;
  background: #fff;
}

.pricing-modal__qr-placeholder {
  display: grid;
  justify-items: center;
  gap: 10px;
  color: #6a7a8d;
  font-size: 13px;
  text-align: center;
}

.pricing-modal__qr-spinner {
  width: 40px;
  height: 40px;
  border-radius: 999px;
  border: 3px solid rgba(28, 90, 215, 0.14);
  border-top-color: rgba(28, 90, 215, 0.88);
  animation: pricing-spin 1s linear infinite;
}

.pricing-modal__caption {
  display: grid;
  gap: 6px;
  justify-items: center;
}

.pricing-modal__caption strong {
  color: #10233b;
  font-size: 16px;
}

.pricing-modal__actions {
  width: 100%;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
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
    box-shadow: 0 22px 48px rgba(16, 35, 59, 0.1);
  }

  50% {
    box-shadow: 0 28px 56px rgba(16, 35, 59, 0.16);
  }
}

@media (max-width: 1080px) {
  .pricing-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .pricing-modal__body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .pricing-stage {
    gap: 12px;
  }

  .pricing-hero {
    flex-direction: column;
    align-items: flex-start;
  }

  .pricing-hero__title {
    font-size: 26px;
  }

  .pricing-hero__hint {
    width: 100%;
    min-width: 0;
  }

  .pricing-card-grid {
    grid-template-columns: 1fr;
  }

  .pricing-card,
  .pricing-modal__dialog {
    padding: 18px;
  }

  .pricing-modal {
    padding: 16px;
  }

  .pricing-modal__dialog {
    max-height: calc(100vh - 32px);
    border-radius: 26px;
  }

  .pricing-modal__facts {
    grid-template-columns: 1fr;
  }

  .pricing-modal__status-row,
  .pricing-modal__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .pricing-modal__actions > * {
    width: 100%;
  }
}
</style>
