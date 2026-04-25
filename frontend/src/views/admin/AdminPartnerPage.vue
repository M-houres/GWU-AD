<template>
  <AdminShell title="渠道返佣" subtitle="先建一级渠道，再把登录和推广信息发给对应负责人。">
    <section class="admin-partner-page">
      <section class="admin-partner-summary">
        <article class="admin-partner-summary-card admin-partner-summary-card--primary">
          <span>一级渠道</span>
          <strong>{{ rootChannelCount }}</strong>
          <p>平台侧只建一级，避免越级代建导致客户归属混乱。</p>
        </article>
        <article class="admin-partner-summary-card">
          <span>全部渠道</span>
          <strong>{{ channels.length }}</strong>
          <p>一级发展二级，二级发展三级，每级都能自己带客户。</p>
        </article>
        <article class="admin-partner-summary-card">
          <span>待审核提现</span>
          <strong>{{ pendingWithdrawalCount }}</strong>
          <p>待处理的渠道提现申请会集中在当前后台处理。</p>
        </article>
        <article class="admin-partner-summary-card">
          <span>待结算返佣</span>
          <strong>{{ totalPendingRebateText }}</strong>
          <p>从专属链接进入的客户会锁定归属到对应渠道。</p>
        </article>
      </section>

      <section class="admin-partner-panel admin-partner-toolbar-panel">
        <div class="admin-partner-toolbar">
          <div class="admin-partner-toolbar__stats">
            <span class="admin-partner-mini-chip">一级渠道 {{ rootChannelCount }}</span>
            <span class="admin-partner-mini-chip">全部渠道 {{ channels.length }}</span>
            <span class="admin-partner-mini-chip">待审核提现 {{ pendingWithdrawalCount }}</span>
            <span class="admin-partner-mini-chip">待结算返佣 {{ totalPendingRebateText }}</span>
          </div>
          <div class="admin-partner-toolbar__filters">
            <input v-model.trim="filters.keyword" class="admin-partner-input" placeholder="搜索渠道名称 / 编码" />
            <select v-model="filters.status" class="admin-partner-input">
              <option value="">全部状态</option>
              <option value="active">启用</option>
              <option value="disabled">停用</option>
            </select>
            <button class="scholar-button scholar-button--secondary" @click="loadChannels">筛选</button>
            <button class="scholar-button scholar-button--secondary" @click="loadAll">刷新</button>
          </div>
        </div>
      </section>

      <div class="admin-partner-grid">
        <section class="admin-partner-panel">
          <div class="admin-partner-panel__head">
            <div>
              <div class="admin-partner-panel__eyebrow">一级渠道</div>
              <h3>{{ editingChannelId ? "编辑渠道" : "新建一级渠道" }}</h3>
            </div>
            <button class="scholar-button scholar-button--secondary" :disabled="submitting" @click="resetChannelForm">重置</button>
          </div>

          <div class="admin-partner-form">
            <label>
              <span>渠道名称</span>
              <input v-model.trim="channelForm.name" class="admin-partner-input" placeholder="例如：华东高校一级渠道" />
            </label>
            <label>
              <span>渠道编码</span>
              <input v-model.trim="channelForm.channel_code" class="admin-partner-input" placeholder="可留空自动生成" :disabled="Boolean(editingChannelId)" />
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
                placeholder="例如 18 表示 18%"
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
              {{ submitting ? "提交中..." : editingChannelId ? "保存渠道" : "创建一级渠道" }}
            </button>
          </div>
          <p v-if="hintText" class="admin-partner-hint admin-partner-hint--success">{{ hintText }}</p>
          <p v-if="errorText" class="admin-partner-hint admin-partner-hint--danger">{{ errorText }}</p>
          <p v-if="!canManage" class="admin-partner-hint">当前账号仅有查看权限，不能修改渠道和月结。</p>
        </section>

        <details class="admin-partner-panel admin-partner-fold-card">
          <summary class="admin-partner-fold-card__summary">
            <div>
              <div class="admin-partner-panel__eyebrow">月结</div>
              <h3>生成月结</h3>
            </div>
          </summary>
          <section>
          <div class="admin-partner-panel__head">
            <div>
              <div class="admin-partner-panel__eyebrow">结算动作</div>
              <h3>按月生成结算单</h3>
            </div>
          </div>

          <div class="admin-partner-form admin-partner-form--statement">
            <label>
              <span>月结渠道</span>
              <select v-model="statementForm.channel_id" class="admin-partner-input">
                <option value="">请选择渠道</option>
                <option v-for="item in channels" :key="item.id" :value="String(item.id)">
                  L{{ item.level }} · {{ item.name }}（{{ item.channel_code }}）
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
        </details>
      </div>

      <section class="admin-partner-panel">
        <div class="admin-partner-panel__head">
          <div>
            <div class="admin-partner-panel__eyebrow">渠道列表</div>
            <h3>渠道列表</h3>
          </div>
        </div>

        <div class="admin-partner-tree-wrap">
          <div class="admin-partner-tree-head">
            <strong>渠道树总览</strong>
            <span>点击任意节点，可直接查看该渠道的客户归属和团队数据。</span>
          </div>
          <div v-if="channelTree.length" class="admin-partner-tree-grid">
            <PartnerChannelTreeNode
              v-for="item in channelTree"
              :key="item.id"
              :node="item"
              :clickable="true"
              @select="selectTreeChannel"
            />
          </div>
          <div v-else class="admin-partner-empty">暂无渠道树数据</div>
        </div>

        <div class="admin-partner-ops-grid">
          <article class="admin-partner-ops-card">
            <strong>平台建一级</strong>
            <span>平台侧只新建一级渠道，避免越级代建影响归属关系。</span>
          </article>
          <article class="admin-partner-ops-card">
            <strong>渠道带下级</strong>
            <span>一级带二级，二级带三级，每一级都可以自己发展客户。</span>
          </article>
          <article class="admin-partner-ops-card">
            <strong>客户归属锁定</strong>
            <span>客户从哪个专属链接进入，就归属到对应渠道，向上只算返佣不改归属。</span>
          </article>
        </div>

        <div class="admin-partner-table-wrap">
          <table class="admin-partner-table">
            <thead>
              <tr>
                <th>渠道</th>
                <th>商品单独返佣</th>
                <th>返佣 / 核心数据</th>
                <th>登录 / 分发</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in channels" :key="item.id">
                <td>
                  <div class="admin-partner-channel" :style="{ paddingLeft: `${Math.max(Number(item.level || 1) - 1, 0) * 16}px` }">
                    <strong>{{ mapLevel(item.level) }} · {{ item.name }}</strong>
                    <span>{{ item.channel_code }}</span>
                    <span>上级 {{ item.parent_channel_name || "平台直营" }} · {{ item.status === "active" ? "启用中" : "已停用" }}</span>
                    <span>{{ item.contact_name || "-" }} / {{ item.contact_phone || "-" }}</span>
                  </div>
                </td>
                <td>
                  <div class="admin-partner-stack">
                    <span>默认 {{ Number(item.default_rebate_rate_pct || 0).toFixed(2) }}%</span>
                    <button class="admin-partner-link-btn" @click="openPolicyPanel(item)">配置商品返佣</button>
                  </div>
                </td>
                <td>
                  <div class="admin-partner-stack">
                    <span>下级 {{ Number(item.child_count || 0) }} 个</span>
                    <span>客户 {{ Number(item.user_count || 0) }} 个</span>
                    <span>待结算 {{ formatFenToCny(item.pending_rebate_fen) }}</span>
                  </div>
                </td>
                <td>
                  <div class="admin-partner-links admin-partner-links--stacked">
                    <span>门户链接 {{ item.portal_link || item.portal_login_link || "-" }}</span>
                    <span>渠道编码 {{ item.channel_code || "-" }}</span>
                    <span>最近登录 {{ formatTime(item.portal_last_login_at) }}</span>
                    <button class="admin-partner-link-btn" @click="copyChannelBundle(item)">刷新并复制渠道门户信息</button>
                    <button class="admin-partner-link-btn" @click="copyChannelCustomerShare(item)">复制客户分发文案</button>
                    <button class="admin-partner-link-btn" @click="copyText(item.order_link, '已复制推广链接')">只复制推广链接</button>
                    <button class="admin-partner-link-btn" @click="copyText(item.portal_link || item.portal_login_link, '已复制渠道门户链接')">只复制门户链接</button>
                    <button class="admin-partner-link-btn" @click="copyText(item.miniapp_order_path, '已复制小程序推广路径')">复制小程序推广路径</button>
                  </div>
                </td>
                <td>
                  <div class="admin-partner-row-actions">
                    <button class="scholar-button scholar-button--compact" @click="startEditChannel(item)">编辑</button>
                    <button
                      class="scholar-button scholar-button--secondary scholar-button--compact"
                      :disabled="!canManage"
                      @click="resetPortalPassword(item)"
                    >
                      刷新门户链接
                    </button>
                    <button class="scholar-button scholar-button--secondary scholar-button--compact" @click="openInsightPanel(item)">
                      查看归属
                    </button>
                    <button
                      class="scholar-button scholar-button--secondary scholar-button--compact admin-partner-danger-btn"
                      :disabled="!canManage"
                      @click="deleteChannel(item)"
                    >
                      删除
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="channels.length === 0">
                <td colspan="5" class="admin-partner-empty">暂无渠道</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="policyPanel.visible" class="admin-partner-panel">
        <div class="admin-partner-panel__head">
          <div>
            <div class="admin-partner-panel__eyebrow">商品单独返佣</div>
            <h3>{{ policyPanel.channel?.name || "-" }} 的返佣设置</h3>
          </div>
          <button class="scholar-button scholar-button--secondary" @click="closePolicyPanel">关闭</button>
        </div>

        <div class="admin-partner-policy-summary">
          <article class="admin-partner-policy-card">
            <span>默认返佣</span>
            <strong>{{ Number(policyPanel.channel?.default_rebate_rate_pct || 0).toFixed(2) }}%</strong>
            <p>未单独配置的套餐，默认走这个比例。</p>
          </article>
          <article class="admin-partner-policy-card">
            <span>已配置套餐</span>
            <strong>{{ policyPanel.items.length }}</strong>
            <p>这里显示当前渠道已单独设置返佣的套餐数。</p>
          </article>
        </div>

        <div v-if="packageOptions.length" class="admin-partner-policy-tags">
          <button
            v-for="item in packageOptions"
            :key="item.name"
            type="button"
            class="admin-partner-policy-tag"
            @click="applyPackagePreset(item)"
          >
            {{ item.name }}
          </button>
        </div>

        <div class="admin-partner-form admin-partner-form--policy">
          <label>
            <span>套餐名</span>
            <select v-model="policyForm.package_name" class="admin-partner-input">
              <option value="">按默认返佣走</option>
              <option v-for="item in packageOptions" :key="item.name" :value="item.name">
                {{ item.name }}{{ item.priceLabel ? ` · ${item.priceLabel}` : "" }}{{ item.creditsLabel ? ` · ${item.creditsLabel}` : "" }}
              </option>
            </select>
          </label>
          <label>
            <span>返佣比例（%）</span>
            <input v-model.number="policyForm.rebate_rate_pct" type="number" min="0" max="100" step="0.01" class="admin-partner-input" />
          </label>
          <label>
            <span>状态</span>
            <select v-model="policyForm.is_active" class="admin-partner-input">
              <option :value="true">启用</option>
              <option :value="false">停用</option>
            </select>
          </label>
        </div>

        <div class="admin-partner-actions">
          <button class="scholar-button" :disabled="policySubmitting || !canManage" @click="savePolicy">
            {{ policySubmitting ? "保存中..." : "保存策略" }}
          </button>
          <button class="scholar-button scholar-button--secondary" :disabled="policySubmitting" @click="resetPolicyForm">
            重置
          </button>
        </div>

        <div class="admin-partner-table-wrap">
          <table class="admin-partner-table">
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
                <td>
                  <button class="admin-partner-link-btn" @click="editPolicyItem(item)">套用到表单</button>
                </td>
              </tr>
              <tr v-if="policyPanel.items.length === 0">
                <td colspan="5" class="admin-partner-empty">暂无商品返佣设置</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="insightPanel.visible" class="admin-partner-panel">
        <div class="admin-partner-panel__head">
          <div>
            <div class="admin-partner-panel__eyebrow">客户归属</div>
            <h3>{{ insightPanel.channel?.name || "-" }} 的归属情况</h3>
          </div>
          <div class="admin-partner-actions admin-partner-actions--tight">
            <select v-model="insightPanel.scope" class="admin-partner-input" @change="loadInsightPanel">
              <option value="self">我的客户</option>
              <option value="team">团队客户</option>
              <option value="subtree">全部客户</option>
            </select>
            <button class="scholar-button scholar-button--secondary" @click="exportInsightCustomers">导出当前结果</button>
            <button class="scholar-button scholar-button--secondary" @click="closeInsightPanel">关闭</button>
          </div>
        </div>

        <div class="admin-partner-insight-banner">
          <div>
            <strong>{{ insightPanel.channel?.name || "-" }}</strong>
            <span>{{ mapLevel(insightPanel.channel?.level) }} · {{ insightScopeText }}</span>
          </div>
          <div class="admin-partner-insight-banner__meta">
            <span>默认返佣 {{ Number(insightPanel.channel?.default_rebate_rate_pct || 0).toFixed(2) }}%</span>
            <span>直属下级 {{ Number(insightPanel.channel?.child_count || 0) }}</span>
            <span>我的客户 {{ Number(insightPanel.channel?.user_count || 0) }}</span>
          </div>
        </div>

        <div class="admin-partner-insight-grid">
          <article class="admin-partner-insight-card">
            <span>渠道数</span>
            <strong>{{ Number(insightPanel.summary?.channel_count || 0) }}</strong>
          </article>
          <article class="admin-partner-insight-card">
            <span>客户数</span>
            <strong>{{ Number(insightPanel.summary?.user_count || 0) }}</strong>
          </article>
          <article class="admin-partner-insight-card">
            <span>订单数</span>
            <strong>{{ Number(insightPanel.summary?.order_count || 0) }}</strong>
          </article>
          <article class="admin-partner-insight-card">
            <span>待结算</span>
            <strong>{{ formatFenToCny(insightPanel.summary?.pending_rebate_fen || 0) }}</strong>
          </article>
          <article class="admin-partner-insight-card">
            <span>已结算</span>
            <strong>{{ formatFenToCny(insightPanel.summary?.settled_rebate_fen || 0) }}</strong>
          </article>
        </div>

        <div class="admin-partner-insight-tip">
          <span>{{ insightScopeDescription }}</span>
        </div>

        <div class="admin-partner-form admin-partner-form--insight">
          <label>
            <span>关键词</span>
            <input v-model.trim="insightPanel.keyword" class="admin-partner-input" placeholder="昵称 / 渠道名 / 渠道编码" />
          </label>
          <label>
            <span>开始日期</span>
            <input v-model="insightPanel.created_from" type="date" class="admin-partner-input" />
          </label>
          <label>
            <span>结束日期</span>
            <input v-model="insightPanel.created_to" type="date" class="admin-partner-input" />
          </label>
          <label>
            <span>&nbsp;</span>
            <button class="scholar-button scholar-button--secondary" @click="applyInsightFilter">筛选客户</button>
          </label>
        </div>

        <div class="admin-partner-table-wrap">
          <table class="admin-partner-table">
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
                <td colspan="7" class="admin-partner-empty">暂无客户归属数据</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="admin-partner-actions admin-partner-actions--tight admin-partner-pagination">
          <button class="scholar-button scholar-button--secondary" :disabled="insightPanel.pagination.page <= 1" @click="changeInsightPage(-1)">上一页</button>
          <span>第 {{ insightPanel.pagination.page }} / {{ Math.max(insightPanel.pagination.pages, 1) }} 页，共 {{ insightPanel.pagination.total }} 条</span>
          <button
            class="scholar-button scholar-button--secondary"
            :disabled="insightPanel.pagination.page >= Math.max(insightPanel.pagination.pages, 1)"
            @click="changeInsightPage(1)"
          >
            下一页
          </button>
        </div>
      </section>

      <details class="admin-partner-panel admin-partner-fold-card">
        <summary class="admin-partner-fold-card__summary">
          <div>
            <div class="admin-partner-panel__eyebrow">更多明细</div>
            <h3>返佣流水与提现审核</h3>
          </div>
        </summary>
        <section>
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
                <td colspan="9" class="admin-partner-empty">暂无返佣流水</td>
              </tr>
            </tbody>
          </table>
        </div>
        </section>

        <section>
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
      </details>
    </section>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import PartnerChannelTreeNode from "../../components/partner/PartnerChannelTreeNode.vue"
