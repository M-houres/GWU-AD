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
            <div class="promo-grid promo-grid--3">
              <article class="promo-stat-card promo-stat-card--soft">
                <span>我的有效邀请</span>
                <strong>{{ inviteSummary.valid_invite_count }}</strong>
                <em>已成功计入奖励的人数</em>
              </article>
              <article class="promo-stat-card promo-stat-card--soft">
                <span>我已获得奖励</span>
                <strong>{{ formatPoints(inviteSummary.total_reward_points) }}</strong>
                <em>仅统计邀请活动已到账点数</em>
              </article>
              <article class="promo-stat-card promo-stat-card--soft">
                <span>下一档里程碑</span>
                <strong>{{ nextMilestoneLabel }}</strong>
                <em>{{ nextMilestoneHint }}</em>
              </article>
            </div>
            <div v-if="inviteRules.milestones.length" class="promo-badge-row">
              <strong v-for="(item, index) in inviteRules.milestones" :key="`invite-milestone-${index}`">
                {{ item.label || `${item.threshold} 人` }} +{{ formatPoints(item.reward_points) }}
              </strong>
            </div>
            <div v-if="inviteSummary.earned_milestones.length" class="promo-chip-grid">
              <article
                v-for="item in inviteSummary.earned_milestones"
                :key="`invite-earned-${item.threshold}`"
                class="promo-chip promo-chip--success"
              >
                已达成 {{ item.label }}，获得 {{ formatPoints(item.reward_points) }}
              </article>
            </div>
          </section>

          <section class="promo-section promo-section--compact">
            <div class="promo-section__head">
              <h4>活动规则</h4>
            </div>
            <div class="promo-chip-grid promo-chip-grid--rules">
              <article v-for="(item, index) in inviteDisplayRuleLines" :key="`invite-rule-${index}`" class="promo-chip">
                {{ item }}
              </article>
            </div>
            <div class="promo-section__head promo-section__head--sub">
              <h4>{{ inviteGuideTitle }}</h4>
            </div>
            <div class="promo-chip-grid promo-chip-grid--steps">
              <article v-for="(step, index) in inviteDisplaySteps" :key="`invite-step-${index}`" class="promo-step-card">
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
                <strong v-if="inviteBoundRelation">
                  已绑定 {{ inviteBoundRelation.inviter_nickname || inviteBoundRelation.inviter_phone || "邀请人" }}
                </strong>
                <strong v-else>{{ inviteBindNoticeText }}</strong>
              </div>
              <div class="promo-action-row__controls">
                <input
                  v-model.trim="inviteBindCode"
                  type="text"
                  maxlength="16"
                  placeholder="请输入好友邀请码"
                  :disabled="bindingInvite || !!inviteBoundRelation"
                />
                <button
                  type="button"
                  class="promo-primary"
                  :disabled="bindingInvite || !inviteBindCode || !!inviteBoundRelation"
                  @click="submitInviteBind"
                >
                  {{ bindingInvite ? "绑定中..." : "确认绑定" }}
                </button>
              </div>
              <div class="promo-action-row__meta">
                <em v-if="inviteBoundRelation">
                  绑定时间：{{ formatDateTime(inviteBoundRelation.created_at) }}，每个账号仅可绑定一次。
                </em>
                <em v-else>每个账号仅可绑定一次邀请码，绑定后不可更换。</em>
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
                <strong class="promo-action-row__wide">{{ inviteShareCopyText }}</strong>
              </div>
              <div class="promo-action-row__controls">
                <button type="button" @click="copyText(inviteShareCopyText, '分享文案已复制')">复制文案</button>
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
                <div class="promo-submit-card">
                  <strong>提交截图</strong>
                  <span class="promo-disabled-note">平台：{{ likePlatformLabel }}</span>
                  <div class="promo-submit-row">
                    <input
                      v-model.trim="likeShareText"
                      type="text"
                      maxlength="500"
                      placeholder="选填：补充说明或分享文案"
                    />
                  </div>
                  <div class="promo-submit-row">
                    <label class="promo-file-trigger">
                      <input class="promo-hidden-input" type="file" accept=".png,.jpg,.jpeg,.webp" @change="handleLikeFileChange" />
                      <span>{{ likeScreenshotName || "选择截图文件" }}</span>
                    </label>
                    <button
                      type="button"
                      class="promo-primary"
                      :disabled="likeSubmitting || !likeScreenshotFile"
                      @click="submitLikeSubmission"
                    >
                      {{ likeSubmitting ? "提交中..." : "提交截图" }}
                    </button>
                  </div>
                  <span class="promo-disabled-note">提交后进入人工审核，奖励在审核通过后发放。</span>
                </div>
              </div>
            </div>
          </section>

          <section class="promo-section promo-section--span-2 promo-section--compact">
            <div class="promo-section__head">
              <h4>我的截图记录</h4>
            </div>
            <div v-if="likeSubmissions.length" class="promo-history-list">
              <article v-for="item in likeSubmissions" :key="`like-history-${item.id}`" class="promo-history-card">
                <div class="promo-history-card__head">
                  <strong>{{ resolveLikePlatformLabel(item.platform) }}</strong>
                  <span class="promo-status-tag" :class="statusTagClass(item.status)">{{ formatSubmissionStatus(item.status) }}</span>
                </div>
                <p>文件：{{ item.original_filename || "未命名截图" }}</p>
                <p v-if="item.share_text">备注：{{ item.share_text }}</p>
                <p>更新时间：{{ formatDateTime(item.updated_at || item.created_at) }}</p>
                <p v-if="item.review_note">审核备注：{{ item.review_note }}</p>
              </article>
            </div>
            <div v-else class="promo-submit-placeholder">
              <strong>还没有截图记录</strong>
              <span>完成集赞后上传截图，这里会展示你的审核状态。</span>
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
              <select v-model="createForm.platform">
                <option value="" disabled>选择发布平台</option>
                <option v-for="platform in enabledCreatePlatforms" :key="platform.key" :value="platform.key">
                  {{ platform.label }}
                </option>
              </select>
              <select v-model="createForm.tier_key">
                <option v-for="item in createTierOptions" :key="item.key" :value="item.key">
                  {{ item.label }}
                </option>
              </select>
            </div>
            <div class="promo-submit-row">
              <input v-model.trim="createForm.share_link" type="text" maxlength="500" placeholder="请输入作品链接" />
            </div>
            <div class="promo-submit-row">
              <input v-model.trim="createForm.payout_name" type="text" maxlength="120" placeholder="收款人姓名（选填）" />
              <input v-model.trim="createForm.payout_account" type="text" maxlength="120" placeholder="收款账号（选填）" />
            </div>
            <div class="promo-submit-row">
              <textarea v-model.trim="createForm.note" maxlength="500" rows="3" placeholder="补充说明（选填）"></textarea>
            </div>
            <div class="promo-submit-row">
              <button
                type="button"
                class="promo-primary"
                :disabled="createSubmitting || !createForm.platform || !createForm.share_link"
                @click="submitCreateSubmission"
              >
                {{ createSubmitting ? "提交中..." : (createPage.submit_button_text || "提交链接") }}
              </button>
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

          <section class="promo-section promo-section--span-2 promo-section--compact">
            <div class="promo-section__head">
              <h4>我的作品记录</h4>
            </div>
            <div v-if="createSubmissions.length" class="promo-history-list">
              <article v-for="item in createSubmissions" :key="`create-history-${item.id}`" class="promo-history-card">
                <div class="promo-history-card__head">
                  <strong>{{ resolveCreatePlatformLabel(item.platform) }}</strong>
                  <span class="promo-status-tag" :class="statusTagClass(item.status)">{{ formatSubmissionStatus(item.status) }}</span>
                </div>
                <p>档位：{{ resolveCreateTierLabel(item.tier_key) }}</p>
                <p>链接：{{ item.share_link }}</p>
                <p v-if="item.note">备注：{{ item.note }}</p>
                <p>更新时间：{{ formatDateTime(item.updated_at || item.created_at) }}</p>
                <p v-if="item.review_note">审核备注：{{ item.review_note }}</p>
              </article>
            </div>
            <div v-else class="promo-submit-placeholder">
              <strong>还没有作品记录</strong>
              <span>提交发布链接后，这里会持续展示审核进度。</span>
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

      <section class="promo-section promo-section--span-2 promo-section--footer">
        <div class="promo-section__head">
          <h4>平台二维码</h4>
        </div>
        <p class="promo-detail promo-detail--compact">电脑端可直接扫码进入对应平台主页，手机端也可长按识别，统一放在每页底部方便取用。</p>
        <div class="promo-platform-qr-strip">
          <article v-for="item in promoPlatformQRCodes" :key="item.key" class="promo-platform-qr-card">
            <div class="promo-platform-qr-card__media">
              <img :src="item.src" :alt="`${item.label} 二维码`" :style="{ objectPosition: item.objectPosition }" />
            </div>
            <div class="promo-platform-qr-card__copy">
              <strong>{{ item.label }}</strong>
              <span>{{ item.desc }}</span>
            </div>
          </article>
        </div>
      </section>
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
const inviteBindCode = ref("")
const inviteBoundRelation = ref(null)
const inviteSummary = ref({
  valid_invite_count: 0,
  invitee_bind_reward_points: 0,
  invitee_bind_reward_granted: false,
  inviter_reward_points_total: 0,
  milestone_reward_points_total: 0,
  total_reward_points: 0,
  earned_milestones: [],
  next_milestone: null,
  bound_relation_id: null,
})
const bindingInvite = ref(false)
const likeShareText = ref("")
const likeScreenshotFile = ref(null)
const likeScreenshotName = ref("")
const likeSubmitting = ref(false)
const likeSubmissions = ref([])
const createSubmitting = ref(false)
const createSubmissions = ref([])
const createForm = ref({
  platform: "",
  tier_key: "",
  share_link: "",
  payout_account: "",
  payout_name: "",
  note: "",
})
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

