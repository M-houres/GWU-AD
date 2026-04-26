<template>
  <AdminShell title="推广审核" subtitle="处理集赞截图与创作链接提审，统一走人工审核闭环。">
    <section class="gw-promo-review-overview">
      <article class="gw-promo-review-overview__hero">
        <div class="gw-promo-review-overview__eyebrow">推广审核台</div>
        <h2>推广中心审核</h2>
        <p>按活动类型切换查看，直接完成通过或驳回，不再依赖线下人工登记。</p>
      </article>
      <article class="gw-promo-review-overview__stat">
        <span>当前加载</span>
        <strong>{{ rows.length }}</strong>
        <em>本次查询返回记录数</em>
      </article>
      <article class="gw-promo-review-overview__stat">
        <span>待审核</span>
        <strong>{{ pendingCount }}</strong>
        <em>优先处理积压项</em>
      </article>
      <article class="gw-promo-review-overview__stat">
        <span>已通过 / 已驳回</span>
        <strong>{{ approvedCount }} / {{ rejectedCount }}</strong>
        <em>当前筛选结果中的审核状态</em>
      </article>
    </section>

    <section class="scholar-panel">
      <div class="scholar-panel__header">
        <div class="scholar-kicker">审核筛选</div>
        <h3 class="scholar-subtitle">按活动类型与状态处理提审记录</h3>
      </div>

      <div class="scholar-panel__body">
        <div class="scholar-inline-actions gw-promo-review-tabs">
          <button
            v-for="item in sceneTabs"
            :key="item.value"
            type="button"
            class="gw-promo-review-tab"
            :class="{ 'is-active': activeScene === item.value }"
            @click="switchScene(item.value)"
          >
            {{ item.label }}
          </button>
        </div>

        <div class="scholar-inline-actions gw-promo-review-toolbar">
          <input v-model.trim="keyword" class="scholar-input" style="max-width: 240px" placeholder="按手机号搜索" />
          <input v-model.trim="platform" class="scholar-input" style="max-width: 180px" placeholder="按平台筛选" />
          <div class="scholar-inline-actions gw-promo-review-status-filters">
            <button
              v-for="item in statusFilters"
              :key="item.value || 'all-status'"
              type="button"
              class="gw-promo-review-status-btn"
              :class="{ 'is-active': activeStatus === item.value }"
              @click="activeStatus = item.value"
            >
              {{ item.label }}
            </button>
          </div>
          <button class="gw-admin-btn" type="button" @click="loadData">查询</button>
        </div>

        <div class="scholar-grid md:grid-cols-4" style="margin-top: 18px">
          <div class="scholar-stat">
            <div class="scholar-stat__label">总记录</div>
            <div class="scholar-stat__value" style="font-size: 26px">{{ totalCount }}</div>
          </div>
          <div class="scholar-stat">
            <div class="scholar-stat__label">待审核</div>
            <div class="scholar-stat__value" style="font-size: 26px; color: #b26f00">{{ pendingCount }}</div>
          </div>
          <div class="scholar-stat">
            <div class="scholar-stat__label">已通过</div>
            <div class="scholar-stat__value" style="font-size: 26px; color: var(--success)">{{ approvedCount }}</div>
          </div>
          <div class="scholar-stat">
            <div class="scholar-stat__label">已驳回</div>
            <div class="scholar-stat__value" style="font-size: 26px; color: var(--danger)">{{ rejectedCount }}</div>
          </div>
        </div>

        <div class="overflow-x-auto" style="margin-top: 18px">
          <table class="scholar-table">
            <thead>
              <tr>
                <th>用户</th>
                <th>平台</th>
                <th>内容</th>
                <th>状态</th>
                <th>奖励</th>
                <th>审核备注</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in rows" :key="`${activeScene}-${row.id}`">
                <td>
                  <div class="gw-promo-review-cell-title">{{ row.user_nickname || "未设置昵称" }}</div>
                  <div class="gw-promo-review-cell-sub">#{{ row.user_id }} · {{ row.user_phone || "-" }}</div>
                </td>
                <td>{{ platformLabel(row) }}</td>
                <td>
                  <div class="gw-promo-review-cell-title">{{ primaryContent(row) }}</div>
                  <div class="gw-promo-review-cell-sub">{{ secondaryContent(row) }}</div>
                </td>
                <td>
                  <span class="scholar-badge" :class="statusBadgeClass(row.status)">
                    {{ statusLabel(row.status) }}
                  </span>
                </td>
                <td>
                  <div class="gw-promo-review-cell-title">{{ rewardLabel(row) }}</div>
                  <div class="gw-promo-review-cell-sub">{{ benefitLabel(row) }}</div>
                </td>
                <td>{{ row.review_note || "-" }}</td>
                <td>{{ formatTime(row.updated_at || row.created_at) }}</td>
                <td>
                  <div class="scholar-inline-actions">
                    <button v-if="activeScene === 'create' && row.share_link" class="gw-admin-btn" type="button" @click="openLink(row.share_link)">
                      打开链接
                    </button>
                    <button v-if="activeScene === 'like' && row.screenshot_path" class="gw-admin-btn" type="button" @click="previewScreenshot(row)">
                      预览截图
                    </button>
                    <button v-if="activeScene === 'like' && row.screenshot_path" class="gw-admin-btn" type="button" @click="downloadScreenshot(row)">
                      下载截图
                    </button>
                    <button
                      v-if="canReview"
                      class="gw-admin-btn"
                      type="button"
                      :disabled="reviewingId === row.id"
                      @click="reviewRow(row, 'approved')"
                    >
                      通过
                    </button>
                    <button
                      v-if="canReview"
                      class="gw-admin-btn gw-admin-btn--danger"
                      type="button"
                      :disabled="reviewingId === row.id"
                      @click="reviewRow(row, 'rejected')"
                    >
                      驳回
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="rows.length === 0">
                <td colspan="8">
                  <div class="scholar-empty">暂无提审记录</div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="gw-promo-review-mobile-list">
          <article v-for="row in rows" :key="`mobile-${activeScene}-${row.id}`" class="gw-promo-review-card">
            <div class="gw-promo-review-card__head">
              <div>
                <div class="gw-promo-review-overview__eyebrow">{{ platformLabel(row) }}</div>
                <strong class="gw-promo-review-card__title">{{ row.user_nickname || "未设置昵称" }}</strong>
                <div class="gw-promo-review-card__sub">#{{ row.user_id }} · {{ row.user_phone || "-" }}</div>
              </div>
              <span class="scholar-badge" :class="statusBadgeClass(row.status)">{{ statusLabel(row.status) }}</span>
            </div>

            <div class="gw-promo-review-card__body">
              <div><span>内容</span><strong>{{ primaryContent(row) }}</strong></div>
              <div><span>补充</span><strong>{{ secondaryContent(row) }}</strong></div>
              <div><span>奖励</span><strong>{{ rewardLabel(row) }}</strong></div>
              <div><span>发放</span><strong>{{ benefitLabel(row) }}</strong></div>
              <div><span>审核备注</span><strong>{{ row.review_note || "-" }}</strong></div>
              <div><span>更新时间</span><strong>{{ formatTime(row.updated_at || row.created_at) }}</strong></div>
            </div>

            <div class="gw-promo-review-card__actions">
              <button v-if="activeScene === 'create' && row.share_link" class="gw-admin-btn" type="button" @click="openLink(row.share_link)">打开链接</button>
              <button v-if="activeScene === 'like' && row.screenshot_path" class="gw-admin-btn" type="button" @click="previewScreenshot(row)">预览截图</button>
              <button v-if="activeScene === 'like' && row.screenshot_path" class="gw-admin-btn" type="button" @click="downloadScreenshot(row)">下载截图</button>
              <button v-if="canReview" class="gw-admin-btn" type="button" :disabled="reviewingId === row.id" @click="reviewRow(row, 'approved')">通过</button>
              <button v-if="canReview" class="gw-admin-btn gw-admin-btn--danger" type="button" :disabled="reviewingId === row.id" @click="reviewRow(row, 'rejected')">驳回</button>
            </div>
          </article>
        </div>

        <div class="gw-promo-review-pagination">
          <button class="gw-admin-btn" type="button" :disabled="currentPage <= 1" @click="changePage(currentPage - 1)">上一页</button>
          <span>第 {{ currentPage }} / {{ totalPages }} 页</span>
          <button class="gw-admin-btn" type="button" :disabled="currentPage >= totalPages" @click="changePage(currentPage + 1)">下一页</button>
        </div>

        <p v-if="hintText" class="scholar-note scholar-note--success" style="margin-top: 18px">{{ hintText }}</p>
        <p v-if="errorText" class="scholar-note scholar-note--danger" style="margin-top: 18px">{{ errorText }}</p>
      </div>
    </section>

    <div v-if="previewDialog.open" class="gw-promo-preview" @click.self="closePreview">
      <div class="gw-promo-preview__panel">
        <div class="gw-promo-preview__head">
          <strong>{{ previewDialog.title || "截图预览" }}</strong>
          <button type="button" class="gw-admin-btn" @click="closePreview">关闭</button>
        </div>
        <div class="gw-promo-preview__body">
          <img v-if="previewDialog.url" :src="previewDialog.url" :alt="previewDialog.title || '截图预览'" />
        </div>
      </div>
    </div>

    <div v-if="rewardDialog.open" class="gw-promo-preview" @click.self="closeRewardDialog">
      <div class="gw-promo-preview__panel gw-promo-reward-panel">
        <div class="gw-promo-preview__head">
          <strong>{{ rewardDialog.title }}</strong>
          <button type="button" class="gw-admin-btn" @click="closeRewardDialog">关闭</button>
        </div>
        <div class="gw-promo-reward-panel__body">
          <p class="gw-promo-review-cell-sub">{{ rewardDialog.subtitle }}</p>
          <div class="gw-promo-reward-options">
            <label v-for="item in rewardOptions" :key="item.key" class="gw-promo-reward-option">
              <input v-model="rewardDialog.selectedKey" type="radio" :value="item.key" />
              <div>
                <strong>{{ item.label }}</strong>
                <span>{{ Number(item.reward_points || 0).toLocaleString() }} 点</span>
              </div>
            </label>
          </div>
          <div class="gw-promo-reward-panel__actions">
            <button class="gw-admin-btn" type="button" @click="closeRewardDialog">取消</button>
            <button class="gw-admin-btn" type="button" :disabled="!rewardDialog.selectedKey || !!reviewingId" @click="confirmApprovedReview">
              确认通过并发奖
            </button>
          </div>
        </div>
      </div>
    </div>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { downloadAxiosBlobResponse } from "../../lib/download"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

