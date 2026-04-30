<template>
  <AdminShell title="渠道返佣" subtitle="平台看全局经营、异常渠道和一级渠道产出。">
    <section class="partner-admin-page">
      <section class="partner-admin-stats">
        <article v-for="item in summaryCards" :key="item.label" class="partner-admin-stat" :class="{ 'partner-admin-stat--primary': item.primary }">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <p>{{ item.hint }}</p>
        </article>
      </section>

      <section class="partner-admin-chart-grid">
        <article class="scholar-chart-card partner-admin-chart-card">
          <div class="partner-admin-section-head">
            <div>
              <div class="partner-admin-kicker">渠道增长</div>
              <h3>近 14 天一级 / 二级新增趋势</h3>
            </div>
            <button class="scholar-button scholar-button--secondary" @click="loadAll">刷新</button>
          </div>
          <div ref="growthChartEl" class="partner-admin-chart"></div>
        </article>

        <article class="scholar-chart-card partner-admin-chart-card">
          <div class="partner-admin-section-head">
            <div>
              <div class="partner-admin-kicker">经营贡献</div>
              <h3>一级渠道返佣排行</h3>
            </div>
            <span class="partner-admin-chart-note">按待结算 + 已结算返佣排序</span>
          </div>
          <div ref="rankChartEl" class="partner-admin-chart"></div>
        </article>

        <article class="scholar-chart-card partner-admin-chart-card">
          <div class="partner-admin-section-head">
            <div>
              <div class="partner-admin-kicker">客户结构</div>
              <h3>按层级归属分布</h3>
            </div>
            <span class="partner-admin-chart-note">看客户主要沉淀在哪一层</span>
          </div>
          <div ref="mixChartEl" class="partner-admin-chart partner-admin-chart--short"></div>
        </article>
      </section>

      <section class="partner-admin-top-grid">
        <article class="partner-admin-panel">
          <div class="partner-admin-section-head">
            <div>
              <div class="partner-admin-kicker">异常提醒</div>
              <h3>优先处理这些渠道</h3>
            </div>
            <span class="partner-admin-chart-note">{{ anomalyItems.length }} 条</span>
          </div>
          <div v-if="anomalyItems.length" class="partner-admin-alert-list">
            <button
              v-for="item in anomalyItems"
              :key="`${item.channel_id}-${item.type}`"
              type="button"
              class="partner-admin-alert-item"
              @click="focusChannel(item.channel_id)"
            >
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.desc }}</p>
              </div>
              <span :class="['partner-admin-pill', `partner-admin-pill--${item.severity}`]">{{ item.level }}</span>
            </button>
          </div>
          <div v-else class="partner-admin-empty">当前没有明显异常渠道。</div>
        </article>

        <article class="partner-admin-panel">
          <div class="partner-admin-section-head">
            <div>
              <div class="partner-admin-kicker">一级渠道</div>
              <h3>{{ editingChannelId ? "编辑一级渠道" : "新建一级渠道" }}</h3>
            </div>
            <button class="scholar-button scholar-button--secondary" :disabled="submitting" @click="resetChannelForm">重置</button>
          </div>

          <div class="partner-admin-form">
            <label>
              <span>渠道名称</span>
              <input v-model.trim="channelForm.name" class="partner-admin-input" placeholder="例如：华东高校一级渠道" />
            </label>
            <label>
              <span>渠道编码</span>
              <input v-model.trim="channelForm.channel_code" class="partner-admin-input" placeholder="可留空自动生成" :disabled="Boolean(editingChannelId)" />
            </label>
            <label>
              <span>联系人</span>
              <input v-model.trim="channelForm.contact_name" class="partner-admin-input" placeholder="联系人姓名" />
            </label>
            <label>
              <span>联系电话</span>
              <input v-model.trim="channelForm.contact_phone" class="partner-admin-input" placeholder="联系电话" />
            </label>
            <label>
              <span>默认返佣比例（%）</span>
              <input v-model.number="channelForm.rebate_rate_pct" type="number" min="0" max="100" step="0.01" class="partner-admin-input" />
            </label>
            <label v-if="editingChannelId">
              <span>状态</span>
              <select v-model="channelForm.status" class="partner-admin-input">
                <option value="active">启用</option>
                <option value="disabled">停用</option>
              </select>
            </label>
          </div>

          <div class="partner-admin-actions">
            <button class="scholar-button" :disabled="submitting || !canManage" @click="saveChannel">
              {{ submitting ? "提交中..." : editingChannelId ? "保存一级渠道" : "创建一级渠道" }}
            </button>
            <button class="scholar-button scholar-button--secondary" :disabled="statementSubmitting || !canManage" @click="generateStatement">
              {{ statementSubmitting ? "生成中..." : "生成月结" }}
            </button>
          </div>

          <div class="partner-admin-inline-form">
            <label>
              <span>月结渠道</span>
              <select v-model="statementForm.channel_id" class="partner-admin-input">
                <option value="">请选择渠道</option>
                <option v-for="item in rootChannels" :key="item.id" :value="String(item.id)">
                  {{ item.name }}（{{ item.channel_code }}）
                </option>
              </select>
            </label>
            <label>
              <span>结算月份</span>
              <input v-model.trim="statementForm.statement_month" class="partner-admin-input" placeholder="YYYY-MM" />
            </label>
          </div>

          <p v-if="hintText" class="partner-admin-message partner-admin-message--success">{{ hintText }}</p>
          <p v-if="errorText" class="partner-admin-message partner-admin-message--danger">{{ errorText }}</p>
          <p v-if="!canManage" class="partner-admin-message">当前账号仅有查看权限。</p>
        </article>
      </section>

      <section class="partner-admin-panel">
        <div class="partner-admin-section-head">
          <div>
            <div class="partner-admin-kicker">渠道列表</div>
            <h3>平台重点看一级，顺手看它带的二级</h3>
          </div>
          <div class="partner-admin-filter-row">
            <input v-model.trim="filters.keyword" class="partner-admin-input partner-admin-input--compact" placeholder="搜索渠道名称 / 编码" />
            <select v-model="filters.status" class="partner-admin-input partner-admin-input--compact">
              <option value="">全部状态</option>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
            <button class="scholar-button scholar-button--secondary" @click="applyChannelFilters">筛选</button>
          </div>
        </div>

        <div class="partner-admin-table-wrap">
          <table class="partner-admin-table">
            <thead>
              <tr>
                <th>渠道</th>
                <th>经营状态</th>
                <th>团队规模</th>
                <th>返佣 / 客户</th>
                <th>渠道入口</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in orderedChannels" :key="item.id" :class="{ 'partner-admin-row--focus': focusedChannelId === Number(item.id) }">
                <td>
                  <div class="partner-admin-channel">
                    <strong>{{ mapLevel(item.level) }} · {{ item.name }}</strong>
                    <span>{{ item.channel_code }}</span>
                    <span>上级 {{ item.parent_channel_name || "平台直营" }}</span>
                    <span>{{ item.contact_name || "-" }} / {{ item.contact_phone || "-" }}</span>
                  </div>
                </td>
                <td>
                  <div class="partner-admin-stack">
                    <span :class="['partner-admin-pill', `partner-admin-pill--${healthOf(item).tone}`]">{{ healthOf(item).label }}</span>
                    <span>{{ item.status === "active" ? "启用中" : "已停用" }}</span>
                    <span>最近登录 {{ formatTime(item.portal_last_login_at) }}</span>
                  </div>
                </td>
                <td>
                  <div class="partner-admin-stack">
                    <span>直属下级 {{ Number(item.child_count || 0) }}</span>
                    <span>层级 {{ mapLevel(item.level) }}</span>
                    <span>默认返佣 {{ Number(item.default_rebate_rate_pct || 0).toFixed(2) }}%</span>
                  </div>
                </td>
                <td>
                  <div class="partner-admin-stack">
                    <span>客户 {{ Number(item.user_count || 0) }}</span>
                    <span>待结算 {{ formatFenToCny(item.pending_rebate_fen) }}</span>
                    <span>已结算 {{ formatFenToCny(item.settled_rebate_fen) }}</span>
                  </div>
                </td>
                <td>
                  <div class="partner-admin-generate-actions">
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" @click="openChannelPortalLinkPanel(item)">
                      {{ portalButtonLabel(item) }}
                    </button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" @click="openChannelCustomerLinkPanel(item)">
                      {{ customerLinkButtonLabel(item) }}
                    </button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" @click="openChannelCustomerQrPanel(item)">
                      {{ customerQrButtonLabel(item) }}
                    </button>
                  </div>
                </td>
                <td>
                  <div class="partner-admin-row-actions">
                    <button class="scholar-button scholar-button--compact" @click="openInsightPanel(item)">查看详情</button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" @click="startEditChannel(item)">编辑</button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" @click="openPolicyPanel(item)">返佣设置</button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact partner-admin-danger-btn" :disabled="!canManage" @click="deleteChannel(item)">删除</button>
                  </div>
                </td>
              </tr>
              <tr v-if="orderedChannels.length === 0">
                <td colspan="6" class="partner-admin-empty">暂无渠道</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="miniappQrPanel.visible" class="partner-admin-panel">
        <div class="partner-admin-section-head">
          <div>
            <div class="partner-admin-kicker">渠道物料</div>
            <h3>{{ miniappQrPanel.title || "-" }}</h3>
          </div>
          <button class="scholar-button scholar-button--secondary" @click="closeMiniappQrPanel">关闭</button>
        </div>

        <div v-if="miniappQrPanel.loading" class="partner-admin-empty">正在生成专用物料...</div>
        <div v-else-if="miniappQrPanel.kind === 'qrcode' && miniappQrPanel.data" class="partner-admin-qrcode-panel">
          <div class="partner-admin-qrcode-card">
            <img :src="miniappQrPanel.data.qrcode_data_url" alt="渠道获客小程序码" class="partner-admin-qrcode-image" />
          </div>
          <div class="partner-admin-qrcode-copy">
            <div class="partner-admin-stack">
              <span>{{ miniappQrPanel.channel?.name || "-" }} 的专用获客小程序码已生成</span>
              <span>可直接发给客户扫码使用</span>
            </div>
            <p v-if="miniappQrPanel.data.fallback_reason" class="partner-admin-message">{{ miniappQrPanel.data.fallback_reason }}</p>
            <div class="partner-admin-actions">
              <button class="scholar-button scholar-button--secondary" @click="copyText(miniappQrPanel.data.miniapp_order_path, '小程序入口已复制')">复制小程序入口</button>
              <button class="scholar-button scholar-button--secondary" @click="refreshMaterialPanel">重新生成</button>
            </div>
          </div>
        </div>
        <div v-else-if="miniappQrPanel.kind === 'link'" class="partner-admin-result-panel">
          <div class="partner-admin-result-box">
            <strong>{{ miniappQrPanel.resultTitle || "专用链接已生成" }}</strong>
            <p>{{ miniappQrPanel.link || "-" }}</p>
          </div>
          <div class="partner-admin-actions">
            <button class="scholar-button scholar-button--secondary" @click="copyText(miniappQrPanel.link || '', miniappQrPanel.copyMessage || '链接已复制')">复制链接</button>
            <button class="scholar-button scholar-button--secondary" @click="refreshMaterialPanel">重新生成</button>
            <button class="scholar-button scholar-button--secondary" @click="closeMiniappQrPanel">关闭</button>
          </div>
        </div>
        <div v-else class="partner-admin-empty">
          当前暂无可展示的物料结果
        </div>
      </section>

      <section v-if="policyPanel.visible" class="partner-admin-panel">
        <div class="partner-admin-section-head">
          <div>
            <div class="partner-admin-kicker">返佣设置</div>
            <h3>{{ policyPanel.channel?.name || "-" }} 的套餐返佣</h3>
          </div>
          <button class="scholar-button scholar-button--secondary" @click="closePolicyPanel">关闭</button>
        </div>

        <div class="partner-admin-policy-cards">
          <article class="partner-admin-mini-card">
            <span>默认返佣</span>
            <strong>{{ Number(policyPanel.channel?.default_rebate_rate_pct || 0).toFixed(2) }}%</strong>
          </article>
          <article class="partner-admin-mini-card">
            <span>已配置套餐</span>
            <strong>{{ policyPanel.items.length }}</strong>
          </article>
        </div>

        <div v-if="packageOptions.length" class="partner-admin-tag-row">
          <button v-for="item in packageOptions" :key="item.name" type="button" class="partner-admin-tag" @click="applyPackagePreset(item)">
            {{ item.name }}
          </button>
        </div>

        <div class="partner-admin-inline-form">
          <label>
            <span>套餐名</span>
            <select v-model="policyForm.package_name" class="partner-admin-input">
              <option value="">按默认返佣走</option>
              <option v-for="item in packageOptions" :key="item.name" :value="item.name">
                {{ item.name }}{{ item.priceLabel ? ` · ${item.priceLabel}` : "" }}{{ item.creditsLabel ? ` · ${item.creditsLabel}` : "" }}
              </option>
            </select>
          </label>
          <label>
            <span>返佣比例（%）</span>
            <input v-model.number="policyForm.rebate_rate_pct" type="number" min="0" max="100" step="0.01" class="partner-admin-input" />
          </label>
          <label>
            <span>状态</span>
            <select v-model="policyForm.is_active" class="partner-admin-input">
              <option :value="true">启用</option>
              <option :value="false">停用</option>
            </select>
          </label>
        </div>

        <div class="partner-admin-actions">
          <button class="scholar-button" :disabled="policySubmitting || !canManage" @click="savePolicy">{{ policySubmitting ? "保存中..." : "保存返佣设置" }}</button>
        </div>

        <div class="partner-admin-table-wrap">
          <table class="partner-admin-table">
            <thead>
              <tr>
                <th>套餐</th>
                <th>比例</th>
                <th>状态</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in policyPanel.items" :key="item.id">
                <td>{{ item.package_name }}</td>
                <td>{{ Number(item.rebate_rate_pct || 0).toFixed(2) }}%</td>
                <td>{{ item.is_active ? "启用" : "停用" }}</td>
                <td>{{ formatTime(item.updated_at || item.created_at) }}</td>
                <td><button class="partner-admin-text-btn" @click="editPolicyItem(item)">套用到表单</button></td>
              </tr>
              <tr v-if="policyPanel.items.length === 0">
                <td colspan="5" class="partner-admin-empty">暂无套餐返佣设置</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="insightPanel.visible" class="partner-admin-panel">
        <div class="partner-admin-section-head">
          <div>
            <div class="partner-admin-kicker">渠道详情</div>
            <h3>{{ insightPanel.channel?.name || "-" }} 的经营详情</h3>
          </div>
          <div class="partner-admin-filter-row">
            <select v-model="insightPanel.scope" class="partner-admin-input partner-admin-input--compact" @change="loadInsightPanel">
              <option value="self">只看自己</option>
              <option value="team">只看下级</option>
              <option value="subtree">自己 + 下级</option>
            </select>
            <button class="scholar-button scholar-button--secondary" @click="exportInsightCustomers">导出客户</button>
            <button class="scholar-button scholar-button--secondary" @click="closeInsightPanel">关闭</button>
          </div>
        </div>

        <div class="partner-admin-policy-cards">
          <article class="partner-admin-mini-card">
            <span>默认返佣</span>
            <strong>{{ Number(insightPanel.channel?.default_rebate_rate_pct || 0).toFixed(2) }}%</strong>
          </article>
          <article class="partner-admin-mini-card">
            <span>直属下级</span>
            <strong>{{ Number(insightPanel.channel?.child_count || 0) }}</strong>
          </article>
          <article class="partner-admin-mini-card">
            <span>客户数</span>
            <strong>{{ Number(insightPanel.summary?.user_count || 0) }}</strong>
          </article>
          <article class="partner-admin-mini-card">
            <span>待结算</span>
            <strong>{{ formatFenToCny(insightPanel.summary?.pending_rebate_fen || 0) }}</strong>
          </article>
        </div>

        <div class="partner-admin-inline-form">
          <label>
            <span>关键词</span>
            <input v-model.trim="insightPanel.keyword" class="partner-admin-input" placeholder="昵称 / 渠道名 / 渠道编码" />
          </label>
          <label>
            <span>开始日期</span>
            <input v-model="insightPanel.created_from" type="date" class="partner-admin-input" />
          </label>
          <label>
            <span>结束日期</span>
            <input v-model="insightPanel.created_to" type="date" class="partner-admin-input" />
          </label>
          <label>
            <span>&nbsp;</span>
            <button class="scholar-button scholar-button--secondary" @click="applyInsightFilter">筛选客户</button>
          </label>
        </div>

        <div class="partner-admin-table-wrap">
          <table class="partner-admin-table">
            <thead>
              <tr>
                <th>用户ID</th>
                <th>昵称</th>
                <th>手机号</th>
                <th>归属渠道</th>
                <th>归属来源</th>
                <th>历史订单</th>
                <th>锁定时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in insightPanel.customers" :key="item.binding_id">
                <td>{{ item.user_id }}</td>
                <td>{{ item.nickname }}</td>
                <td>{{ item.phone_masked || "-" }}</td>
                <td>{{ item.channel_name || item.channel_code || "-" }}</td>
                <td>{{ item.bind_source || "-" }}</td>
                <td>{{ Number(item.order_count || 0) }}</td>
                <td>{{ formatTime(item.locked_at || item.updated_at || item.created_at) }}</td>
              </tr>
              <tr v-if="insightPanel.customers.length === 0">
                <td colspan="7" class="partner-admin-empty">暂无客户归属数据</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="partner-admin-actions partner-admin-actions--tight">
          <button class="scholar-button scholar-button--secondary" :disabled="insightPanel.pagination.page <= 1" @click="changeInsightPage(-1)">上一页</button>
          <span>第 {{ insightPanel.pagination.page }} / {{ Math.max(insightPanel.pagination.pages, 1) }} 页，共 {{ insightPanel.pagination.total }} 条</span>
          <button class="scholar-button scholar-button--secondary" :disabled="insightPanel.pagination.page >= Math.max(insightPanel.pagination.pages, 1)" @click="changeInsightPage(1)">下一页</button>
        </div>
      </section>

      <details class="partner-admin-panel">
        <summary class="partner-admin-summary">
          <div>
            <div class="partner-admin-kicker">更多明细</div>
            <h3>返佣流水与提现审核</h3>
          </div>
        </summary>

        <div class="partner-admin-table-wrap">
          <table class="partner-admin-table">
            <thead>
              <tr>
                <th>流水ID</th>
                <th>收益渠道</th>
                <th>来源渠道</th>
                <th>订单号</th>
                <th>类型</th>
                <th>比例</th>
                <th>金额</th>
                <th>状态</th>
                <th>结算月</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in ledgerRows" :key="item.id">
                <td>{{ item.id }}</td>
                <td>{{ item.channel_name || item.channel_code || item.channel_id }}</td>
                <td>{{ item.source_channel_name || item.source_channel_code || item.source_channel_id || "-" }}</td>
                <td>{{ item.order_no }}</td>
                <td>{{ mapEntryType(item.entry_type) }}</td>
                <td>{{ formatRate(item.rebate_rate_bp) }}</td>
                <td>{{ formatFenToCny(item.rebate_amount_fen) }}</td>
                <td>{{ mapStatus(item.status) }}</td>
                <td>{{ item.statement_month || "-" }}</td>
              </tr>
              <tr v-if="ledgerRows.length === 0">
                <td colspan="9" class="partner-admin-empty">暂无返佣流水</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="partner-admin-table-wrap">
          <table class="partner-admin-table">
            <thead>
              <tr>
                <th>申请单号</th>
                <th>渠道</th>
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
                <td>{{ item.channel_name || item.channel_code || item.channel_id }}</td>
                <td>{{ formatFenToCny(item.apply_amount_fen) }}</td>
                <td>{{ mapStatus(item.status) }}</td>
                <td>{{ item.note || "-" }}</td>
                <td>{{ item.reject_reason || "-" }}</td>
                <td>{{ formatTime(item.created_at) }}</td>
                <td>
                  <div class="partner-admin-row-actions">
                    <button class="scholar-button scholar-button--compact" :disabled="!canManage || item.status !== 'pending' || withdrawalReviewingId === item.id" @click="reviewWithdrawal(item, true)">
                      {{ withdrawalReviewingId === item.id ? "处理中..." : "通过" }}
                    </button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" :disabled="!canManage || item.status !== 'pending' || withdrawalReviewingId === item.id" @click="reviewWithdrawal(item, false)">驳回</button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" :disabled="!canManage || item.status !== 'approved' || withdrawalPayingId === item.id" @click="markWithdrawalPaid(item)">
                      {{ withdrawalPayingId === item.id ? "提交中..." : "标记打款" }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="withdrawalRows.length === 0">
                <td colspan="8" class="partner-admin-empty">暂无提现申请</td>
              </tr>
            </tbody>
          </table>
        </div>
      </details>
    </section>
  </AdminShell>
</template>

<script setup>
import * as echarts from "echarts/core"
import { BarChart, LineChart, PieChart } from "echarts/charts"
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { triggerBlobDownload } from "../../lib/download"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

echarts.use([LineChart, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const growthChartEl = ref(null)
const rankChartEl = ref(null)
const mixChartEl = ref(null)

let growthChart = null
let rankChart = null
let mixChart = null

const channels = ref([])
const analytics = ref(null)
const ledgerRows = ref([])
const withdrawalRows = ref([])
const editingChannelId = ref(0)
const submitting = ref(false)
const statementSubmitting = ref(false)
const withdrawalReviewingId = ref(0)
const withdrawalPayingId = ref(0)
const hintText = ref("")
const errorText = ref("")
const policySubmitting = ref(false)
const focusedChannelId = ref(0)

const canManage = computed(() => adminHasPermission("configs:manage"))
const rootChannels = computed(() => channels.value.filter((item) => Number(item.level || 1) === 1))
const summaryCards = computed(() => {
  const summary = analytics.value?.summary || {}
  return [
    { label: "一级渠道", value: String(Number(summary.root_channel_count || 0)), hint: "平台只新建一级渠道", primary: true },
    { label: "活跃二级", value: String(Number(summary.active_second_count || 0)), hint: "启用中的直属二级总数" },
    { label: "待审核提现", value: String(Number(summary.pending_withdrawal_count || 0)), hint: "需要平台审核的提现申请" },
    { label: "累计返佣池", value: formatFenToCny(summary.total_rebate_pool_fen), hint: `待结算 ${formatFenToCny(summary.total_pending_rebate_fen)}` },
  ]
})
const orderedChannels = computed(() =>
  [...channels.value].sort((a, b) => {
    const aScore = Number(a.pending_rebate_fen || 0) + Number(a.settled_rebate_fen || 0)
    const bScore = Number(b.pending_rebate_fen || 0) + Number(b.settled_rebate_fen || 0)
    if (bScore !== aScore) return bScore - aScore
    return Number(a.level || 1) - Number(b.level || 1)
  })
)
const anomalyItems = computed(() => (Array.isArray(analytics.value?.anomalies) ? analytics.value.anomalies : []))

const filters = reactive({
  keyword: "",
  status: "",
})

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

const policyPanel = reactive({
  visible: false,
  channel: null,
  items: [],
})
const packageOptions = ref([])
const insightPanel = reactive({
  visible: false,
  channel: null,
  scope: "subtree",
  summary: null,
  customers: [],
  keyword: "",
  created_from: "",
  created_to: "",
  pagination: { page: 1, page_size: 20, total: 0, pages: 0 },
})
const miniappQrPanel = reactive({
  visible: false,
  loading: false,
  kind: "",
  title: "",
  resultTitle: "",
  copyMessage: "",
  action: "",
  channel: null,
  data: null,
  link: "",
})

const policyForm = reactive({
  package_name: "",
  rebate_rate_pct: 0,
  is_active: true,
})

watch(
  () => analytics.value,
  async () => {
    await nextTick()
    renderCharts()
  },
  { deep: true }
)

onMounted(async () => {
  await loadAll()
  window.addEventListener("resize", handleResize)
})

onUnmounted(() => {
  window.removeEventListener("resize", handleResize)
  disposeCharts()
})

async function loadAll() {
  await Promise.all([loadChannels(), loadAnalytics(), loadLedger(), loadWithdrawals(), loadPackageOptions()])
}

async function loadPackageOptions() {
  try {
    const data = await adminHttp.get("/billing/packages")
    const items = Array.isArray(data?.items) ? data.items : []
    packageOptions.value = items
      .map((item) => ({
        name: String(item?.name || "").trim(),
        priceLabel: Number(item?.amount_cny || item?.price || 0) > 0 ? `¥${Number(item.amount_cny || item.price).toFixed(2)}` : "",
        creditsLabel: Number(item?.credits || item?.processable_chars || 0) > 0 ? `${Number(item.credits || item.processable_chars)}点` : "",
      }))
      .filter((item) => item.name)
  } catch {}
}

async function loadChannels() {
  const data = await adminHttp.get("/partners/admin/channels", {
    params: { page: 1, page_size: 100, keyword: filters.keyword, status: filters.status },
  })
  channels.value = Array.isArray(data?.items) ? data.items : []
}

async function loadAnalytics() {
  const data = await adminHttp.get("/partners/admin/analytics", {
    params: { days: 14, keyword: filters.keyword || undefined, status: filters.status || undefined },
  })
  analytics.value = data || null
}

async function applyChannelFilters() {
  await Promise.all([loadChannels(), loadAnalytics()])
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

function renderCharts() {
  const growthSeries = Array.isArray(analytics.value?.growth_series) ? analytics.value.growth_series : []
  const rankRows = (Array.isArray(analytics.value?.root_rank) ? analytics.value.root_rank : [])
    .map((item) => ({
      name: String(item.name || ""),
      total: Number(item.total_rebate_fen || 0),
    }))
    .reverse()
  const customerMix = (Array.isArray(analytics.value?.customer_mix) ? analytics.value.customer_mix : []).filter((item) => Number(item?.value || 0) > 0)
  const xLabels = growthSeries.map((item) => String(item.date || "").slice(5) || "-")

  growthChart = initChart(growthChartEl.value, growthChart)
  rankChart = initChart(rankChartEl.value, rankChart)
  mixChart = initChart(mixChartEl.value, mixChart)

  if (growthChart) {
    growthChart.setOption({
      grid: { left: 30, right: 18, top: 18, bottom: 26 },
      tooltip: { trigger: "axis" },
      legend: { bottom: 0, textStyle: { color: "#5b6b83" } },
      xAxis: { type: "category", data: xLabels, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#5b6b83" } },
      yAxis: { type: "value", axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: "rgba(72, 96, 132, 0.12)" } }, axisLabel: { color: "#5b6b83" } },
      series: [
        { name: "一级新增", type: "line", smooth: true, data: growthSeries.map((item) => Number(item.level_one_new || 0)), lineStyle: { width: 3, color: "#1e5bdf" }, symbolSize: 7, itemStyle: { color: "#1e5bdf" } },
        { name: "二级新增", type: "line", smooth: true, data: growthSeries.map((item) => Number(item.level_two_new || 0)), lineStyle: { width: 3, color: "#6aa3ff" }, symbolSize: 7, itemStyle: { color: "#6aa3ff" } },
      ],
    })
  }

  if (rankChart) {
    rankChart.setOption({
      grid: { left: 90, right: 18, top: 18, bottom: 18 },
      tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
      xAxis: { type: "value", axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: "rgba(72, 96, 132, 0.12)" } }, axisLabel: { color: "#5b6b83", formatter: (value) => `¥${(Number(value || 0) / 100).toFixed(0)}` } },
      yAxis: { type: "category", data: rankRows.map((item) => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#244165" } },
      series: [
        {
          type: "bar",
          data: rankRows.map((item) => item.total),
          barWidth: 18,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(1, 0, 0, 0, [
              { offset: 0, color: "#4a90ff" },
              { offset: 1, color: "#1e5bdf" },
            ]),
            borderRadius: [10, 10, 10, 10],
          },
        },
      ],
    })
  }

  if (mixChart) {
    mixChart.setOption({
      tooltip: { trigger: "item" },
      legend: { bottom: 0, textStyle: { color: "#5b6b83" } },
      series: [
        {
          type: "pie",
          radius: ["46%", "72%"],
          center: ["50%", "42%"],
          label: { color: "#244165", formatter: "{b}\n{d}%" },
          data: customerMix.length ? customerMix : [{ name: "暂无客户", value: 1, itemStyle: { color: "#d9e5fb" }, label: { color: "#7d8da7" } }],
        },
      ],
    })
  }
}

function initChart(el, existing) {
  if (!el) return null
  return existing || echarts.init(el)
}

function disposeCharts() {
  for (const chart of [growthChart, rankChart, mixChart]) {
    if (chart) {
      chart.dispose()
    }
  }
  growthChart = null
  rankChart = null
  mixChart = null
}

function handleResize() {
  for (const chart of [growthChart, rankChart, mixChart]) {
    if (chart) {
      chart.resize()
    }
  }
}

function focusChannel(channelId) {
  focusedChannelId.value = Number(channelId || 0)
  const row = orderedChannels.value.find((item) => Number(item.id || 0) === Number(channelId || 0))
  if (row) {
    openInsightPanel(row)
  }
}

function healthOf(item) {
  const status = String(item.status || "")
  const level = Number(item.level || 1)
  const childCount = Number(item.child_count || 0)
  const userCount = Number(item.user_count || 0)
  const pendingFen = Number(item.pending_rebate_fen || 0)
  if (status !== "active") return { label: "已停用", tone: "muted" }
  if (pendingFen >= 50000) return { label: "待处理", tone: "warning" }
  if (level === 1 && childCount === 0) return { label: "待扩张", tone: "warning" }
  if (userCount <= 0) return { label: "待激活", tone: "danger" }
  return { label: "增长中", tone: "success" }
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
  channelForm.rebate_rate_pct = Number(item.default_rebate_rate_pct || 0)
  channelForm.status = String(item.status || "active")
  focusedChannelId.value = Number(item.id || 0)
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
      parent_channel_id: null,
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
      hintText.value = "一级渠道已更新"
    } else {
      const data = await adminHttp.post("/partners/admin/channels", payload)
      const bundle = buildChannelBundle(data || payload)
      if (bundle) {
        await copyText(bundle, "一级渠道整段信息已复制")
      }
      hintText.value = bundle ? "一级渠道已创建并复制分发信息" : "一级渠道已创建"
    }
    resetChannelForm()
    await Promise.all([loadChannels(), loadAnalytics(), loadLedger(), loadWithdrawals()])
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
    await Promise.all([loadLedger(), loadChannels(), loadAnalytics(), loadWithdrawals()])
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
    if (!rejectReason) return
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
    await Promise.all([loadWithdrawals(), loadChannels(), loadAnalytics()])
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
    await Promise.all([loadWithdrawals(), loadChannels(), loadAnalytics()])
  } catch (error) {
    errorText.value = String(error?.message || "标记打款失败")
  } finally {
    withdrawalPayingId.value = 0
  }
}

