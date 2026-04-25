<template>
  <AdminShell title="订单管理" subtitle="筛选、详情与退款操作。">
    <section class="gw-admin-order-overview">
      <article class="gw-admin-order-overview__hero">
        <div class="gw-admin-order-overview__eyebrow">订单工作台</div>
        <h2>订单管理</h2>
        <p>常用筛选、订单状态和退款动作都集中处理，减少来回切页。</p>
      </article>
      <article class="gw-admin-order-overview__stat">
        <span>当前结果</span>
        <strong>{{ rows.length }}</strong>
        <em>按筛选条件返回</em>
      </article>
      <article class="gw-admin-order-overview__stat">
        <span>已支付</span>
        <strong>{{ paidCount }}</strong>
        <em>当前结果中的有效订单</em>
      </article>
      <article class="gw-admin-order-overview__stat">
        <span>当前收入</span>
        <strong>¥{{ currentRevenueCny }}</strong>
        <em>基于当前结果统计</em>
      </article>
    </section>

    <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
      <div class="mb-4 space-y-4 rounded-2xl border border-[#dee6ed] bg-white p-4">
        <div class="grid gap-2 md:grid-cols-3">
          <input v-model.trim="filters.qPhone" class="rounded-lg border border-[#ccd5dd] px-3 py-2 text-sm outline-none" placeholder="手机号" />
          <input v-model.trim="filters.orderNo" class="rounded-lg border border-[#ccd5dd] px-3 py-2 text-sm outline-none" placeholder="订单号" />
          <input v-model.trim="filters.providerKeyword" class="rounded-lg border border-[#ccd5dd] px-3 py-2 text-sm outline-none" placeholder="支付通道关键字（可选）" />
        </div>

        <div class="grid gap-3 md:grid-cols-3">
          <div>
            <div class="mb-2 text-xs font-semibold tracking-[0.08em] text-[#6b7a86]">支付方式</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="item in providerOptions" :key="item.value || 'all-provider'" type="button" :class="chipClass(filters.provider, item.value)" @click="filters.provider = item.value">
                {{ item.label }}
              </button>
            </div>
          </div>

          <div>
            <div class="mb-2 text-xs font-semibold tracking-[0.08em] text-[#6b7a86]">订单状态</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="item in statusOptions" :key="item.value || 'all-status'" type="button" :class="chipClass(filters.status, item.value)" @click="filters.status = item.value">
                {{ item.label }}
              </button>
            </div>
          </div>

          <div>
            <div class="mb-2 text-xs font-semibold tracking-[0.08em] text-[#6b7a86]">来源</div>
            <div class="flex flex-wrap gap-2">
              <button v-for="item in sourceOptions" :key="item.value || 'all-source'" type="button" :class="chipClass(filters.source, item.value)" @click="filters.source = item.value">
                {{ item.label }}
              </button>
            </div>
          </div>
        </div>

        <div class="flex flex-wrap gap-2">
          <button class="scholar-button" @click="loadData">查询</button>
          <button class="scholar-button scholar-button--secondary" @click="resetFilters">重置</button>
        </div>

        <div class="flex flex-wrap gap-4 text-xs text-[#4b5965]">
          <span>订单 Web: {{ sourceOrderStats.web || 0 }}</span>
          <span>订单 小程序: {{ sourceOrderStats.miniapp || 0 }}</span>
          <span>收入 Web: ¥{{ sourceRevenueStats.web || 0 }}</span>
          <span>收入 小程序: ¥{{ sourceRevenueStats.miniapp || 0 }}</span>
        </div>
      </div>

      <div class="overflow-x-auto admin-order-table-shell">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="border-b border-[#e1e6eb] text-left text-[#5a6671]">
              <th class="px-2 py-2">订单号</th>
              <th class="px-2 py-2">用户ID</th>
              <th class="px-2 py-2">金额</th>
              <th class="px-2 py-2">到账通用点数</th>
              <th class="px-2 py-2">支付方式</th>
              <th class="px-2 py-2">来源</th>
              <th class="px-2 py-2">状态</th>
              <th class="px-2 py-2">首充</th>
              <th class="px-2 py-2">时间</th>
              <th class="px-2 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.order_no" class="border-b border-[#eef2f5]">
              <td class="px-2 py-2">{{ row.order_no }}</td>
              <td class="px-2 py-2">{{ row.user_id }}</td>
              <td class="px-2 py-2">¥{{ Number(row.amount_cny || 0).toFixed(2) }}</td>
              <td class="px-2 py-2">{{ formatCredits(rowRechargeFen(row)) }}</td>
              <td class="px-2 py-2">{{ mapProvider(row.provider) }}</td>
              <td class="px-2 py-2">{{ mapSource(row.source) }}</td>
              <td class="px-2 py-2">
                <span :class="statusClass(row.status)" class="inline-flex items-center rounded-full border px-2 py-1 text-xs">{{ mapStatus(row.status) }}</span>
              </td>
              <td class="px-2 py-2">{{ row.is_first_pay ? '是' : '否' }}</td>
              <td class="px-2 py-2">{{ formatTime(row.created_at) }}</td>
              <td class="px-2 py-2">
                <div class="flex gap-2">
                  <button class="scholar-button scholar-button--compact" @click="openDetail(row.order_no)">详情</button>
                  <button v-if="canRefund" class="scholar-button scholar-button--secondary scholar-button--compact" :disabled="row.status !== 'paid'" @click="refund(row)">退款</button>
                </div>
              </td>
            </tr>
            <tr v-if="rows.length === 0">
              <td class="px-2 py-3 text-[#5b6771]" colspan="10">暂无订单</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="admin-order-mobile-list">
        <article v-for="row in rows" :key="`mobile-${row.order_no}`" class="admin-order-card">
          <div class="admin-order-card__head">
            <div>
              <div class="admin-order-card__eyebrow">订单号</div>
              <strong class="admin-order-card__title">{{ row.order_no }}</strong>
            </div>
            <span :class="statusClass(row.status)" class="inline-flex items-center rounded-full border px-2 py-1 text-xs">{{ mapStatus(row.status) }}</span>
          </div>

          <div class="admin-order-card__grid">
            <div><span>用户</span><strong>#{{ row.user_id }}</strong></div>
            <div><span>金额</span><strong>¥{{ row.amount_cny }}</strong></div>
            <div><span>到账通用点数</span><strong>{{ formatCredits(rowRechargeFen(row)) }}</strong></div>
            <div><span>支付方式</span><strong>{{ mapProvider(row.provider) }}</strong></div>
            <div><span>来源</span><strong>{{ mapSource(row.source) }}</strong></div>
            <div><span>首充</span><strong>{{ row.is_first_pay ? '是' : '否' }}</strong></div>
            <div><span>时间</span><strong>{{ formatTime(row.created_at) }}</strong></div>
          </div>

          <div class="admin-order-card__actions">
            <button class="scholar-button scholar-button--compact" @click="openDetail(row.order_no)">详情</button>
            <button v-if="canRefund" class="scholar-button scholar-button--secondary scholar-button--compact" :disabled="row.status !== 'paid'" @click="refund(row)">退款</button>
          </div>
        </article>
        <div v-if="rows.length === 0" class="text-sm text-[#5b6771]">暂无订单</div>
      </div>
    </section>

    <section v-if="detail" class="mt-4 rounded-2xl border border-[#d9dee4] bg-white p-5 text-sm">
      <div class="mb-3 flex items-center justify-between">
        <h3 class="text-base font-semibold">订单详情 {{ detail.order_no }}</h3>
        <button class="scholar-button scholar-button--secondary scholar-button--compact" @click="detail = null">关闭</button>
      </div>
      <div class="grid gap-2 md:grid-cols-2">
        <div>用户：{{ detail.user_id }} {{ detail.user_phone ? `(${detail.user_phone})` : '' }}</div>
        <div>金额：¥{{ Number(detail.amount_cny || 0).toFixed(2) }}</div>
        <div>到账通用点数：{{ formatCredits(rowRechargeFen(detail)) }}</div>
        <div>支付方式：{{ mapProvider(detail.provider) }}</div>
        <div>来源：{{ mapSource(detail.source) }}</div>
        <div>状态：{{ mapStatus(detail.status) }}</div>
        <div>首充：{{ detail.is_first_pay ? '是' : '否' }}</div>
        <div>下单时间：{{ formatTime(detail.created_at) }}</div>
        <div>更新时间：{{ formatTime(detail.updated_at) }}</div>
      </div>
    </section>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