import { triggerBlobDownload } from "../../lib/download"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

const channels = ref([])
const channelTree = ref([])
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

const canManage = computed(() => adminHasPermission("configs:manage"))
const rootChannelCount = computed(() => channels.value.filter((item) => Number(item.level || 1) === 1).length)
const pendingWithdrawalCount = computed(() => withdrawalRows.value.filter((item) => String(item.status || "") === "pending").length)
const totalPendingRebateText = computed(() =>
  formatFenToCny(channels.value.reduce((sum, item) => sum + Number(item.pending_rebate_fen || 0), 0))
)
const insightScopeText = computed(() => {
  const scope = String(insightPanel.scope || "subtree")
  if (scope === "self") return "当前查看我的客户"
  if (scope === "team") return "当前查看团队客户"
  return "当前查看全部客户"
})
const insightScopeDescription = computed(() => {
  const scope = String(insightPanel.scope || "subtree")
  if (scope === "self") return "只看当前渠道自己直接归属的客户。"
  if (scope === "team") return "只看下级团队带来的客户，不含当前渠道自己。"
  return "合并查看当前渠道自己和下级团队带来的全部客户。"
})

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

const policyForm = reactive({
  package_name: "",
  rebate_rate_pct: 0,
  is_active: true,
})

onMounted(loadAll)

