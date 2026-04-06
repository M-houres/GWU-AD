<template>
  <AdminShell title="用户管理" subtitle="查询用户、封禁状态与积分调整。">
    <section class="scholar-panel">
      <div class="scholar-panel__header">
        <div class="scholar-kicker">用户搜索</div>
        <h3 class="scholar-subtitle">检索与筛选</h3>
      </div>

      <div class="scholar-panel__body">
        <div class="scholar-inline-actions">
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

        <div class="overflow-x-auto" style="margin-top: 18px">
          <table class="scholar-table">
            <thead>
              <tr>
                <th>用户 ID</th>
                <th>手机号</th>
                <th>昵称</th>
                <th>积分</th>
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
                <td>{{ row.credits }}</td>
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
                      调整积分
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
      </div>
    </section>

    <section v-if="editing && canManageUsers" class="scholar-panel scholar-panel--soft">
      <div class="scholar-panel__body">
        <div class="scholar-kicker">积分调整</div>
        <h3 class="scholar-subtitle">调整用户积分：{{ editing.phone }}</h3>
        <div class="scholar-grid md:grid-cols-3" style="margin-top: 18px">
          <input v-model.number="delta" class="scholar-input" placeholder="输入正负积分" />
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
  hintText.value = `已调整成功，当前积分 ${data.credits}`
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
  return value ? String(value).slice(0, 19).replace("T", " ") : "-"
}

function mapSource(value) {
  if (value === "miniapp") return "小程序"
  if (value === "web") return "Web"
  return "其他"
}
</script>

<style scoped>
.gw-admin-status-filters {
  gap: 8px;
}

.gw-admin-status-btn,
.gw-admin-btn {
  min-height: 34px !important;
  padding: 0 14px !important;
  border-radius: 999px !important;
  border: 1px solid #111111 !important;
  background: #ffffff !important;
  color: #111111 !important;
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
  background: #111111 !important;
  color: #ffffff !important;
  border-color: #111111 !important;
}

.gw-admin-status-btn.is-active,
.gw-admin-status-btn[aria-pressed="true"] {
  background: #111111 !important;
  color: #ffffff !important;
  border-color: #111111 !important;
}

.gw-admin-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
</style>