const rows = ref([])
const detail = ref(null)
const sourceOrderStats = ref({ web: 0, miniapp: 0, other: 0, total: 0 })
const sourceRevenueStats = ref({ web: 0, miniapp: 0, other: 0, total: 0 })
const filters = reactive({
  qPhone: "",
  orderNo: "",
  providerKeyword: "",
  provider: "",
  status: "",
  source: "",
})

const canRefund = computed(() => adminHasPermission("orders:refund"))
const providerOptions = [
  { value: "", label: "全部" },
  { value: "mock", label: "测试支付" },
  { value: "wechat", label: "微信支付" },
  { value: "alipay", label: "支付宝" },
]
const statusOptions = [
  { value: "", label: "全部" },
  { value: "paid", label: "已支付" },
  { value: "created", label: "待支付" },
  { value: "closed", label: "已关闭" },
  { value: "refunded", label: "已退款" },
]
const sourceOptions = [
  { value: "", label: "全部" },
  { value: "web", label: "Web" },
  { value: "miniapp", label: "小程序" },
  { value: "other", label: "其他" },
]
const paidCount = computed(() => rows.value.filter((row) => String(row.status || "") === "paid").length)
const currentRevenueCny = computed(() =>
  rows.value
    .reduce((sum, row) => sum + Number(row.amount_cny || 0), 0)
    .toFixed(2)
)

