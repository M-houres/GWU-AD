<template>
  <AdminShell title="渠道返佣" subtitle="渠道创建、链接查看、返佣流水与提现管理。">
    <section class="admin-partner-page">
      <div class="admin-partner-grid">
        <section class="admin-partner-panel">
          <div class="admin-partner-panel__head">
            <div>
              <div class="admin-partner-panel__eyebrow">渠道配置</div>
              <h3>{{ editingChannelId ? "编辑渠道" : "新建渠道" }}</h3>
            </div>
          </div>
          <p class="admin-partner-note">
            返佣基于专属链接归属用户的已支付消费流水计算，比例按百分比设置。
          </p>

          <div class="admin-partner-form">
            <label>
              <span>渠道名称</span>
              <input v-model.trim="channelForm.name" class="admin-partner-input" placeholder="例如：华东高校代理" />
            </label>
            <label>
              <span>渠道编码</span>
              <input v-model.trim="channelForm.channel_code" class="admin-partner-input" placeholder="可留空自动生成" />
            </label>
            <label>
              <span>联系人</span>
              <input v-model.trim="channelForm.contact_name" class="admin-partner-input" placeholder="联系人姓名" />
            </label>
            <label>
              <span>联系电话</span>
              <input v-model.trim="channelForm.contact_phone" class="admin-partner-input" placeholder="联系电话" />
            </label>
            <label>
              <span>默认返佣比例（%）</span>
              <input
                v-model.number="channelForm.rebate_rate_pct"
                type="number"
                min="0"
                max="100"
                step="0.01"
                class="admin-partner-input"
                placeholder="例如 15 表示 15%"
              />
            </label>
            <label v-if="editingChannelId">
              <span>渠道状态</span>
              <select v-model="channelForm.status" class="admin-partner-input">
                <option value="active">启用</option>
                <option value="disabled">停用</option>
              </select>
            </label>
          </div>

          <div class="admin-partner-actions">
            <button class="scholar-button" :disabled="submitting || !canManage" @click="saveChannel">
              {{ submitting ? "提交中..." : editingChannelId ? "保存渠道" : "创建渠道" }}
            </button>
            <button class="scholar-button scholar-button--secondary" :disabled="submitting" @click="resetChannelForm">重置</button>
          </div>
          <p v-if="hintText" class="admin-partner-hint admin-partner-hint--success">{{ hintText }}</p>
          <p v-if="errorText" class="admin-partner-hint admin-partner-hint--danger">{{ errorText }}</p>
          <p v-if="!canManage" class="admin-partner-hint">当前账号仅有查看权限，不能修改渠道和月结。</p>
        </section>

        <section class="admin-partner-panel">
          <div class="admin-partner-panel__head">
            <div>
              <div class="admin-partner-panel__eyebrow">月结生成</div>
              <h3>按渠道生成月结</h3>
            </div>
          </div>

          <div class="admin-partner-form">
            <label>
              <span>渠道</span>
              <select v-model="statementForm.channel_id" class="admin-partner-input">
                <option value="">请选择渠道</option>
                <option v-for="item in channels" :key="item.id" :value="String(item.id)">
                  {{ item.name }}（{{ item.channel_code }}）
                </option>
              </select>
            </label>
            <label>
              <span>结算月份</span>
              <input v-model.trim="statementForm.statement_month" class="admin-partner-input" placeholder="YYYY-MM，例如 2026-04" />
            </label>
          </div>

          <div class="admin-partner-actions">
            <button class="scholar-button" :disabled="statementSubmitting || !canManage" @click="generateStatement">
              {{ statementSubmitting ? "生成中..." : "生成月结" }}
            </button>
          </div>
        </section>
      </div>

      <section class="admin-partner-panel">
        <div class="admin-partner-panel__head">
          <div>
            <div class="admin-partner-panel__eyebrow">渠道列表</div>
            <h3>返佣渠道</h3>
          </div>
          <button class="scholar-button scholar-button--secondary" @click="loadAll">刷新</button>
        </div>

        <div class="admin-partner-table-wrap">
          <table class="admin-partner-table">
            <thead>
              <tr>
                <th>渠道</th>
                <th>返佣比例</th>
                <th>待结算</th>
                <th>已结算</th>
                <th>状态</th>
                <th>专属链接</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in channels" :key="item.id">
                <td>
                  <div class="admin-partner-channel">
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.channel_code }}</span>
                    <span>{{ item.contact_name || "-" }} / {{ item.contact_phone || "-" }}</span>
                  </div>
                </td>
                <td>{{ Number(item.default_rebate_rate_pct || 0).toFixed(2) }}%</td>
                <td>{{ formatFenToCny(item.pending_rebate_fen) }}</td>
                <td>{{ formatFenToCny(item.settled_rebate_fen) }}</td>
                <td>{{ item.status === "active" ? "启用" : "停用" }}</td>
                <td>
                  <div class="admin-partner-links">
                    <a :href="item.order_link" target="_blank" rel="noreferrer">下单链接</a>
                    <a :href="item.portal_link" target="_blank" rel="noreferrer">门户链接</a>
                  </div>
                </td>
                <td>
                  <div class="admin-partner-row-actions">
                    <button class="scholar-button scholar-button--compact" @click="startEditChannel(item)">编辑</button>
                  </div>
                </td>
              </tr>
              <tr v-if="channels.length === 0">
                <td colspan="7" class="admin-partner-empty">暂无渠道</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="admin-partner-panel">
        <div class="admin-partner-panel__head">
          <div>
            <div class="admin-partner-panel__eyebrow">返佣流水</div>
            <h3>最近流水</h3>
          </div>
        </div>

        <div class="admin-partner-table-wrap">
          <table class="admin-partner-table">
            <thead>
              <tr>
                <th>流水ID</th>
                <th>渠道ID</th>
                <th>订单号</th>
                <th>类型</th>
                <th>金额</th>
                <th>状态</th>
                <th>结算月</th>
                <th>创建时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in ledgerRows" :key="item.id">
                <td>{{ item.id }}</td>
                <td>{{ item.channel_id }}</td>
                <td>{{ item.order_no }}</td>
                <td>{{ mapEntryType(item.entry_type) }}</td>
                <td>{{ formatFenToCny(item.rebate_amount_fen) }}</td>
                <td>{{ mapStatus(item.status) }}</td>
                <td>{{ item.statement_month || "-" }}</td>
                <td>{{ formatTime(item.created_at) }}</td>
              </tr>
              <tr v-if="ledgerRows.length === 0">
                <td colspan="8" class="admin-partner-empty">暂无返佣流水</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="admin-partner-panel">
        <div class="admin-partner-panel__head">
          <div>
            <div class="admin-partner-panel__eyebrow">提现审核</div>
            <h3>渠道提现申请</h3>
          </div>
        </div>

        <div class="admin-partner-table-wrap">
          <table class="admin-partner-table">
            <thead>
              <tr>
                <th>申请单号</th>
                <th>渠道ID</th>
                <th>申请金额</th>
                <th>状态</th>
                <th>备注</th>
                <th>驳回原因</th>
                <th>申请时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in withdrawalRows" :key="item.id">
                <td>{{ item.request_no }}</td>
                <td>{{ item.channel_id }}</td>
                <td>{{ formatFenToCny(item.apply_amount_fen) }}</td>
                <td>{{ mapStatus(item.status) }}</td>
                <td>{{ item.note || "-" }}</td>
                <td>{{ item.reject_reason || "-" }}</td>
                <td>{{ formatTime(item.created_at) }}</td>
                <td>
                  <div class="admin-partner-row-actions">
                    <button
                      class="scholar-button scholar-button--compact"
                      :disabled="!canManage || item.status !== 'pending' || withdrawalReviewingId === item.id"
                      @click="reviewWithdrawal(item, true)"
                    >
                      {{ withdrawalReviewingId === item.id ? "处理中..." : "通过" }}
                    </button>
                    <button
                      class="scholar-button scholar-button--secondary scholar-button--compact"
                      :disabled="!canManage || item.status !== 'pending' || withdrawalReviewingId === item.id"
                      @click="reviewWithdrawal(item, false)"
                    >
                      驳回
                    </button>
                    <button
                      class="scholar-button scholar-button--secondary scholar-button--compact"
                      :disabled="!canManage || item.status !== 'approved' || withdrawalPayingId === item.id"
                      @click="markWithdrawalPaid(item)"
                    >
                      {{ withdrawalPayingId === item.id ? "提交中..." : "标记打款" }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="withdrawalRows.length === 0">
                <td colspan="8" class="admin-partner-empty">暂无提现申请</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

const channels = ref([])
const ledgerRows = ref([])
const withdrawalRows = ref([])
const editingChannelId = ref(0)
const submitting = ref(false)
const statementSubmitting = ref(false)
const withdrawalReviewingId = ref(0)
const withdrawalPayingId = ref(0)
const hintText = ref("")
const errorText = ref("")

const canManage = computed(() => adminHasPermission("configs:manage"))

const channelForm = reactive({
  name: "",
  channel_code: "",
  contact_name: "",
  contact_phone: "",
  rebate_rate_pct: 15,
  status: "active",
})

const statementForm = reactive({
  channel_id: "",
  statement_month: currentMonthText(),
})

onMounted(loadAll)

async function loadAll() {
  await Promise.all([loadChannels(), loadLedger(), loadWithdrawals()])
}

async function loadChannels() {
  const data = await adminHttp.get("/partners/admin/channels", {
    params: { page: 1, page_size: 100 },
  })
  channels.value = Array.isArray(data?.items) ? data.items : []
}

async function loadLedger() {
  const data = await adminHttp.get("/partners/admin/ledger", {
    params: { page: 1, page_size: 100 },
  })
  ledgerRows.value = Array.isArray(data?.items) ? data.items : []
}

async function loadWithdrawals() {
  const data = await adminHttp.get("/partners/admin/withdrawals", {
    params: { page: 1, page_size: 100 },
  })
  withdrawalRows.value = Array.isArray(data?.items) ? data.items : []
}

function resetChannelForm() {
  editingChannelId.value = 0
  channelForm.name = ""
  channelForm.channel_code = ""
  channelForm.contact_name = ""
  channelForm.contact_phone = ""
  channelForm.rebate_rate_pct = 15
  channelForm.status = "active"
}

function startEditChannel(item) {
  editingChannelId.value = Number(item.id || 0)
  channelForm.name = String(item.name || "")
  channelForm.channel_code = String(item.channel_code || "")
  channelForm.contact_name = String(item.contact_name || "")
  channelForm.contact_phone = String(item.contact_phone || "")
  const pct = Number(item.default_rebate_rate_pct)
  channelForm.rebate_rate_pct = Number.isFinite(pct) ? pct : Number(item.default_rebate_rate_bp || 0) / 100
  channelForm.status = String(item.status || "active")
  hintText.value = ""
  errorText.value = ""
}

async function saveChannel() {
  if (!canManage.value) return
  if (!String(channelForm.name || "").trim()) {
    errorText.value = "渠道名称不能为空"
    hintText.value = ""
    return
  }
  const rebateRatePct = Number(channelForm.rebate_rate_pct)
  if (!Number.isFinite(rebateRatePct) || rebateRatePct < 0 || rebateRatePct > 100) {
    errorText.value = "返佣比例需在 0~100% 范围内"
    hintText.value = ""
    return
  }
  submitting.value = true
  hintText.value = ""
  errorText.value = ""
  try {
    const payload = {
      name: channelForm.name,
      contact_name: channelForm.contact_name,
      contact_phone: channelForm.contact_phone,
      rebate_rate_bp: Math.round(rebateRatePct * 100),
    }
    if (!editingChannelId.value && String(channelForm.channel_code || "").trim()) {
      payload.channel_code = String(channelForm.channel_code || "").trim()
    }
    if (editingChannelId.value) {
      payload.status = channelForm.status
      await adminHttp.patch(`/partners/admin/channels/${editingChannelId.value}`, payload)
      hintText.value = "渠道已更新"
    } else {
      await adminHttp.post("/partners/admin/channels", payload)
      hintText.value = "渠道已创建"
    }
    resetChannelForm()
    await Promise.all([loadChannels(), loadLedger(), loadWithdrawals()])
  } catch (error) {
    errorText.value = String(error?.message || "保存渠道失败")
  } finally {
    submitting.value = false
  }
}

async function generateStatement() {
  if (!canManage.value) return
  const channelId = Number(statementForm.channel_id || 0)
  if (channelId <= 0) {
    errorText.value = "请先选择渠道"
    hintText.value = ""
    return
  }
  statementSubmitting.value = true
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/partners/admin/statements/generate", {
      channel_id: channelId,
      statement_month: String(statementForm.statement_month || "").trim(),
    })
    hintText.value = "月结已生成"
    await Promise.all([loadLedger(), loadChannels(), loadWithdrawals()])
  } catch (error) {
    errorText.value = String(error?.message || "生成月结失败")
  } finally {
    statementSubmitting.value = false
  }
}

