<template>
  <div class="partner-portal-page">
    <section class="partner-portal-shell">
      <header class="partner-portal-head">
        <div>
          <p class="partner-portal-head__eyebrow">渠道返佣专属门户</p>
          <h1 class="partner-portal-head__title">渠道后台</h1>
          <p class="partner-portal-head__desc">看收益、发链接、带下级，常用操作都收在这里。</p>
        </div>
        <div class="partner-portal-head__actions">
          <button type="button" class="partner-portal-head__refresh" :disabled="loading" @click="loadPortalData">
            {{ loading ? "加载中..." : "刷新数据" }}
          </button>
          <button v-if="hasPortalSession" type="button" class="partner-btn--ghost" @click="logoutPortal">
            退出登录
          </button>
        </div>
      </header>

      <p v-if="errorText" class="partner-alert partner-alert--danger">{{ errorText }}</p>
      <p v-if="successText" class="partner-alert partner-alert--success">{{ successText }}</p>

      <section v-if="hasPortalSession && overview" class="partner-overview">
        <div class="partner-overview__meta">
          <span>渠道：{{ overview.channel_name || "-" }}</span>
          <span>当前层级：{{ formatLevel(overview.level) }}</span>
          <span>上级：{{ overview.parent_channel_name || "平台直营" }}</span>
        </div>
        <div class="partner-overview__cards">
          <article class="partner-card">
            <p>本月净返佣</p>
            <strong>{{ formatFenToCny(overview.month_rebate_fen) }}</strong>
          </article>
          <article class="partner-card">
            <p>待结算返佣</p>
            <strong>{{ formatFenToCny(overview.pending_rebate_fen) }}</strong>
          </article>
          <article class="partner-card">
            <p>可提现余额</p>
            <strong>{{ formatFenToCny(overview.withdrawable_fen) }}</strong>
          </article>
          <article class="partner-card">
            <p>我的客户</p>
            <strong>{{ Number(overview.user_count || 0) }}</strong>
          </article>
          <article class="partner-card">
            <p>团队客户</p>
            <strong>{{ Math.max(Number(overview.team_subtree?.user_count || 0) - Number(overview.user_count || 0), 0) }}</strong>
          </article>
          <article class="partner-card">
            <p>直属下级</p>
            <strong>{{ Number(overview.child_count || 0) }}</strong>
          </article>
        </div>
      </section>

      <section v-if="hasPortalSession && overview" class="partner-data-grid">
        <article class="partner-data-card partner-workbench-card">
          <header class="partner-data-card__head">
            <h2>先做这几步</h2>
            <span>把最常用的动作放前面，打开就能直接做</span>
          </header>
          <div class="partner-workbench-grid">
            <div class="partner-task-grid partner-task-grid--compact">
              <article class="partner-task-card">
                <strong>{{ taskItems[0].title }}</strong>
                <span>{{ taskItems[0].desc }}</span>
                <button type="button" class="partner-btn--ghost" @click="taskItems[0].action()">{{ taskItems[0].cta }}</button>
              </article>
              <article class="partner-task-card">
                <strong>{{ taskItems[1].title }}</strong>
                <span>{{ taskItems[1].desc }}</span>
                <button type="button" class="partner-btn--ghost" @click="taskItems[1].action()">{{ taskItems[1].cta }}</button>
              </article>
              <article class="partner-task-card">
                <strong>{{ taskItems[2].title }}</strong>
                <span>{{ taskItems[2].desc }}</span>
                <button type="button" class="partner-btn--ghost" @click="taskItems[2].action()">{{ taskItems[2].cta }}</button>
              </article>
            </div>
            <div class="partner-quick-grid partner-quick-grid--compact">
              <button type="button" class="partner-quick-action partner-quick-action--primary" @click="copyCustomerShareText">
                <strong>发给客户</strong>
                <span>只复制客户需要的推广信息</span>
              </button>
              <button type="button" class="partner-quick-action" @click="copyRecruitmentBundle">
                <strong>发给下级</strong>
                <span>复制招募文案、门户链接和推广信息</span>
              </button>
              <button type="button" class="partner-quick-action" @click="scrollToSection('child-form')">
                <strong>新建直属下级</strong>
                <span>快速跳到下级创建区</span>
              </button>
              <button type="button" class="partner-quick-action" @click="scrollToSection('withdraw-panel')">
                <strong>提交提现</strong>
                <span>直接跳到提现区</span>
              </button>
            </div>
          </div>
        </article>
        <article class='partner-data-card'>
          <header class="partner-data-card__head">
            <h2>分发与下级</h2>
            <span>先分发，再建直属下级，后面的动作都围绕这条主线。</span>
          </header>

          <div class="partner-share-strip">
            <article class="partner-share-card partner-share-card--primary">
              <div class="partner-share-card__head">
                <strong>我的分发信息</strong>
                <span>把客户分发和下级招募拆开，减少发错内容。</span>
              </div>
              <div class="partner-share-card__meta">
                <span>门户链接：{{ overview.portal_link || overview.portal_login_link || "-" }}</span>
                <span>推广链接：{{ overview.order_link || "-" }}</span>
              </div>
              <div class="partner-share-card__actions">
                <button type="button" @click="copyCustomerShareText">复制客户分发文案</button>
                <button type="button" class="partner-btn--ghost" @click="copyRecruitmentBundle">复制下级招募信息</button>
                <button type="button" class="partner-btn--ghost" @click="copyText(overview.order_link, '已复制推广链接')">只复制推广链接</button>
                <button type="button" class="partner-btn--ghost" @click="copyText(overview.portal_link || overview.portal_login_link, '已复制渠道门户链接')">只复制门户链接</button>
                <button type="button" class="partner-btn--ghost" @click="copyText(overview.miniapp_order_path, '已复制小程序推广路径')">复制小程序路径</button>
              </div>
            </article>
          </div>

          <div class="partner-manage-grid">
            <section class="partner-block">
              <div id="child-form" class="partner-section-anchor"></div>
              <div class="partner-block__head">
                <strong>{{ editingChildId ? "编辑直属下级" : "新建直属下级" }}</strong>
                <span v-if="overview.can_create_child">最多到三级，下级返佣比例不能高于你当前的比例。</span>
                <span v-else>你当前已经到三级，不能继续往下建，但还能维护已有下级。</span>
              </div>
              <div class="partner-child-summary">
                <article class="partner-child-summary__card">
                  <span>当前查看</span>
                  <strong>{{ selectedTreeNode?.name || overview.channel_name || "-" }}</strong>
                </article>
                <article class="partner-child-summary__card">
                  <span>直属下级数</span>
                  <strong>{{ subchannels.length }}</strong>
                </article>
                <article class="partner-child-summary__card">
                  <span>当前默认返佣</span>
                  <strong>{{ formatRate(overview.default_rebate_rate_bp) }}</strong>
                </article>
              </div>
              <div class="partner-subchannel-grid">
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
              <div class="partner-subchannel-actions">
                <button type="button" :disabled="childSubmitting || (!overview.can_create_child && !editingChildId)" @click="submitChildForm">
                  {{ childSubmitting ? "提交中..." : editingChildId ? "保存下级" : "创建下级" }}
                </button>
                <button v-if="editingChildId" type="button" class="partner-btn--ghost" @click="resetChildForm">取消编辑</button>
                <button type="button" class="partner-btn--ghost" @click="copyRecruitmentBundle">复制当前招募信息</button>
              </div>
            </section>
          </div>

          <div class="partner-tree-board">
            <div class="partner-tree-board__head">
              <div class="partner-block__head">
                <strong>渠道树</strong>
                <span>按层级查看团队结构，点节点即可切换查看对应渠道的直属下级。</span>
              </div>
              <div class="partner-tree-board__actions">
                <span v-if="selectedTreeNode">当前查看：{{ selectedTreeNode.name || "-" }}</span>
                <button
                  v-if="selectedTreeNode && Number(selectedTreeNode.id || 0) !== Number(channelTree?.id || 0)"
                  type="button"
                  class="partner-btn--ghost"
                  @click="resetTreeSelection"
                >
                  回到当前渠道
                </button>
              </div>
            </div>
            <PartnerChannelTreeNode
              v-if="channelTree"
              :clickable="true"
              :node="channelTree"
              @select="selectTreeChannel"
            />
            <div v-else class="partner-subchannel-empty">当前暂无渠道树数据。</div>
          </div>

          <div class="partner-subchannel-board">
            <div class="partner-subchannel-board__head">
              <div class="partner-block__head">
                <strong>直属下级列表</strong>
                <span>从谁的推广链接进入，客户就归谁名下。</span>
              </div>
              <div class="partner-subchannel-board__actions">
                <span v-if="selectedTreeNode">当前视角：{{ selectedTreeNode.name || "-" }}</span>
                <button v-if="subchannels.length" type="button" class="partner-btn--ghost" @click="scrollToSection('child-form')">继续新增下级</button>
              </div>
            </div>
            <div v-if="subchannels.length > 0" class="partner-subchannel-items">
              <article v-for="item in subchannels" :key="item.id" class="partner-subchannel-item">
                <div class="partner-subchannel-item__top">
                  <div>
                    <strong>{{ item.name }}</strong>
                    <span>{{ item.channel_code }}</span>
                  </div>
                  <b>{{ Number(item.default_rebate_rate_pct || 0).toFixed(2) }}%</b>
                </div>
                <div class="partner-subchannel-item__meta">
                  <span>{{ formatLevel(item.level) }}</span>
                  <span>{{ item.status === "active" ? "启用中" : "已停用" }}</span>
                  <span>客户 {{ Number(item.user_count || 0) }}</span>
                  <span>{{ item.contact_name || "-" }} / {{ item.contact_phone || "-" }}</span>
                </div>
                <div class="partner-subchannel-share">
                  <span>门户链接：{{ item.portal_link || item.portal_login_link || "-" }}</span>
                  <span>推广链接：{{ item.order_link || "-" }}</span>
                </div>
                <div class="partner-subchannel-item__links">
                  <button type="button" @click="copyChildBundle(item)">刷新并复制下级门户信息</button>
                  <button type="button" @click="copyChildCustomerShare(item)">复制该渠道客户分发文案</button>
                  <button type="button" @click="copyText(item.order_link, `已复制 ${item.name} 的推广链接`)">只复制推广链接</button>
                  <button type="button" @click="copyText(item.portal_link || item.portal_login_link, `已复制 ${item.name} 的渠道门户链接`)">只复制门户链接</button>
                  <button type="button" @click="copyText(item.miniapp_order_path, `已复制 ${item.name} 的小程序推广路径`)">复制小程序推广路径</button>
                  <button type="button" @click="copyText(item.miniapp_portal_path, `已复制 ${item.name} 的小程序后台路径`)">复制小程序后台路径</button>
                </div>
                <div class="partner-subchannel-item__actions">
                  <button type="button" class="partner-btn--ghost" @click="startEditChild(item)">编辑</button>
                  <button type="button" class="partner-btn--ghost" @click="openPolicyPanel(item)">不同套餐返佣</button>
                  <button type="button" class="partner-btn--ghost" @click="toggleChildStatus(item)">
                    {{ item.status === "active" ? "停用" : "启用" }}
                  </button>
                </div>
              </article>
            </div>
            <div v-else class="partner-subchannel-empty">当前还没有直属下级渠道。</div>
          </div>
        </article>

        <article v-if="policyPanel.visible" class="partner-data-card">
          <header class="partner-data-card__head">
            <h2>{{ policyPanel.channel?.name || "-" }} 的商品单独返佣</h2>
            <button type="button" class="partner-btn--ghost" @click="closePolicyPanel">关闭</button>
          </header>
          <div class="partner-policy-shell">
            <div class="partner-subchannel-grid">
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
            <div class="partner-subchannel-actions">
              <button type="button" :disabled="policySubmitting" @click="savePolicy">
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
                    <td colspan="4" class="partner-table__empty">暂无套餐返佣设置</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </article>

        <article id="withdraw-panel" class="partner-data-card">
          <header class="partner-data-card__head">
            <h2>提现</h2>
            <span>门槛 ¥100.00</span>
          </header>
          <div class="partner-withdraw-shell">
            <label class="partner-field">
              <span>提现金额（元）</span>
              <input v-model.number="withdrawAmountCny" type="number" min="100" step="0.01" />
            </label>
            <label class="partner-field partner-field--wide">
              <span>备注（可选）</span>
              <input v-model.trim="withdrawNote" type="text" maxlength="120" placeholder="例如：4月结算提现" />
            </label>
            <div class="partner-subchannel-actions">
              <button type="button" :disabled="withdrawSubmitting" @click="submitWithdrawApply">
                {{ withdrawSubmitting ? "提交中..." : "提交提现申请" }}
              </button>
              <span>当前可提：{{ formatFenToCny(overview.withdrawable_fen) }}</span>
            </div>
          </div>
        </article>

        <details class="partner-data-card partner-fold-card">
          <summary class="partner-fold-card__summary">
            <div>
              <h2>查看更多明细</h2>
              <span>订单、返佣明细、客户归属都收在这里</span>
            </div>
          </summary>

          <div class="partner-fold-card__body">
            <article class="partner-inline-panel">
              <header class="partner-data-card__head">
                <h2>订单列表</h2>
                <div class="partner-head-actions">
                  <select v-model="scopeFilters.orders" @change="loadOrders">
                    <option value="self">我的订单</option>
                    <option value="team">团队订单</option>
                    <option value="subtree">全部订单</option>
                  </select>
                  <button type="button" class="partner-btn--ghost" @click="exportRows('orders')">导出当前结果</button>
                  <span>{{ ordersPagination.total }} 条</span>
                </div>
              </header>
              <div class="partner-filter-row">
                <label class="partner-filter-field">
                  <span>开始日期</span>
                  <input v-model="dateFilters.orders_from" type="date" />
                </label>
                <label class="partner-filter-field">
                  <span>结束日期</span>
                  <input v-model="dateFilters.orders_to" type="date" />
                </label>
                <button type="button" class="partner-btn--ghost" @click="applyListFilter('orders')">筛选</button>
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
                    <tr v-if="orders.length === 0">
                      <td colspan="10" class="partner-table__empty">暂无订单数据</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="partner-pagination">
                <button type="button" class="partner-btn--ghost" :disabled="ordersPagination.page <= 1" @click="changePage('orders', -1)">上一页</button>
                <span>第 {{ ordersPagination.page }} / {{ Math.max(ordersPagination.pages, 1) }} 页</span>
                <button type="button" class="partner-btn--ghost" :disabled="ordersPagination.page >= Math.max(ordersPagination.pages, 1)" @click="changePage('orders', 1)">下一页</button>
              </div>
            </article>

            <article class="partner-inline-panel">
              <header class="partner-data-card__head">
                <h2>返佣流水</h2>
                <div class="partner-head-actions">
                  <select v-model="scopeFilters.ledger" @change="loadLedger">
                    <option value="self">我的返佣</option>
                    <option value="team">团队返佣</option>
                    <option value="subtree">全部返佣</option>
                  </select>
                  <button type="button" class="partner-btn--ghost" @click="exportRows('ledger')">导出当前结果</button>
                  <span>{{ ledgerPagination.total }} 条</span>
                </div>
              </header>
              <div class="partner-filter-row">
                <label class="partner-filter-field">
                  <span>开始日期</span>
                  <input v-model="dateFilters.ledger_from" type="date" />
                </label>
                <label class="partner-filter-field">
                  <span>结束日期</span>
                  <input v-model="dateFilters.ledger_to" type="date" />
                </label>
                <button type="button" class="partner-btn--ghost" @click="applyListFilter('ledger')">筛选</button>
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
                    <tr v-if="ledger.length === 0">
                      <td colspan="10" class="partner-table__empty">暂无返佣流水</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="partner-pagination">
                <button type="button" class="partner-btn--ghost" :disabled="ledgerPagination.page <= 1" @click="changePage('ledger', -1)">上一页</button>
                <span>第 {{ ledgerPagination.page }} / {{ Math.max(ledgerPagination.pages, 1) }} 页</span>
                <button type="button" class="partner-btn--ghost" :disabled="ledgerPagination.page >= Math.max(ledgerPagination.pages, 1)" @click="changePage('ledger', 1)">下一页</button>
              </div>
            </article>

            <article id="customer-panel" class="partner-inline-panel">
              <header class="partner-data-card__head">
                <h2>客户归属</h2>
                <div class="partner-head-actions">
                  <select v-model="scopeFilters.customers" @change="loadCustomers">
                    <option value="self">仅本渠道</option>
                    <option value="team">团队客户</option>
                    <option value="subtree">全部客户</option>
                  </select>
                  <button type="button" class="partner-btn--ghost" @click="exportRows('customers')">导出当前结果</button>
                  <span>{{ customersPagination.total }} 条</span>
                </div>
              </header>
              <div class="partner-filter-row partner-filter-row--wide">
                <label class="partner-filter-field">
                  <span>关键词</span>
                  <input v-model.trim="dateFilters.customers_keyword" type="text" placeholder="昵称 / 渠道名 / 渠道编码" />
                </label>
                <label class="partner-filter-field">
                  <span>开始日期</span>
                  <input v-model="dateFilters.customers_from" type="date" />
                </label>
                <label class="partner-filter-field">
                  <span>结束日期</span>
                  <input v-model="dateFilters.customers_to" type="date" />
                </label>
                <button type="button" class="partner-btn--ghost" @click="applyListFilter('customers')">筛选</button>
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
                    <tr v-if="customers.length === 0">
                      <td colspan="7" class="partner-table__empty">暂无客户归属数据</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="partner-pagination">
                <button type="button" class="partner-btn--ghost" :disabled="customersPagination.page <= 1" @click="changePage('customers', -1)">上一页</button>
                <span>第 {{ customersPagination.page }} / {{ Math.max(customersPagination.pages, 1) }} 页</span>
                <button type="button" class="partner-btn--ghost" :disabled="customersPagination.page >= Math.max(customersPagination.pages, 1)" @click="changePage('customers', 1)">下一页</button>
              </div>
            </article>
          </div>
        </details>
      </section>

      <section v-if="!hasPortalSession && !loading" class="partner-empty">
        <h2>请先登录渠道门户</h2>
        <p>渠道门户已升级为正式登录态。你也可以继续使用旧专属链接自动换取登录会话。</p>
        <div class="partner-subchannel-actions">
          <button type="button" @click="goLogin">前往登录</button>
        </div>
      </section>
    </section>
  </div>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import PartnerChannelTreeNode from "../../components/partner/PartnerChannelTreeNode.vue"
