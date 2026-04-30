<template>
  <AdminShell title="用户管理" subtitle="查询用户、封禁状态与通用点数调整。">
    <section class="gw-admin-overview">
      <article class="gw-admin-overview__hero">
        <div class="gw-admin-overview__eyebrow">用户工作台</div>
        <h2>用户管理</h2>
        <p>搜索、筛选和处理常用操作集中在一个页面，减少来回切换。</p>
      </article>
      <article class="gw-admin-overview__stat">
        <span>当前加载</span>
        <strong>{{ rows.length }}</strong>
        <em>本次查询返回用户数</em>
      </article>
      <article class="gw-admin-overview__stat">
        <span>正常用户</span>
        <strong>{{ activeCount }}</strong>
        <em>当前结果中的可用账号</em>
      </article>
      <article class="gw-admin-overview__stat">
        <span>小程序来源</span>
        <strong>{{ miniappCount }}</strong>
        <em>方便单独观察渠道结构</em>
      </article>
    </section>

    <section class="scholar-panel">
      <div class="scholar-panel__header">
        <div class="scholar-kicker">用户搜索</div>
        <h3 class="scholar-subtitle">搜索与筛选</h3>
      </div>

      <div class="scholar-panel__body">
        <div class="scholar-inline-actions gw-admin-toolbar">
          <input v-model.trim="keyword" class="scholar-input" style="max-width: 320px" placeholder="按手机号搜索" />
          <div class="scholar-inline-actions gw-admin-status-filters">
            <button
              v-for="item in statusFilters"
              :key="item.value || 'all'"
              type="button"
              class="gw-admin-status-btn"
              :class="{ 'is-active': activeStatusFilter === item.value }"
              :aria-pressed="activeStatusFilter === item.value ? 'true' : 'false'"
              @click="activeStatusFilter = item.value"
            >
              {{ item.label }}
            </button>
          </div>
          <div class="scholar-inline-actions gw-admin-status-filters">
            <button
              v-for="item in sourceFilters"
              :key="item.value || 'all-source'"
              type="button"
              class="gw-admin-status-btn"
              :class="{ 'is-active': activeSourceFilter === item.value }"
              :aria-pressed="activeSourceFilter === item.value ? 'true' : 'false'"
              @click="activeSourceFilter = item.value"
            >
              {{ item.label }}
            </button>
          </div>
          <button class="gw-admin-btn" type="button" @click="loadData">查询</button>
        </div>

        <div class="scholar-grid md:grid-cols-4" style="margin-top: 18px">
          <div class="scholar-stat">
            <div class="scholar-stat__label">当前加载用户</div>
            <div class="scholar-stat__value" style="font-size: 26px">{{ rows.length }}</div>
          </div>
          <div class="scholar-stat">
            <div class="scholar-stat__label">正常用户</div>
            <div class="scholar-stat__value" style="font-size: 26px; color: var(--success)">{{ activeCount }}</div>
          </div>
          <div class="scholar-stat">
            <div class="scholar-stat__label">封禁用户</div>
            <div class="scholar-stat__value" style="font-size: 26px; color: var(--danger)">{{ bannedCount }}</div>
          </div>
          <div class="scholar-stat">
            <div class="scholar-stat__label">小程序来源用户</div>
            <div class="scholar-stat__value" style="font-size: 26px">{{ miniappCount }}</div>
          </div>
        </div>

        <div class="overflow-x-auto gw-admin-user-table-shell" style="margin-top: 18px">
          <table class="scholar-table">
            <thead>
              <tr>
                <th>用户 ID</th>
                <th>手机号</th>
                <th>昵称</th>
                <th>通用点数</th>
                <th>状态</th>
                <th>来源</th>
                <th>创建时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in displayRows" :key="row.id">
                <td>{{ row.id }}</td>
                <td>{{ row.phone }}</td>
                <td>{{ row.nickname }}</td>
                <td>{{ formatCredits(userBalanceFen(row)) }}</td>
                <td>
                  <span class="scholar-badge" :class="row.is_banned ? 'scholar-badge--danger' : 'scholar-badge--success'">
                    {{ row.is_banned ? "已封禁" : "正常" }}
                  </span>
                </td>
                <td>{{ mapSource(row.source) }}</td>
                <td>{{ formatTime(row.created_at) }}</td>
                <td>
                  <div class="scholar-inline-actions">
                    <button class="gw-admin-btn" type="button" @click="goDetail(row)">
                      查看详情
                    </button>
                    <button v-if="canManageUsers" class="gw-admin-btn" type="button" @click="toggleBan(row)">
                      {{ row.is_banned ? "解封" : "封禁" }}
                    </button>
                    <button v-if="canManageUsers" class="gw-admin-btn" type="button" @click="openAdjust(row)">
                      调整点数
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="displayRows.length === 0">
                <td colspan="8">
                  <div class="scholar-empty">暂无用户数据</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="gw-admin-user-mobile-list">
          <article v-for="row in displayRows" :key="`mobile-user-${row.id}`" class="gw-admin-user-card">
            <div class="gw-admin-user-card__head">
              <div>
                <div class="gw-admin-user-card__eyebrow">用户 #{{ row.id }}</div>
                <strong class="gw-admin-user-card__title">{{ row.nickname || "未设置昵称" }}</strong>
                <div class="gw-admin-user-card__sub">{{ row.phone }}</div>
              </div>
              <span class="scholar-badge" :class="row.is_banned ? 'scholar-badge--danger' : 'scholar-badge--success'">
                {{ row.is_banned ? "已封禁" : "正常" }}
              </span>
            </div>

            <div class="gw-admin-user-card__grid">
              <div><span>通用点数</span><strong>{{ formatCredits(userBalanceFen(row)) }}</strong></div>
              <div><span>来源</span><strong>{{ mapSource(row.source) }}</strong></div>
              <div><span>创建时间</span><strong>{{ formatTime(row.created_at) }}</strong></div>
            </div>

            <div class="gw-admin-user-card__actions">
              <button class="gw-admin-btn" type="button" @click="goDetail(row)">查看详情</button>
              <button v-if="canManageUsers" class="gw-admin-btn" type="button" @click="toggleBan(row)">
                {{ row.is_banned ? "解封" : "封禁" }}
              </button>
              <button v-if="canManageUsers" class="gw-admin-btn" type="button" @click="openAdjust(row)">调整点数</button>
            </div>
          </article>
          <div v-if="displayRows.length === 0" class="scholar-empty">暂无用户数据</div>
        </div>
      </div>
    </section>

    <section v-if="editing && canManageUsers" class="scholar-panel scholar-panel--soft">
      <div class="scholar-panel__body">
        <div class="scholar-kicker">点数调整</div>
        <h3 class="scholar-subtitle">调整用户通用点数：{{ editing.phone }}</h3>
        <div class="scholar-grid md:grid-cols-3" style="margin-top: 18px">
          <input v-model.number="delta" class="scholar-input" placeholder="输入正负点数，例如 200 或 -200" />
          <input v-model.trim="reason" class="scholar-input" placeholder="调整原因" />
          <button class="gw-admin-btn" type="button" @click="submitAdjust">确认调整</button>
        </div>
        <p v-if="hintText" class="scholar-note scholar-note--success" style="margin-top: 18px">{{ hintText }}</p>
        <p v-if="errorText" class="scholar-note scholar-note--danger" style="margin-top: 18px">{{ errorText }}</p>
      </div>
    </section>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { useRouter } from "vue-router"