onMounted(loadData)

async function loadData() {
  const params = {
    page: 1,
    page_size: 100,
    q_phone: filters.qPhone || undefined,
    order_no: filters.orderNo || undefined,
    provider: filters.provider || undefined,
    status: filters.status || undefined,
    source: filters.source || undefined,
  }
  const data = await adminHttp.get("/admin/orders", { params })
  rows.value = data.items || []
  sourceOrderStats.value = data.source_stats?.orders || { web: 0, miniapp: 0, other: 0, total: 0 }
  sourceRevenueStats.value = data.source_stats?.revenue || { web: 0, miniapp: 0, other: 0, total: 0 }

  if (filters.providerKeyword) {
    const keyword = String(filters.providerKeyword).trim().toLowerCase()
    rows.value = rows.value.filter((row) => String(row.provider || "").toLowerCase().includes(keyword))
  }
}

function resetFilters() {
  filters.qPhone = ""
  filters.orderNo = ""
  filters.providerKeyword = ""
  filters.provider = ""
  filters.status = ""
  filters.source = ""
  loadData()
}

async function openDetail(orderNo) {
  detail.value = await adminHttp.get(`/admin/orders/${orderNo}/detail`)
}

async function refund(row) {
  const confirmed = window.confirm(`确认退款订单 ${row.order_no} 吗？`)
  if (!confirmed) return
  await adminHttp.post(`/admin/orders/${row.order_no}/refund`)
  await loadData()
  if (detail.value?.order_no === row.order_no) {
    await openDetail(row.order_no)
  }
}

function mapProvider(provider) {
  const mapping = {
    mock: "测试支付",
    wechat: "微信支付",
    alipay: "支付宝",
  }
  return mapping[provider] || provider
}

