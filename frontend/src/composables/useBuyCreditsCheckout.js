import { computed, onUnmounted, ref } from "vue"

export function useBuyCreditsCheckout({ userHttp, resolvePaymentError, onPaid }) {
  const loading = ref(false)
  const orderNo = ref("")
  const qrCodeDataUrl = ref("")
  const remainSeconds = ref(0)
  const expireSecondsTotal = ref(300)
  const orderStatus = ref("created")

  let countdownTimer = null
  let pollTimer = null

  const orderStatusText = computed(() => {
    const map = {
      created: "待支付",
      paid: "已支付",
      closed: "已过期",
      refunded: "已退款",
    }
    return map[orderStatus.value] || orderStatus.value
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

  onUnmounted(stopTimers)

  function resetOrderState() {
    stopTimers()
    orderNo.value = ""
    qrCodeDataUrl.value = ""
    remainSeconds.value = 0
    expireSecondsTotal.value = 300
    orderStatus.value = "created"
  }

  async function createOrder({ provider, packageName, channelCode = "", channelToken = "" }) {
    if (!packageName) return { ok: false, error: "" }
    loading.value = true
    try {
      const payload = { provider, package_name: packageName }
      const normalizedChannelCode = String(channelCode || "").trim()
      const normalizedChannelToken = String(channelToken || "").trim()
      if (normalizedChannelCode) {
        payload.channel_code = normalizedChannelCode
      }
      if (normalizedChannelToken) {
        payload.channel_token = normalizedChannelToken
      }
      const data = await userHttp.post(
        "/billing/create-order",
        payload,
        { timeout: 45000 }
      )
      orderNo.value = data.order_no
      qrCodeDataUrl.value = data.qrcode_data_url
      expireSecondsTotal.value = Number(data.expire_seconds || 300)
      remainSeconds.value = expireSecondsTotal.value
      orderStatus.value = data.status || "created"
      startTimers()
      return { ok: true, data }
    } catch (error) {
      return { ok: false, error: resolvePaymentError(error, "创建订单失败") }
    } finally {
      loading.value = false
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
    if (!orderNo.value) return { ok: false, error: "" }
    try {
      const data = await userHttp.post(`/billing/order-pay/${orderNo.value}`)
      onPaySuccess(data)
      return { ok: true, data }
    } catch (error) {
      return { ok: false, error: resolvePaymentError(error, "支付失败") }
    }
  }

  function onPaySuccess(data) {
    stopTimers()
    orderStatus.value = "paid"
    onPaid(data, orderNo.value)
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

  return {
    loading,
    orderNo,
    qrCodeDataUrl,
    remainSeconds,
    expireSecondsTotal,
    orderStatus,
    orderStatusText,
    formattedRemain,
    countdownProgress,
    resetOrderState,
    createOrder,
    checkOrderStatus,
    mockPay,
    stopTimers,
  }
}