async function loadAll() {
  await Promise.all([loadChannels(), loadChannelTree(), loadLedger(), loadWithdrawals(), loadPackageOptions()])
}

async function loadPackageOptions() {
  try {
    const data = await adminHttp.get("/billing/packages")
    const items = Array.isArray(data?.items) ? data.items : []
    packageOptions.value = items.map((item) => ({
      name: String(item?.name || "").trim(),
      priceLabel: Number(item?.amount_cny || item?.price || 0) > 0 ? `¥${Number(item.amount_cny || item.price).toFixed(2)}` : "",
      creditsLabel: Number(item?.credits || item?.processable_chars || 0) > 0 ? `${Number(item.credits || item.processable_chars)}点` : "",
    })).filter((item) => item.name)
  } catch {}
}

async function loadChannels() {
  const data = await adminHttp.get("/partners/admin/channels", {
    params: { page: 1, page_size: 100, keyword: filters.keyword, status: filters.status },
  })
  channels.value = Array.isArray(data?.items) ? data.items : []
}

async function loadChannelTree() {
  const data = await adminHttp.get("/partners/admin/channels/tree")
  channelTree.value = Array.isArray(data?.items) ? data.items : []
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
      hintText.value = "渠道已更新"
    } else {
      const data = await adminHttp.post("/partners/admin/channels", payload)
      const bundle = buildChannelBundle(data || payload)
      hintText.value = bundle ? "一级渠道已创建，整段分发信息已复制" : "一级渠道已创建"
      if (bundle) {
        await copyText(bundle, "一级渠道分发信息已复制")
      }
    }
    resetChannelForm()
    await Promise.all([loadChannels(), loadChannelTree(), loadLedger(), loadWithdrawals()])
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
    await Promise.all([loadLedger(), loadChannels(), loadChannelTree(), loadWithdrawals()])
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
    await Promise.all([loadWithdrawals(), loadChannels(), loadChannelTree()])
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
    await Promise.all([loadWithdrawals(), loadChannels(), loadChannelTree()])
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
  const confirmed = window.confirm(`确认刷新 ${item.name || item.channel_code || "该渠道"} 的门户链接吗？刷新后旧链接将失效。`)
  if (!confirmed) return
  hintText.value = ""
  errorText.value = ""
  try {
    const data = await adminHttp.post(`/partners/admin/channels/${item.id}/portal-link/refresh`)
    const bundle = buildChannelBundle({ ...item, ...data })
    if (bundle) {
      await copyText(bundle, "渠道门户信息已复制")
    }
    hintText.value = "渠道门户链接已刷新并复制"
    await Promise.all([loadChannels(), loadChannelTree()])
  } catch (error) {
    errorText.value = String(error?.message || "刷新门户链接失败")
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
    await Promise.all([loadChannels(), loadChannelTree(), loadLedger(), loadWithdrawals()])
  } catch (error) {
    errorText.value = String(error?.message || "删除渠道失败")
  }
}