import AdminShell from "../../components/AdminShell.vue"
import { formatBeijingDateTime } from "../../lib/dateTime"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

const router = useRouter()
const rows = ref([])
const keyword = ref("")
const activeStatusFilter = ref("")
const activeSourceFilter = ref("")
const editing = ref(null)
const delta = ref(0)
const reason = ref("")
const hintText = ref("")
const errorText = ref("")
const sourceStats = ref({ web: 0, miniapp: 0, other: 0, total: 0 })

const canManageUsers = computed(() => adminHasPermission("users:manage"))
const statusFilters = [
  { value: "", label: "全部状态" },
  { value: "active", label: "正常" },
  { value: "banned", label: "已封禁" },
]
const sourceFilters = [
  { value: "", label: "全部来源" },
  { value: "web", label: "Web" },
  { value: "miniapp", label: "小程序" },
  { value: "other", label: "其他" },
]
const displayRows = computed(() => {
  if (!activeStatusFilter.value) return rows.value
  if (activeStatusFilter.value === "active") return rows.value.filter((row) => !row.is_banned)
  return rows.value.filter((row) => row.is_banned)
})
const activeCount = computed(() => rows.value.filter((row) => !row.is_banned).length)
const bannedCount = computed(() => rows.value.filter((row) => row.is_banned).length)
const miniappCount = computed(() => Number(sourceStats.value.miniapp || 0))

onMounted(loadData)

async function loadData() {
  const data = await adminHttp.get("/admin/users", {
    params: {
      page: 1,
      page_size: 50,
      q: keyword.value || undefined,
      source: activeSourceFilter.value || undefined,
    },
  })
  rows.value = data.items || []
  sourceStats.value = data.source_stats || { web: 0, miniapp: 0, other: 0, total: 0 }
}

function openAdjust(row) {
  editing.value = row
  delta.value = 0
  reason.value = ""
  hintText.value = ""
  errorText.value = ""
}

async function submitAdjust() {
  if (!editing.value) return
  if (!delta.value) {
    errorText.value = "调整值不能为 0"
    return
  }
  if (!reason.value) {
    errorText.value = "请输入调整原因"
    return
  }
  errorText.value = ""
  const data = await adminHttp.post(`/admin/users/${editing.value.id}/adjust-credits`, {
    delta: delta.value,
    reason: reason.value,
  })
  hintText.value = `已调整成功，当前通用点数 ${formatCredits(userBalanceFen(data))}`
  await loadData()
}

