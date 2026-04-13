<template>
  <AdminShell title="推广管理" subtitle="积分补贴、班级福利、分享红包审核">
    <section class="promo-admin">
      <p v-if="feedback.text" class="promo-admin__feedback" :class="`is-${feedback.tone}`">{{ feedback.text }}</p>

      <div class="promo-admin__stats">
        <article v-for="item in statCards" :key="item.label">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.note }}</small>
        </article>
      </div>

      <div class="promo-admin__grid">
        <section class="promo-admin__panel">
          <div class="promo-admin__head">
            <div>
              <div class="promo-admin__eyebrow">分享审核</div>
              <h3>待处理分享任务</h3>
            </div>
            <button type="button" class="promo-admin__link" @click="loadAll">刷新</button>
          </div>

          <div class="promo-admin__list">
            <article v-for="item in submissions" :key="item.id" class="promo-admin__item">
              <div>
                <strong>{{ item.platform_label }}</strong>
                <p>用户 #{{ item.user_id }} · {{ item.tier_key }} 档位</p>
                <p>{{ item.share_link }}</p>
                <p>支付宝号：{{ item.payout_account || "-" }}</p>
                <p>支付宝姓名：{{ item.payout_name || "-" }}</p>
                <p v-if="item.paid_at">打款时间：{{ formatTime(item.paid_at) }}</p>
                <p v-if="item.review_note">{{ item.review_note }}</p>
              </div>
              <div class="promo-admin__side">
                <span class="promo-admin__badge" :class="`is-${item.status}`">{{ item.status }}</span>
                <span v-if="item.payout_status && item.payout_status !== 'none'" class="promo-admin__badge" :class="`is-payout-${item.payout_status}`">
                  {{ item.payout_status === "paid" ? "已打款" : "待打款" }}
                </span>
                <small>{{ item.reward_amount_cny }} 元红包</small>
                <div class="promo-admin__actions" v-if="canManage">
                  <button v-if="item.status === 'submitted'" type="button" @click="review(item, 'approved')">通过</button>
                  <button v-if="item.status === 'submitted'" type="button" class="is-muted" @click="review(item, 'rejected')">驳回</button>
                  <button v-if="item.status === 'approved' && item.payout_status !== 'paid'" type="button" @click="markPaid(item)">标记已打款</button>
                </div>
              </div>
            </article>
            <div v-if="!submissions.length" class="promo-admin__empty">暂无分享审核记录</div>
          </div>
        </section>

        <section class="promo-admin__panel">
          <div class="promo-admin__head">
            <div>
              <div class="promo-admin__eyebrow">班级福利</div>
              <h3>班级活跃榜</h3>
            </div>
          </div>

          <div class="promo-admin__list">
            <article v-for="item in classrooms" :key="item.id" class="promo-admin__item">
              <div>
                <strong>{{ item.name }}</strong>
                <p>{{ item.level }} · {{ item.member_count }} 人</p>
                <p>邀请码：{{ item.invite_code }}</p>
              </div>
              <div class="promo-admin__side">
                <span class="promo-admin__badge is-current">活跃度 {{ item.activity_score }}</span>
              </div>
            </article>
            <div v-if="!classrooms.length" class="promo-admin__empty">暂无班级数据</div>
          </div>
        </section>
      </div>
    </section>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

const stats = reactive({
  classroom_count: 0,
  share_submission_count: 0,
  pending_share_count: 0,
  pending_payout_count: 0,
  pending_payout_amount: 0,
  paid_cash_total: 0,
})

const submissions = ref([])
const classrooms = ref([])
const feedback = reactive({ text: "", tone: "info" })
const canManage = computed(() => adminHasPermission("referrals:manage"))

const statCards = computed(() => [
  { label: "活跃班级", value: stats.classroom_count, note: "当前活动班级数" },
  { label: "分享提交", value: stats.share_submission_count, note: "累计分享审核记录" },
  { label: "待审核", value: stats.pending_share_count, note: "当前待处理红包任务" },
  { label: "待打款", value: `${stats.pending_payout_amount || 0} 元`, note: `${stats.pending_payout_count || 0} 条已审核待发放` },
  { label: "已打款", value: `${stats.paid_cash_total || 0} 元`, note: "已人工发放完成的红包总额" },
])

onMounted(loadAll)

async function loadAll() {
  const [statData, shareData, classData] = await Promise.all([
    adminHttp.get("/admin/referrals/stats"),
    adminHttp.get("/admin/referrals/share-tasks", { params: { page: 1, page_size: 50 } }),
    adminHttp.get("/admin/referrals/suspicious", { params: { page: 1, page_size: 20 } }),
  ])
  Object.assign(stats, statData)
  submissions.value = shareData.items || []
  classrooms.value = classData.items || []
}