function buildChannelBundle(item) {
  const name = String(item?.name || "").trim()
  const portalLink = String(item?.portal_link || item?.portal_login_link || "").trim()
  const orderLink = String(item?.order_link || "").trim()
  const miniappOrderPath = String(item?.miniapp_order_path || "").trim()
  const miniappPortalPath = String(item?.miniapp_portal_path || "").trim()
  const lines = [
    name ? `渠道名称：${name}` : "",
    portalLink ? `门户链接：${portalLink}` : "",
    orderLink ? `推广链接：${orderLink}` : "",
    miniappOrderPath ? `小程序推广路径：${miniappOrderPath}` : "",
    miniappPortalPath ? `小程序后台路径：${miniappPortalPath}` : "",
  ].filter(Boolean)
  return lines.join("\n")
}

function buildCustomerShareBundle(item) {
  const name = String(item?.name || "").trim() || "当前渠道"
  const orderLink = String(item?.order_link || "").trim()
  const miniappOrderPath = String(item?.miniapp_order_path || "").trim()
  const lines = [
    `你好，我是 ${name}。`,
    "这是我的专属办理入口，直接从这里进入即可：",
    orderLink ? `推广链接：${orderLink}` : "",
    miniappOrderPath ? `小程序路径：${miniappOrderPath}` : "",
  ].filter(Boolean)
  return lines.join("\n")
}