async function reviewWithdrawal(item, approve) {
  if (!canManage.value) return
  let rejectReason = ""
  if (!approve) {
    rejectReason = String(window.prompt("请输入驳回原因", "资料不完整") || "").trim()
    if (!rejectReason) {
      return
    }
  }
  withdrawalReviewingId.value = Number(item.id || 0)
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post(`/partners/admin/withdrawals/${item.id}/review`, {
      approve: Boolean(approve),
      reject_reason: rejectReason,
    })
    hintText.value = approve ? "提现申请已通过审核" : "提现申请已驳回"
    await Promise.all([loadWithdrawals(), loadChannels()])
  } catch (error) {
    errorText.value = String(error?.message || "审核失败")
  } finally {
    withdrawalReviewingId.value = 0
  }
}

async function markWithdrawalPaid(item) {
  if (!canManage.value) return
  withdrawalPayingId.value = Number(item.id || 0)
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post(`/partners/admin/withdrawals/${item.id}/mark-paid`)
    hintText.value = "提现申请已标记打款"
    await Promise.all([loadWithdrawals(), loadChannels()])
  } catch (error) {
    errorText.value = String(error?.message || "标记打款失败")
  } finally {
    withdrawalPayingId.value = 0
  }
}

function currentMonthText() {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, "0")
  return `${year}-${month}`
}