const sceneTabs = [
  { value: "like", label: "集赞截图" },
  { value: "create", label: "创作链接" },
]
const rows = ref([])
const keyword = ref("")
const platform = ref("")
const activeScene = ref("like")
const activeStatus = ref("")
const statusStats = ref({})
const pagination = ref({ total: 0, page: 1, page_size: 20, total_pages: 1 })
const currentPage = ref(1)
const reviewingId = ref(null)
const hintText = ref("")
const errorText = ref("")
const previewDialog = ref({ open: false, url: "", title: "" })
const rewardOptions = ref([])
const rewardDialog = ref({
  open: false,
  row: null,
  title: "",
  subtitle: "",
  selectedKey: "",
})

const canReview = computed(() => adminHasPermission("users:manage"))
const statusFilters = computed(() => {
  if (activeScene.value === "like") {
    return [
      { value: "", label: "全部状态" },
      { value: "pending", label: "待审核" },
      { value: "approved", label: "已通过" },
      { value: "rejected", label: "已驳回" },
    ]
  }
  return [
    { value: "", label: "全部状态" },
    { value: "submitted", label: "待审核" },
    { value: "approved", label: "已通过" },
    { value: "rejected", label: "已驳回" },
  ]
})
const totalCount = computed(() => Number(statusStats.value.total || pagination.value.total || 0))
const pendingCount = computed(() => Number(statusStats.value.pending || statusStats.value.submitted || 0))
const approvedCount = computed(() => Number(statusStats.value.approved || 0))
const rejectedCount = computed(() => Number(statusStats.value.rejected || 0))
const totalPages = computed(() => Math.max(1, Number(pagination.value.total_pages || 1)))

