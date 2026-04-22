<template>
  <div class="partner-portal-page">
    <section class="partner-portal-shell">
      <header class="partner-portal-head">
        <div>
          <p class="partner-portal-head__eyebrow">渠道返佣专属门户</p>
          <h1 class="partner-portal-head__title">渠道订单与返佣看板</h1>
          <p class="partner-portal-head__desc">本页面仅展示当前渠道的订单、返佣流水与提现数据。</p>
        </div>
        <button type="button" class="partner-portal-head__refresh" :disabled="loading" @click="loadPortalData">
          {{ loading ? "加载中..." : "刷新数据" }}
        </button>
      </header>

      <p v-if="errorText" class="partner-alert partner-alert--danger">{{ errorText }}</p>

      <section v-if="hasPortalCredential && overview" class="partner-overview">
        <div class="partner-overview__meta">
          <span>渠道：{{ overview.channel_name || "-" }}</span>
          <span>渠道编码：{{ overview.channel_code || channelCode }}</span>
          <span>结算月份：{{ overview.statement_month || "-" }}</span>
        </div>
        <div class="partner-overview__cards">
          <article class="partner-card">
            <p>本月订单数</p>
            <strong>{{ Number(overview.month_order_count || 0).toLocaleString() }}</strong>
          </article>
          <article class="partner-card">
            <p>本月净返佣</p>
            <strong>{{ formatFenToCny(overview.month_rebate_fen) }}</strong>
          </article>
          <article class="partner-card">
            <p>待结算返佣</p>
            <strong>{{ formatFenToCny(overview.pending_rebate_fen) }}</strong>
          </article>
          <article class="partner-card">
            <p>累计已结算</p>
            <strong>{{ formatFenToCny(overview.settled_rebate_fen) }}</strong>
          </article>
          <article class="partner-card">
            <p>可提现余额</p>
            <strong>{{ formatFenToCny(overview.withdrawable_fen) }}</strong>
          </article>
          <article class="partner-card">
            <p>提现审核中</p>
            <strong>{{ formatFenToCny(overview.pending_withdraw_fen) }}</strong>
          </article>
        </div>
      </section>

      <section v-if="hasPortalCredential && overview" class="partner-data-grid">
        <article class="partner-data-card">
          <header class="partner-data-card__head">
            <h2>实时提现申请</h2>
            <span>门槛 ¥100.00</span>
          </header>
          <div class="partner-withdraw-shell">
            <label class="partner-withdraw-field">
              <span>提现金额（元）</span>
              <input v-model.number="withdrawAmountCny" type="number" min="100" step="0.01" />
            </label>
            <label class="partner-withdraw-field partner-withdraw-field--wide">
              <span>备注（可选）</span>
              <input v-model.trim="withdrawNote" type="text" maxlength="120" placeholder="例如：4月结算提现" />
            </label>
            <div class="partner-withdraw-actions">
              <button type="button" :disabled="withdrawSubmitting" @click="submitWithdrawApply">
                {{ withdrawSubmitting ? "提交中..." : "提交提现申请" }}
              </button>
              <span>当前可提：{{ formatFenToCny(overview.withdrawable_fen) }}</span>
            </div>
          </div>
        </article>

        <article class="partner-data-card">
          <header class="partner-data-card__head">
            <h2>订单列表</h2>
            <span>{{ orders.length }} 条</span>
          </header>
          <div class="partner-table-wrap">
            <table class="partner-table">
              <thead>
                <tr>
                  <th>订单号</th>
                  <th>用户ID</th>
                  <th>套餐</th>
                  <th>订单金额</th>
                  <th>返佣比例</th>
                  <th>净返佣</th>
                  <th>状态</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in orders" :key="item.order_no">
                  <td>{{ item.order_no }}</td>
                  <td>{{ item.user_id }}</td>
                  <td>{{ item.package_name || "-" }}</td>
                  <td>{{ formatFenToCny(item.amount_fen) }}</td>
                  <td>{{ formatRate(item.rebate_rate_bp) }}</td>
                  <td>{{ formatFenToCny(item.net_rebate_fen) }}</td>
                  <td>{{ formatStatus(item.order_status) }}</td>
                  <td>{{ formatDateTime(item.created_at) }}</td>
                </tr>
                <tr v-if="orders.length === 0">
                  <td colspan="8" class="partner-table__empty">暂无订单数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="partner-data-card">
          <header class="partner-data-card__head">
            <h2>返佣流水</h2>
            <span>{{ ledger.length }} 条</span>
          </header>
          <div class="partner-table-wrap">
            <table class="partner-table">
              <thead>
                <tr>
                  <th>流水ID</th>
                  <th>订单号</th>
                  <th>类型</th>
                  <th>返佣金额</th>
                  <th>状态</th>
                  <th>结算月</th>
                  <th>创建时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in ledger" :key="item.id">
                  <td>{{ item.id }}</td>
                  <td>{{ item.order_no || "-" }}</td>
                  <td>{{ formatEntryType(item.entry_type) }}</td>
                  <td>{{ formatFenToCny(item.rebate_amount_fen) }}</td>
                  <td>{{ formatStatus(item.status) }}</td>
                  <td>{{ item.statement_month || "-" }}</td>
                  <td>{{ formatDateTime(item.created_at) }}</td>
                </tr>
                <tr v-if="ledger.length === 0">
                  <td colspan="7" class="partner-table__empty">暂无返佣流水</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="partner-data-card">
          <header class="partner-data-card__head">
            <h2>提现记录</h2>
            <span>{{ withdrawals.length }} 条</span>
          </header>
          <div class="partner-table-wrap">
            <table class="partner-table">
              <thead>
                <tr>
                  <th>申请单号</th>
                  <th>金额</th>
                  <th>状态</th>
                  <th>备注</th>
                  <th>驳回原因</th>
                  <th>申请时间</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in withdrawals" :key="item.id">
                  <td>{{ item.request_no }}</td>
                  <td>{{ formatFenToCny(item.apply_amount_fen) }}</td>
                  <td>{{ formatStatus(item.status) }}</td>
                  <td>{{ item.note || "-" }}</td>
                  <td>{{ item.reject_reason || "-" }}</td>
                  <td>{{ formatDateTime(item.created_at) }}</td>
                </tr>
                <tr v-if="withdrawals.length === 0">
                  <td colspan="6" class="partner-table__empty">暂无提现记录</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

      </section>

      <section v-if="!hasPortalCredential" class="partner-empty">
        <h2>渠道访问参数缺失</h2>
        <p>请使用后台生成的专属渠道链接访问该页面。</p>
      </section>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { useRoute } from "vue-router"