import { partnerHttp } from "../../lib/http"
import { triggerBlobDownload } from "../../lib/download"
import { clearPartnerSession, getPartnerInfo, setPartnerInfo, setPartnerRefreshToken, setPartnerToken } from "../../lib/session"

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const errorText = ref("")
const successText = ref("")
const overview = ref(null)
const orders = ref([])
const ledger = ref([])
const withdrawals = ref([])
const subchannels = ref([])
const customers = ref([])
const channelTree = ref(null)
const selectedTreeNode = ref(null)
const packageOptions = ref([])
const ordersPagination = ref({ page: 1, page_size: 20, total: 0, pages: 0 })
const ledgerPagination = ref({ page: 1, page_size: 20, total: 0, pages: 0 })
const customersPagination = ref({ page: 1, page_size: 20, total: 0, pages: 0 })
const withdrawAmountCny = ref(100)
const withdrawNote = ref("")
const withdrawSubmitting = ref(false)
const childSubmitting = ref(false)
const policySubmitting = ref(false)
const editingChildId = ref(0)

const childForm = ref(createEmptyChildForm())
const policyPanel = ref({
  visible: false,
  channel: null,
  items: [],
})
const policyForm = ref({
  package_name: "",
  rebate_rate_pct: 0,
  is_active: true,
})
const scopeFilters = ref({
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

const channelCode = computed(() => normalizeQueryValue(route.query.ch).toUpperCase())
const portalToken = computed(() => normalizeQueryValue(route.query.pk))
const partnerInfo = ref(getPartnerInfo())
const hasPortalSession = computed(() => Boolean(partnerInfo.value?.id))
const recruitmentMessage = computed(() => {
  const name = String(overview.value?.channel_name || "").trim() || "当前渠道"
  const portalLink = String(overview.value?.portal_link || overview.value?.portal_login_link || "").trim()
  const orderLink = String(overview.value?.order_link || "").trim()
  const lines = [
    `你好，我是 ${name}。`,
    "如果你要做下级渠道，下面这套信息可以直接开用：",
    portalLink ? `渠道门户链接：${portalLink}` : "",
    orderLink ? `推广链接：${orderLink}` : "",
    "打开后会自动进入渠道后台，可以看收益、发链接、发展自己的直属下级。",
  ].filter(Boolean)
  return lines.join("\n")
})
const customerShareText = computed(() => {
  const name = String(overview.value?.channel_name || "").trim() || "当前渠道"
  const orderLink = String(overview.value?.order_link || "").trim()
  const miniappOrderPath = String(overview.value?.miniapp_order_path || "").trim()
  const lines = [
    `你好，我是 ${name}。`,
    "这是我的专属办理入口，直接从这里进入即可：",
    orderLink ? `推广链接：${orderLink}` : "",
    miniappOrderPath ? `小程序路径：${miniappOrderPath}` : "",
  ].filter(Boolean)
  return lines.join("\n")
})
const taskItems = computed(() => {
  const canCreateChild = Boolean(overview.value?.can_create_child)
  const childCount = Number(overview.value?.child_count || 0)
  return [
    {
      title: "先把推广信息发出去",
      desc: "客户和合作方先拿到专属链接，渠道归属才能锁定到你名下。",
      cta: "发给客户",
      action: () => copyCustomerShareText(),
    },
    {
      title: canCreateChild ? (childCount > 0 ? "继续发展直属下级" : "先建一个直属下级") : "当前已到三级",
      desc: canCreateChild ? "把直属下级先发展起来，后面复制和分发会顺很多。" : "不能继续往下建了，但还能继续维护客户和推广信息。",
      cta: canCreateChild ? "去创建下级" : "去提现区",
      action: () => scrollToSection(canCreateChild ? "child-form" : "withdraw-panel"),
    },
    {
      title: Number(overview.value?.pending_rebate_fen || 0) > 0 ? "跟进返佣与提现" : "查看客户归属",
      desc: Number(overview.value?.pending_rebate_fen || 0) > 0 ? "已有待结算返佣时，直接跟进提现节奏更重要。" : "直接看我的客户和团队客户，确认归属链路是否跑通。",
      cta: Number(overview.value?.pending_rebate_fen || 0) > 0 ? "去提现区" : "看客户列表",
      action: () => {
        if (Number(overview.value?.pending_rebate_fen || 0) > 0) {
          scrollToSection("withdraw-panel")
          return
        }
        scrollToSection("customer-panel")
      },
    },
  ]
})

watch(
  () => [channelCode.value, portalToken.value],
  async () => {
    if (channelCode.value && portalToken.value && !hasPortalSession.value) {
      await exchangeLegacyCredential()
      return
    }
    loadPortalData()
  },
  { immediate: true }
)

async function exchangeLegacyCredential() {
  loading.value = true
  errorText.value = ""
  try {
    const data = await partnerHttp.post("/partners/portal/auth/exchange", {
      channel_code: channelCode.value,
      portal_token: portalToken.value,
    })
    setPartnerToken(data.token)
    setPartnerRefreshToken(data.refresh_token)
    setPartnerInfo(data.channel || null)
    partnerInfo.value = data.channel || null
    await router.replace({ path: "/app/partner" })
    await loadPortalData()
  } catch (error) {
    clearPartnerSession()
    partnerInfo.value = null
    errorText.value = String(error?.message || "渠道登录失败")
  } finally {
    loading.value = false
  }
}

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

async function loadPortalData() {
  errorText.value = ""
  if (!hasPortalSession.value) {
    overview.value = null
    orders.value = []
    ledger.value = []
    withdrawals.value = []
    subchannels.value = []
    customers.value = []
    channelTree.value = null
    selectedTreeNode.value = null
    successText.value = ""
    return
  }
  loading.value = true
  try {
    const [overviewResp, withdrawalResp, subchannelResp, channelTreeResp] = await Promise.all([
      partnerHttp.get("/partners/portal/overview", { timeout: 30000 }),
      partnerHttp.get("/partners/portal/withdrawals", { params: { page: 1, page_size: 20 }, timeout: 30000 }),
      partnerHttp.get("/partners/portal/subchannels", { timeout: 30000 }),
      partnerHttp.get("/partners/portal/channel-tree", { timeout: 30000 }),
    ])
    overview.value = overviewResp || null
    withdrawals.value = Array.isArray(withdrawalResp?.items) ? withdrawalResp.items : []
    subchannels.value = Array.isArray(subchannelResp?.items) ? subchannelResp.items : []
    channelTree.value = channelTreeResp?.item || null
    selectedTreeNode.value = channelTreeResp?.item || null
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

async function submitWithdrawApply() {
  if (!hasPortalSession.value || !overview.value) return
  withdrawSubmitting.value = true
  errorText.value = ""
  successText.value = ""
  try {
    await partnerHttp.post(
      "/partners/portal/withdraw-apply",
      {
        apply_amount_cny: Number(withdrawAmountCny.value || 0),
        note: String(withdrawNote.value || "").trim(),
      },
      { timeout: 30000 }
    )
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
      if (bundle) {
        await copyText(bundle, "下级渠道整段信息已复制")
      }
      successText.value = bundle ? "下级渠道已创建，整段信息已复制" : "下级渠道已创建"
    } else {
      await partnerHttp.patch(`/partners/portal/subchannels/${editingChildId.value}`, payload, { timeout: 30000 })
      successText.value = "下级渠道已更新"
    }
    resetChildForm()
    await loadPortalData()
  } catch (error) {
    errorText.value = String(error?.message || "保存下级渠道失败")
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
    await partnerHttp.patch(
      `/partners/portal/subchannels/${item.id}`,
      { status: nextStatus },
      { timeout: 30000 }
    )
    await loadPortalData()
    successText.value = nextStatus === "active" ? "下级渠道已启用" : "下级渠道已停用"
  } catch (error) {
    errorText.value = String(error?.message || "更新渠道状态失败")
  }
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
  policyPanel.value = {
    visible: false,
    channel: null,
    items: [],
  }
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
    await partnerHttp.post(
      `/partners/portal/subchannels/${policyPanel.value.channel.id}/policy`,
      {
        package_name: String(policyForm.value.package_name || "").trim() || null,
        rebate_rate_bp: Math.round(rebateRatePct * 100),
        is_active: Boolean(policyForm.value.is_active),
      },
      { timeout: 30000 }
    )
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
  const name = String(item?.name || item?.channel_name || "").trim()
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
  const name = String(item?.name || item?.channel_name || "").trim() || "当前渠道"
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

async function copyOwnBundle() {
  const bundle = buildChannelBundle({
    ...overview.value,
    name: overview.value?.channel_name || "",
  })
  if (!bundle) {
    errorText.value = "暂无可复制的分发信息"
    successText.value = ""
    return
  }
  await copyText(bundle, "整段分发信息已复制")
}

async function copyCustomerShareText() {
  await copyText(customerShareText.value, "客户分发文案已复制")
}

async function copyRecruitmentBundle() {
  const bundle = buildChannelBundle({
    ...overview.value,
    name: overview.value?.channel_name || "",
  })
  if (!bundle) {
    errorText.value = "暂无可复制的下级招募信息"
    successText.value = ""
    return
  }
  await copyText([recruitmentMessage.value, "", bundle].filter(Boolean).join("\n"), "下级招募信息已复制")
}

async function copyChildBundle(item) {
  if (!hasPortalSession.value) return
  errorText.value = ""
  successText.value = ""
  try {
    const data = await partnerHttp.post(
      `/partners/portal/subchannels/${item.id}/portal-link/refresh`,
      {},
      { timeout: 30000 }
    )
    const bundle = buildChannelBundle({ ...item, ...data })
    if (!bundle) {
      errorText.value = "暂无可复制的下级门户信息"
      return
    }
    await copyText(
      [`你好，这是 ${String(item?.name || "该渠道")} 的下级门户信息：`, bundle].filter(Boolean).join("\n"),
      `已复制 ${item.name} 的下级门户信息`
    )
    successText.value = `已刷新 ${item.name} 的门户链接并复制完整信息`
    await loadPortalData()
  } catch (error) {
    errorText.value = String(error?.message || "复制下级门户信息失败")
  }
}

async function copyChildCustomerShare(item) {
  const bundle = buildCustomerShareBundle(item)
  if (!bundle) {
    errorText.value = "暂无可复制的客户分发文案"
    successText.value = ""
    return
  }
  await copyText(bundle, `已复制 ${item.name} 的客户分发文案`)
}

function normalizeQueryValue(value) {
  if (Array.isArray(value)) {
    return String(value[0] || "").trim()
  }
  return String(value || "").trim()
}

function formatFenToCny(value) {
  const amount = Number(value || 0) / 100
  return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : "¥0.00"
}

function formatRate(value) {
  const bp = Number(value || 0)
  return Number.isFinite(bp) ? `${(bp / 100).toFixed(2)}%` : "-"
}

function formatLevel(value) {
  const level = Number(value || 1)
  if (level === 1) return "一级渠道"
  if (level === 2) return "二级渠道"
  if (level === 3) return "三级渠道"
  return `L${level}`
}

function selectTreeChannel(node) {
  if (!node) return
  selectedTreeNode.value = node
  const children = Array.isArray(node.children) ? node.children : []
  subchannels.value = children
  successText.value = `已切换查看 ${String(node.name || "该渠道")} 的直属下级`
  errorText.value = ""
}

function resetTreeSelection() {
  selectedTreeNode.value = channelTree.value || null
  subchannels.value = Array.isArray(channelTree.value?.children) ? channelTree.value.children : []
  successText.value = "已切回当前渠道视角"
  errorText.value = ""
}

function formatDateTime(value) {
  const text = String(value || "").trim()
  if (!text) return "-"
  const date = new Date(text)
  if (Number.isNaN(date.getTime())) return text
  return date.toLocaleString("zh-CN", { hour12: false })
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

function changePage(type, delta) {
  if (type === "orders") {
    ordersPagination.value.page = Math.max(1, Number(ordersPagination.value.page || 1) + delta)
    loadOrders()
    return
  }
  if (type === "ledger") {
    ledgerPagination.value.page = Math.max(1, Number(ledgerPagination.value.page || 1) + delta)
    loadLedger()
    return
  }
  customersPagination.value.page = Math.max(1, Number(customersPagination.value.page || 1) + delta)
  loadCustomers()
}

function exportRows(type) {
  let rows = []
  let headers = []
  if (type === "orders") {
    headers = ["订单号", "用户ID", "收益渠道", "来源渠道", "套餐", "订单金额", "返佣比例", "净返佣", "状态", "创建时间"]
    rows = orders.value.map((item) => [
      item.order_no,
      item.user_id,
      item.channel_name || item.channel_code || "",
      item.source_channel_code || "",
      item.package_name || "",
      formatFenToCny(item.amount_fen),
      formatRate(item.rebate_rate_bp),
      formatFenToCny(item.net_rebate_fen),
      formatStatus(item.order_status),
      formatDateTime(item.created_at),
    ])
  } else if (type === "ledger") {
    headers = ["流水ID", "订单号", "收益渠道", "来源渠道", "类型", "返佣比例", "返佣金额", "状态", "结算月", "创建时间"]
    rows = ledger.value.map((item) => [
      item.id,
      item.order_no || "",
      item.channel_name || item.channel_code || "",
      item.source_channel_code || "",
      formatEntryType(item.entry_type),
      formatRate(item.rebate_rate_bp),
      formatFenToCny(item.rebate_amount_fen),
      formatStatus(item.status),
      item.statement_month || "",
      formatDateTime(item.created_at),
    ])
  } else {
    headers = ["用户ID", "昵称", "手机号", "归属渠道", "归属来源", "历史订单", "锁定时间"]
    rows = customers.value.map((item) => [
      item.user_id,
      item.nickname,
      item.phone_masked || "",
      item.channel_name || item.channel_code || "",
      item.bind_source || "",
      Number(item.order_count || 0),
      formatDateTime(item.locked_at || item.updated_at || item.created_at),
    ])
  }
  const csv = [headers, ...rows]
    .map((line) => line.map((cell) => `"${String(cell ?? "").replaceAll("\"", "\"\"")}"`).join(","))
    .join("\n")
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" })
  triggerBlobDownload(blob, `partner_${type}_${new Date().toISOString().slice(0, 10)}.csv`)
}
</script>

<style scoped>
.partner-portal-page {
  min-height: 100vh;
  padding: 24px;
  background:
    radial-gradient(circle at 15% 12%, rgba(30, 91, 223, 0.16), transparent 34%),
    radial-gradient(circle at 88% 22%, rgba(24, 145, 110, 0.12), transparent 28%),
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

.partner-portal-head__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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

.partner-portal-head__refresh,
.partner-subchannel-actions button,
.partner-btn--ghost,
.partner-subchannel-item__links button,
.partner-subchannel-item__actions button {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 0;
  cursor: pointer;
  font-weight: 700;
}

.partner-portal-head__refresh,
.partner-subchannel-actions button {
  background: linear-gradient(135deg, #1457cc 0%, #0c73d6 100%);
  color: #fff;
}

.partner-btn--ghost,
.partner-subchannel-item__links button,
.partner-subchannel-item__actions button {
  background: #f4f8ff;
  border: 1px solid #c8d7ea;
  color: #1457cc;
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

.partner-alert--success {
  border: 1px solid #c6eadf;
  background: #effdf7;
  color: #0d7c5e;
}

.partner-overview,
.partner-data-card,
.partner-empty {
  border-radius: 16px;
  background: #fff;
  border: 1px solid #dae3f1;
  box-shadow: 0 14px 28px rgba(19, 40, 72, 0.08);
}

.partner-fold-card {
  overflow: hidden;
}

.partner-fold-card[open] {
  padding-bottom: 8px;
}

.partner-fold-card__summary {
  list-style: none;
  cursor: pointer;
  padding: 16px;
}

.partner-fold-card__summary::-webkit-details-marker {
  display: none;
}

.partner-fold-card__summary h2 {
  margin: 0;
  color: #14345f;
  font-size: 18px;
}

.partner-fold-card__summary span {
  display: block;
  margin-top: 4px;
  color: #617391;
  font-size: 12px;
}

.partner-fold-card__body {
  display: grid;
  gap: 14px;
  padding: 0 0 8px;
}

.partner-inline-panel {
  border-top: 1px solid #e6edf7;
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
  grid-template-columns: repeat(6, minmax(0, 1fr));
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

.partner-workbench-card {
  overflow: hidden;
}

.partner-workbench-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
  padding: 14px 16px 16px;
}

.partner-task-grid {
  display: grid;
  gap: 12px;
  padding: 14px 16px 16px;
}

.partner-task-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.partner-task-grid--compact,
.partner-quick-grid--compact {
  padding: 0;
}

.partner-task-card {
  border: 1px solid #d7e4f6;
  border-radius: 16px;
  padding: 14px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  display: grid;
  gap: 8px;
}

.partner-task-card strong {
  color: #14345f;
  font-size: 15px;
}

.partner-task-card button {
  width: fit-content;
}

.partner-task-card span {
  color: #617391;
  font-size: 12px;
  line-height: 1.7;
}

.partner-quick-card {
  overflow: hidden;
}

.partner-quick-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  padding: 14px 16px 16px;
}

.partner-quick-grid--compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.partner-quick-action {
  border: 1px solid #d6e2f4;
  border-radius: 16px;
  background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
  padding: 14px;
  text-align: left;
  display: grid;
  gap: 6px;
  cursor: pointer;
}

.partner-quick-action strong {
  color: #14345f;
  font-size: 15px;
}

.partner-quick-action span {
  color: #617391;
  font-size: 12px;
  line-height: 1.6;
}

.partner-quick-action--primary {
  background: linear-gradient(135deg, rgba(20, 87, 204, 0.1) 0%, rgba(12, 115, 214, 0.03) 100%);
  border-color: #c9daf6;
}

.partner-share-strip {
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr;
  padding: 14px 16px 0;
}

.partner-share-card {
  border: 1px solid #d7e4f6;
  border-radius: 16px;
  padding: 14px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  display: grid;
  gap: 12px;
}

.partner-share-card--primary {
  background: linear-gradient(135deg, rgba(20, 87, 204, 0.08) 0%, rgba(12, 115, 214, 0.03) 100%);
}

.partner-share-card__head {
  display: grid;
  gap: 4px;
}

.partner-share-card__head strong {
  color: #14345f;
  font-size: 15px;
}

.partner-share-card__head span,
.partner-share-card__meta span {
  color: #5d7090;
  font-size: 12px;
  line-height: 1.6;
}

.partner-share-card__meta {
  display: grid;
  gap: 6px;
}

.partner-share-card__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.partner-data-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 16px 16px 0;
}

.partner-data-card__head h2 {
  margin: 0;
  color: #14345f;
  font-size: 18px;
}

.partner-data-card__head span {
  color: #617391;
  font-size: 12px;
}

.partner-head-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.partner-filter-row {
  display: flex;
  align-items: end;
  gap: 10px;
  flex-wrap: wrap;
  padding: 0 16px 14px;
}

.partner-filter-row--wide {
  display: grid;
  grid-template-columns: minmax(220px, 1.2fr) repeat(2, minmax(160px, 0.9fr)) auto;
}

.partner-filter-field {
  display: grid;
  gap: 6px;
  min-width: 140px;
}

.partner-filter-field span {
  color: #5d7090;
  font-size: 12px;
}

.partner-filter-field input {
  min-height: 34px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid #cfdbec;
  color: #12345c;
  background: #fff;
}

.partner-pagination {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  padding: 0 16px 16px;
  color: #617391;
  font-size: 12px;
}

.partner-head-actions select {
  min-height: 34px;
  padding: 0 10px;
  border-radius: 10px;
  border: 1px solid #cfdbec;
  color: #12345c;
  background: #fff;
}

.partner-manage-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr;
  padding: 14px 16px 0;
}

.partner-block,
.partner-policy-shell,
.partner-withdraw-shell,
.partner-table-wrap,
.partner-subchannel-board,
.partner-tree-board {
  padding: 14px 16px 16px;
}

.partner-tree-board__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.partner-tree-board__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: #5d7090;
  font-size: 12px;
}

.partner-child-summary {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 12px;
}

.partner-child-summary__card {
  border-radius: 12px;
  background: #f4f8ff;
  border: 1px solid #dde7f5;
  padding: 12px;
}

.partner-child-summary__card span {
  display: block;
  color: #627492;
  font-size: 12px;
}

.partner-child-summary__card strong {
  display: block;
  margin-top: 6px;
  color: #14345f;
  font-size: 18px;
}

.partner-subchannel-board__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.partner-subchannel-board__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  color: #5d7090;
  font-size: 12px;
}

.partner-block {
  border-radius: 14px;
  background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
  border: 1px solid #dde7f5;
}

.partner-block__head {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
}

.partner-block__head strong {
  color: #14345f;
  font-size: 15px;
}

.partner-block__head span {
  color: #617391;
  font-size: 12px;
  line-height: 1.6;
}

.partner-section-anchor {
  position: relative;
  top: -8px;
}

.partner-subchannel-items {
  display: grid;
  gap: 10px;
}

.partner-subchannel-items {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.partner-field {
  display: grid;
  gap: 6px;
}

.partner-field span {
  color: #5d7090;
  font-size: 12px;
}

.partner-field input,
.partner-field select {
  min-height: 38px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #cfdbec;
  background: #fff;
  color: #12345c;
  width: 100%;
}

.partner-subchannel-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.partner-subchannel-actions {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 12px;
}

.partner-subchannel-actions span {
  color: #4d6283;
  font-size: 13px;
}

.partner-subchannel-item {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 14px;
  background: linear-gradient(180deg, #f7faff 0%, #ffffff 100%);
  border: 1px solid #dde7f5;
}

.partner-subchannel-item__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.partner-subchannel-item__top strong {
  display: block;
  color: #12345c;
  font-size: 15px;
}

.partner-subchannel-item__top span {
  display: block;
  margin-top: 4px;
  color: #6b7d97;
  font-size: 12px;
}

.partner-subchannel-item__top b {
  color: #1558cb;
  font-size: 18px;
}

.partner-subchannel-item__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.partner-subchannel-share {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 12px;
  background: #f5f9ff;
  border: 1px solid #dde7f5;
}

.partner-subchannel-share span {
  color: #536883;
  font-size: 12px;
  line-height: 1.6;
}

.partner-subchannel-item__meta span {
  padding: 4px 8px;
  border-radius: 999px;
  background: #eef4ff;
  color: #4f6691;
  font-size: 12px;
}

.partner-subchannel-item__links,
.partner-subchannel-item__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.partner-subchannel-empty,
.partner-table__empty {
  color: #647481;
  text-align: center;
  padding: 18px 12px;
}

.partner-table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  font-size: 13px;
}

.partner-table th,
.partner-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #e8edf2;
  text-align: left;
  vertical-align: top;
}

.partner-table th {
  color: #647481;
  font-weight: 700;
}

.partner-empty {
  padding: 28px;
  text-align: center;
}

.partner-empty h2 {
  margin: 0 0 8px;
}

.partner-empty p {
  margin: 0;
  color: #647481;
}

@media (max-width: 1180px) {
  .partner-workbench-grid,
  .partner-task-grid,
  .partner-quick-grid,
  .partner-overview__cards {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .partner-manage-grid {
    grid-template-columns: 1fr;
  }

  .partner-share-strip {
    grid-template-columns: 1fr;
  }

  .partner-workbench-grid,
  .partner-filter-row--wide {
    grid-template-columns: 1fr 1fr;
  }

  .partner-subchannel-items {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .partner-portal-page {
    padding: 14px;
  }

  .partner-portal-head {
    flex-direction: column;
  }

  .partner-workbench-grid,
  .partner-task-grid,
  .partner-quick-grid,
  .partner-overview__cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .partner-subchannel-grid,
  .partner-tree-board {
    grid-template-columns: 1fr;
  }

  .partner-filter-row,
  .partner-pagination,
  .partner-head-actions,
  .partner-share-card__actions,
  .partner-tree-board__actions,
  .partner-subchannel-board__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .partner-filter-row--wide {
    grid-template-columns: 1fr;
  }

  .partner-workbench-grid,
  .partner-manage-grid,
  .partner-subchannel-items,
  .partner-child-summary {
    grid-template-columns: 1fr;
  }
}
</style>