async function copyText(value, message) {
  const text = String(value || "").trim()
  if (!text) {
    errorText.value = "内容为空，无法复制"
    hintText.value = ""
    return
  }
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const input = document.createElement("textarea")
      input.value = text
      input.setAttribute("readonly", "readonly")
      input.style.position = "fixed"
      input.style.top = "-9999px"
      document.body.appendChild(input)
      input.select()
      document.execCommand("copy")
      document.body.removeChild(input)
    }
    hintText.value = message
    errorText.value = ""
  } catch (error) {
    errorText.value = String(error?.message || "复制失败")
    hintText.value = ""
  }
}

async function resetPortalPassword(item) {
  if (!canManage.value) return
  const confirmed = window.confirm(`确认重置 ${item.name || item.channel_code || "该渠道"} 的门户密码吗？重置后需用新密码登录。`)
  if (!confirmed) return
  hintText.value = ""
  errorText.value = ""
  try {
    const data = await adminHttp.post(`/partners/admin/channels/${item.id}/portal-password/reset`)
    const bundle = buildChannelBundle({ ...item, ...data })
    if (bundle) {
      await copyText(bundle, "渠道门户信息已复制")
    }
    hintText.value = "渠道门户密码已重置并复制"
    await Promise.all([loadChannels(), loadAnalytics()])
  } catch (error) {
    errorText.value = String(error?.message || "重置门户密码失败")
  }
}