onMounted(loadData)

async function loadData() {
  hintText.value = ""
  errorText.value = ""
  try {
    const endpoint = activeScene.value === "like" ? "/admin/promo/like-submissions" : "/admin/promo/create-submissions"
    const data = await adminHttp.get(endpoint, {
      params: {
        page: currentPage.value,
        page_size: 20,
        q_phone: keyword.value || undefined,
        platform: platform.value || undefined,
        status: activeStatus.value || undefined,
      },
    })
    rows.value = Array.isArray(data?.items) ? data.items : []
    rewardOptions.value = Array.isArray(data?.reward_options) ? data.reward_options : []
    statusStats.value = data?.status_stats || {}
    pagination.value = data?.pagination || { total: rows.value.length, page: currentPage.value, total_pages: 1 }
  } catch (error) {
    errorText.value = String(error?.message || "加载推广审核列表失败")
  }
}

async function switchScene(value) {
  activeScene.value = value
  activeStatus.value = ""
  currentPage.value = 1
  await loadData()
}

async function changePage(page) {
  currentPage.value = page
  await loadData()
}

async function reviewRow(row, nextStatus) {
  if (!canReview.value || reviewingId.value) return
  if (nextStatus === "approved") {
    if (activeScene.value === "like") {
      openRewardDialog(row)
      return
    }
    await submitReview(row, nextStatus, { reward_option_key: row?.tier_key || firstRewardOptionKey() })
    return
  }
  await submitReview(row, nextStatus, {})
}