async function copyChannelBundle(item) {
  if (!canManage.value) return
  hintText.value = ""
  errorText.value = ""
  try {
    const data = await adminHttp.post(`/partners/admin/channels/${item.id}/portal-link/refresh`)
    const bundle = buildChannelBundle({ ...item, ...data })
    if (!bundle) {
      errorText.value = "暂无可复制的门户信息"
      return
    }
    await copyText(
      [`你好，这是 ${String(item?.name || item?.channel_code || "该渠道")} 的渠道门户信息：`, bundle].filter(Boolean).join("\n"),
      "渠道门户信息已复制"
    )
    hintText.value = `已刷新 ${item.name || item.channel_code || "该渠道"} 的门户链接并复制完整信息`
    await Promise.all([loadChannels(), loadChannelTree()])
  } catch (error) {
    errorText.value = String(error?.message || "复制门户信息失败")
  }
}

async function copyChannelCustomerShare(item) {
  const bundle = buildCustomerShareBundle(item)
  if (!bundle) {
    errorText.value = "暂无可复制的客户分发文案"
    hintText.value = ""
    return
  }
  await copyText(bundle, "客户分发文案已复制")
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
  insightPanel.scope = "subtree"
  insightPanel.keyword = ""
  insightPanel.created_from = ""
  insightPanel.created_to = ""
  insightPanel.pagination = { page: 1, page_size: 20, total: 0, pages: 0 }
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
  const csv = [headers, ...rows]
    .map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll("\"", "\"\"")}"`).join(","))
    .join("\n")
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
    await loadChannels()
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
  if (level === 3) return "三级渠道"
  return `L${level}`
}