async function deleteChannel(item) {
  if (!canManage.value) return
  const channelName = String(item?.name || "").trim()
  const confirmName = String(window.prompt(`请输入渠道名称后删除：${channelName}`, "") || "").trim()
  if (!confirmName) return
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.delete(`/partners/admin/channels/${item.id}`, {
      data: { confirm_name: confirmName },
    })
    if (editingChannelId.value === Number(item.id || 0)) {
      resetChannelForm()
    }
    if (policyPanel.channel && Number(policyPanel.channel.id || 0) === Number(item.id || 0)) {
      closePolicyPanel()
    }
    if (insightPanel.channel && Number(insightPanel.channel.id || 0) === Number(item.id || 0)) {
      closeInsightPanel()
    }
    hintText.value = "渠道已删除"
    await Promise.all([loadChannels(), loadAnalytics(), loadLedger(), loadWithdrawals()])
  } catch (error) {
    errorText.value = String(error?.message || "删除渠道失败")
  }
}

async function openMiniappQrPanel(item) {
  miniappQrPanel.visible = true
  miniappQrPanel.loading = true
  miniappQrPanel.kind = "qrcode"
  miniappQrPanel.title = `${String(item?.name || "-")} 的专用获客小程序码`
  miniappQrPanel.resultTitle = "专用获客小程序码"
  miniappQrPanel.copyMessage = "小程序入口已复制"
  miniappQrPanel.action = "customer_qrcode"
  miniappQrPanel.channel = item
  miniappQrPanel.data = null
  miniappQrPanel.link = ""
  hintText.value = ""
  errorText.value = ""
  try {
    const data = await adminHttp.get(`/partners/admin/channels/${item.id}/miniapp-qrcode`)
    miniappQrPanel.data = data || null
  } catch (error) {
    errorText.value = String(error?.message || "加载小程序码失败")
  } finally {
    miniappQrPanel.loading = false
  }
}