async function submitReview(row, nextStatus, extraPayload = {}) {
  const actionLabel = nextStatus === "approved" ? "通过" : "驳回"
  const reviewNote = window.prompt(`请输入${actionLabel}备注（可留空）`, row.review_note || "")
  if (reviewNote === null) return
  reviewingId.value = row.id
  hintText.value = ""
  errorText.value = ""
  try {
    const endpoint =
      activeScene.value === "like"
        ? `/admin/promo/like-submissions/${row.id}/review`
        : `/admin/promo/create-submissions/${row.id}/review`
    const data = await adminHttp.post(endpoint, { status: nextStatus, review_note: reviewNote, ...extraPayload })
    upsertRow(data?.item)
    hintText.value = `${actionLabel}成功`
    closeRewardDialog()
    await loadData()
  } catch (error) {
    errorText.value = String(error?.message || `${actionLabel}失败`)
  } finally {
    reviewingId.value = null
  }
}

async function copyText(value, successMessage) {
  const text = String(value || "").trim()
  if (!text) return
  try {
    await navigator.clipboard.writeText(text)
    hintText.value = successMessage
    errorText.value = ""
  } catch (error) {
    errorText.value = String(error?.message || "复制失败")
  }
}

function upsertRow(item) {
  if (!item || typeof item.id !== "number") return
  const next = [item, ...rows.value.filter((row) => row.id !== item.id)]
  rows.value = next
}

function openRewardDialog(row) {
  rewardDialog.value = {
    open: true,
    row,
    title: "选择集赞奖励档位",
    subtitle: `${row?.user_nickname || "该用户"} · ${row?.original_filename || "截图记录"}`,
    selectedKey: row?.reward_option_key || "",
  }
}

function closeRewardDialog() {
  rewardDialog.value = {
    open: false,
    row: null,
    title: "",
    subtitle: "",
    selectedKey: "",
  }
}

async function confirmApprovedReview() {
  if (!rewardDialog.value.row || !rewardDialog.value.selectedKey) return
  await submitReview(rewardDialog.value.row, "approved", { reward_option_key: rewardDialog.value.selectedKey })
}

function firstRewardOptionKey() {
  return rewardOptions.value[0]?.key || ""
}

function openLink(link) {
  const value = String(link || "").trim()
  if (!value) return
  window.open(value, "_blank", "noopener,noreferrer")
}

