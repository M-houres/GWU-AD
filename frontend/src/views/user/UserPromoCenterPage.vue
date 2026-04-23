<template>
  <UserShell
    title="推广中心"
    subtitle="通过专属邀请链接邀请好友注册，双方奖励积分由后台统一配置。"
    :credits="userCredits"
    :hide-topbar="true"
    :hide-header-title="true"
    :disable-notice-dialog="true"
    @buy="showBuy = !showBuy"
  >
    <section class="promo-page">
      <p v-if="errorText" class="aigc-alert aigc-alert--danger">{{ errorText }}</p>
      <p v-if="hintText" class="aigc-alert aigc-alert--success">{{ hintText }}</p>

      <section class="aigc-page-head promo-head">
        <div class="promo-head__title-wrap">
          <h2 class="aigc-page-head__title">推广中心</h2>
          <p class="aigc-page-head__quota">
            邀请好友注册并填写邀请码，邀请人与被邀请人可各得 <strong>{{ rewardPointsLabel }}</strong>。
          </p>
        </div>
        <button type="button" class="promo-head__refresh" :disabled="loading" @click="loadData">
          {{ loading ? "加载中..." : "刷新数据" }}
        </button>
      </section>
      <div class="aigc-page-head__divider" aria-hidden="true"></div>

      <section class="promo-panel">
        <header class="promo-panel__head">
          <h3>好友邀请奖励</h3>
          <p>分享专属邀请链接，被邀请人注册后填写邀请码即可参与奖励。</p>
        </header>

        <div class="promo-invite-grid">
          <article class="promo-metric-card">
            <span>当前奖励积分</span>
            <strong>{{ rewardPointsLabel }}</strong>
            <em>邀请人与被邀请人各得</em>
          </article>

          <article class="promo-metric-card">
            <span>专属邀请码</span>
            <strong>{{ inviteCode || "登录后生成" }}</strong>
            <button type="button" :disabled="!inviteCode" @click="copyText(inviteCode, '邀请码已复制')">复制邀请码</button>
          </article>

          <article class="promo-metric-card">
            <span>专属邀请链接</span>
            <strong class="promo-link-value">{{ inviteLink || "登录后生成" }}</strong>
            <button type="button" :disabled="!inviteLink" @click="copyText(inviteLink, '邀请链接已复制')">复制链接</button>
          </article>
        </div>
      </section>

      <section class="promo-panel">
        <header class="promo-panel__head">
          <h3>机构客户合作区</h3>
          <p>电话、微信号、邮箱均支持后台配置多个联系人。</p>
        </header>

        <div class="promo-contact-grid">
          <article class="promo-contact-card">
            <h4>电话</h4>
            <ul>
              <li v-for="item in contactPhones" :key="`phone-${item}`">{{ item }}</li>
              <li v-if="contactPhones.length === 0" class="is-empty">暂未配置</li>
            </ul>
          </article>

          <article class="promo-contact-card">
            <h4>微信号</h4>
            <ul>
              <li v-for="item in contactWechat" :key="`wechat-${item}`">{{ item }}</li>
              <li v-if="contactWechat.length === 0" class="is-empty">暂未配置</li>
            </ul>
          </article>

          <article class="promo-contact-card">
            <h4>邮箱</h4>
            <ul>
              <li v-for="item in contactEmail" :key="`email-${item}`">{{ item }}</li>
              <li v-if="contactEmail.length === 0" class="is-empty">暂未配置</li>
            </ul>
          </article>
        </div>
      </section>
    </section>

    <BuyCreditsPanel v-if="showBuy" @paid="afterPaid" />
  </UserShell>
</template>

<script setup>
import { computed, ref } from "vue"

import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { userHttp } from "../../lib/http"
import { getUserToken } from "../../lib/session"

const showBuy = ref(false)
const loading = ref(false)
const errorText = ref("")
const hintText = ref("")
const inviteCode = ref("")
const promoConfig = ref({
  enabled: true,
  invite_reward_points: 2000,
  contacts: {
    phone: [],
    wechat: [],
    email: [],
  },
})

const { user, refreshUser } = useUserProfile()
const userCredits = computed(() => {
  const value = user.value && (user.value.balance_fen ?? user.value.credits)
  return typeof value === "number" ? value : null
})
const rewardPoints = computed(() => Math.max(0, Number(promoConfig.value?.invite_reward_points || 0)))
const rewardPointsLabel = computed(() => `${rewardPoints.value.toLocaleString()} 积分`)
const inviteLink = computed(() => {
  if (!inviteCode.value) return ""
  if (typeof window === "undefined") return ""
  const base = `${window.location.origin}/register`
  return `${base}?invite_code=${encodeURIComponent(inviteCode.value)}`
})
const contactPhones = computed(() => normalizeContactList(promoConfig.value?.contacts?.phone))
const contactWechat = computed(() => normalizeContactList(promoConfig.value?.contacts?.wechat))
const contactEmail = computed(() => normalizeContactList(promoConfig.value?.contacts?.email))