async function selectTreeChannel(node) {
  if (!node?.id) return
  await openInsightPanel(node)
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
.admin-partner-page {
  display: grid;
  gap: 18px;
}

.admin-partner-summary {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.admin-partner-summary-card {
  border: 1px solid rgba(214, 225, 242, 0.96);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(247, 251, 255, 0.99) 100%);
  padding: 18px 19px;
  display: grid;
  gap: 8px;
  box-shadow: 0 14px 28px rgba(20, 64, 146, 0.08);
}

.admin-partner-summary-card--primary {
  border-color: rgba(112, 157, 245, 0.4);
  background:
    radial-gradient(circle at 100% 0%, rgba(255, 255, 255, 0.18), transparent 24%),
    linear-gradient(135deg, rgba(238, 244, 255, 0.98) 0%, rgba(255, 255, 255, 0.98) 100%);
}

.admin-partner-summary-card span {
  color: #6b7a86;
  font-size: 12px;
}

.admin-partner-summary-card strong {
  color: #17385f;
  font-size: 30px;
}

.admin-partner-summary-card p {
  margin: 0;
  color: #5d6c79;
  font-size: 13px;
  line-height: 1.6;
}

.admin-partner-grid {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr);
}

.admin-partner-panel {
  border: 1px solid rgba(214, 225, 242, 0.96);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(248, 251, 255, 0.99) 100%);
  padding: 20px;
  box-shadow: 0 14px 28px rgba(20, 64, 146, 0.08);
}