const invitePage = computed(() => promoConfig.value?.pages?.invite || DEFAULT_PROMO_CENTER_CONFIG.pages.invite)
const likePage = computed(() => promoConfig.value?.pages?.like || DEFAULT_PROMO_CENTER_CONFIG.pages.like)
const createPage = computed(() => promoConfig.value?.pages?.create || DEFAULT_PROMO_CENTER_CONFIG.pages.create)
const partnerPage = computed(() => promoConfig.value?.pages?.partner || DEFAULT_PROMO_CENTER_CONFIG.pages.partner)
const inviteRules = computed(() => promoConfig.value?.reward_rules?.invite || DEFAULT_PROMO_CENTER_CONFIG.reward_rules.invite)
const likeRules = computed(() => promoConfig.value?.reward_rules?.like || DEFAULT_PROMO_CENTER_CONFIG.reward_rules.like)
const createRules = computed(() => promoConfig.value?.reward_rules?.create || DEFAULT_PROMO_CENTER_CONFIG.reward_rules.create)
const visibleLikeEntries = computed(() => (Array.isArray(likePage.value?.other_entries) ? likePage.value.other_entries : []).filter((item) => item?.enabled !== false))
const visiblePartnerContacts = computed(() => (Array.isArray(partnerPage.value?.contacts) ? partnerPage.value.contacts : []).filter((item) => item?.enabled !== false))
const enabledCreatePlatforms = computed(() => (Array.isArray(createPage.value?.platforms) ? createPage.value.platforms : []).filter((item) => item?.enabled !== false))
const createTierOptions = computed(() => {
  const list = Array.isArray(createRules.value?.tiers) ? createRules.value.tiers : []
  return list.map((item, index) => ({
    key: String(item?.key || item?.tier_key || `tier-${index + 1}`),
    label: String(item?.label || `${item?.threshold || 0}+`),
  }))
})
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
const nextMilestoneLabel = computed(() => {
  const milestone = inviteSummary.value?.next_milestone
  if (!milestone) return "已全部达成"
  return milestone.label || `${milestone.threshold} 人`
})
const nextMilestoneHint = computed(() => {
  const milestone = inviteSummary.value?.next_milestone
  if (!milestone) return "当前已拿满已配置里程碑奖励"
  return `再邀请 ${Number(milestone.remaining_count || 0)} 人，可得 ${formatPoints(milestone.reward_points)}`
})
const inviteDisplayRuleLines = computed(() => [
  `好友填写邀请码后，可获得 ${formatPoints(inviteRules.value?.invitee_bind_reward_points || 0)}。`,
  `每产生 1 个有效邀请，邀请人可获得 ${formatPoints(inviteRules.value?.inviter_valid_invite_reward_points || 0)}。`,
  "里程碑奖励按后台配置累计发放，人数越多，额外点数越高。",
])
const inviteGuideTitle = computed(() => "邀请方式")
const inviteDisplaySteps = computed(() => [
  "复制你的邀请码或邀请链接，直接发给好友。",
  "好友注册后填写邀请码，系统立即建立邀请关系。",
  "满足有效邀请条件后，奖励按规则发放到双方账户。",
])
const inviteBindNoticeText = computed(() => "好友注册后填写邀请码，即可建立邀请关系并参与奖励计算。")
const inviteShareCopyText = computed(() => {
  const suffix = inviteCode.value ? `我的邀请码是 ${inviteCode.value}。` : ""
  return `我正在用格物学术处理论文，注册后填写邀请码即可参加邀请有奖活动。${suffix}`.trim()
})
const likePlatformLabel = computed(() => {
  const title = String(likePage.value?.qrcode_title || "").trim()
  return title || "微信集赞活动"
})
const promoPlatformQRCodes = computed(() => {
  const assets = promoConfig.value?.assets || {}
  return [
    {
      key: "douyin",
      label: "抖音",
      desc: "扫码直达格物学术抖音主页",
      src: String(assets.platform_douyin_qrcode_url || "/promo-qr-douyin.jpg").trim(),
      objectPosition: "50% 35%",
    },
    {
      key: "xiaohongshu",
      label: "小红书",
      desc: "扫码查看小红书账号内容",
      src: String(assets.platform_xiaohongshu_qrcode_url || "/promo-qr-xiaohongshu.jpg").trim(),
      objectPosition: "50% 42%",
    },
    {
      key: "bilibili",
      label: "B站",
      desc: "扫码进入 B 站主页",
      src: String(assets.platform_bilibili_qrcode_url || "/promo-qr-bilibili.jpg").trim(),
      objectPosition: "50% 30%",
    },
    {
      key: "wechat",
      label: "微信公众号",
      desc: "扫码关注公众号获取更新",
      src: String(assets.platform_wechat_qrcode_url || "/promo-qr-wechat.jpg").trim(),
      objectPosition: "50% 50%",
    },
  ].filter((item) => item.src)
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

watch(
  enabledCreatePlatforms,
  (items) => {
    const keys = items.map((item) => String(item?.key || ""))
    if (!keys.includes(createForm.value.platform)) {
      createForm.value.platform = keys[0] || ""
    }
  },
  { immediate: true },
)

watch(
  createTierOptions,
  (items) => {
    const keys = items.map((item) => item.key)
    if (!keys.includes(createForm.value.tier_key)) {
      createForm.value.tier_key = keys[0] || ""
    }
  },
  { immediate: true },
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
      const [invite, likeData, createData] = await Promise.all([
        userHttp.get("/users/me/invite"),
        userHttp.get("/users/me/promo/like-submissions"),
        userHttp.get("/users/me/promo/create-submissions"),
      ])
      inviteCode.value = String(invite?.invite_code || "").trim()
      inviteBoundRelation.value = invite?.bound_relation || null
      inviteSummary.value = normalizeInviteSummary(invite?.invite_summary)
      likeSubmissions.value = Array.isArray(likeData?.items) ? likeData.items : []
      createSubmissions.value = Array.isArray(createData?.items) ? createData.items : []
    } else {
      inviteCode.value = ""
      inviteBoundRelation.value = null
      inviteSummary.value = normalizeInviteSummary(null)
      likeSubmissions.value = []
      createSubmissions.value = []
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

async function submitInviteBind() {
  if (!inviteBindCode.value || bindingInvite.value) return
  bindingInvite.value = true
  errorText.value = ""
  hintText.value = ""
  try {
    const data = await userHttp.post("/users/me/invite/bind", { invite_code: inviteBindCode.value })
    inviteBoundRelation.value = data?.bound_relation || null
    inviteSummary.value = normalizeInviteSummary(data?.invite_summary)
    inviteBindCode.value = ""
    const rewardText = Number(inviteSummary.value?.invitee_bind_reward_points || 0) > 0 ? `，${formatPoints(inviteSummary.value.invitee_bind_reward_points)} 已到账` : ""
    hintText.value = `邀请码绑定成功${rewardText}`
    await refreshUser()
  } catch (error) {
    errorText.value = String(error?.message || "邀请码绑定失败")
  } finally {
    bindingInvite.value = false
  }
}

function handleLikeFileChange(event) {
  const files = event?.target?.files
  const file = files && files[0] ? files[0] : null
  likeScreenshotFile.value = file
  likeScreenshotName.value = file?.name || ""
}

async function submitLikeSubmission() {
  if (!likeScreenshotFile.value || likeSubmitting.value) return
  likeSubmitting.value = true
  errorText.value = ""
  hintText.value = ""
  try {
    const formData = new FormData()
    formData.append("platform", "wechat")
    formData.append("share_text", likeShareText.value || "")
    formData.append("screenshot", likeScreenshotFile.value)
    const data = await userHttp.post("/users/me/promo/like-submissions", formData)
    upsertSubmission(likeSubmissions.value, data?.item)
    likeScreenshotFile.value = null
    likeScreenshotName.value = ""
    likeShareText.value = ""
    hintText.value = "截图已提交，等待审核"
  } catch (error) {
    errorText.value = String(error?.message || "截图提交失败")
  } finally {
    likeSubmitting.value = false
  }
}

async function submitCreateSubmission() {
  if (!createForm.value.platform || !createForm.value.share_link || createSubmitting.value) return
  createSubmitting.value = true
  errorText.value = ""
  hintText.value = ""
  try {
    const data = await userHttp.post("/users/me/promo/create-submissions", { ...createForm.value })
    upsertSubmission(createSubmissions.value, data?.item)
    createForm.value.share_link = ""
    createForm.value.payout_account = ""
    createForm.value.payout_name = ""
    createForm.value.note = ""
    hintText.value = "作品链接已提交，等待审核"
  } catch (error) {
    errorText.value = String(error?.message || "作品提交失败")
  } finally {
    createSubmitting.value = false
  }
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

function normalizeInviteSummary(value) {
  const data = value && typeof value === "object" ? value : {}
  return {
    valid_invite_count: Number(data.valid_invite_count || 0),
    invitee_bind_reward_points: Number(data.invitee_bind_reward_points || 0),
    invitee_bind_reward_granted: Boolean(data.invitee_bind_reward_granted),
    inviter_reward_points_total: Number(data.inviter_reward_points_total || 0),
    milestone_reward_points_total: Number(data.milestone_reward_points_total || 0),
    total_reward_points: Number(data.total_reward_points || 0),
    earned_milestones: Array.isArray(data.earned_milestones) ? data.earned_milestones : [],
    next_milestone: data.next_milestone && typeof data.next_milestone === "object" ? data.next_milestone : null,
    bound_relation_id: data.bound_relation_id ?? null,
  }
}

function upsertSubmission(list, item) {
  if (!item || !item.platform) return
  const items = Array.isArray(list) ? list : []
  const next = [item, ...items.filter((row) => row?.platform !== item.platform)]
  list.splice(0, list.length, ...next)
}

function formatDateTime(value) {
  if (!value) return "--"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  })
}

function formatSubmissionStatus(status) {
  const key = String(status || "").trim().toLowerCase()
  return {
    pending: "待审核",
    submitted: "已提交",
    approved: "已通过",
    rejected: "已驳回",
  }[key] || key || "待处理"
}

function statusTagClass(status) {
  const key = String(status || "").trim().toLowerCase()
  return `promo-status-tag--${key || "default"}`
}

function resolveLikePlatformLabel(platform) {
  const key = String(platform || "").trim().toLowerCase()
  if (key === "wechat") return likePlatformLabel.value
  return likePlatformLabel.value
}

function resolveCreatePlatformLabel(platform) {
  const key = String(platform || "").trim()
  const matched = enabledCreatePlatforms.value.find((item) => String(item?.key || "") === key)
  return matched?.label || key || "创作活动"
}

function resolveCreateTierLabel(tierKey) {
  const key = String(tierKey || "").trim()
  const matched = createTierOptions.value.find((item) => item.key === key)
  return matched?.label || key || "默认档位"
}
</script>

<style scoped>
.promo-page {
  display: grid;
  gap: 16px;
  font-family: var(--font-sans);
}

.promo-primary,
.promo-secondary,
.promo-action-row__controls button {
  min-height: 42px;
  padding: 0 16px;
  border-radius: 14px;
  font-weight: 700;
  cursor: pointer;
  transition:
    transform var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    background-color var(--motion-fast) var(--ease-standard);
}

.promo-primary:disabled,
.promo-secondary:disabled,
.promo-action-row__controls button:disabled {
  opacity: 0.62;
  cursor: default;
}

.promo-tabs {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.promo-tab {
  position: relative;
  overflow: hidden;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(194, 212, 242, 0.92);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(247, 251, 255, 0.98) 100%);
  text-align: left;
  cursor: pointer;
  box-shadow: 0 14px 28px rgba(24, 74, 164, 0.08);
  transition:
    transform var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard),
    border-color var(--motion-fast) var(--ease-standard),
    background var(--motion-fast) var(--ease-standard);
}

.promo-tab::after {
  content: "";
  position: absolute;
  inset: auto 18px 0;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(77, 132, 255, 0), rgba(77, 132, 255, 0.88), rgba(77, 132, 255, 0));
  opacity: 0;
  transform: translateY(6px);
  transition:
    opacity var(--motion-fast) var(--ease-standard),
    transform var(--motion-fast) var(--ease-standard);
}