void initialize()

async function initialize() {
  try {
    await refreshUser()
  } catch {
    // ignore profile refresh errors; promo data can still load independently
  }
  await loadData()
}

async function loadData() {
  loading.value = true
  errorText.value = ""
  hintText.value = ""
  try {
    const options = await userHttp.get("/auth/options")
    promoConfig.value = normalizePromoConfig(options?.promo_center)
    if (getUserToken()) {
      const invite = await userHttp.get("/users/me/invite")
      inviteCode.value = String(invite?.invite_code || "").trim()
    } else {
      inviteCode.value = ""
    }
  } catch (error) {
    errorText.value = String(error?.message || "加载推广中心信息失败")
  } finally {
    loading.value = false
  }
}

async function copyText(value, successMessage) {
  const text = String(value || "").trim()
  if (!text) return
  hintText.value = ""
  errorText.value = ""
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      throw new Error("当前浏览器不支持直接复制")
    }
    hintText.value = successMessage
  } catch (error) {
    errorText.value = String(error?.message || "复制失败，请手动复制")
  }
}

async function afterPaid() {
  showBuy.value = false
  await refreshUser()
}

function normalizePromoConfig(raw) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    enabled: source.enabled !== false,
    invite_reward_points: normalizeInt(source.invite_reward_points, 2000),
    contacts: {
      phone: normalizeContactList(source?.contacts?.phone),
      wechat: normalizeContactList(source?.contacts?.wechat),
      email: normalizeContactList(source?.contacts?.email),
    },
  }
}

function normalizeContactList(values) {
  if (!Array.isArray(values)) return []
  const seen = new Set()
  const list = []
  for (const item of values) {
    const text = String(item || "").trim()
    if (!text) continue
    const key = text.toLowerCase()
    if (seen.has(key)) continue
    seen.add(key)
    list.push(text)
    if (list.length >= 20) break
  }
  return list
}

function normalizeInt(value, fallback) {
  const num = Number.parseInt(value, 10)
  if (!Number.isFinite(num)) return fallback
  return Math.max(0, Math.min(num, 100000))
}
</script>

<style scoped>
.promo-page {
  display: grid;
  gap: 16px;
}

.promo-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.promo-head__title-wrap {
  flex: 1;
  text-align: center;
}

.promo-head__refresh {
  min-height: 38px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid rgba(30, 91, 223, 0.24);
  background: rgba(30, 91, 223, 0.08);
  color: var(--primary);
  font-weight: 600;
  cursor: pointer;
}

.promo-head__refresh:disabled {
  opacity: 0.66;
  cursor: default;
}

.promo-panel {
  border-radius: 18px;
  border: 1px solid #d7e2ef;
  background: #fff;
  padding: 18px;
}

.promo-panel__head h3 {
  margin: 0;
  color: #17385f;
  font-size: 20px;
}

.promo-panel__head p {
  margin: 8px 0 0;
  color: #5a6f88;
  font-size: 13px;
  line-height: 1.7;
}

.promo-invite-grid {
  margin-top: 14px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.promo-metric-card {
  border-radius: 14px;
  border: 1px solid #dbe5f1;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  padding: 14px;
  display: grid;
  gap: 8px;
}

.promo-metric-card span {
  font-size: 12px;
  color: #60779b;
}

.promo-metric-card strong {
  font-size: 24px;
  line-height: 1.3;
  color: #13365d;
  word-break: break-all;
}

.promo-metric-card em {
  font-size: 12px;
  color: #5f738b;
  font-style: normal;
}

.promo-metric-card button {
  justify-self: start;
  min-height: 32px;
  border-radius: 10px;
  border: 1px solid rgba(30, 91, 223, 0.24);
  background: rgba(30, 91, 223, 0.08);
  color: var(--primary);
  padding: 0 10px;
  font-weight: 600;
  cursor: pointer;
}

.promo-metric-card button:disabled {
  opacity: 0.64;
  cursor: default;
}

.promo-link-value {
  font-size: 14px !important;
  line-height: 1.7;
}

.promo-contact-grid {
  margin-top: 14px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.promo-contact-card {
  border-radius: 14px;
  border: 1px solid #dbe5f1;
  background: #fff;
  padding: 14px;
}

.promo-contact-card h4 {
  margin: 0;
  color: #17385f;
  font-size: 18px;
}

.promo-contact-card ul {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.promo-contact-card li {
  border-radius: 10px;
  background: #f6f9ff;
  border: 1px solid #e1e9f4;
  padding: 8px 10px;
  color: #2d4768;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-all;
}

.promo-contact-card li.is-empty {
  color: #7289a5;
}

@media (max-width: 1100px) {
  .promo-invite-grid,
  .promo-contact-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .promo-head {
    flex-direction: column;
  }

  .promo-head__title-wrap {
    width: 100%;
  }
}
</style>