function closeMiniappQrPanel() {
  miniappQrPanel.visible = false
  miniappQrPanel.loading = false
  miniappQrPanel.kind = ""
  miniappQrPanel.title = ""
  miniappQrPanel.resultTitle = ""
  miniappQrPanel.copyMessage = ""
  miniappQrPanel.action = ""
  miniappQrPanel.channel = null
  miniappQrPanel.data = null
  miniappQrPanel.link = ""
}

function portalButtonLabel(item) {
  return Number(item?.level || 1) === 1 ? "生成一级渠道登录入口" : "生成二级渠道登录入口"
}

function customerLinkButtonLabel(item) {
  return Number(item?.level || 1) === 1 ? "生成一级渠道网页获客链接" : "生成二级渠道网页获客链接"
}

function customerQrButtonLabel(item) {
  return Number(item?.level || 1) === 1 ? "生成一级渠道获客小程序码" : "生成二级渠道获客小程序码"
}

function openLinkResultPanel(item, options) {
  miniappQrPanel.visible = true
  miniappQrPanel.loading = false
  miniappQrPanel.kind = "link"
  miniappQrPanel.title = options.title
  miniappQrPanel.resultTitle = options.resultTitle
  miniappQrPanel.copyMessage = options.copyMessage
  miniappQrPanel.action = options.action
  miniappQrPanel.channel = item
  miniappQrPanel.data = null
  miniappQrPanel.link = options.link
}