.promo-tab:hover {
  transform: translateY(-2px);
  border-color: rgba(82, 132, 231, 0.4);
  box-shadow: 0 18px 34px rgba(24, 74, 164, 0.12);
}

.promo-tab:hover::after {
  opacity: 1;
  transform: translateY(0);
}

.promo-tab--active {
  border-color: rgba(30, 91, 223, 0.62);
  background: linear-gradient(135deg, #6ca0ff 0%, #4584fa 28%, #1e5bdf 66%, #184ec8 100%);
  box-shadow: 0 20px 36px rgba(30, 91, 223, 0.22);
}

.promo-tab--active::after {
  opacity: 1;
  transform: translateY(0);
  background: linear-gradient(90deg, rgba(255, 255, 255, 0), rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0));
}

.promo-tab span {
  display: block;
  font-size: 11px;
  color: #2f67d7;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
}

.promo-tab strong {
  display: block;
  margin-top: 6px;
  font-size: 17px;
  color: #183962;
}

.promo-tab em {
  display: block;
  margin-top: 7px;
  font-size: 12px;
  line-height: 1.65;
  color: #607894;
  font-style: normal;
}

.promo-tab--active span,
.promo-tab--active strong,
.promo-tab--active em {
  color: #fff;
}

.promo-section,
.promo-tab {
  box-sizing: border-box;
}