function mapEntryType(value) {
  const normalized = String(value || "").toLowerCase()
  if (normalized === "accrual") return "入账"
  if (normalized === "reversal") return "冲正"
  return normalized || "-"
}

function mapStatus(value) {
  const normalized = String(value || "").toLowerCase()
  const statusMap = {
    pending: "待结算",
    settled: "已结算",
    reversed: "已冲正",
    generated: "已生成",
    approved: "已通过",
    rejected: "已驳回",
    paid: "已打款",
    active: "启用",
    disabled: "停用",
  }
  return statusMap[normalized] || normalized || "-"
}

function formatFenToCny(value) {
  const amount = Number(value || 0) / 100
  return `¥${amount.toFixed(2)}`
}

function formatTime(value) {
  return value ? String(value).slice(0, 19).replace("T", " ") : "-"
}
</script>

<style scoped>
.admin-partner-page {
  display: grid;
  gap: 16px;
}

.admin-partner-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
}

.admin-partner-panel {
  border: 1px solid #d9dee4;
  border-radius: 20px;
  background: #ffffff;
  padding: 20px;
}

.admin-partner-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.admin-partner-panel__eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #6b7a86;
}

.admin-partner-panel__head h3 {
  margin: 6px 0 0;
  font-size: 20px;
  color: #18242b;
}