async function openChannelPortalLinkPanel(item) {
  if (!canManage.value) return
  hintText.value = ""
  errorText.value = ""
  try {
    const data = await adminHttp.post(`/partners/admin/channels/${item.id}/portal-link/refresh`)
    const merged = { ...item, ...data }
    const link = String(merged?.portal_login_link || merged?.portal_link || "").trim()
    if (!link) {
      errorText.value = "生成渠道登录入口失败"
      return
    }
    openLinkResultPanel(item, {
      title: portalButtonLabel(item),
      resultTitle: "专用登录入口已生成",
      copyMessage: "渠道登录入口已复制",
      action: "portal_link",
      link,
    })
    hintText.value = `${item.name || item.channel_code || "该渠道"} 的登录入口已生成`
    await Promise.all([loadChannels(), loadAnalytics()])
  } catch (error) {
    errorText.value = String(error?.message || "生成渠道登录入口失败")
  }
}

async function openChannelCustomerLinkPanel(item) {
  const link = String(item?.order_link || "").trim()
  if (!link) {
    errorText.value = "生成网页获客链接失败"
    hintText.value = ""
    return
  }
  openLinkResultPanel(item, {
    title: customerLinkButtonLabel(item),
    resultTitle: "专用网页获客链接已生成",
    copyMessage: "网页获客链接已复制",
    action: "customer_link",
    link,
  })
  hintText.value = `${item.name || item.channel_code || "该渠道"} 的网页获客链接已生成`
  errorText.value = ""
}