import { userHttp } from "../../lib/http"

const route = useRoute()
const loading = ref(false)
const errorText = ref("")
const overview = ref(null)
const orders = ref([])
const ledger = ref([])
const withdrawals = ref([])
const withdrawAmountCny = ref(100)
const withdrawNote = ref("")
const withdrawSubmitting = ref(false)

const channelCode = computed(() => normalizeQueryValue(route.query.ch).toUpperCase())
const portalToken = computed(() => normalizeQueryValue(route.query.pk))
const hasPortalCredential = computed(() => Boolean(channelCode.value && portalToken.value))

watch(
  () => [channelCode.value, portalToken.value],
  () => {
    loadPortalData()
  },
  { immediate: true }
)

async function loadPortalData() {
  errorText.value = ""
  if (!hasPortalCredential.value) {
    overview.value = null
    orders.value = []
    ledger.value = []
    withdrawals.value = []
    return
  }
  loading.value = true
  try {
    const params = { ch: channelCode.value, pk: portalToken.value }
    const [overviewResp, ordersResp, ledgerResp, withdrawalResp] = await Promise.all([
      userHttp.get("/partners/portal/overview", { params, timeout: 30000 }),
      userHttp.get("/partners/portal/orders", { params: { ...params, page: 1, page_size: 20 }, timeout: 30000 }),
      userHttp.get("/partners/portal/ledger", { params: { ...params, page: 1, page_size: 20 }, timeout: 30000 }),
      userHttp.get("/partners/portal/withdrawals", { params: { ...params, page: 1, page_size: 20 }, timeout: 30000 }),
    ])
    overview.value = overviewResp || null
    orders.value = Array.isArray(ordersResp?.items) ? ordersResp.items : []
    ledger.value = Array.isArray(ledgerResp?.items) ? ledgerResp.items : []
    withdrawals.value = Array.isArray(withdrawalResp?.items) ? withdrawalResp.items : []
  } catch (error) {
    errorText.value = String(error?.message || "加载渠道数据失败，请稍后重试")
  } finally {
    loading.value = false
  }
}

async function submitWithdrawApply() {
  if (!hasPortalCredential.value || !overview.value) return
  withdrawSubmitting.value = true
  errorText.value = ""
  try {
    await userHttp.post(
      "/partners/portal/withdraw-apply",
      {
        apply_amount_cny: Number(withdrawAmountCny.value || 0),
        note: String(withdrawNote.value || "").trim(),
      },
      {
        params: { ch: channelCode.value, pk: portalToken.value },
        timeout: 30000,
      }
    )
    withdrawNote.value = ""
    await loadPortalData()
  } catch (error) {
    errorText.value = String(error?.message || "提交提现申请失败")
  } finally {
    withdrawSubmitting.value = false
  }
}

function normalizeQueryValue(value) {
  if (Array.isArray(value)) {
    return String(value[0] || "").trim()
  }
  return String(value || "").trim()
}

function formatFenToCny(value) {
  const amount = Number(value || 0) / 100
  if (!Number.isFinite(amount)) {
    return "¥0.00"
  }
  return `¥${amount.toFixed(2)}`
}

function formatRate(value) {
  const bp = Number(value || 0)
  if (!Number.isFinite(bp)) {
    return "-"
  }
  return `${(bp / 100).toFixed(2)}%`
}

