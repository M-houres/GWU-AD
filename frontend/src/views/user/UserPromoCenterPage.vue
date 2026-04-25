<template>
  <UserShell
    title="推广中心"
    subtitle="参与活动，领取点数奖励"
    :credits="userCredits"
    :hide-topbar="true"
    :hide-header-title="true"
    :disable-notice-dialog="true"
    @buy="showBuy = !showBuy"
  >
    <section class="promo-page">
      <p v-if="errorText" class="aigc-alert aigc-alert--danger">{{ errorText }}</p>
      <p v-if="hintText" class="aigc-alert aigc-alert--success">{{ hintText }}</p>

      <section class="promo-tabs">
        <button
          v-for="card in enabledCards"
          :key="card.key"
          type="button"
          class="promo-tab"
          :class="{ 'promo-tab--active': card.key === activeTab }"
          @click="selectTab(card.key)"
        >
          <span>{{ card.badge || "活动" }}</span>
          <strong>{{ card.title }}</strong>
          <em>{{ card.description }}</em>
        </button>
      </section>

      <section v-if="currentPage" class="promo-banner">
        <div>
          <h3>{{ currentPage.title }}</h3>
          <p>{{ currentPage.subtitle }}</p>
        </div>
        <span class="promo-banner__pill">{{ currentCard?.badge || "活动中" }}</span>
      </section>

      <template v-if="activeTab === 'invite'">
        <section class="promo-layout">
          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>奖励概览</h4>
            </div>
            <div class="promo-grid promo-grid--3">
              <article class="promo-stat-card">
                <span>被邀请人奖励</span>
                <strong>{{ formatPoints(inviteRules.invitee_bind_reward_points) }}</strong>
                <em>完成绑定后发放</em>
              </article>
              <article class="promo-stat-card">
                <span>邀请人奖励</span>
                <strong>{{ formatPoints(inviteRules.inviter_valid_invite_reward_points) }}</strong>
                <em>每个有效邀请获得</em>
              </article>
              <article class="promo-stat-card">
                <span>里程碑加奖</span>
                <strong>{{ inviteRules.milestones.length }} 档</strong>
                <em>邀请越多，奖励越高</em>
              </article>
            </div>
            <div v-if="inviteRules.milestones.length" class="promo-badge-row">
              <strong v-for="(item, index) in inviteRules.milestones" :key="`invite-milestone-${index}`">
                {{ item.label || `${item.threshold} 人` }} +{{ formatPoints(item.reward_points) }}
              </strong>
            </div>
          </section>

          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>活动规则</h4>
            </div>
            <div class="promo-chip-grid promo-chip-grid--rules">
              <article v-for="(item, index) in invitePage.rule_lines" :key="`invite-rule-${index}`" class="promo-chip">
                {{ item }}
              </article>
            </div>
            <div class="promo-chip-grid promo-chip-grid--steps">
              <article v-for="(step, index) in invitePage.miniapp_steps" :key="`invite-step-${index}`" class="promo-step-card">
                <span>STEP {{ index + 1 }}</span>
                <strong>{{ step }}</strong>
              </article>
            </div>
          </section>

          <section class="promo-section promo-section--span-2">
          <div class="promo-section__head">
            <h4>{{ invitePage.quick_actions_title }}</h4>
          </div>
          <div class="promo-action-list">
            <article class="promo-action-row">
              <div class="promo-action-row__copy">
                <span>{{ invitePage.bind_code_label }}</span>
                <strong>邀请码填写入口即将开放</strong>
              </div>
              <div class="promo-action-row__controls">
                <input v-model.trim="bindInviteCodeValue" :placeholder="invitePage.bind_code_placeholder" />
                <button type="button" disabled @click="bindInviteCode">{{ invitePage.bind_code_button_text }}</button>
              </div>
            </article>

            <article class="promo-action-row">
              <div class="promo-action-row__copy">
                <span>我的邀请码</span>
                <strong>{{ inviteCode || "登录后生成" }}</strong>
              </div>
              <div class="promo-action-row__controls">
                <button type="button" :disabled="!inviteCode" @click="copyText(inviteCode, '邀请码已复制')">复制邀请码</button>
              </div>
            </article>

            <article class="promo-action-row">
              <div class="promo-action-row__copy">
                <span>分享链接</span>
                <strong class="promo-action-row__wide">{{ inviteLink || "登录后生成" }}</strong>
              </div>
              <div class="promo-action-row__controls">
                <button type="button" :disabled="!inviteLink" @click="copyText(inviteLink, '邀请链接已复制')">复制链接</button>
              </div>
            </article>

            <article class="promo-action-row">
              <div class="promo-action-row__copy">
                <span>{{ invitePage.share_copy_title }}</span>
                <strong class="promo-action-row__wide">{{ invitePage.share_copy_text }}</strong>
              </div>
              <div class="promo-action-row__controls">
                <button type="button" @click="copyText(invitePage.share_copy_text, '分享文案已复制')">复制文案</button>
              </div>
            </article>
          </div>
          </section>
        </section>
      </template>

      <template v-else-if="activeTab === 'like'">
        <section class="promo-layout">
          <section class="promo-section promo-section--span-2 promo-section--compact">
            <div class="promo-section__head">
              <h4>活动流程</h4>
            </div>
            <div class="promo-grid promo-grid--4">
              <article v-for="(item, index) in likeFlow" :key="`like-flow-${index}`" class="promo-flow-card">
                <span>0{{ index + 1 }}</span>
                <strong>{{ item.title }}</strong>
                <em>{{ item.desc }}</em>
              </article>
            </div>
          </section>

          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>活动规则</h4>
            </div>
            <div class="promo-chip-grid">
              <article v-for="(item, index) in likePage.rule_lines" :key="`like-rule-${index}`" class="promo-chip promo-chip--accent">
                {{ item }}
              </article>
            </div>
            <div class="promo-tier-grid">
              <article v-for="(item, index) in likeRules.tiers" :key="`like-tier-${index}`" class="promo-tier-card promo-tier-card--accent">
                <span>{{ item.label || `${item.threshold} 赞` }}</span>
                <strong>{{ formatPoints(item.reward_points) }}</strong>
              </article>
            </div>
          </section>

          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>{{ likePage.qrcode_title }}</h4>
            </div>
            <div class="promo-qrcode-layout">
              <div class="promo-qrcode-box">
                <img v-if="promoConfig.assets.like_qrcode_url" :src="promoConfig.assets.like_qrcode_url" alt="集赞活动二维码" />
                <strong v-else>活动二维码即将上线</strong>
              </div>
              <div class="promo-qrcode-side">
                <p>{{ likePage.review_notice }}</p>
                <button type="button" class="promo-primary" disabled @click="submitPlaceholder('like')">提交截图</button>
              </div>
            </div>
          </section>

          <section v-if="likePage.other_entries.length" class="promo-section promo-section--span-2">
            <div class="promo-section__head">
              <h4>{{ likePage.other_entries_title }}</h4>
            </div>
            <div class="promo-entry-grid">
              <article v-for="(entry, index) in visibleLikeEntries" :key="`like-entry-${index}`" class="promo-entry-card">
                <div>
                  <strong>{{ entry.title || "更多活动" }}</strong>
                  <p>{{ entry.description || "查看活动详情" }}</p>
                </div>
                <img v-if="entry.qrcode_url" :src="entry.qrcode_url" :alt="entry.title || '活动二维码'" />
              </article>
            </div>
          </section>
        </section>
      </template>

      <template v-else-if="activeTab === 'create'">
        <section class="promo-layout">
          <section class="promo-section promo-section--span-2 promo-section--compact">
            <div class="promo-section__head">
              <h4>参与平台</h4>
            </div>
            <div class="promo-grid promo-grid--5">
              <article
                v-for="platform in createPage.platforms"
                :key="platform.key"
                class="promo-platform-card"
                :class="{ 'promo-platform-card--disabled': !platform.enabled }"
              >
                <strong>{{ platform.label }}</strong>
                <span>{{ platform.status_text }}</span>
              </article>
            </div>
          </section>

          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>奖励规则</h4>
              <span class="promo-banner__pill">最高 {{ maxCreateRewardLabel }}</span>
            </div>
            <div class="promo-chip-grid">
              <article v-for="(item, index) in createPage.rule_lines" :key="`create-rule-${index}`" class="promo-chip">
                {{ item }}
              </article>
            </div>
            <div class="promo-tier-grid">
              <article v-for="(item, index) in createRules.tiers" :key="`create-tier-${index}`" class="promo-tier-card">
                <span>{{ item.label || `${item.threshold}+` }}</span>
                <strong>{{ formatPoints(item.reward_points) }}</strong>
              </article>
            </div>
            <div class="promo-submit-row">
              <input v-model.trim="createSubmissionUrl" :placeholder="createPage.submit_placeholder" />
              <button type="button" class="promo-primary" disabled @click="submitPlaceholder('create')">{{ createPage.submit_button_text }}</button>
              <button type="button" class="promo-secondary" disabled @click="openSubmissionHistory">{{ createPage.history_button_text }}</button>
            </div>
          </section>

          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>{{ createPage.template_title }}</h4>
            </div>
            <div class="promo-template-box">{{ currentTemplate }}</div>
            <div class="promo-button-row">
              <button type="button" class="promo-secondary" @click="rotateTemplate">换个文案</button>
              <button type="button" class="promo-primary" @click="copyText(currentTemplate, '创作文案已复制')">一键复制</button>
            </div>
          </section>
        </section>
      </template>

      <template v-else-if="activeTab === 'partner'">
        <section class="promo-layout">
          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>合作说明</h4>
            </div>
            <p class="promo-detail">{{ partnerPage.description }}</p>
            <div class="promo-chip-grid">
              <article v-for="(item, index) in partnerPage.benefits" :key="`partner-benefit-${index}`" class="promo-chip">
                {{ item }}
              </article>
            </div>
          </section>

          <section class="promo-section promo-section--compact promo-section--soft">
            <div class="promo-section__head">
              <h4>合作支持</h4>
            </div>
            <div class="promo-badge-row">
              <strong>校园大使合作</strong>
              <strong>机构批量采购</strong>
              <strong>品牌联合推广</strong>
              <strong>企业服务支持</strong>
            </div>
          </section>

          <section class="promo-section promo-section--span-2">
            <div class="promo-section__head">
              <h4>联系入口</h4>
            </div>
            <div class="promo-partner-grid">
              <article v-for="(item, index) in visiblePartnerContacts" :key="`partner-contact-${index}`" class="promo-partner-card">
                <div class="promo-partner-card__copy">
                  <span>{{ item.title }}</span>
                  <strong>{{ item.description }}</strong>
                  <em v-if="item.wechat_id">微信号：{{ item.wechat_id }}</em>
                </div>
                <div class="promo-partner-card__qr">
                  <img v-if="item.qrcode_url" :src="item.qrcode_url" :alt="item.title || '合作二维码'" />
                  <strong v-else>二维码即将上线</strong>
                </div>
              </article>
            </div>
          </section>
        </section>
      </template>
    </section>

    <BuyCreditsPanel v-if="showBuy" @paid="afterPaid" />
  </UserShell>