async function openChannelCustomerQrPanel(item) {
  await openMiniappQrPanel(item)
}

async function refreshMaterialPanel() {
  if (!miniappQrPanel.channel) return
  if (miniappQrPanel.action === "portal_link") {
    await openChannelPortalLinkPanel(miniappQrPanel.channel)
    return
  }
  if (miniappQrPanel.action === "customer_link") {
    await openChannelCustomerLinkPanel(miniappQrPanel.channel)
    return
  }
  if (miniappQrPanel.action === "customer_qrcode") {
    await openMiniappQrPanel(miniappQrPanel.channel)
  }
}

function buildChannelBundle(item) {
  const lines = [
    `渠道名称：${String(item?.name || "").trim() || "-"}`,
    `渠道编码：${String(item?.channel_code || "").trim() || "-"}`,
    `登录账号：${String(item?.portal_account || item?.channel_code || "").trim() || "-"}`,
    `登录密码：${String(item?.portal_password || "").trim() || "-"}`,
    `Web 登录入口：${String(item?.portal_login_link || item?.portal_link || "").trim() || "-"}`,
    `Web 下单链接：${String(item?.order_link || "").trim() || "-"}`,
    `小程序下单路径：${String(item?.miniapp_order_path || "").trim() || "-"}`,
  ]
  return lines.join("\n")
}