async function previewScreenshot(row) {
  const id = Number(row?.id || 0)
  if (!id) return
  errorText.value = ""
  hintText.value = ""
  try {
    const resp = await adminHttp.get(`/admin/promo/like-submissions/${id}/screenshot`, { responseType: "blob" })
    const contentType = resp?.headers?.["content-type"] || "image/png"
    const blob = resp?.data instanceof Blob ? resp.data : new Blob([resp.data], { type: contentType })
    if (previewDialog.value.url) {
      window.URL.revokeObjectURL(previewDialog.value.url)
    }
    previewDialog.value = {
      open: true,
      url: window.URL.createObjectURL(blob),
      title: row?.original_filename || `截图 #${id}`,
    }
  } catch (error) {
    errorText.value = String(error?.message || "截图预览失败")
  }
}

async function downloadScreenshot(row) {
  const id = Number(row?.id || 0)
  if (!id) return
  errorText.value = ""
  hintText.value = ""
  try {
    const resp = await adminHttp.get(`/admin/promo/like-submissions/${id}/screenshot`, { responseType: "blob" })
    downloadAxiosBlobResponse(resp, row?.original_filename || `promo_like_${id}`)
    hintText.value = "截图已开始下载"
  } catch (error) {
    errorText.value = String(error?.message || "截图下载失败")
  }
}

function closePreview() {
  if (previewDialog.value.url) {
    window.URL.revokeObjectURL(previewDialog.value.url)
  }
  previewDialog.value = { open: false, url: "", title: "" }
}

function platformLabel(row) {
  const key = String(row?.platform || "").trim()
  if (activeScene.value === "like" && key === "wechat") return "微信集赞"
  if (key === "xiaohongshu") return "小红书"
  if (key === "douyin") return "抖音"
  if (key === "kuaishou") return "快手"
  if (key === "bilibili") return "B站"
  return key || "-"
}

function primaryContent(row) {
  if (activeScene.value === "like") return row.original_filename || "未命名截图"
  return row.share_link || "-"
}

function secondaryContent(row) {
  if (activeScene.value === "like") return row.share_text || row.screenshot_path || "-"
  return [row.tier_key, row.note || row.payout_name || row.payout_account || "-"].filter(Boolean).join(" · ")
}

function rewardLabel(row) {
  if (Number(row?.reward_credits || 0) > 0) {
    return `${Number(row.reward_credits || 0).toLocaleString()} 点`
  }
  return "未确定"
}

function benefitLabel(row) {
  if (row?.benefit_granted_at) {
    return `已发放 · ${formatTime(row.benefit_granted_at)}`
  }
  if (String(row?.benefit_status || "").trim()) {
    return String(row.benefit_status)
  }
  return "未发放"
}

function statusLabel(value) {
  const key = String(value || "").trim().toLowerCase()
  return {
    pending: "待审核",
    submitted: "待审核",
    approved: "已通过",
    rejected: "已驳回",
  }[key] || key || "-"
}

function statusBadgeClass(value) {
  const key = String(value || "").trim().toLowerCase()
  if (key === "approved") return "scholar-badge--success"
  if (key === "rejected") return "scholar-badge--danger"
  return "scholar-badge--warn"
}

function formatTime(value) {
  return value ? String(value).slice(0, 19).replace("T", " ") : "-"
}
</script>

<style scoped>
.gw-promo-review-overview {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) repeat(3, minmax(0, 0.62fr));
  gap: 14px;
  margin-bottom: 16px;
}

.gw-promo-review-overview__hero,
.gw-promo-review-overview__stat,
.gw-promo-review-card {
  border: 1px solid rgba(30, 91, 223, 0.12);
  border-radius: 22px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 255, 0.94));
  box-shadow: 0 16px 30px rgba(30, 91, 223, 0.08);
}

.gw-promo-review-overview__hero {
  padding: 20px 22px;
  display: grid;
  gap: 8px;
}

.gw-promo-review-overview__eyebrow {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #6c87ac;
}

.gw-promo-review-overview__hero h2 {
  margin: 0;
  font-size: 28px;
  line-height: 1.1;
  color: #1f3555;
}

.gw-promo-review-overview__hero p,
.gw-promo-review-cell-sub,
.gw-promo-review-card__sub {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #6883a7;
}