function mapSource(source) {
  const mapping = {
    web: "Web",
    miniapp: "小程序",
    other: "其他",
  }
  return mapping[source] || "其他"
}

function mapStatus(status) {
  const mapping = {
    paid: "已支付",
    created: "待支付",
    closed: "已关闭",
    refunded: "已退款",
  }
  return mapping[status] || status
}

function rowRechargeFen(row) {
  if (typeof row?.recharge_fen === "number") return row.recharge_fen
  if (typeof row?.credits === "number") return row.credits
  return 0
}

function formatCredits(value) {
  return `${Number(value || 0).toLocaleString()} 通用点数`
}

function statusClass(status) {
  if (status === "paid") return "border-[#111111] bg-[#111111] text-white"
  if (status === "refunded") return "border-[#111111] bg-white text-[#111111]"
  if (status === "closed") return "border-[#111111] bg-white text-[#111111]"
  return "border-[#111111] bg-white text-[#111111]"
}

function chipClass(current, value) {
  const active = current === value
  if (active) {
    return "is-active rounded-xl border border-[#111111] bg-[#111111] px-3 py-1.5 text-sm font-medium text-white"
  }
  return "rounded-xl border border-[#111111] bg-white px-3 py-1.5 text-sm text-[#111111]"
}

function formatTime(value) {
  return value ? String(value).slice(0, 19).replace("T", " ") : "-"
}
</script>

<style scoped>
.gw-admin-order-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) repeat(3, minmax(0, 0.62fr));
  gap: 14px;
  margin-bottom: 16px;
}

.gw-admin-order-overview__hero,
.gw-admin-order-overview__stat,
.admin-order-card {
  border: 1px solid rgba(30, 91, 223, 0.12);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 255, 0.94));
  box-shadow: 0 16px 30px rgba(30, 91, 223, 0.08);
}

.gw-admin-order-overview__hero {
  padding: 20px 22px;
  display: grid;
  gap: 8px;
}

.gw-admin-order-overview__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6c87ac;
}

.gw-admin-order-overview__hero h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.1;
  color: #1f3555;
}

.gw-admin-order-overview__hero p {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #607894;
}

.gw-admin-order-overview__stat {
  padding: 18px 18px 16px;
  display: grid;
  gap: 6px;
}

.gw-admin-order-overview__stat span {
  font-size: 12px;
  color: #6d84a2;
}

.gw-admin-order-overview__stat strong {
  font-size: 24px;
  line-height: 1.08;
  color: #1e5bdf;
}

.gw-admin-order-overview__stat em {
  font-style: normal;
  font-size: 12px;
  line-height: 1.6;
  color: #68809d;
}

.admin-order-mobile-list {
  display: none;
}

.admin-order-card {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.admin-order-card + .admin-order-card {
  margin-top: 12px;
}

.admin-order-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.admin-order-card__eyebrow {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6b85a8;
}

.admin-order-card__title {
  display: block;
  margin-top: 6px;
  font-size: 15px;
  line-height: 1.6;
  color: #1f3555;
  word-break: break-all;
}

.admin-order-card__grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.admin-order-card__grid div {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(30, 91, 223, 0.1);
  background: #ffffff;
}

.admin-order-card__grid span {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6c85a8;
}

.admin-order-card__grid strong {
  font-size: 13px;
  line-height: 1.6;
  color: #1f3555;
  word-break: break-word;
}

.admin-order-card__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 980px) {
  .gw-admin-order-overview {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .gw-admin-order-overview__hero {
    grid-column: 1 / -1;
  }
}

@media (max-width: 768px) {
  .gw-admin-order-overview {
    grid-template-columns: 1fr;
  }

  .admin-order-table-shell {
    display: none;
  }

  .admin-order-mobile-list {
    display: block;
  }

  .admin-order-card__grid {
    grid-template-columns: 1fr;
  }
}
</style>