async function openPolicyPanel(item) {
  await loadPackageOptions()
  policyPanel.visible = true
  policyPanel.channel = item
  resetPolicyForm(item)
  const data = await adminHttp.get(`/partners/admin/channels/${item.id}/policies`)
  policyPanel.items = Array.isArray(data?.items) ? data.items : []
}

function closePolicyPanel() {
  policyPanel.visible = false
  policyPanel.channel = null
  policyPanel.items = []
  resetPolicyForm()
}

function resetPolicyForm(channel = policyPanel.channel) {
  policyForm.package_name = ""
  policyForm.rebate_rate_pct = Number(channel?.default_rebate_rate_pct || 0)
  policyForm.is_active = true
}

function applyPackagePreset(item) {
  policyForm.package_name = String(item?.name || "").trim()
  if (!policyForm.rebate_rate_pct && policyPanel.channel) {
    policyForm.rebate_rate_pct = Number(policyPanel.channel?.default_rebate_rate_pct || 0)
  }
}

function editPolicyItem(item) {
  policyForm.package_name = String(item?.package_name || "").trim()
  policyForm.rebate_rate_pct = Number(item?.rebate_rate_pct || 0)
  policyForm.is_active = Boolean(item?.is_active)
}

async function openInsightPanel(item) {
  insightPanel.visible = true
  insightPanel.channel = item
  insightPanel.scope = Number(item?.level || 1) === 1 ? "subtree" : "self"
  insightPanel.keyword = ""
  insightPanel.created_from = ""
  insightPanel.created_to = ""
  insightPanel.pagination = { page: 1, page_size: 20, total: 0, pages: 0 }
  focusedChannelId.value = Number(item.id || 0)
  await loadInsightPanel()
}

function closeInsightPanel() {
  insightPanel.visible = false
  insightPanel.channel = null
  insightPanel.summary = null
  insightPanel.customers = []
  insightPanel.keyword = ""
  insightPanel.created_from = ""
  insightPanel.created_to = ""
  insightPanel.pagination = { page: 1, page_size: 20, total: 0, pages: 0 }
}

async function loadInsightPanel() {
  if (!insightPanel.channel) return
  const channelId = Number(insightPanel.channel.id || 0)
  const scope = String(insightPanel.scope || "subtree")
  const [summary, customers] = await Promise.all([
    adminHttp.get(`/partners/admin/channels/${channelId}/team-summary`, { params: { scope } }),
    adminHttp.get(`/partners/admin/channels/${channelId}/customers`, {
      params: {
        scope,
        page: insightPanel.pagination.page,
        page_size: insightPanel.pagination.page_size,
        keyword: insightPanel.keyword || undefined,
        created_from: insightPanel.created_from || undefined,
        created_to: insightPanel.created_to || undefined,
      },
    }),
  ])
  insightPanel.summary = summary || null
  insightPanel.customers = Array.isArray(customers?.items) ? customers.items : []
  insightPanel.pagination = { ...(customers?.pagination || insightPanel.pagination) }
}

function applyInsightFilter() {
  insightPanel.pagination.page = 1
  loadInsightPanel()
}

function changeInsightPage(delta) {
  insightPanel.pagination.page = Math.max(1, Number(insightPanel.pagination.page || 1) + delta)
  loadInsightPanel()
}

function exportInsightCustomers() {
  const headers = ["用户ID", "昵称", "手机号", "归属渠道", "归属来源", "历史订单", "锁定时间"]
  const rows = insightPanel.customers.map((item) => [
    item.user_id,
    item.nickname,
    item.phone_masked || "",
    item.channel_name || item.channel_code || "",
    item.bind_source || "",
    Number(item.order_count || 0),
    formatTime(item.locked_at || item.updated_at || item.created_at),
  ])
  const csv = [headers, ...rows].map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll("\"", "\"\"")}"`).join(",")).join("\n")
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
  triggerBlobDownload(blob, `partner_customers_${new Date().toISOString().slice(0, 10)}.csv`)
}