.admin-partner-toolbar-panel {
  padding-top: 18px;
  padding-bottom: 18px;
}

.admin-partner-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
}

.admin-partner-toolbar__stats,
.admin-partner-toolbar__filters {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.admin-partner-toolbar__filters {
  flex: 1;
  justify-content: flex-end;
}

.admin-partner-toolbar__filters > .admin-partner-input {
  flex: 1 1 180px;
}

.admin-partner-mini-chip {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(207, 221, 243, 0.96);
  background: linear-gradient(180deg, #f5f9ff 0%, #ffffff 100%);
  color: #1e4fae;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
}

.admin-partner-fold-card {
  padding: 0;
  overflow: hidden;
}

.admin-partner-fold-card > section {
  padding: 0 20px 20px;
}

.admin-partner-fold-card__summary {
  list-style: none;
  cursor: pointer;
  padding: 18px 20px;
}

.admin-partner-fold-card__summary::-webkit-details-marker {
  display: none;
}

.admin-partner-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.admin-partner-list-tip {
  max-width: 420px;
  color: #5d6c79;
  font-size: 12px;
  line-height: 1.6;
}

.admin-partner-panel__eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: #6b7a86;
}

.admin-partner-panel__head h3 {
  margin: 6px 0 0;
  font-size: 21px;
  color: #17385f;
}

.admin-partner-form {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.admin-partner-form--policy {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.admin-partner-form--statement {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.admin-partner-form--insight {
  grid-template-columns: minmax(220px, 1.2fr) repeat(2, minmax(160px, 0.9fr)) auto;
  margin-bottom: 16px;
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
  border: 1px solid #cfdae8;
  border-radius: 14px;
  padding: 0 14px;
  font-size: 14px;
  outline: none;
  background: #fff;
  transition:
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.admin-partner-input:focus {
  border-color: rgba(30, 91, 223, 0.58);
  box-shadow: 0 0 0 4px rgba(30, 91, 223, 0.08);
}

.admin-partner-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.admin-partner-actions--tight {
  margin-top: 0;
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

.admin-partner-note--compact {
  margin-bottom: 12px;
}

.admin-partner-note-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 14px;
}

.admin-partner-note-pill {
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: #eef4ff;
  color: #2256ba;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
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

.admin-partner-tree-wrap {
  display: grid;
  gap: 14px;
  margin-bottom: 16px;
  padding: 18px;
  border-radius: 20px;
  background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
  border: 1px solid rgba(217, 228, 245, 0.96);
}

.admin-partner-tree-head {
  display: grid;
  gap: 4px;
}

.admin-partner-tree-head strong {
  color: #14345f;
  font-size: 16px;
}

.admin-partner-tree-head span {
  color: #607290;
  font-size: 12px;
}

.admin-partner-tree-grid {
  display: grid;
  gap: 12px;
}

.admin-partner-ops-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 16px;
}

.admin-partner-policy-summary {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-bottom: 16px;
}

.admin-partner-policy-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid #d9e4f5;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.admin-partner-policy-card span {
  color: #607290;
  font-size: 12px;
}

.admin-partner-policy-card strong {
  color: #14345f;
  font-size: 24px;
}

.admin-partner-policy-card p {
  margin: 0;
  color: #607290;
  font-size: 12px;
  line-height: 1.7;
}

.admin-partner-policy-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.admin-partner-insight-banner {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid #d9e4f5;
  background: linear-gradient(135deg, #eef4ff 0%, #ffffff 100%);
  margin-bottom: 16px;
}

.admin-partner-insight-banner strong {
  display: block;
  color: #14345f;
  font-size: 20px;
}

.admin-partner-insight-banner span {
  display: block;
  margin-top: 4px;
  color: #607290;
  font-size: 12px;
}

.admin-partner-insight-banner__meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.admin-partner-insight-banner__meta span {
  margin-top: 0;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid #d8e4f5;
  color: #1e4fae;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  font-weight: 700;
}

.admin-partner-insight-tip {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 14px;
  background: #f7fbff;
  border: 1px solid #d9e4f5;
}

.admin-partner-insight-tip span {
  color: #607290;
  font-size: 12px;
  line-height: 1.7;
}

.admin-partner-policy-tag {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid #d8e4f5;
  background: #f4f8ff;
  color: #1e4fae;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.admin-partner-ops-card {
  display: grid;
  gap: 6px;
  padding: 15px 16px;
  border-radius: 18px;
  border: 1px solid rgba(217, 228, 245, 0.96);
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.admin-partner-ops-card strong {
  color: #14345f;
  font-size: 15px;
}

.admin-partner-ops-card span {
  color: #607290;
  font-size: 12px;
  line-height: 1.7;
}

.admin-partner-table {
  width: 100%;
  min-width: 920px;
  border-collapse: collapse;
  font-size: 13px;
}

.admin-partner-table th,
.admin-partner-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #e5edf7;
  text-align: left;
  vertical-align: top;
}

.admin-partner-table th {
  color: #647481;
  font-weight: 700;
  white-space: nowrap;
}

.admin-partner-channel,
.admin-partner-links,
.admin-partner-row-actions,
.admin-partner-stack {
  display: grid;
  gap: 4px;
}

.admin-partner-links--stacked span {
  color: #5d6c79;
}

.admin-partner-channel strong {
  color: #18242b;
}

.admin-partner-channel span,
.admin-partner-stack span {
  color: #5d6c79;
}

.admin-partner-links a,
.admin-partner-link-btn {
  width: fit-content;
  padding: 0;
  border: 0;
  background: transparent;
  color: #1f5fd6;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}

.admin-partner-danger-btn {
  color: #af3f33;
  border-color: #efc5bf;
  background: #fff6f4;
}

.admin-partner-empty {
  color: #667480;
}

.admin-partner-insight-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  margin-bottom: 16px;
}

.admin-partner-insight-card {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #dbe5f6;
  background: #f7fbff;
}

.admin-partner-insight-card span {
  display: block;
  color: #617391;
  font-size: 12px;
}

.admin-partner-insight-card strong {
  display: block;
  margin-top: 6px;
  color: #12345c;
  font-size: 24px;
}

.admin-partner-pagination {
  justify-content: flex-end;
  align-items: center;
}

@media (max-width: 1080px) {
  .admin-partner-summary,
  .admin-partner-grid {
    grid-template-columns: 1fr;
  }

  .admin-partner-insight-grid,
  .admin-partner-ops-grid,
  .admin-partner-policy-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .admin-partner-panel {
    padding: 16px;
  }

  .admin-partner-toolbar,
  .admin-partner-toolbar__stats,
  .admin-partner-toolbar__filters {
    align-items: stretch;
  }

  .admin-partner-toolbar__filters {
    justify-content: stretch;
  }

  .admin-partner-toolbar__filters > * {
    width: 100%;
  }

  .admin-partner-fold-card > section,
  .admin-partner-fold-card__summary {
    padding-left: 16px;
    padding-right: 16px;
  }

  .admin-partner-form,
  .admin-partner-form--policy,
  .admin-partner-form--insight {
    grid-template-columns: 1fr;
  }

  .admin-partner-summary,
  .admin-partner-insight-grid,
  .admin-partner-ops-grid,
  .admin-partner-policy-summary {
    grid-template-columns: 1fr;
  }

  .admin-partner-insight-banner,
  .admin-partner-insight-banner__meta {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