.gw-promo-review-overview__stat {
  padding: 18px 20px;
  display: grid;
  gap: 10px;
  align-content: center;
}

.gw-promo-review-overview__stat span,
.gw-promo-review-card__body span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #6983a7;
}

.gw-promo-review-overview__stat strong {
  font-size: 28px;
  line-height: 1;
  color: #18345c;
}

.gw-promo-review-overview__stat em {
  font-style: normal;
  font-size: 13px;
  color: #5f7798;
}

.gw-promo-review-tabs,
.gw-promo-review-toolbar,
.gw-promo-review-status-filters,
.gw-promo-review-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.gw-promo-review-tab,
.gw-promo-review-status-btn {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(30, 91, 223, 0.12);
  background: #fff;
  color: #23446f;
  font-weight: 700;
}

.gw-promo-review-tab.is-active,
.gw-promo-review-status-btn.is-active {
  border-color: rgba(30, 91, 223, 0.42);
  background: rgba(30, 91, 223, 0.08);
  color: #1246ad;
}

.gw-promo-review-toolbar {
  margin-top: 18px;
  align-items: center;
}

.gw-promo-review-cell-title,
.gw-promo-review-card__title {
  font-weight: 700;
  color: #1f3555;
}

.gw-promo-review-card {
  padding: 16px;
  display: grid;
  gap: 14px;
}

.gw-promo-review-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.gw-promo-review-card__body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.gw-promo-review-card__body strong {
  display: block;
  margin-top: 4px;
  color: #18345c;
  word-break: break-all;
}

.gw-promo-review-mobile-list {
  display: none;
  margin-top: 18px;
  gap: 12px;
}

.gw-promo-review-pagination {
  margin-top: 18px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.gw-admin-btn--danger {
  border-color: rgba(210, 74, 74, 0.24);
  color: #b22f2f;
}

.gw-promo-preview {
  position: fixed;
  inset: 0;
  z-index: 120;
  padding: 24px;
  background: rgba(9, 20, 40, 0.58);
  display: grid;
  place-items: center;
}

.gw-promo-preview__panel {
  width: min(920px, 100%);
  max-height: calc(100vh - 48px);
  border-radius: 22px;
  background: #fff;
  box-shadow: 0 24px 60px rgba(15, 40, 90, 0.24);
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  overflow: hidden;
}

.gw-promo-preview__head {
  padding: 16px 18px;
  border-bottom: 1px solid rgba(30, 91, 223, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.gw-promo-preview__head strong {
  color: #1f3555;
}

.gw-promo-preview__body {
  padding: 18px;
  overflow: auto;
  background: #f5f8fd;
  display: grid;
  place-items: center;
}

.gw-promo-preview__body img {
  display: block;
  max-width: 100%;
  height: auto;
  border-radius: 16px;
  box-shadow: 0 10px 24px rgba(15, 40, 90, 0.12);
}

.gw-promo-reward-panel {
  width: min(640px, 100%);
}

.gw-promo-reward-panel__body {
  padding: 18px;
  display: grid;
  gap: 16px;
}

.gw-promo-reward-options {
  display: grid;
  gap: 12px;
}

.gw-promo-reward-option {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(30, 91, 223, 0.12);
  background: #f8fbff;
}

.gw-promo-reward-option strong,
.gw-promo-reward-option span {
  display: block;
}

.gw-promo-reward-option strong {
  color: #1f3555;
}

.gw-promo-reward-option span {
  margin-top: 4px;
  font-size: 13px;
  color: #6b86a8;
}

.gw-promo-reward-panel__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 1024px) {
  .gw-promo-review-overview {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 768px) {
  .gw-promo-review-overview,
  .gw-promo-review-card__body {
    grid-template-columns: 1fr;
  }

  .gw-promo-review-mobile-list {
    display: grid;
  }

  .overflow-x-auto {
    display: none;
  }

  .gw-promo-review-pagination {
    flex-direction: column;
    align-items: stretch;
  }

  .gw-promo-preview {
    padding: 12px;
  }

  .gw-promo-reward-panel__actions {
    flex-direction: column;
  }
}
</style>