function formatDateTime(value) {
  const text = String(value || "").trim()
  if (!text) {
    return "-"
  }
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) {
    return text
  }
  return date.toLocaleString("zh-CN", { hour12: false })
}

function formatEntryType(value) {
  const normalized = String(value || "").toLowerCase()
  if (normalized === "accrual") {
    return "入账"
  }
  if (normalized === "reversal") {
    return "冲正"
  }
  return normalized || "-"
}

function formatStatus(value) {
  const normalized = String(value || "").toLowerCase()
  const statusMap = {
    created: "待支付",
    paid: "已支付",
    closed: "已关闭",
    refunded: "已退款",
    pending: "待结算",
    settled: "已结算",
    reversed: "已冲正",
    generated: "已生成",
    approved: "已通过",
    rejected: "已驳回",
  }
  return statusMap[normalized] || normalized || "-"
}
</script>

<style scoped>
.partner-portal-page {
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(circle at 15% 12%, rgba(30, 91, 223, 0.16), transparent 34%),
    radial-gradient(circle at 88% 22%, rgba(24, 145, 110, 0.14), transparent 28%),
    #f3f7ff;
}

.partner-portal-shell {
  width: min(1380px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 16px;
}

.partner-portal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 18px;
  background: linear-gradient(135deg, #123b7a 0%, #1f5fd6 100%);
  color: #fff;
  box-shadow: 0 20px 36px rgba(13, 42, 88, 0.24);
}

.partner-portal-head__eyebrow {
  margin: 0;
  opacity: 0.9;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.partner-portal-head__title {
  margin: 6px 0;
  font-size: 30px;
  line-height: 1.08;
}

.partner-portal-head__desc {
  margin: 0;
  font-size: 13px;
  opacity: 0.9;
}

.partner-portal-head__refresh {
  min-height: 40px;
  padding: 0 16px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.36);
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.partner-portal-head__refresh:disabled {
  opacity: 0.64;
  cursor: default;
}

.partner-alert {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.65;
}

.partner-alert--danger {
  border: 1px solid #f1c7c3;
  background: #fff1ef;
  color: #a83f35;
}

.partner-overview,
.partner-data-card,
.partner-empty {
  border-radius: 16px;
  background: #fff;
  border: 1px solid #dae3f1;
  box-shadow: 0 14px 28px rgba(19, 40, 72, 0.08);
}

.partner-overview {
  padding: 16px;
  display: grid;
  gap: 14px;
}

.partner-overview__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  color: #4f6181;
  font-size: 13px;
}

.partner-overview__cards {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.partner-card {
  padding: 14px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f6f9ff 0%, #ffffff 100%);
  border: 1px solid #dde6f2;
}

.partner-card p {
  margin: 0;
  color: #617391;
  font-size: 12px;
}

.partner-card strong {
  display: block;
  margin-top: 8px;
  color: #0f2849;
  font-size: 24px;
  line-height: 1.1;
}

.partner-data-grid {
  display: grid;
  gap: 14px;
}

.partner-data-card {
  overflow: hidden;
}

.partner-withdraw-shell {
  padding: 14px;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.partner-withdraw-field {
  display: grid;
  gap: 6px;
}

.partner-withdraw-field span {
  color: #4d6283;
  font-size: 12px;
}

.partner-withdraw-field input {
  min-height: 38px;
  border-radius: 10px;
  border: 1px solid #d4deeb;
  padding: 0 10px;
}

.partner-withdraw-field--wide {
  grid-column: 1 / -1;
}

.partner-withdraw-actions {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.partner-withdraw-actions button {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 0;
  background: #123b7a;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}

.partner-withdraw-actions button:disabled {
  opacity: 0.64;
  cursor: default;
}

.partner-withdraw-actions span {
  color: #4d6283;
  font-size: 13px;
}

.partner-data-card__head {
  min-height: 52px;
  padding: 0 14px;
  border-bottom: 1px solid #e3eaf5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.partner-data-card__head h2 {
  margin: 0;
  color: #142f55;
  font-size: 17px;
}

.partner-data-card__head span {
  color: #647796;
  font-size: 13px;
  font-weight: 700;
}

.partner-table-wrap {
  overflow: auto;
}

.partner-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
}

.partner-table th,
.partner-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #edf2f8;
  text-align: left;
  font-size: 12px;
  color: #304867;
  white-space: nowrap;
}

.partner-table th {
  color: #5c7192;
  font-weight: 700;
  background: #f8fbff;
}

.partner-table__empty {
  text-align: center;
  color: #7d8da6;
}

.partner-empty {
  padding: 24px;
}

.partner-empty h2 {
  margin: 0 0 10px;
  color: #173760;
}

.partner-empty p {
  margin: 0;
  color: #62728a;
}

@media (max-width: 1080px) {
  .partner-overview__cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .partner-portal-page {
    padding: 14px;
  }

  .partner-portal-head {
    padding: 14px;
    flex-direction: column;
    align-items: stretch;
  }

  .partner-portal-head__title {
    font-size: 24px;
  }

  .partner-overview__cards {
    grid-template-columns: 1fr;
  }
}
</style>