.admin-partner-form {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.admin-partner-form label {
  display: grid;
  gap: 6px;
  font-size: 13px;
  color: #42525f;
}

.admin-partner-input {
  width: 100%;
  min-height: 42px;
  border: 1px solid #ccd5dd;
  border-radius: 12px;
  padding: 0 12px;
  font-size: 14px;
  outline: none;
}

.admin-partner-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.admin-partner-hint {
  margin: 12px 0 0;
  font-size: 13px;
}

.admin-partner-note {
  margin: 0 0 14px;
  color: #52616f;
  font-size: 13px;
  line-height: 1.7;
}

.admin-partner-hint--success {
  color: #0f7a5f;
}

.admin-partner-hint--danger {
  color: #af3f33;
}

.admin-partner-table-wrap {
  overflow-x: auto;
}

.admin-partner-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  font-size: 13px;
}

.admin-partner-table th,
.admin-partner-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #e8edf2;
  text-align: left;
  vertical-align: top;
}

.admin-partner-table th {
  color: #647481;
  font-weight: 700;
}

.admin-partner-channel,
.admin-partner-links,
.admin-partner-row-actions {
  display: grid;
  gap: 4px;
}

.admin-partner-channel strong {
  color: #18242b;
}

.admin-partner-channel span {
  color: #5d6c79;
}

.admin-partner-links a {
  color: #125f4b;
  text-decoration: underline;
  text-underline-offset: 3px;
}

.admin-partner-empty {
  color: #667480;
}

@media (max-width: 1080px) {
  .admin-partner-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .admin-partner-panel {
    padding: 16px;
  }

  .admin-partner-form {
    grid-template-columns: 1fr;
  }
}
</style>