async function savePolicy() {
  if (!policyPanel.channel || !canManage.value) return
  const rebateRatePct = Number(policyForm.rebate_rate_pct || 0)
  if (!Number.isFinite(rebateRatePct) || rebateRatePct < 0 || rebateRatePct > 100) {
    errorText.value = "返佣比例需在 0~100% 范围内"
    hintText.value = ""
    return
  }
  policySubmitting.value = true
  errorText.value = ""
  hintText.value = ""
  try {
    await adminHttp.post(`/partners/admin/channels/${policyPanel.channel.id}/policy`, {
      package_name: String(policyForm.package_name || "").trim() || null,
      rebate_rate_bp: Math.round(rebateRatePct * 100),
      is_active: Boolean(policyForm.is_active),
    })
    hintText.value = "返佣设置已保存"
    await openPolicyPanel(policyPanel.channel)
    resetPolicyForm(policyPanel.channel)
    await Promise.all([loadChannels(), loadAnalytics()])
  } catch (error) {
    errorText.value = String(error?.message || "保存返佣设置失败")
  } finally {
    policySubmitting.value = false
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

function mapLevel(value) {
  const level = Number(value || 1)
  if (level === 1) return "一级渠道"
  if (level === 2) return "二级渠道"
  if (level === 3) return "历史三级渠道"
  return `L${level}`
}

function formatRate(value) {
  const bp = Number(value || 0)
  return `${(bp / 100).toFixed(2)}%`
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
.partner-admin-page {
  display: grid;
  gap: 18px;
}

.partner-admin-stats {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.partner-admin-stat {
  border: 1px solid rgba(214, 225, 242, 0.96);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(247, 251, 255, 0.99) 100%);
  padding: 18px 20px;
  display: grid;
  gap: 8px;
  box-shadow: 0 14px 28px rgba(20, 64, 146, 0.08);
}

.partner-admin-stat--primary {
  border-color: rgba(82, 131, 255, 0.45);
  background: linear-gradient(135deg, #1f56cc 0%, #2f77ff 100%);
  color: #fff;
}

.partner-admin-stat span,
.partner-admin-mini-card span {
  font-size: 13px;
  color: #6d7f99;
}

.partner-admin-stat--primary span,
.partner-admin-stat--primary p {
  color: rgba(255, 255, 255, 0.84);
}

.partner-admin-stat strong,
.partner-admin-mini-card strong {
  font-size: 30px;
  line-height: 1;
  color: #183c6c;
}

.partner-admin-stat--primary strong {
  color: #fff;
}

.partner-admin-stat p,
.partner-admin-mini-card p {
  margin: 0;
  font-size: 12px;
  color: #7b8da8;
}

.partner-admin-chart-grid,
.partner-admin-top-grid {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.partner-admin-top-grid {
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.2fr);
}

.partner-admin-panel,
.partner-admin-chart-card {
  border: 1px solid rgba(214, 225, 242, 0.96);
  border-radius: 22px;
  background: #fff;
  padding: 18px 20px;
  box-shadow: 0 14px 28px rgba(20, 64, 146, 0.08);
}

.partner-admin-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.partner-admin-section-head h3 {
  margin: 4px 0 0;
  color: #17365f;
  font-size: 20px;
}

.partner-admin-kicker {
  color: #1d5ce0;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.partner-admin-chart-note {
  color: #7890b0;
  font-size: 12px;
}

.partner-admin-chart {
  width: 100%;
  height: 280px;
  margin-top: 14px;
}

.partner-admin-chart--short {
  height: 250px;
}

.partner-admin-alert-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.partner-admin-alert-item {
  width: 100%;
  border: 1px solid #deebff;
  border-radius: 16px;
  background: #f7fbff;
  padding: 14px 16px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  text-align: left;
}

.partner-admin-alert-item strong {
  color: #1b3f6f;
  font-size: 14px;
}

.partner-admin-alert-item p {
  margin: 6px 0 0;
  color: #6f819b;
  font-size: 12px;
  line-height: 1.6;
}

.partner-admin-pill {
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  white-space: nowrap;
}

.partner-admin-pill--success {
  background: #e8f7ef;
  color: #127246;
}

.partner-admin-pill--warning {
  background: #fff4dd;
  color: #9a6a00;
}

.partner-admin-pill--danger {
  background: #ffe7e7;
  color: #b33636;
}

.partner-admin-pill--muted {
  background: #eef3fb;
  color: #60738f;
}

.partner-admin-form,
.partner-admin-inline-form {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 14px;
}

.partner-admin-form label,
.partner-admin-inline-form label {
  display: grid;
  gap: 6px;
}

.partner-admin-form span,
.partner-admin-inline-form span {
  color: #627694;
  font-size: 13px;
}

.partner-admin-input {
  width: 100%;
  min-height: 42px;
  border: 1px solid #d7e2f4;
  border-radius: 12px;
  padding: 0 12px;
  color: #1a365e;
  background: #fff;
}

.partner-admin-input--compact {
  width: auto;
  min-width: 160px;
}

.partner-admin-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.partner-admin-actions--tight {
  justify-content: space-between;
}

.partner-admin-qrcode-panel {
  margin-top: 14px;
  display: grid;
  gap: 18px;
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: start;
}

.partner-admin-qrcode-card {
  border: 1px solid #e2ebf8;
  border-radius: 20px;
  background: #f8fbff;
  padding: 18px;
}

.partner-admin-qrcode-image {
  display: block;
  width: 100%;
  border-radius: 16px;
  background: #ffffff;
}

.partner-admin-qrcode-copy {
  display: grid;
  gap: 12px;
}

.partner-admin-message {
  margin: 10px 0 0;
  font-size: 13px;
}

.partner-admin-message--success {
  color: #156a43;
}

.partner-admin-message--danger {
  color: #b33b3b;
}

.partner-admin-filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.partner-admin-table-wrap {
  margin-top: 14px;
  overflow-x: auto;
}

.partner-admin-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 1040px;
}

.partner-admin-table th,
.partner-admin-table td {
  border-bottom: 1px solid #e6eef9;
  padding: 12px 10px;
  text-align: left;
  vertical-align: top;
}

.partner-admin-table th {
  color: #5f7697;
  font-size: 12px;
  font-weight: 600;
}

.partner-admin-row--focus {
  background: #f5f9ff;
}

.partner-admin-channel,
.partner-admin-stack,
.partner-admin-links {
  display: grid;
  gap: 6px;
}

.partner-admin-channel strong {
  color: #17365f;
}

.partner-admin-channel span,
.partner-admin-stack span,
.partner-admin-links span {
  color: #6d809d;
  font-size: 12px;
  line-height: 1.5;
}

.partner-admin-generate-actions {
  display: grid;
  gap: 8px;
}

.partner-admin-link-actions,
.partner-admin-row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.partner-admin-text-btn {
  border: none;
  background: transparent;
  padding: 0;
  color: #1d5ce0;
  cursor: pointer;
  font-size: 12px;
}

.partner-admin-danger-btn {
  color: #b33636;
}

.partner-admin-result-panel {
  margin-top: 14px;
  display: grid;
  gap: 14px;
}

.partner-admin-result-box {
  padding: 16px 18px;
  border: 1px solid #dbe7fb;
  border-radius: 18px;
  background: #f8fbff;
}

.partner-admin-result-box strong {
  color: #17365f;
  font-size: 14px;
}

.partner-admin-result-box p {
  margin: 10px 0 0;
  color: #5f7593;
  font-size: 13px;
  line-height: 1.7;
  word-break: break-all;
}

.partner-admin-policy-cards {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 14px;
}

.partner-admin-mini-card {
  border: 1px solid #e2ebf8;
  border-radius: 16px;
  background: #f8fbff;
  padding: 14px 16px;
  display: grid;
  gap: 6px;
}

.partner-admin-tag-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 14px;
}

.partner-admin-tag {
  border: 1px solid #d4e1f9;
  border-radius: 999px;
  background: #f8fbff;
  padding: 6px 10px;
  color: #2a4c78;
  font-size: 12px;
}

.partner-admin-summary {
  cursor: pointer;
  list-style: none;
}

.partner-admin-summary::-webkit-details-marker {
  display: none;
}

.partner-admin-empty {
  padding: 22px 0;
  text-align: center;
  color: #7b8da8;
}

@media (max-width: 1100px) {
  .partner-admin-stats,
  .partner-admin-chart-grid,
  .partner-admin-top-grid,
  .partner-admin-policy-cards,
  .partner-admin-qrcode-panel {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .partner-admin-form,
  .partner-admin-inline-form {
    grid-template-columns: 1fr;
  }

  .partner-admin-chart {
    height: 240px;
  }

  .partner-admin-section-head,
  .partner-admin-actions--tight {
    align-items: stretch;
  }

  .partner-admin-input--compact {
    width: 100%;
    min-width: 0;
  }
}
</style>
