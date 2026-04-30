<template>
  <div class="partner-page">
    <section class="partner-shell">
      <header class="partner-head">
        <div>
          <p class="partner-head__eyebrow">渠道返佣门户</p>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageSubtitle }}</p>
        </div>
        <div class="partner-head__actions">
          <button type="button" class="partner-button partner-button--ghost" :disabled="loading" @click="loadPortalData">
            {{ loading ? "刷新中..." : "刷新数据" }}
          </button>
          <button v-if="hasPortalSession" type="button" class="partner-button partner-button--ghost" @click="logoutPortal">
            退出登录
          </button>
        </div>
      </header>

      <p v-if="errorText" class="partner-message partner-message--danger">{{ errorText }}</p>
      <p v-if="successText" class="partner-message partner-message--success">{{ successText }}</p>

      <section v-if="hasPortalSession && overview" class="partner-stat-grid">
        <article v-for="item in summaryCards" :key="item.label" class="partner-stat-card" :class="{ 'partner-stat-card--primary': item.primary }">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <p>{{ item.hint }}</p>
        </article>
      </section>

      <section v-if="hasPortalSession && overview" class="partner-workbench">
        <article class="partner-panel">
          <div class="partner-section-head">
            <div>
              <div class="partner-kicker">快捷动作</div>
              <h2>打开就能做的事</h2>
            </div>
          </div>
          <div class="partner-action-grid">
            <button v-if="isLevelOne" type="button" class="partner-action-card partner-action-card--primary" @click="scrollToSection('channel-materials')">
              <strong>生成二级物料</strong>
              <span>直接到二级渠道操作区</span>
            </button>
            <button v-else type="button" class="partner-action-card partner-action-card--primary" @click="openOwnCustomerLinkPanel">
              <strong>生成获客链接</strong>
              <span>生成二级渠道网页获客链接</span>
            </button>
            <button v-if="isLevelOne" type="button" class="partner-action-card" @click="scrollToSection('subchannel-form')">
              <strong>新建二级</strong>
              <span>直接跳到创建区</span>
            </button>
            <button v-else type="button" class="partner-action-card" @click="openOwnCustomerQrPanel">
              <strong>生成小程序码</strong>
              <span>生成二级渠道获客小程序码</span>
            </button>
            <button type="button" class="partner-action-card" @click="scrollToSection('withdraw-panel')">
              <strong>提现</strong>
              <span>进入提现区</span>
            </button>
          </div>
        </article>

        <article class="partner-panel">
          <div class="partner-section-head">
            <div>
              <div class="partner-kicker">经营提醒</div>
              <h2>{{ isLevelOne ? `今天先看${analyticsScopeLabel}` : "今天先看自己" }}</h2>
            </div>
          </div>
          <div class="partner-alert-list">
            <div v-for="item in actionTips" :key="item.title" class="partner-alert-item">
              <strong>{{ item.title }}</strong>
              <p>{{ item.desc }}</p>
            </div>
          </div>
        </article>
      </section>

      <section v-if="hasPortalSession && overview" class="partner-chart-grid">
        <article class="partner-panel">
          <div class="partner-section-head">
            <div>
              <div class="partner-kicker">经营趋势</div>
              <h2>{{ isLevelOne ? `近 14 天${analyticsScopeLabel}经营趋势` : "近 14 天个人经营趋势" }}</h2>
            </div>
            <div v-if="isLevelOne" class="partner-filter-row">
              <select v-model="scopeFilters.analytics" @change="loadAnalytics">
                <option value="self">仅自己</option>
                <option value="team">仅二级</option>
                <option value="subtree">自己 + 二级</option>
              </select>
            </div>
          </div>
          <div ref="activityChartEl" class="partner-chart"></div>
        </article>

        <article class="partner-panel">
          <div class="partner-section-head">
            <div>
              <div class="partner-kicker">{{ isLevelOne ? "二级贡献" : "订单结构" }}</div>
              <h2>{{ isLevelOne ? "哪个二级最有产出" : "当前订单主要来自哪些套餐" }}</h2>
            </div>
          </div>
          <div ref="mixChartEl" class="partner-chart"></div>
        </article>
      </section>

      <section v-if="hasPortalSession && overview && isLevelOne" id="channel-materials" class="partner-panel">
        <div class="partner-section-head">
          <div>
            <div class="partner-kicker">二级管理</div>
            <h2>一级重点看二级表现</h2>
          </div>
        </div>

        <div class="partner-table-wrap">
          <table class="partner-table">
            <thead>
              <tr>
                <th>二级渠道</th>
                <th>状态</th>
                <th>客户 / 返佣</th>
                <th>用途入口</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in subchannels" :key="item.id">
                <td>
                  <div class="partner-stack">
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.channel_code }}</span>
                    <span>{{ item.contact_name || "-" }} / {{ item.contact_phone || "-" }}</span>
                  </div>
                </td>
                <td>
                  <div class="partner-stack">
                    <span :class="['partner-pill', `partner-pill--${subchannelHealth(item).tone}`]">{{ subchannelHealth(item).label }}</span>
                    <span>{{ item.status === "active" ? "启用中" : "已停用" }}</span>
                    <span>默认返佣 {{ Number(item.default_rebate_rate_pct || 0).toFixed(2) }}%</span>
                  </div>
                </td>
                <td>
                  <div class="partner-stack">
                    <span>客户 {{ Number(item.user_count || 0) }}</span>
                    <span>待结算 {{ formatFenToCny(item.pending_rebate_fen) }}</span>
                    <span>已结算 {{ formatFenToCny(item.settled_rebate_fen) }}</span>
                  </div>
                </td>
                <td>
                  <div class="partner-generate-actions">
                    <button type="button" class="partner-button partner-button--ghost" @click="openChildPortalLinkPanel(item)">生成二级渠道登录入口</button>
                    <button type="button" class="partner-button partner-button--ghost" @click="openChildCustomerLinkPanel(item)">生成二级渠道网页获客链接</button>
                    <button type="button" class="partner-button partner-button--ghost" @click="openChildMiniappQr(item)">生成二级渠道获客小程序码</button>
                  </div>
                </td>
                <td>
                  <div class="partner-row-actions">
                    <button type="button" class="partner-button partner-button--ghost" @click="startEditChild(item)">编辑</button>
                    <button type="button" class="partner-button partner-button--ghost" @click="openPolicyPanel(item)">返佣设置</button>
                    <button type="button" class="partner-button partner-button--ghost" @click="toggleChildStatus(item)">
                      {{ item.status === "active" ? "停用" : "启用" }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="subchannels.length === 0">
                <td colspan="5" class="partner-empty">当前还没有直属二级渠道。</td>
              </tr>
            </tbody>
          </table>
        </div>

        <details class="partner-detail-box">
          <summary id="subchannel-form">新建 / 编辑二级渠道</summary>
          <div class="partner-form-grid">
            <label class="partner-field">
              <span>渠道名称</span>
              <input v-model.trim="childForm.name" type="text" maxlength="40" placeholder="例如：杭州高校二级渠道" :disabled="!overview.can_create_child && !editingChildId" />
            </label>
            <label class="partner-field">
              <span>渠道编码</span>
              <input v-model.trim="childForm.channel_code" type="text" maxlength="32" placeholder="可留空自动生成" :disabled="Boolean(editingChildId)" />
            </label>
            <label class="partner-field">
              <span>联系人</span>
              <input v-model.trim="childForm.contact_name" type="text" maxlength="30" placeholder="联系人姓名" />
            </label>
            <label class="partner-field">
              <span>联系电话</span>
              <input v-model.trim="childForm.contact_phone" type="text" maxlength="30" placeholder="联系电话" />
            </label>
            <label class="partner-field">
              <span>默认返佣比例（%）</span>
              <input v-model.number="childForm.rebate_rate_pct" type="number" min="0" max="100" step="0.01" />
            </label>
            <label v-if="editingChildId" class="partner-field">
              <span>渠道状态</span>
              <select v-model="childForm.status">
                <option value="active">启用</option>
                <option value="disabled">停用</option>
              </select>
            </label>
          </div>
          <div class="partner-row-actions partner-row-actions--top">
            <button type="button" class="partner-button" :disabled="childSubmitting || (!overview.can_create_child && !editingChildId)" @click="submitChildForm">
              {{ childSubmitting ? "提交中..." : editingChildId ? "保存二级渠道" : "创建二级渠道" }}
            </button>
            <button v-if="editingChildId" type="button" class="partner-button partner-button--ghost" @click="resetChildForm">取消编辑</button>
          </div>
        </details>
      </section>

      <section v-if="hasPortalSession && overview && !isLevelOne" class="partner-panel">
        <div class="partner-section-head">
          <div>
            <div class="partner-kicker">我的入口</div>
            <h2>二级重点先持续做客户</h2>
          </div>
        </div>
        <div class="partner-generate-actions partner-generate-actions--own">
          <button type="button" class="partner-button partner-button--ghost" @click="openOwnPortalLinkPanel">生成二级渠道登录入口</button>
          <button type="button" class="partner-button partner-button--ghost" @click="openOwnCustomerLinkPanel">生成二级渠道网页获客链接</button>
          <button type="button" class="partner-button partner-button--ghost" @click="openOwnCustomerQrPanel">生成二级渠道获客小程序码</button>
        </div>
      </section>

      <section v-if="childMiniappQr.visible" class="partner-panel">
        <div class="partner-section-head">
          <div>
            <div class="partner-kicker">渠道物料</div>
            <h2>{{ childMiniappQr.title || "-" }}</h2>
          </div>
          <button type="button" class="partner-button partner-button--ghost" @click="closeChildMiniappQr">关闭</button>
        </div>
        <div v-if="childMiniappQr.loading" class="partner-empty">正在生成专用物料...</div>
        <div v-else-if="childMiniappQr.kind === 'qrcode' && childMiniappQr.data" class="partner-qrcode-panel">
          <div class="partner-qrcode-card">
            <img :src="childMiniappQr.data.qrcode_data_url" alt="二级渠道小程序码" class="partner-qrcode-image" />
          </div>
          <div class="partner-stack">
            <span>{{ childMiniappQr.channel?.name || "当前渠道" }} 的专用获客小程序码已生成</span>
            <span>可直接发给客户扫码使用</span>
            <p v-if="childMiniappQr.data.fallback_reason" class="partner-message">{{ childMiniappQr.data.fallback_reason }}</p>
            <div class="partner-row-actions partner-row-actions--top">
              <button type="button" class="partner-button partner-button--ghost" @click="copyText(childMiniappQr.data.miniapp_order_path, '小程序入口已复制')">复制小程序入口</button>
              <button type="button" class="partner-button partner-button--ghost" @click="refreshChildMaterialPanel">重新生成</button>
            </div>
          </div>
        </div>
        <div v-else-if="childMiniappQr.kind === 'link'" class="partner-result-panel">
          <div class="partner-result-box">
            <strong>{{ childMiniappQr.resultTitle || "专用链接已生成" }}</strong>
            <p>{{ childMiniappQr.link || "-" }}</p>
          </div>
          <div class="partner-row-actions partner-row-actions--top">
            <button type="button" class="partner-button partner-button--ghost" @click="copyText(childMiniappQr.link || '', childMiniappQr.copyMessage || '链接已复制')">复制链接</button>
            <button type="button" class="partner-button partner-button--ghost" @click="refreshChildMaterialPanel">重新生成</button>
            <button type="button" class="partner-button partner-button--ghost" @click="closeChildMiniappQr">关闭</button>
          </div>
        </div>
        <div v-else class="partner-empty">
          当前暂无可展示的物料结果
        </div>
      </section>

      <section v-if="policyPanel.visible" class="partner-panel">
        <div class="partner-section-head">
          <div>
            <div class="partner-kicker">返佣设置</div>
            <h2>{{ policyPanel.channel?.name || "-" }} 的套餐返佣</h2>
          </div>
          <button type="button" class="partner-button partner-button--ghost" @click="closePolicyPanel">关闭</button>
        </div>
        <div class="partner-form-grid">
          <label class="partner-field">
            <span>套餐名</span>
            <select v-model="policyForm.package_name">
              <option value="">按默认返佣走</option>
              <option v-for="item in packageOptions" :key="item.name" :value="item.name">
                {{ item.name }}{{ item.priceLabel ? ` · ${item.priceLabel}` : "" }}{{ item.creditsLabel ? ` · ${item.creditsLabel}` : "" }}
              </option>
            </select>
          </label>
          <label class="partner-field">
            <span>返佣比例（%）</span>
            <input v-model.number="policyForm.rebate_rate_pct" type="number" min="0" max="100" step="0.01" />
          </label>
          <label class="partner-field">
            <span>状态</span>
            <select v-model="policyForm.is_active">
              <option :value="true">启用</option>
              <option :value="false">停用</option>
            </select>
          </label>
        </div>
        <div class="partner-row-actions partner-row-actions--top">
          <button type="button" class="partner-button" :disabled="policySubmitting" @click="savePolicy">
            {{ policySubmitting ? "保存中..." : "保存返佣设置" }}
          </button>
        </div>
        <div class="partner-table-wrap">
          <table class="partner-table">
            <thead>
              <tr>
                <th>套餐</th>
                <th>比例</th>
                <th>状态</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in policyPanel.items" :key="item.id">
                <td>{{ item.package_name }}</td>
                <td>{{ Number(item.rebate_rate_pct || 0).toFixed(2) }}%</td>
                <td>{{ item.is_active ? "启用" : "停用" }}</td>
                <td>{{ formatDateTime(item.updated_at || item.created_at) }}</td>
              </tr>
              <tr v-if="policyPanel.items.length === 0">
                <td colspan="4" class="partner-empty">暂无套餐返佣设置</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="hasPortalSession && overview" id="withdraw-panel" class="partner-panel">
        <div class="partner-section-head">
          <div>
            <div class="partner-kicker">提现</div>
            <h2>当前可提 {{ formatFenToCny(overview.withdrawable_fen) }}</h2>
          </div>
          <span class="partner-head-note">门槛 ¥100.00</span>
        </div>
        <div class="partner-form-grid">
          <label class="partner-field">
            <span>提现金额（元）</span>
            <input v-model.number="withdrawAmountCny" type="number" min="100" step="0.01" />
          </label>
          <label class="partner-field partner-field--wide">
            <span>备注（可选）</span>
            <input v-model.trim="withdrawNote" type="text" maxlength="120" placeholder="例如：4月结算提现" />
          </label>
        </div>
        <div class="partner-row-actions partner-row-actions--top">
          <button type="button" class="partner-button" :disabled="withdrawSubmitting" @click="submitWithdrawApply">
            {{ withdrawSubmitting ? "提交中..." : "提交提现申请" }}
          </button>
        </div>
      </section>

      <details v-if="hasPortalSession && overview" class="partner-panel">
        <summary class="partner-detail-summary">查看更多明细</summary>
        <div class="partner-inline-section">
          <div class="partner-section-head">
            <div>
              <div class="partner-kicker">订单列表</div>
              <h2>{{ isLevelOne ? "团队订单" : "我的订单" }}</h2>
            </div>
            <div class="partner-filter-row">
              <select v-model="scopeFilters.orders" @change="loadOrders">
                <option value="self">仅自己</option>
                <option v-if="isLevelOne" value="team">仅二级</option>
                <option v-if="isLevelOne" value="subtree">自己 + 二级</option>
              </select>
              <button type="button" class="partner-button partner-button--ghost" @click="exportRows('orders')">导出</button>
            </div>
          </div>
          <div class="partner-filter-row partner-filter-row--wide">
            <label class="partner-field"><span>开始日期</span><input v-model="dateFilters.orders_from" type="date" /></label>
            <label class="partner-field"><span>结束日期</span><input v-model="dateFilters.orders_to" type="date" /></label>
            <button type="button" class="partner-button partner-button--ghost" @click="applyListFilter('orders')">筛选</button>
          </div>
          <div class="partner-table-wrap">
            <table class="partner-table">
              <thead>
                <tr>
                  <th>订单号</th>
                  <th>用户ID</th>
                  <th>收益渠道</th>
                  <th>来源渠道</th>
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
                  <td>{{ item.channel_name || item.channel_code || "-" }}</td>
                  <td>{{ item.source_channel_code || "-" }}</td>
                  <td>{{ item.package_name || "-" }}</td>
                  <td>{{ formatFenToCny(item.amount_fen) }}</td>
                  <td>{{ formatRate(item.rebate_rate_bp) }}</td>
                  <td>{{ formatFenToCny(item.net_rebate_fen) }}</td>
                  <td>{{ formatStatus(item.order_status) }}</td>
                  <td>{{ formatDateTime(item.created_at) }}</td>
                </tr>
                <tr v-if="orders.length === 0"><td colspan="10" class="partner-empty">暂无订单数据</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="partner-inline-section">
          <div class="partner-section-head">
            <div>
              <div class="partner-kicker">返佣流水</div>
              <h2>{{ isLevelOne ? "团队返佣" : "我的返佣" }}</h2>
            </div>
            <div class="partner-filter-row">
              <select v-model="scopeFilters.ledger" @change="loadLedger">
                <option value="self">仅自己</option>
                <option v-if="isLevelOne" value="team">仅二级</option>
                <option v-if="isLevelOne" value="subtree">自己 + 二级</option>
              </select>
              <button type="button" class="partner-button partner-button--ghost" @click="exportRows('ledger')">导出</button>
            </div>
          </div>
          <div class="partner-table-wrap">
            <table class="partner-table">
              <thead>
                <tr>
                  <th>流水ID</th>
                  <th>订单号</th>
                  <th>收益渠道</th>
                  <th>来源渠道</th>
                  <th>类型</th>
                  <th>返佣比例</th>
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
                  <td>{{ item.channel_name || item.channel_code || "-" }}</td>
                  <td>{{ item.source_channel_code || "-" }}</td>
                  <td>{{ formatEntryType(item.entry_type) }}</td>
                  <td>{{ formatRate(item.rebate_rate_bp) }}</td>
                  <td>{{ formatFenToCny(item.rebate_amount_fen) }}</td>
                  <td>{{ formatStatus(item.status) }}</td>
                  <td>{{ item.statement_month || "-" }}</td>
                  <td>{{ formatDateTime(item.created_at) }}</td>
                </tr>
                <tr v-if="ledger.length === 0"><td colspan="10" class="partner-empty">暂无返佣流水</td></tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="partner-inline-section">
          <div class="partner-section-head">
            <div>
              <div class="partner-kicker">客户归属</div>
              <h2>{{ isLevelOne ? "自己和二级的客户" : "我的客户" }}</h2>
            </div>
            <div class="partner-filter-row">
              <select v-model="scopeFilters.customers" @change="loadCustomers">
                <option value="self">仅自己</option>
                <option v-if="isLevelOne" value="team">仅二级</option>
                <option v-if="isLevelOne" value="subtree">自己 + 二级</option>
              </select>
              <button type="button" class="partner-button partner-button--ghost" @click="exportRows('customers')">导出</button>
            </div>
          </div>
          <div class="partner-filter-row partner-filter-row--wide">
            <label class="partner-field"><span>关键词</span><input v-model.trim="dateFilters.customers_keyword" type="text" placeholder="昵称 / 渠道名 / 渠道编码" /></label>
            <label class="partner-field"><span>开始日期</span><input v-model="dateFilters.customers_from" type="date" /></label>
            <label class="partner-field"><span>结束日期</span><input v-model="dateFilters.customers_to" type="date" /></label>
            <button type="button" class="partner-button partner-button--ghost" @click="applyListFilter('customers')">筛选</button>
          </div>
          <div class="partner-table-wrap">
            <table class="partner-table">
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
                <tr v-for="item in customers" :key="item.binding_id">
                  <td>{{ item.user_id }}</td>
                  <td>{{ item.nickname }}</td>
                  <td>{{ item.phone_masked || "-" }}</td>
                  <td>{{ item.channel_name || item.channel_code || "-" }}</td>
                  <td>{{ item.bind_source || "-" }}</td>
                  <td>{{ Number(item.order_count || 0) }}</td>
                  <td>{{ formatDateTime(item.locked_at || item.updated_at || item.created_at) }}</td>
                </tr>
                <tr v-if="customers.length === 0"><td colspan="7" class="partner-empty">暂无客户归属数据</td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </details>

      <section v-if="!hasPortalSession && !loading" class="partner-panel partner-panel--center">
        <h2>请先登录渠道门户</h2>
        <p>登录后可直接查看客户、订单、返佣和分发信息。</p>
        <button type="button" class="partner-button" @click="goLogin">前往登录</button>
      </section>
    </section>
  </div>
</template>

<script setup>
import * as echarts from "echarts/core"
import { BarChart, LineChart, PieChart } from "echarts/charts"
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components"
import { CanvasRenderer } from "echarts/renderers"
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue"
import { useRouter } from "vue-router"

import { formatBeijingDateTime } from "../../lib/dateTime"
import { triggerBlobDownload } from "../../lib/download"
import { partnerHttp } from "../../lib/http"
import { clearPartnerSession, getPartnerInfo } from "../../lib/session"

echarts.use([LineChart, BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const router = useRouter()
const activityChartEl = ref(null)
const mixChartEl = ref(null)

let activityChart = null
let mixChart = null

const loading = ref(false)
const errorText = ref("")
const successText = ref("")
const overview = ref(null)
const analytics = ref(null)
const orders = ref([])
const ledger = ref([])
const withdrawals = ref([])
const subchannels = ref([])
const customers = ref([])
const packageOptions = ref([])
const ordersPagination = ref({ page: 1, page_size: 100, total: 0, pages: 0 })
const ledgerPagination = ref({ page: 1, page_size: 100, total: 0, pages: 0 })
const customersPagination = ref({ page: 1, page_size: 100, total: 0, pages: 0 })
const withdrawAmountCny = ref(100)
const withdrawNote = ref("")
const withdrawSubmitting = ref(false)
const childSubmitting = ref(false)
const policySubmitting = ref(false)
const editingChildId = ref(0)
const scopeInitialized = ref(false)

const childForm = ref(createEmptyChildForm())
const policyPanel = ref({
  visible: false,
  channel: null,
  items: [],
})
const childMiniappQr = ref({
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
const policyForm = ref({
  package_name: "",
  rebate_rate_pct: 0,
  is_active: true,
})
const scopeFilters = ref({
  analytics: "self",
  orders: "self",
  ledger: "self",
  customers: "self",
})
const dateFilters = ref({
  orders_from: "",
  orders_to: "",
  ledger_from: "",
  ledger_to: "",
  customers_keyword: "",
  customers_from: "",
  customers_to: "",
})

const partnerInfo = ref(getPartnerInfo())
const hasPortalSession = computed(() => Boolean(partnerInfo.value?.id))
const isLevelOne = computed(() => Number(overview.value?.level || 1) === 1)
const analyticsScopeLabel = computed(() => {
  const scope = String(scopeFilters.value.analytics || "self")
  if (scope === "team") return "二级"
  if (scope === "subtree") return "团队"
  return "自己"
})
const pageTitle = computed(() => {
  if (!overview.value) return "渠道后台"
  return isLevelOne.value ? "一级渠道后台" : "二级渠道后台"
})
const pageSubtitle = computed(() => {
  if (!overview.value) return "收益、客户和分发信息都在这里。"
  return isLevelOne.value ? "重点看二级表现、客户归属和返佣产出。" : "重点看自己的客户、订单和返佣。"
})
const summaryCards = computed(() => {
  if (!overview.value) return []
  return isLevelOne.value
    ? [
        { label: "本月净返佣", value: formatFenToCny(overview.value.month_rebate_fen), hint: "本月已入账返佣", primary: true },
        { label: "待结算返佣", value: formatFenToCny(overview.value.pending_rebate_fen), hint: "需要继续跟进处理" },
        { label: "直属二级", value: String(Number(overview.value.child_count || 0)), hint: "当前带着的二级数量" },
        { label: "团队客户", value: String(Number(overview.value.team_subtree?.user_count || 0)), hint: "自己 + 二级带来的客户" },
      ]
    : [
        { label: "本月净返佣", value: formatFenToCny(overview.value.month_rebate_fen), hint: "本月已入账返佣", primary: true },
        { label: "可提现余额", value: formatFenToCny(overview.value.withdrawable_fen), hint: "达到门槛即可申请提现" },
        { label: "我的客户", value: String(Number(overview.value.user_count || 0)), hint: "当前归属到你的客户数" },
        { label: "待结算返佣", value: formatFenToCny(overview.value.pending_rebate_fen), hint: "需要继续跟进订单转化" },
      ]
})
const actionTips = computed(() => {
  if (!overview.value) return []
  const trendSeries = Array.isArray(analytics.value?.trend_series) ? analytics.value.trend_series : []
  if (isLevelOne.value) {
    const childSummary = analytics.value?.child_summary || {}
    const idleChildCount = Number(childSummary.idle_child_count || 0)
    const totalRebateFen = Number(childSummary.total_rebate_fen || 0)
    return [
      {
        title: Number(overview.value.child_count || 0) > 0 ? `先看${analyticsScopeLabel.value}排行` : "先建一个二级渠道",
        desc: Number(overview.value.child_count || 0) > 0 ? `先看${analyticsScopeLabel.value}里谁最有产出，再决定后续扶持。` : "一级当前没有二级，先搭起二级渠道结构。",
      },
      {
        title: idleChildCount > 0 ? `有 ${idleChildCount} 个二级待激活` : "二级活跃状态正常",
        desc: idleChildCount > 0 ? "建议先发催活文案，推动二级开始分发客户。" : "当前二级基本都在正常经营。",
      },
      {
        title: totalRebateFen > 0 ? `当前${analyticsScopeLabel.value}已有返佣产出` : "今天先继续分发客户入口",
        desc: totalRebateFen > 0 ? `返佣已经开始积累，优先跟进${analyticsScopeLabel.value}里的高产出渠道。` : "当前返佣不高，优先继续做客户。",
      },
    ]
  }
  const recentOrderCount = trendSeries.slice(-7).reduce((sum, item) => sum + Number(item.order_count || 0), 0)
  const recentCustomerCount = trendSeries.slice(-7).reduce((sum, item) => sum + Number(item.new_customers || 0), 0)
  return [
    {
      title: recentOrderCount > 0 ? "近 7 天已有订单" : "近 7 天还没有新订单",
      desc: recentOrderCount > 0 ? "继续保持当前分发节奏即可。" : "建议今天优先转发客户入口，先拉回新增。",
    },
    {
      title: recentCustomerCount > 0 || Number(overview.value.user_count || 0) > 0 ? "当前已有客户沉淀" : "还没有客户沉淀",
      desc: recentCustomerCount > 0 || Number(overview.value.user_count || 0) > 0 ? "下一步重点看客户转单和返佣增长。" : "先把专属推广链接持续发出去。",
    },
    {
      title: Number(overview.value.pending_rebate_fen || 0) > 0 ? "待结算返佣正在累积" : "返佣还在起量阶段",
      desc: Number(overview.value.pending_rebate_fen || 0) > 0 ? "可以同步关注到账和提现节奏。" : "继续做客户，不需要复杂操作。",
    },
  ]
})

watch(
  () => hasPortalSession.value,
  () => {
    loadPortalData()
  },
  { immediate: true }
)

watch(
  () => [overview.value, analytics.value],
  async () => {
    await nextTick()
    renderCharts()
  },
  { deep: true }
)

onMounted(() => {
  window.addEventListener("resize", handleResize)
})

onUnmounted(() => {
  window.removeEventListener("resize", handleResize)
  disposeCharts()
})

function createEmptyChildForm() {
  return {
    name: "",
    channel_code: "",
    contact_name: "",
    contact_phone: "",
    rebate_rate_pct: 0,
    status: "active",
  }
}

function initScopes() {
  if (!overview.value || scopeInitialized.value) return
  const baseScope = isLevelOne.value ? "subtree" : "self"
  scopeFilters.value = {
    analytics: baseScope,
    orders: baseScope,
    ledger: baseScope,
    customers: baseScope,
  }
  scopeInitialized.value = true
}

async function loadPortalData() {
  errorText.value = ""
  if (!hasPortalSession.value) {
    overview.value = null
    analytics.value = null
    orders.value = []
    ledger.value = []
    withdrawals.value = []
    subchannels.value = []
    customers.value = []
    successText.value = ""
    return
  }
  loading.value = true
  try {
    const overviewResp = await partnerHttp.get("/partners/portal/overview", { timeout: 30000 })
    overview.value = overviewResp || null
    initScopes()
    const [analyticsResp, withdrawalResp, subchannelResp] = await Promise.all([
      partnerHttp.get("/partners/portal/analytics", { params: { days: 14, scope: scopeFilters.value.analytics }, timeout: 30000 }),
      partnerHttp.get("/partners/portal/withdrawals", { params: { page: 1, page_size: 20 }, timeout: 30000 }),
      partnerHttp.get("/partners/portal/subchannels", { timeout: 30000 }),
    ])
    analytics.value = analyticsResp || null
    withdrawals.value = Array.isArray(withdrawalResp?.items) ? withdrawalResp.items : []
    subchannels.value = Array.isArray(subchannelResp?.items) ? subchannelResp.items : []
    if (!editingChildId.value && overviewResp) {
      childForm.value.rebate_rate_pct = Number(overviewResp.default_rebate_rate_bp || 0) / 100
    }
    await Promise.all([loadOrders(), loadLedger(), loadCustomers(), loadPackageOptions()])
  } catch (error) {
    errorText.value = String(error?.message || "加载渠道数据失败，请稍后重试")
  } finally {
    loading.value = false
  }
}

async function loadPackageOptions() {
  try {
    const data = await partnerHttp.get("/billing/packages", { timeout: 30000 })
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

async function loadOrders() {
  if (!hasPortalSession.value) return
  try {
    const resp = await partnerHttp.get("/partners/portal/orders", {
      params: {
        scope: scopeFilters.value.orders,
        page: ordersPagination.value.page,
        page_size: ordersPagination.value.page_size,
        created_from: dateFilters.value.orders_from || undefined,
        created_to: dateFilters.value.orders_to || undefined,
      },
      timeout: 30000,
    })
    orders.value = Array.isArray(resp?.items) ? resp.items : []
    ordersPagination.value = { ...(resp?.pagination || ordersPagination.value) }
  } catch (error) {
    errorText.value = String(error?.message || "加载订单失败")
  }
}

async function loadAnalytics() {
  if (!hasPortalSession.value) return
  try {
    const resp = await partnerHttp.get("/partners/portal/analytics", {
      params: { days: 14, scope: scopeFilters.value.analytics || "self" },
      timeout: 30000,
    })
    analytics.value = resp || null
  } catch (error) {
    errorText.value = String(error?.message || "加载经营分析失败")
  }
}

async function loadLedger() {
  if (!hasPortalSession.value) return
  try {
    const resp = await partnerHttp.get("/partners/portal/ledger", {
      params: {
        scope: scopeFilters.value.ledger,
        page: ledgerPagination.value.page,
        page_size: ledgerPagination.value.page_size,
        created_from: dateFilters.value.ledger_from || undefined,
        created_to: dateFilters.value.ledger_to || undefined,
      },
      timeout: 30000,
    })
    ledger.value = Array.isArray(resp?.items) ? resp.items : []
    ledgerPagination.value = { ...(resp?.pagination || ledgerPagination.value) }
  } catch (error) {
    errorText.value = String(error?.message || "加载返佣流水失败")
  }
}

async function loadCustomers() {
  if (!hasPortalSession.value) return
  try {
    const resp = await partnerHttp.get("/partners/portal/customers", {
      params: {
        scope: scopeFilters.value.customers,
        page: customersPagination.value.page,
        page_size: customersPagination.value.page_size,
        keyword: dateFilters.value.customers_keyword || undefined,
        created_from: dateFilters.value.customers_from || undefined,
        created_to: dateFilters.value.customers_to || undefined,
      },
      timeout: 30000,
    })
    customers.value = Array.isArray(resp?.items) ? resp.items : []
    customersPagination.value = { ...(resp?.pagination || customersPagination.value) }
  } catch (error) {
    errorText.value = String(error?.message || "加载客户归属失败")
  }
}

function renderCharts() {
  if (!overview.value) return
  const trendSeries = Array.isArray(analytics.value?.trend_series) ? analytics.value.trend_series : []
  const xLabels = trendSeries.map((item) => String(item.date || "").slice(5) || "-")

  activityChart = initChart(activityChartEl.value, activityChart)
  mixChart = initChart(mixChartEl.value, mixChart)

  if (activityChart) {
    activityChart.setOption({
      grid: { left: 30, right: 18, top: 18, bottom: 26 },
      legend: { bottom: 0, textStyle: { color: "#617793" } },
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: xLabels, axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#617793" } },
      yAxis: [
        { type: "value", axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: "rgba(72, 96, 132, 0.12)" } }, axisLabel: { color: "#617793" } },
        { type: "value", axisLine: { show: false }, axisTick: { show: false }, splitLine: { show: false }, axisLabel: { color: "#617793", formatter: (value) => `¥${value}` } },
      ],
      series: [
        { name: "新增客户", type: "line", smooth: true, data: trendSeries.map((item) => Number(item.new_customers || 0)), lineStyle: { width: 3, color: "#1e5bdf" }, symbolSize: 6, itemStyle: { color: "#1e5bdf" } },
        { name: "订单数", type: "line", smooth: true, data: trendSeries.map((item) => Number(item.order_count || 0)), lineStyle: { width: 3, color: "#6aa3ff" }, symbolSize: 6, itemStyle: { color: "#6aa3ff" } },
        { name: "返佣额", type: "bar", yAxisIndex: 1, data: trendSeries.map((item) => Number(Number(item.rebate_amount_cny || 0).toFixed(2))), itemStyle: { color: "#c8dafd", borderRadius: [8, 8, 0, 0] } },
      ],
    })
  }

  if (mixChart) {
    if (isLevelOne.value) {
      const rows = [...(Array.isArray(analytics.value?.subchannel_rank) ? analytics.value.subchannel_rank : [])]
        .slice(0, 8)
        .map((item) => ({
          name: String(item.name || ""),
          users: Number(item.user_count || 0),
          rebate: Number(item.rebate_amount_fen || 0),
        }))
        .reverse()
      mixChart.setOption({
        grid: { left: 90, right: 18, top: 18, bottom: 18 },
        legend: { bottom: 0, textStyle: { color: "#617793" } },
        tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
        xAxis: { type: "value", axisLine: { show: false }, axisTick: { show: false }, splitLine: { lineStyle: { color: "rgba(72, 96, 132, 0.12)" } }, axisLabel: { color: "#617793" } },
        yAxis: { type: "category", data: rows.map((item) => item.name), axisLine: { show: false }, axisTick: { show: false }, axisLabel: { color: "#244165" } },
        series: [
          { name: "客户数", type: "bar", data: rows.map((item) => item.users), barWidth: 14, itemStyle: { color: "#8eb7ff", borderRadius: 8 } },
          { name: "返佣(元)", type: "bar", data: rows.map((item) => Number((item.rebate / 100).toFixed(2))), barWidth: 14, itemStyle: { color: "#1e5bdf", borderRadius: 8 } },
        ],
      })
    } else {
      const pieRows = Array.isArray(analytics.value?.package_mix) ? analytics.value.package_mix : []
      mixChart.setOption({
        tooltip: { trigger: "item" },
        legend: { bottom: 0, textStyle: { color: "#617793" } },
        series: [
          {
            type: "pie",
            radius: ["46%", "72%"],
            center: ["50%", "42%"],
            label: { color: "#244165", formatter: "{b}\n{d}%" },
            data: pieRows.length ? pieRows : [{ name: "暂无订单", value: 1, itemStyle: { color: "#d9e5fb" }, label: { color: "#7b8da8" } }],
          },
        ],
      })
    }
  }
}

function initChart(el, existing) {
  if (!el) return null
  return existing || echarts.init(el)
}

function disposeCharts() {
  for (const chart of [activityChart, mixChart]) {
    if (chart) chart.dispose()
  }
  activityChart = null
  mixChart = null
}

function handleResize() {
  for (const chart of [activityChart, mixChart]) {
    if (chart) chart.resize()
  }
}

async function submitWithdrawApply() {
  if (!hasPortalSession.value || !overview.value) return
  withdrawSubmitting.value = true
  errorText.value = ""
  successText.value = ""
  try {
    await partnerHttp.post("/partners/portal/withdraw-apply", { apply_amount_cny: Number(withdrawAmountCny.value || 0), note: String(withdrawNote.value || "").trim() }, { timeout: 30000 })
    withdrawNote.value = ""
    await loadPortalData()
    successText.value = "提现申请已提交"
  } catch (error) {
    errorText.value = String(error?.message || "提交提现申请失败")
  } finally {
    withdrawSubmitting.value = false
  }
}

function scrollToSection(id) {
  if (typeof document === "undefined") return
  const element = document.getElementById(id)
  if (element) {
    element.scrollIntoView({ behavior: "smooth", block: "start" })
  }
}

async function submitChildForm() {
  if (!hasPortalSession.value || !overview.value) return
  const name = String(childForm.value.name || "").trim()
  if (!name) {
    errorText.value = "渠道名称不能为空"
    successText.value = ""
    return
  }
  const rebateRatePct = Number(childForm.value.rebate_rate_pct || 0)
  const parentRateBp = Number(overview.value.default_rebate_rate_bp || 0)
  if (!Number.isFinite(rebateRatePct) || rebateRatePct < 0 || rebateRatePct > 100) {
    errorText.value = "返佣比例需在 0~100% 范围内"
    successText.value = ""
    return
  }
  if (Math.round(rebateRatePct * 100) > parentRateBp) {
    errorText.value = "下级返佣比例不能高于当前渠道"
    successText.value = ""
    return
  }
  childSubmitting.value = true
  errorText.value = ""
  successText.value = ""
  try {
    const payload = {
      name,
      contact_name: String(childForm.value.contact_name || "").trim(),
      contact_phone: String(childForm.value.contact_phone || "").trim(),
      rebate_rate_bp: Math.round(rebateRatePct * 100),
      status: String(childForm.value.status || "active"),
    }
    if (!editingChildId.value) {
      payload.channel_code = String(childForm.value.channel_code || "").trim() || undefined
      const data = await partnerHttp.post("/partners/portal/subchannels", payload, { timeout: 30000 })
      const bundle = buildChannelBundle(data)
      if (bundle) await copyText(bundle, "二级渠道整段信息已复制")
      successText.value = bundle ? "二级渠道已创建并复制信息" : "二级渠道已创建"
    } else {
      await partnerHttp.patch(`/partners/portal/subchannels/${editingChildId.value}`, payload, { timeout: 30000 })
      successText.value = "二级渠道已更新"
    }
    resetChildForm()
    await loadPortalData()
  } catch (error) {
    errorText.value = String(error?.message || "保存二级渠道失败")
  } finally {
    childSubmitting.value = false
  }
}

function startEditChild(item) {
  editingChildId.value = Number(item.id || 0)
  childForm.value = {
    name: String(item.name || ""),
    channel_code: String(item.channel_code || ""),
    contact_name: String(item.contact_name || ""),
    contact_phone: String(item.contact_phone || ""),
    rebate_rate_pct: Number(item.default_rebate_rate_pct || 0),
    status: String(item.status || "active"),
  }
  successText.value = ""
  errorText.value = ""
}

function resetChildForm() {
  editingChildId.value = 0
  childForm.value = createEmptyChildForm()
  if (overview.value) {
    childForm.value.rebate_rate_pct = Number(overview.value.default_rebate_rate_bp || 0) / 100
  }
}

async function toggleChildStatus(item) {
  const nextStatus = item.status === "active" ? "disabled" : "active"
  try {
    await partnerHttp.patch(`/partners/portal/subchannels/${item.id}`, { status: nextStatus }, { timeout: 30000 })
    await loadPortalData()
    successText.value = nextStatus === "active" ? "二级渠道已启用" : "二级渠道已停用"
  } catch (error) {
    errorText.value = String(error?.message || "更新渠道状态失败")
  }
}

function subchannelHealth(item) {
  const userCount = Number(item.user_count || 0)
  const totalFen = Number(item.pending_rebate_fen || 0) + Number(item.settled_rebate_fen || 0)
  if (String(item.status || "") !== "active") return { label: "已停用", tone: "muted" }
  if (totalFen > 0) return { label: "活跃", tone: "success" }
  if (userCount > 0) return { label: "一般", tone: "warning" }
  return { label: "待激活", tone: "danger" }
}

async function openPolicyPanel(item) {
  await loadPackageOptions()
  const data = await partnerHttp.get(`/partners/portal/subchannels/${item.id}/policies`, { timeout: 30000 })
  policyPanel.value = {
    visible: true,
    channel: item,
    items: Array.isArray(data?.items) ? data.items : [],
  }
  policyForm.value = {
    package_name: "",
    rebate_rate_pct: Number(item.default_rebate_rate_pct || 0),
    is_active: true,
  }
}

function closePolicyPanel() {
  policyPanel.value = { visible: false, channel: null, items: [] }
}

async function savePolicy() {
  if (!policyPanel.value.channel) return
  const rebateRatePct = Number(policyForm.value.rebate_rate_pct || 0)
  if (!Number.isFinite(rebateRatePct) || rebateRatePct < 0 || rebateRatePct > 100) {
    errorText.value = "返佣比例需在 0~100% 范围内"
    return
  }
  policySubmitting.value = true
  errorText.value = ""
  successText.value = ""
  try {
    await partnerHttp.post(`/partners/portal/subchannels/${policyPanel.value.channel.id}/policy`, { package_name: String(policyForm.value.package_name || "").trim() || null, rebate_rate_bp: Math.round(rebateRatePct * 100), is_active: Boolean(policyForm.value.is_active) }, { timeout: 30000 })
    successText.value = "返佣设置已保存"
    await openPolicyPanel(policyPanel.value.channel)
    await loadPortalData()
  } catch (error) {
    errorText.value = String(error?.message || "保存返佣设置失败")
  } finally {
    policySubmitting.value = false
  }
}

async function copyText(value, message) {
  const text = String(value || "").trim()
  if (!text) {
    errorText.value = "内容为空，无法复制"
    successText.value = ""
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
    errorText.value = ""
    successText.value = message
  } catch (error) {
    errorText.value = String(error?.message || "复制失败，请稍后重试")
    successText.value = ""
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

function openChildLinkPanel(item, options) {
  childMiniappQr.value = {
    visible: true,
    loading: false,
    kind: "link",
    title: options.title,
    resultTitle: options.resultTitle,
    copyMessage: options.copyMessage,
    action: options.action,
    channel: item,
    data: null,
    link: options.link,
  }
}

async function openChildMiniappQr(item) {
  if (!hasPortalSession.value) return
  childMiniappQr.value = {
    visible: true,
    loading: true,
    kind: "qrcode",
    title: "生成二级渠道获客小程序码",
    resultTitle: "专用获客小程序码已生成",
    copyMessage: "小程序入口已复制",
    action: "child_customer_qrcode",
    channel: item,
    data: null,
    link: "",
  }
  errorText.value = ""
  successText.value = ""
  try {
    const data = await partnerHttp.get(`/partners/portal/subchannels/${item.id}/miniapp-qrcode`, { timeout: 30000 })
    childMiniappQr.value.data = data || null
  } catch (error) {
    errorText.value = String(error?.message || "加载二级渠道小程序码失败")
  } finally {
    childMiniappQr.value.loading = false
  }
}

function closeChildMiniappQr() {
  childMiniappQr.value = {
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
  }
}

async function openChildPortalLinkPanel(item) {
  if (!hasPortalSession.value) return
  errorText.value = ""
  successText.value = ""
  try {
    const data = await partnerHttp.post(`/partners/portal/subchannels/${item.id}/portal-link/refresh`, {}, { timeout: 30000 })
    const merged = { ...item, ...data }
    const link = String(merged?.portal_login_link || merged?.portal_link || "").trim()
    if (!link) {
      errorText.value = "生成二级渠道登录入口失败"
      return
    }
    openChildLinkPanel(item, {
      title: "生成二级渠道登录入口",
      resultTitle: "专用登录入口已生成",
      copyMessage: "二级渠道登录入口已复制",
      action: "child_portal_link",
      link,
    })
    successText.value = `${item.name || "该二级渠道"} 的登录入口已生成`
    await loadPortalData()
  } catch (error) {
    errorText.value = String(error?.message || "生成二级渠道登录入口失败")
  }
}

async function openChildCustomerLinkPanel(item) {
  const link = String(item?.order_link || "").trim()
  if (!link) {
    errorText.value = "生成二级渠道网页获客链接失败"
    successText.value = ""
    return
  }
  openChildLinkPanel(item, {
    title: "生成二级渠道网页获客链接",
    resultTitle: "专用网页获客链接已生成",
    copyMessage: "二级渠道网页获客链接已复制",
    action: "child_customer_link",
    link,
  })
  errorText.value = ""
  successText.value = `${item.name || "该二级渠道"} 的网页获客链接已生成`
}

async function openOwnPortalLinkPanel() {
  const link = String(overview.value?.portal_login_link || overview.value?.portal_link || "").trim()
  if (!link) {
    errorText.value = "生成二级渠道登录入口失败"
    successText.value = ""
    return
  }
  openChildLinkPanel(overview.value, {
    title: "生成二级渠道登录入口",
    resultTitle: "专用登录入口已生成",
    copyMessage: "二级渠道登录入口已复制",
    action: "own_portal_link",
    link,
  })
  errorText.value = ""
  successText.value = "二级渠道登录入口已生成"
}

async function openOwnCustomerLinkPanel() {
  const link = String(overview.value?.order_link || "").trim()
  if (!link) {
    errorText.value = "生成二级渠道网页获客链接失败"
    successText.value = ""
    return
  }
  openChildLinkPanel(overview.value, {
    title: "生成二级渠道网页获客链接",
    resultTitle: "专用网页获客链接已生成",
    copyMessage: "二级渠道网页获客链接已复制",
    action: "own_customer_link",
    link,
  })
  errorText.value = ""
  successText.value = "二级渠道网页获客链接已生成"
}

async function openOwnCustomerQrPanel() {
  if (!overview.value || !hasPortalSession.value) return
  childMiniappQr.value = {
    visible: true,
    loading: true,
    kind: "qrcode",
    title: "生成二级渠道获客小程序码",
    resultTitle: "专用获客小程序码已生成",
    copyMessage: "小程序入口已复制",
    action: "own_customer_qrcode",
    channel: overview.value,
    data: null,
    link: "",
  }
  errorText.value = ""
  successText.value = ""
  try {
    const data = await partnerHttp.get("/partners/portal/miniapp-qrcode", { timeout: 30000 })
    childMiniappQr.value.data = data || null
    successText.value = "二级渠道获客小程序码已生成"
  } catch (error) {
    errorText.value = String(error?.message || "生成二级渠道获客小程序码失败")
    closeChildMiniappQr()
  } finally {
    childMiniappQr.value.loading = false
  }
}

async function refreshChildMaterialPanel() {
  const target = childMiniappQr.value.channel
  if (!target) return
  if (childMiniappQr.value.action === "child_portal_link") {
    await openChildPortalLinkPanel(target)
    return
  }
  if (childMiniappQr.value.action === "child_customer_link") {
    await openChildCustomerLinkPanel(target)
    return
  }
  if (childMiniappQr.value.action === "own_portal_link") {
    await openOwnPortalLinkPanel()
    return
  }
  if (childMiniappQr.value.action === "own_customer_link") {
    await openOwnCustomerLinkPanel()
    return
  }
  if (childMiniappQr.value.action === "child_customer_qrcode") {
    await openChildMiniappQr(target)
    return
  }
  if (childMiniappQr.value.action === "own_customer_qrcode") {
    await openOwnCustomerQrPanel()
  }
}

function formatFenToCny(value) {
  const amount = Number(value || 0) / 100
  return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : "¥0.00"
}

function formatRate(value) {
  if (value === null || value === undefined || value === "") return "-"
  const bp = Number(value)
  return Number.isFinite(bp) ? `${(bp / 100).toFixed(2)}%` : "-"
}

function formatDateTime(value) {
  return formatBeijingDateTime(value)
}

function formatEntryType(value) {
  const normalized = String(value || "").toLowerCase()
  if (normalized === "accrual") return "入账"
  if (normalized === "reversal") return "冲正"
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
    active: "启用",
    disabled: "停用",
  }
  return statusMap[normalized] || normalized || "-"
}

async function logoutPortal() {
  try {
    await partnerHttp.post("/partners/portal/auth/logout")
  } catch {}
  clearPartnerSession()
  partnerInfo.value = null
  overview.value = null
  await router.replace("/app/partner/login")
}

function goLogin() {
  router.push("/app/partner/login")
}

function applyListFilter(type) {
  if (type === "orders") {
    ordersPagination.value.page = 1
    loadOrders()
    return
  }
  if (type === "ledger") {
    ledgerPagination.value.page = 1
    loadLedger()
    return
  }
  customersPagination.value.page = 1
  loadCustomers()
}

function exportRows(type) {
  let rows = []
  let headers = []
  if (type === "orders") {
    headers = ["订单号", "用户ID", "收益渠道", "来源渠道", "套餐", "订单金额", "返佣比例", "净返佣", "状态", "创建时间"]
    rows = orders.value.map((item) => [item.order_no, item.user_id, item.channel_name || item.channel_code || "", item.source_channel_code || "", item.package_name || "", formatFenToCny(item.amount_fen), formatRate(item.rebate_rate_bp), formatFenToCny(item.net_rebate_fen), formatStatus(item.order_status), formatDateTime(item.created_at)])
  } else if (type === "ledger") {
    headers = ["流水ID", "订单号", "收益渠道", "来源渠道", "类型", "返佣比例", "返佣金额", "状态", "结算月", "创建时间"]
    rows = ledger.value.map((item) => [item.id, item.order_no || "", item.channel_name || item.channel_code || "", item.source_channel_code || "", formatEntryType(item.entry_type), formatRate(item.rebate_rate_bp), formatFenToCny(item.rebate_amount_fen), formatStatus(item.status), item.statement_month || "", formatDateTime(item.created_at)])
  } else {
    headers = ["用户ID", "昵称", "手机号", "归属渠道", "归属来源", "历史订单", "锁定时间"]
    rows = customers.value.map((item) => [item.user_id, item.nickname, item.phone_masked || "", item.channel_name || item.channel_code || "", item.bind_source || "", Number(item.order_count || 0), formatDateTime(item.locked_at || item.updated_at || item.created_at)])
  }
  const csv = [headers, ...rows].map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll("\"", "\"\"")}"`).join(",")).join("\n")
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
  triggerBlobDownload(blob, `partner_${type}_${new Date().toISOString().slice(0, 10)}.csv`)
}
</script>

<style scoped>
.partner-page {
  min-height: 100vh;
  padding: 22px;
  background:
    radial-gradient(circle at 10% 14%, rgba(30, 91, 223, 0.14), transparent 30%),
    radial-gradient(circle at 90% 18%, rgba(93, 145, 255, 0.12), transparent 24%),
    linear-gradient(180deg, #eef5ff 0%, #f7faff 30%, #ffffff 60%, #ffffff 100%);
}

.partner-shell {
  width: min(1360px, 100%);
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.partner-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
  border-radius: 24px;
  background: linear-gradient(135deg, #153d80 0%, #1e5bdf 56%, #4b89fb 100%);
  color: #fff;
  box-shadow: 0 24px 44px rgba(13, 42, 88, 0.22);
}

.partner-head__eyebrow {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.88;
}

.partner-head h1 {
  margin: 8px 0 6px;
  font-size: 34px;
  line-height: 1.1;
}

.partner-head p:last-child {
  margin: 0;
  color: rgba(255, 255, 255, 0.82);
}

.partner-head__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.partner-message {
  margin: 0;
  padding: 12px 14px;
  border-radius: 12px;
  font-size: 13px;
}

.partner-message--danger {
  background: #ffe9e9;
  color: #b33636;
}

.partner-message--success {
  background: #eaf8ef;
  color: #126942;
}

.partner-stat-grid,
.partner-workbench,
.partner-chart-grid {
  display: grid;
  gap: 16px;
}

.partner-stat-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.partner-workbench,
.partner-chart-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.partner-stat-card,
.partner-panel {
  border: 1px solid rgba(214, 225, 242, 0.96);
  border-radius: 22px;
  background: #fff;
  padding: 18px 20px;
  box-shadow: 0 14px 28px rgba(20, 64, 146, 0.08);
}

.partner-stat-card {
  display: grid;
  gap: 8px;
}

.partner-stat-card--primary {
  border-color: rgba(82, 131, 255, 0.45);
  background: linear-gradient(135deg, #1f56cc 0%, #2f77ff 100%);
  color: #fff;
}

.partner-stat-card span {
  color: #6d7f99;
  font-size: 13px;
}

.partner-stat-card--primary span,
.partner-stat-card--primary p {
  color: rgba(255, 255, 255, 0.84);
}

.partner-stat-card strong {
  color: #163862;
  font-size: 30px;
  line-height: 1;
}

.partner-stat-card--primary strong {
  color: #fff;
}

.partner-stat-card p {
  margin: 0;
  color: #7c8ea8;
  font-size: 12px;
}

.partner-section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.partner-kicker {
  color: #1d5ce0;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.partner-section-head h2 {
  margin: 4px 0 0;
  color: #17365f;
  font-size: 20px;
}

.partner-head-note {
  color: #7991b2;
  font-size: 12px;
}

.partner-action-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 14px;
}

.partner-qrcode-panel {
  margin-top: 14px;
  display: grid;
  gap: 18px;
  grid-template-columns: 280px minmax(0, 1fr);
  align-items: start;
}

.partner-qrcode-card {
  border: 1px solid #dbe7fb;
  border-radius: 18px;
  background: #f8fbff;
  padding: 16px;
}

.partner-qrcode-image {
  display: block;
  width: 100%;
  border-radius: 14px;
  background: #ffffff;
}

.partner-action-card {
  border: 1px solid #dbe7fb;
  border-radius: 16px;
  background: #f8fbff;
  padding: 14px 16px;
  text-align: left;
  display: grid;
  gap: 6px;
}

.partner-action-card--primary {
  background: linear-gradient(135deg, #1e5bdf 0%, #4586ff 100%);
  border-color: transparent;
  color: #fff;
}

.partner-action-card strong {
  font-size: 15px;
}

.partner-action-card span {
  font-size: 12px;
  color: inherit;
  opacity: 0.85;
}

.partner-alert-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.partner-alert-item {
  border: 1px solid #deebff;
  border-radius: 16px;
  background: #f7fbff;
  padding: 14px 16px;
}

.partner-alert-item strong {
  display: block;
  color: #17365f;
  font-size: 14px;
}

.partner-alert-item p {
  margin: 6px 0 0;
  color: #6f819b;
  font-size: 12px;
  line-height: 1.6;
}

.partner-chart {
  width: 100%;
  height: 280px;
  margin-top: 14px;
}

.partner-table-wrap {
  margin-top: 14px;
  overflow-x: auto;
}

.partner-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
}

.partner-table th,
.partner-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #e6eef9;
  text-align: left;
  vertical-align: top;
}

.partner-table th {
  color: #5f7697;
  font-size: 12px;
  font-weight: 600;
}

.partner-stack {
  display: grid;
  gap: 6px;
}

.partner-stack strong {
  color: #17365f;
}

.partner-stack span {
  color: #6d809d;
  font-size: 12px;
}

.partner-pill {
  display: inline-flex;
  width: fit-content;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
}

.partner-pill--success {
  background: #e8f7ef;
  color: #127246;
}

.partner-pill--warning {
  background: #fff4dd;
  color: #9a6a00;
}

.partner-pill--danger {
  background: #ffe7e7;
  color: #b33636;
}

.partner-pill--muted {
  background: #eef3fb;
  color: #60738f;
}

.partner-row-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.partner-row-actions--top {
  margin-top: 14px;
}

.partner-button {
  min-height: 40px;
  border: none;
  border-radius: 12px;
  padding: 0 14px;
  background: #1e5bdf;
  color: #fff;
}

.partner-button--ghost {
  background: #eef4ff;
  color: #1d4ea1;
}

.partner-detail-box {
  margin-top: 14px;
  border: 1px dashed #d6e2f8;
  border-radius: 16px;
  padding: 14px;
  background: #fbfdff;
}

.partner-detail-box summary,
.partner-detail-summary {
  cursor: pointer;
  color: #1d4ea1;
  font-weight: 600;
}

.partner-form-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 14px;
}

.partner-field {
  display: grid;
  gap: 6px;
}

.partner-field span {
  color: #627694;
  font-size: 13px;
}

.partner-field input,
.partner-field select {
  width: 100%;
  min-height: 42px;
  border: 1px solid #d7e2f4;
  border-radius: 12px;
  padding: 0 12px;
  color: #1a365e;
  background: #fff;
}

.partner-field--wide {
  grid-column: 1 / -1;
}

.partner-material-list {
  display: grid;
  gap: 10px;
}

.partner-material-list--own {
  margin-top: 14px;
}

.partner-material-card {
  display: grid;
  gap: 8px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid #dbe7fb;
  background: #f8fbff;
}

.partner-material-card strong {
  color: #17365f;
  font-size: 13px;
}

.partner-material-card span {
  color: #5f7593;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}

.partner-inline-section + .partner-inline-section {
  margin-top: 22px;
}

.partner-filter-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.partner-filter-row--wide {
  align-items: flex-end;
}

.partner-empty {
  padding: 20px 0;
  text-align: center;
  color: #7b8da8;
}

.partner-panel--center {
  text-align: center;
}

@media (max-width: 1100px) {
  .partner-stat-grid,
  .partner-workbench,
  .partner-chart-grid,
  .partner-qrcode-panel {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .partner-page {
    padding: 14px;
  }

  .partner-head,
  .partner-section-head,
  .partner-filter-row {
    align-items: stretch;
  }

  .partner-action-grid,
  .partner-form-grid {
    grid-template-columns: 1fr;
  }

  .partner-chart {
    height: 240px;
  }

  .partner-head h1 {
    font-size: 28px;
  }
}
</style>