</template>

<script setup>
import { computed, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { normalizePromotionCenterConfig, DEFAULT_PROMO_CENTER_CONFIG } from "../../lib/adminConfig"
import { userHttp } from "../../lib/http"
import { getUserToken } from "../../lib/session"

const route = useRoute()
const router = useRouter()

const showBuy = ref(false)
const loading = ref(false)
const errorText = ref("")
const hintText = ref("")
const inviteCode = ref("")
const bindInviteCodeValue = ref("")
const createSubmissionUrl = ref("")
const currentTemplateIndex = ref(0)
const promoConfig = ref(normalizePromotionCenterConfig(DEFAULT_PROMO_CENTER_CONFIG))

const { user, refreshUser } = useUserProfile()
const userCredits = computed(() => {
  const value = user.value && (user.value.balance_fen ?? user.value.credits)
  return typeof value === "number" ? value : null
})

const enabledCards = computed(() => {
  const cards = Array.isArray(promoConfig.value?.nav_cards) ? promoConfig.value.nav_cards : []
  return cards.filter((item) => item?.enabled !== false)
})

const activeTab = computed(() => {
  const requested = String(route.query.tab || "").trim().toLowerCase()
  const keys = enabledCards.value.map((item) => item.key)
  if (requested && keys.includes(requested)) return requested
  return keys[0] || "invite"
})

const currentCard = computed(() => enabledCards.value.find((item) => item.key === activeTab.value) || null)
const currentPage = computed(() => promoConfig.value?.pages?.[activeTab.value] || null)
const invitePage = computed(() => promoConfig.value?.pages?.invite || DEFAULT_PROMO_CENTER_CONFIG.pages.invite)
const likePage = computed(() => promoConfig.value?.pages?.like || DEFAULT_PROMO_CENTER_CONFIG.pages.like)
const createPage = computed(() => promoConfig.value?.pages?.create || DEFAULT_PROMO_CENTER_CONFIG.pages.create)
const partnerPage = computed(() => promoConfig.value?.pages?.partner || DEFAULT_PROMO_CENTER_CONFIG.pages.partner)
const inviteRules = computed(() => promoConfig.value?.reward_rules?.invite || DEFAULT_PROMO_CENTER_CONFIG.reward_rules.invite)
const likeRules = computed(() => promoConfig.value?.reward_rules?.like || DEFAULT_PROMO_CENTER_CONFIG.reward_rules.like)
const createRules = computed(() => promoConfig.value?.reward_rules?.create || DEFAULT_PROMO_CENTER_CONFIG.reward_rules.create)
const visibleLikeEntries = computed(() => (Array.isArray(likePage.value?.other_entries) ? likePage.value.other_entries : []).filter((item) => item?.enabled !== false))
const visiblePartnerContacts = computed(() => (Array.isArray(partnerPage.value?.contacts) ? partnerPage.value.contacts : []).filter((item) => item?.enabled !== false))
const createTemplates = computed(() => {
  const list = Array.isArray(createPage.value?.templates) ? createPage.value.templates : []
  return list.length ? list : DEFAULT_PROMO_CENTER_CONFIG.pages.create.templates
})
const currentTemplate = computed(() => createTemplates.value[currentTemplateIndex.value % createTemplates.value.length] || "")
const maxCreateRewardLabel = computed(() => {
  const rewards = (Array.isArray(createRules.value?.tiers) ? createRules.value.tiers : []).map((item) => Number(item?.reward_points || 0))
  return formatPoints(Math.max(0, ...rewards))
})
const inviteLink = computed(() => {
  if (!inviteCode.value || typeof window === "undefined") return ""
  return `${window.location.origin}/register?invite_code=${encodeURIComponent(inviteCode.value)}`
})

const likeFlow = [
  { title: "扫码转发", desc: "保存活动码或海报后分享给好友。" },
  { title: "完成集赞", desc: "达到对应点赞数后保留完整截图。" },
  { title: "提交截图", desc: "按活动要求提交截图等待审核。" },
  { title: "领取点数", desc: "审核通过后按规则发放点数。" },
]

void initialize()

watch(
  () => route.query.tab,
  (value) => {
    const requested = String(value || "").trim().toLowerCase()
    const keys = enabledCards.value.map((item) => item.key)
    if (requested && !keys.includes(requested) && keys.length) {
      void selectTab(keys[0])
    }
  },
)

async function initialize() {
  try {
    await refreshUser()
  } catch {
    // ignore
  }
  await loadData()
}

async function loadData() {
  loading.value = true
  errorText.value = ""
  hintText.value = ""
  try {
    const options = await userHttp.get("/auth/options")
    promoConfig.value = normalizePromotionCenterConfig(options?.promo_center)
    if (getUserToken()) {
      const invite = await userHttp.get("/users/me/invite")
      inviteCode.value = String(invite?.invite_code || "").trim()
    } else {
      inviteCode.value = ""
    }
    const keys = enabledCards.value.map((item) => item.key)
    if (keys.length && !keys.includes(activeTab.value)) {
      await selectTab(keys[0])
    }
  } catch (error) {
    errorText.value = String(error?.message || "加载推广中心信息失败")
  } finally {
    loading.value = false
  }
}

async function selectTab(tab) {
  await router.replace({ path: "/app/promo-center", query: { ...route.query, tab } })
}

async function copyText(value, successMessage) {
  const text = String(value || "").trim()
  if (!text) return
  hintText.value = ""
  errorText.value = ""
  try {
    if (navigator?.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      hintText.value = successMessage
      return
    }
    throw new Error("当前浏览器不支持直接复制")
  } catch (error) {
    errorText.value = String(error?.message || "复制失败，请手动复制")
  }
}

function bindInviteCode() {
  hintText.value = ""
  errorText.value = "邀请码填写入口即将开放。"
}

function submitPlaceholder(type) {
  hintText.value = ""
  errorText.value = type === "like" ? "截图提交通道即将开放。" : "作品提交通道即将开放。"
}

function openSubmissionHistory() {
  hintText.value = ""
  errorText.value = "记录查询功能即将开放。"
}

function rotateTemplate() {
  if (!createTemplates.value.length) return
  currentTemplateIndex.value = (currentTemplateIndex.value + 1) % createTemplates.value.length
}

async function afterPaid() {
  showBuy.value = false
  await refreshUser()
}

function formatPoints(value) {
  return `${Math.max(0, Number(value || 0)).toLocaleString()} 点`
}
</script>

<style scoped>
.promo-page {
  display: grid;
  gap: 14px;
  font-family: var(--font-sans);
}
.promo-primary,
.promo-secondary,
.promo-action-row__controls button {
  min-height: 40px;
  padding: 0 14px;
  border-radius: 12px;
  font-weight: 700;
  cursor: pointer;
}

.promo-primary:disabled,
.promo-secondary:disabled,
.promo-action-row__controls button:disabled {
  opacity: 0.62;
  cursor: default;
}

.promo-tabs {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.promo-tab {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid #dbe5f1;
  background: #fff;
  text-align: left;
  cursor: pointer;
}

.promo-tab--active {
  border-color: var(--primary);
  background: var(--primary-gradient);
  box-shadow: 0 12px 28px rgba(30, 91, 223, 0.18);
}

.promo-tab span {
  display: block;
  font-size: 11px;
  color: var(--primary);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}

.promo-tab strong {
  display: block;
  margin-top: 6px;
  font-size: 16px;
  color: #17385f;
}

.promo-tab em {
  display: block;
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.55;
  color: #657c97;
  font-style: normal;
}

.promo-tab--active span,
.promo-tab--active strong,
.promo-tab--active em {
  color: #fff;
}

.promo-banner,
.promo-section,
.promo-tab {
  box-sizing: border-box;
}

.promo-banner {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid #dbe5f1;
  background: linear-gradient(180deg, #fafcff 0%, #ffffff 100%);
}

.promo-banner h3,
.promo-section__head h4 {
  margin: 0;
  color: #17385f;
  font-family: var(--font-display);
}

.promo-banner h3 {
  font-size: 24px;
}

.promo-banner p,
.promo-detail,
.promo-qrcode-side p,
.promo-entry-card p {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: #627a95;
}

.promo-banner__pill {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 13px;
  border-radius: 999px;
  background: var(--primary-light);
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
}

.promo-layout {
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.promo-section {
  padding: 16px 18px;
  border-radius: 18px;
  border: 1px solid #dbe5f1;
  background: #fff;
}

.promo-section--soft {
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
}

.promo-section--compact {
  height: 100%;
}

.promo-section--span-2 {
  grid-column: 1 / -1;
}

.promo-section__head {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
}

.promo-section__head h4 {
  font-size: 20px;
}

.promo-grid {
  display: grid;
  gap: 14px;
}

.promo-grid--2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.promo-grid--3 {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.promo-grid--4 {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.promo-grid--5 {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.promo-stat-card,
.promo-flow-card,
.promo-platform-card,
.promo-tier-card,
.promo-chip,
.promo-step-card,
.promo-entry-card,
.promo-partner-card,
.promo-badge-row strong {
  border: 1px solid #dbe5f1;
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
}

.promo-stat-card,
.promo-flow-card,
.promo-platform-card,
.promo-tier-card,
.promo-step-card,
.promo-entry-card,
.promo-partner-card {
  padding: 14px;
  border-radius: 16px;
}

.promo-stat-card span,
.promo-flow-card span,
.promo-tier-card span,
.promo-step-card span,
.promo-platform-card span,
.promo-partner-card__copy span {
  font-size: 12px;
  color: #60779b;
}

.promo-stat-card strong,
.promo-flow-card strong,
.promo-tier-card strong,
.promo-platform-card strong,
.promo-entry-card strong,
.promo-partner-card__copy strong {
  display: block;
  margin-top: 6px;
  color: #17385f;
}

.promo-stat-card strong {
  font-size: 24px;
  font-family: var(--font-display);
}

.promo-stat-card em,
.promo-flow-card em,
.promo-partner-card__copy em {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.7;
  color: #6f839b;
  font-style: normal;
}

.promo-chip-grid,
.promo-tier-grid,
.promo-badge-row,
.promo-entry-grid,
.promo-partner-grid {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.promo-chip-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.promo-chip-grid--steps {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.promo-tier-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.promo-entry-grid,
.promo-partner-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.promo-chip {
  padding: 10px 12px;
  border-radius: 16px;
  font-size: 12px;
  line-height: 1.65;
  color: #2f4763;
}

.promo-chip--accent,
.promo-tier-card--accent {
  border-color: rgba(30, 91, 223, 0.14);
  background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 100%);
}

.promo-step-card strong {
  display: block;
  margin-top: 6px;
  font-size: 14px;
  line-height: 1.65;
  color: #1f436b;
}

.promo-tier-card strong {
  font-size: 21px;
  font-family: var(--font-display);
}

.promo-badge-row {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.promo-badge-row strong {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  font-size: 12px;
  color: #1f436b;
}

.promo-action-list {
  margin-top: 12px;
  display: grid;
  gap: 10px;
}

.promo-action-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid #dbe5f1;
  background: linear-gradient(180deg, #fcfdff 0%, #ffffff 100%);
}

.promo-action-row__copy span {
  font-size: 12px;
  color: var(--primary);
  font-weight: 700;
}

.promo-action-row__copy strong {
  display: block;
  margin-top: 6px;
  font-size: 15px;
  line-height: 1.55;
  color: #17385f;
}

.promo-action-row__wide {
  word-break: break-all;
}

.promo-action-row__controls,
.promo-submit-row,
.promo-button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.promo-action-row__controls {
  justify-content: flex-end;
}

.promo-action-row__controls input,
.promo-submit-row input {
  flex: 1;
  min-width: 220px;
  min-height: 40px;
  padding: 0 12px;
  border-radius: 12px;
  border: 1px solid #d1dceb;
  background: #fff;
  color: #17385f;
  font-size: 14px;
  outline: none;
}

.promo-primary {
  border: 1px solid var(--primary);
  background: var(--primary-gradient);
  color: #fff;
  box-shadow: 0 10px 20px rgba(30, 91, 223, 0.14);
}

.promo-secondary {
  border: 1px solid rgba(30, 91, 223, 0.18);
  background: rgba(30, 91, 223, 0.06);
  color: var(--primary);
}

.promo-qrcode-layout {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 14px;
}

.promo-qrcode-box {
  min-height: 220px;
  border-radius: 18px;
  border: 1px dashed #cfdcec;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  display: grid;
  place-items: center;
  overflow: hidden;
}

.promo-qrcode-box img,
.promo-entry-card img,
.promo-partner-card__qr img {
  display: block;
  width: 100%;
  height: auto;
}

.promo-qrcode-side {
  display: grid;
  align-content: space-between;
  gap: 12px;
}

.promo-entry-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 96px;
  gap: 12px;
  align-items: center;
}

.promo-platform-card {
  text-align: center;
}

.promo-platform-card span {
  display: block;
  margin-top: 5px;
}

.promo-platform-card--disabled {
  opacity: 0.56;
}

.promo-template-box {
  margin-top: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  color: #24466f;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.promo-submit-row {
  margin-top: 12px;
}

.promo-detail {
  font-size: 13px;
}

.promo-partner-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 160px;
  gap: 12px;
  align-items: center;
}

.promo-partner-card__qr {
  min-height: 160px;
  border-radius: 16px;
  border: 1px dashed #cfdcec;
  background: #fff;
  display: grid;
  place-items: center;
  overflow: hidden;
}

@media (max-width: 1200px) {
  .promo-layout,
  .promo-tabs,
  .promo-grid--3,
  .promo-grid--4,
  .promo-grid--5,
  .promo-chip-grid,
  .promo-chip-grid--steps,
  .promo-badge-row,
  .promo-entry-grid,
  .promo-partner-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .promo-qrcode-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .promo-layout,
  .promo-banner,
  .promo-grid--2,
  .promo-grid--3,
  .promo-grid--4,
  .promo-grid--5,
  .promo-chip-grid,
  .promo-chip-grid--steps,
  .promo-tier-grid,
  .promo-badge-row,
  .promo-entry-grid,
  .promo-partner-grid {
    grid-template-columns: 1fr;
  }

  .promo-action-row,
  .promo-entry-card,
  .promo-partner-card {
    grid-template-columns: 1fr;
  }

  .promo-submit-row,
  .promo-button-row,
  .promo-action-row__controls {
    flex-direction: column;
    align-items: stretch;
  }

  .promo-action-row__controls input,
  .promo-submit-row input {
    min-width: 100%;
    width: 100%;
  }
}
</style>