async function review(item, status) {
  try {
    await adminHttp.post(`/admin/referrals/share-tasks/${item.id}/review`, { status, review_note: status === "approved" ? "审核通过" : "内容不符合活动要求" })
    feedback.text = status === "approved" ? "分享任务已审核通过" : "分享任务已驳回"
    feedback.tone = status === "approved" ? "ok" : "error"
    await loadAll()
  } catch (error) {
    feedback.text = String(error?.message || "审核失败")
    feedback.tone = "error"
  }
}

async function markPaid(item) {
  try {
    await adminHttp.post(`/admin/referrals/share-tasks/${item.id}/payout`, { payout_note: "已人工打款" })
    feedback.text = "红包已标记为人工打款完成"
    feedback.tone = "ok"
    await loadAll()
  } catch (error) {
    feedback.text = String(error?.message || "标记打款失败")
    feedback.tone = "error"
  }
}

function formatTime(value) {
  if (!value) return "-"
  return String(value).replace("T", " ").slice(0, 19)
}
</script>

<style scoped>
.promo-admin{display:grid;gap:18px}
.promo-admin__feedback{margin:0;padding:12px 16px;border-radius:16px;background:#fff;border:1px solid #d7e1ef;color:#14345f}
.promo-admin__feedback.is-ok{color:#0f6f56}
.promo-admin__feedback.is-error{color:#b24439}
.promo-admin__stats{display:grid;gap:12px;grid-template-columns:repeat(5,minmax(0,1fr))}
.promo-admin__stats article,.promo-admin__panel{padding:18px;border-radius:24px;border:1px solid #d7e1ef;background:#fff;box-shadow:0 20px 40px rgba(17,53,116,.06)}
.promo-admin__stats span,.promo-admin__eyebrow{color:#7487a6;font-size:11px;letter-spacing:.14em;text-transform:uppercase}
.promo-admin__stats strong{display:block;margin-top:8px;color:#10294b;font-size:28px}
.promo-admin__stats small{display:block;margin-top:6px;color:#5d7393;font-size:12px;line-height:1.7}
.promo-admin__grid{display:grid;gap:18px;grid-template-columns:repeat(2,minmax(0,1fr))}
.promo-admin__head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}
.promo-admin__head h3{margin:4px 0 0;color:#10294b;font-size:26px;line-height:1.1}
.promo-admin__link{border:0;background:transparent;color:#1e5bdf;font-size:13px;font-weight:700;cursor:pointer}
.promo-admin__list{display:grid;gap:12px}
.promo-admin__item{display:flex;justify-content:space-between;gap:12px;padding:16px;border-radius:18px;border:1px solid #e3eaf3;background:#fbfdff}
.promo-admin__item strong{color:#14345f}
.promo-admin__item p{margin:6px 0 0;color:#5d7393;font-size:12px;line-height:1.7;word-break:break-all}
.promo-admin__side{display:grid;gap:8px;justify-items:end}
.promo-admin__badge{width:fit-content;min-height:28px;padding:0 12px;border-radius:999px;display:inline-flex;align-items:center;background:rgba(30,91,223,.12);color:#1e5bdf;font-size:12px;font-weight:700}
.promo-admin__badge.is-approved{background:rgba(16,122,95,.12);color:#0f6f56}
.promo-admin__badge.is-rejected{background:rgba(186,68,57,.12);color:#b24439}
.promo-admin__badge.is-payout-pending{background:rgba(217,119,6,.12);color:#b45309}
.promo-admin__badge.is-payout-paid{background:rgba(16,122,95,.12);color:#0f6f56}
.promo-admin__actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.promo-admin__actions button{min-height:32px;padding:0 12px;border-radius:999px;border:1px solid rgba(30,91,223,.18);background:rgba(30,91,223,.08);color:#1e5bdf;font-size:12px;font-weight:700;cursor:pointer}
.promo-admin__actions .is-muted{background:rgba(244,247,252,.98);color:#6c809d}
.promo-admin__empty{padding:16px;border-radius:18px;background:#f7faff;color:#6c809d;font-size:13px}
@media (max-width: 1100px){.promo-admin__stats,.promo-admin__grid{grid-template-columns:1fr 1fr}}
@media (max-width: 720px){.promo-admin__stats,.promo-admin__grid{grid-template-columns:1fr}.promo-admin__item,.promo-admin__head{flex-direction:column;align-items:stretch}.promo-admin__side{justify-items:start}.promo-admin__actions{justify-content:flex-start}}
</style>