function goDetail(row) {
  router.push(`/admin/users/${row.id}`)
}

async function toggleBan(row) {
  const target = !row.is_banned
  const confirmed = window.confirm(target ? "确认封禁该用户吗？" : "确认解封该用户吗？")
  if (!confirmed) {
    return
  }
  await adminHttp.post(`/admin/users/${row.id}/ban`, { is_banned: target })
  await loadData()
}

function formatTime(value) {
  return formatBeijingDateTime(value)
}

function userBalanceFen(row) {
  if (typeof row?.balance_fen === "number") return row.balance_fen
  if (typeof row?.credits === "number") return row.credits
  return 0
}

function formatCredits(value) {
  return `${Number(value || 0).toLocaleString()} 通用点数`
}

function mapSource(value) {
  if (value === "miniapp") return "小程序"
  if (value === "web") return "Web"
  return "其他"
}
</script>

<style scoped>
.gw-admin-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) repeat(3, minmax(0, 0.62fr));
  gap: 14px;
  margin-bottom: 16px;
}

.gw-admin-overview__hero,
.gw-admin-overview__stat,
.gw-admin-user-card {
  border: 1px solid rgba(30, 91, 223, 0.12);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 255, 0.94));
  box-shadow: 0 16px 30px rgba(30, 91, 223, 0.08);
}

.gw-admin-overview__hero {
  padding: 20px 22px;
  display: grid;
  gap: 8px;
}

.gw-admin-overview__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6c87ac;
}

.gw-admin-overview__hero h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.1;
  color: #1f3555;
}

.gw-admin-overview__hero p {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #607894;
}

.gw-admin-overview__stat {
  padding: 18px 18px 16px;
  display: grid;
  gap: 6px;
}

.gw-admin-overview__stat span {
  font-size: 12px;
  color: #6d84a2;
}

.gw-admin-overview__stat strong {
  font-size: 24px;
  line-height: 1.08;
  color: #1e5bdf;
}

.gw-admin-overview__stat em {
  font-style: normal;
  font-size: 12px;
  line-height: 1.6;
  color: #68809d;
}

.gw-admin-toolbar {
  align-items: stretch;
}

.gw-admin-status-filters {
  gap: 8px;
}

.gw-admin-status-btn,
.gw-admin-btn {
  min-height: 34px !important;
  padding: 0 14px !important;
  border-radius: 999px !important;
  border: 1px solid rgba(30, 91, 223, 0.14) !important;
  background: #ffffff !important;
  color: #35527d !important;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  line-height: 1;
  transition: background-color 0.16s ease, color 0.16s ease, border-color 0.16s ease;
}

.gw-admin-status-btn:hover,
.gw-admin-btn:hover,
.gw-admin-status-btn:focus-visible,
.gw-admin-btn:focus-visible,
.gw-admin-btn:active {
  background: #eef4ff !important;
  color: #1e5bdf !important;
  border-color: rgba(30, 91, 223, 0.22) !important;
}

.gw-admin-status-btn.is-active,
.gw-admin-status-btn[aria-pressed="true"] {
  background: linear-gradient(135deg, #5d92ff, #1e5bdf) !important;
  color: #ffffff !important;
  border-color: rgba(30, 91, 223, 0.14) !important;
}

.gw-admin-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.gw-admin-user-mobile-list {
  display: none;
  margin-top: 18px;
}

.gw-admin-user-card {
  display: grid;
  gap: 14px;
  padding: 16px;
}

.gw-admin-user-card + .gw-admin-user-card {
  margin-top: 12px;
}

.gw-admin-user-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.gw-admin-user-card__eyebrow {
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6b85a8;
}

.gw-admin-user-card__title {
  display: block;
  margin-top: 6px;
  font-size: 16px;
  line-height: 1.5;
  color: #1f3555;
}

.gw-admin-user-card__sub {
  margin-top: 4px;
  font-size: 13px;
  color: #607894;
}

.gw-admin-user-card__grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.gw-admin-user-card__grid div {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  border: 1px solid rgba(30, 91, 223, 0.1);
  background: #ffffff;
}

.gw-admin-user-card__grid span {
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6c85a8;
}

.gw-admin-user-card__grid strong {
  font-size: 13px;
  line-height: 1.6;
  color: #1f3555;
  word-break: break-word;
}

.gw-admin-user-card__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .gw-admin-overview {
    grid-template-columns: 1fr;
  }

  .gw-admin-toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .gw-admin-toolbar > * {
    width: 100%;
    max-width: none !important;
  }

  .gw-admin-user-table-shell {
    display: none;
  }

  .gw-admin-user-mobile-list {
    display: block;
  }

  .gw-admin-user-card__grid {
    grid-template-columns: 1fr;
  }
}
</style>