.promo-section__head h4,
.promo-section__head h4 {
  margin: 0;
  color: #17385f;
  font-family: var(--font-display);
}

.promo-detail,
.promo-qrcode-side p,
.promo-entry-card p {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: #627a95;
}

.promo-layout {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.promo-section {
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid rgba(207, 222, 244, 0.96);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(248, 251, 255, 0.99) 100%);
  box-shadow: 0 16px 32px rgba(20, 64, 146, 0.08);
}

.promo-section--soft {
  background: linear-gradient(180deg, rgba(242, 248, 255, 0.98) 0%, rgba(255, 255, 255, 0.98) 100%);
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
  margin-bottom: 2px;
}

.promo-section__head--sub {
  margin-top: 16px;
}

.promo-section__head h4 {
  font-size: 19px;
}

.promo-grid {
  display: grid;
  gap: 12px;
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
.promo-step-card,
.promo-entry-card,
.promo-partner-card {
  border: 1px solid rgba(212, 224, 242, 0.96);
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
}
.promo-stat-card,
.promo-flow-card,
.promo-platform-card,
.promo-tier-card,
.promo-step-card,
.promo-entry-card,
.promo-partner-card {
  padding: 14px 15px;
  border-radius: 18px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
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
  font-size: 25px;
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
  gap: 12px;
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
  padding: 11px 13px;
  border-radius: 14px;
  border: 1px solid rgba(212, 224, 242, 0.96);
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  font-size: 12px;
  line-height: 1.65;
  color: #2f4763;
}

.promo-chip--accent,
.promo-tier-card--accent {
  border-color: rgba(30, 91, 223, 0.14);
  background: linear-gradient(180deg, #f3f8ff 0%, #ffffff 100%);
}

.promo-chip--success,
.promo-stat-card--soft {
  border-color: rgba(62, 164, 104, 0.2);
  background: linear-gradient(180deg, #f1fbf5 0%, #ffffff 100%);
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
  min-height: 38px;
  padding: 0 16px;
  border-radius: 999px;
  border: 1px solid rgba(198, 214, 238, 0.96);
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  font-size: 12px;
  color: #1f436b;
}

.promo-action-list {
  margin-top: 12px;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.promo-action-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
  align-items: start;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(212, 224, 242, 0.96);
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
  justify-content: flex-start;
}

.promo-action-row__meta,
.promo-submit-placeholder,
.promo-disabled-note {
  color: #5e7393;
  font-size: 13px;
  line-height: 1.7;
}

.promo-action-row__meta {
  justify-self: start;
  text-align: left;
}

.promo-action-row__controls input,
.promo-submit-row input,
.promo-submit-row select,
.promo-submit-row textarea {
  flex: 1;
  min-width: 220px;
  min-height: 42px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px solid #d1dceb;
  background: #fff;
  color: #17385f;
  font-size: 14px;
  outline: none;
  transition:
    border-color var(--motion-fast) var(--ease-standard),
    box-shadow var(--motion-fast) var(--ease-standard);
}

.promo-action-row__controls input:focus,
.promo-submit-row input:focus,
.promo-submit-row select:focus,
.promo-submit-row textarea:focus {
  border-color: rgba(30, 91, 223, 0.58);
  box-shadow: 0 0 0 4px rgba(30, 91, 223, 0.08);
}

.promo-submit-row textarea {
  min-height: 96px;
  padding-top: 10px;
  resize: vertical;
}

.promo-primary {
  border: 1px solid var(--primary);
  background: var(--primary-gradient);
  color: #fff;
  box-shadow: 0 12px 24px rgba(30, 91, 223, 0.18);
}

.promo-secondary {
  border: 1px solid rgba(30, 91, 223, 0.18);
  background: rgba(30, 91, 223, 0.08);
  color: var(--primary);
}

.promo-primary:hover:not(:disabled),
.promo-secondary:hover:not(:disabled),
.promo-action-row__controls button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.promo-qrcode-layout {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 14px;
}

.promo-qrcode-box {
  min-height: 220px;
  border-radius: 20px;
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
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  color: #24466f;
  font-size: 14px;
  line-height: 1.8;
  white-space: pre-wrap;
}

.promo-submit-row {
  margin-top: 12px;
}

.promo-submit-placeholder {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px dashed #cfdcec;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  display: grid;
  gap: 6px;
}

.promo-submit-placeholder strong {
  color: #183b68;
  font-size: 14px;
}

.promo-submit-card {
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(212, 224, 242, 0.96);
  background: linear-gradient(180deg, #fcfdff 0%, #ffffff 100%);
  display: grid;
  gap: 10px;
}

.promo-submit-card strong {
  color: #183b68;
  font-size: 14px;
}

.promo-hidden-input {
  display: none;
}

.promo-file-trigger {
  min-height: 42px;
  padding: 0 14px;
  border-radius: 14px;
  border: 1px dashed #b8cce8;
  background: #f8fbff;
  color: #20456d;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
}

.promo-history-list {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.promo-history-card {
  padding: 14px 15px;
  border-radius: 18px;
  border: 1px solid rgba(212, 224, 242, 0.96);
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  display: grid;
  gap: 6px;
}

.promo-history-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.promo-history-card__head strong {
  color: #17385f;
}

.promo-history-card p {
  margin: 0;
  font-size: 13px;
  line-height: 1.7;
  color: #627a95;
  word-break: break-all;
}

.promo-status-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  color: #1f436b;
  background: #eef4ff;
}

.promo-status-tag--pending,
.promo-status-tag--submitted {
  color: #945d00;
  background: #fff4dc;
}

.promo-status-tag--approved {
  color: #1f7a3b;
  background: #e9f8ee;
}

.promo-status-tag--rejected {
  color: #b03838;
  background: #ffe8e8;
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

.promo-section--footer {
  margin-top: 4px;
}

.promo-detail--compact {
  margin-top: 8px;
}

.promo-platform-qr-strip {
  margin-top: 14px;
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.promo-platform-qr-card {
  padding: 12px;
  border-radius: 20px;
  border: 1px solid rgba(212, 224, 242, 0.96);
  background: linear-gradient(180deg, #fbfdff 0%, #ffffff 100%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.88);
  display: grid;
  gap: 10px;
}

.promo-platform-qr-card__media {
  aspect-ratio: 1 / 1;
  border-radius: 18px;
  overflow: hidden;
  background: #f4f8ff;
  border: 1px solid rgba(204, 220, 243, 0.96);
}

.promo-platform-qr-card__media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.promo-platform-qr-card__copy {
  display: grid;
  gap: 4px;
}

.promo-platform-qr-card__copy strong {
  color: #17385f;
  font-size: 15px;
}

.promo-platform-qr-card__copy span {
  color: #627a95;
  font-size: 12px;
  line-height: 1.6;
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

  .promo-platform-qr-strip {
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
  .promo-action-list,
  .promo-history-list,
  .promo-entry-grid,
  .promo-partner-grid,
  .promo-platform-qr-strip {
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
  .promo-submit-row input,
  .promo-submit-row select,
  .promo-submit-row textarea {
    min-width: 100%;
    width: 100%;
  }
}
</style>
