<template>
  <UserShell
    title="推广福利"
    subtitle="全班免费查、分享领红包"
    :credits="userCredits"
    :hide-topbar="true"
    :hide-header-title="true"
    @buy="goBuy"
  >
    <section class="promo-page">
      <div class="activity-wrap activity-wrap--center">
        <div class="activity-layout">
          <aside class="activity-sidebar">
            <ul class="activity-topbar__nav">
              <li v-for="item in tabs" :key="item.key">
                <button type="button" :class="{ 'is-active': activePage === item.key }" @click="activePage = item.key">{{ item.label }}</button>
              </li>
            </ul>
          </aside>

          <div class="activity-main">
            <p v-if="feedback.text" class="activity-feedback" :class="`is-${feedback.tone}`">{{ feedback.text }}</p>

            <section v-if="activePage === 'classroom'" class="activity-page">
              <div class="page-title-bar page-title-bar--center">
                <div>
                  <h2>全班免费查</h2>
                  <div class="subtitle">创建班级后持续邀请同学，人数越高，整班解锁的卡券档位越高</div>
                </div>
              </div>

              <div class="class-show-wrap">
                <div>
                  <div class="class-hero">
                  <div class="class-hero__eyebrow">班级裂变福利</div>
                    <h1>创建班级后邀请同学加入，按人数逐步解锁查重券与降重券，人数越多，整班可领取的免费权益越高。</h1>
                    <div class="class-hero__stats">
                      <article>
                        <span>当前人数</span>
                        <strong>{{ classroom.created ? classroom.memberCount : 0 }}</strong>
                      </article>
                      <article>
                        <span>班级等级</span>
                        <strong>{{ classroom.created ? classroom.level : "待创建" }}</strong>
                      </article>
                      <article>
                        <span>下一档目标</span>
                        <strong>{{ nextClassroomTarget }}</strong>
                      </article>
                    </div>
                  </div>

                  <div class="class-tiers">
                    <div v-for="item in classroomTiers" :key="item.title" class="class-tier">
                      <div class="class-tier-icon">{{ item.icon }}</div>
                      <div>
                        <div class="class-tier-title">{{ item.title }}</div>
                        <div class="class-tier-cond">{{ item.desc }}</div>
                      </div>
                      <span class="class-tier-tag">{{ item.tag }}</span>
                    </div>
                  </div>

                  <button type="button" class="create-btn-big" @click="createClassroom">
                    {{ classroom.created ? "继续邀请同学，全班免费查" : "立即创建班级，全班免费查" }}
                  </button>

                  <div v-if="classroom.created" class="class-room-box">
                    <article>
                      <strong>{{ classroom.name }}</strong>
                      <p>{{ classroom.level }} · {{ classroom.memberCount }} 人 · 活跃度 {{ classroom.activityScore }}</p>
                    </article>
                    <article>
                      <strong>入班口令：{{ classroom.inviteCode }}</strong>
                      <p>支持复制口令和二维码邀请两种拉人方式</p>
                    </article>
                    <div class="class-room-actions">
                      <button type="button" class="btn-ghost" @click="copyClassroomCode">复制口令</button>
                      <button type="button" class="btn-ghost" @click="downloadPoster">下载海报</button>
                    </div>
                  </div>
                </div>

                <div class="lb-card">
                  <h3>上周班级活跃榜</h3>
                  <div v-for="item in classroomLeaderboard" :key="item.rank" class="lb-row">
                    <div class="lb-rank">{{ item.rank }}</div>
                    <div class="lb-info">
                      <div class="lb-name">{{ item.name }}</div>
                      <div class="lb-meta">活跃度: {{ item.activity }} · {{ item.members }}人</div>
                    </div>
                    <span class="lb-level">{{ item.level }}</span>
                  </div>
                </div>
              </div>
            </section>

            <section v-else class="activity-page activity-page--share">
              <div class="page-title-bar page-title-bar--center">
                <div>
                  <h2>分享领红包</h2>
                  <div class="subtitle">选择平台后直接提交审核，奖励按档位人工发放</div>
                </div>
              </div>

              <div class="share-plat-tabs share-plat-tabs--center">
                <button
                  v-for="item in sharePlatforms"
                  :key="item.key"
                  type="button"
                  class="plat-tab"
                  :class="{ active: activePlatform === item.key }"
                  @click="activePlatform = item.key"
                >
                  <div class="plat-tab__icon" :class="`is-${item.tone}`">{{ item.mark }}</div>
                  <div class="plat-tab__body">
                    <strong>{{ item.name }}-分享</strong>
                    <small>{{ item.rewardText }}</small>
                    <em>{{ activePlatform === item.key ? "当前" : "立即领取" }}</em>
                  </div>
                  <div v-if="activePlatform === item.key" class="plat-tab__check">✓</div>
                </button>
              </div>

              <div class="share-layout">
                <div class="share-layout__left">
                  <div class="reward-card">
                    <h4>任务详情</h4>
                    <div class="task-table">
                      <div class="task-table__row"><span>任务时间</span><strong>长期有效</strong></div>
                      <div class="task-table__row"><span>参与次数</span><strong>每个三方平台各参与1次（更换手机号视为同一账户，不可再次参与）</strong></div>
                      <div class="task-table__row"><span>参与对象</span><strong>格物学术平台用户</strong></div>
                      <div class="task-table__row"><span>发放方式</span><strong>7个工作日内审核通过后，发送到用户余额</strong></div>
                      <div class="task-table__row">
                        <span>对应奖励</span>
                        <strong class="task-table__reward-list">
                          <span v-for="item in currentShareRewards" :key="item">{{ item }}</span>
                        </strong>
                      </div>
                    </div>
                  </div>

                  <div class="submit-card">
                    <h4>{{ currentPlatformName }}提交审核</h4>
                    <div class="submit-grid">
                      <label class="form-group">
                        <span>输入{{ currentPlatformName }}分享链接</span>
                        <input v-model.trim="shareForm.link" type="text" placeholder="填写分享后的链接（链接必须为可访问地址）" />
                      </label>
                      <label class="form-group">
                        <span>输入平台昵称</span>
                        <input v-model.trim="shareForm.nickname" type="text" placeholder="请输入账号昵称（提交后不可修改哦，请谨慎填写）" />
                      </label>
                      <label class="form-group">
                        <span>输入领取奖励的支付宝号</span>
                        <input v-model.trim="shareForm.account" type="text" placeholder="请输入支付宝号（提交后不可修改哦，请谨慎填写）" />
                      </label>
                      <label class="form-group">
                        <span>输入支付宝认证姓名</span>
                        <input v-model.trim="shareForm.realName" type="text" placeholder="请输入支付宝认证姓名（用于打款时的身份验证）" />
                      </label>
                      <label class="form-group form-group--full">
                        <span>选择符合条件的奖励</span>
                        <select v-model="shareForm.tier">
                          <option v-for="item in shareTiers" :key="item.key" :value="item.key">
                            {{ item.reward }}（{{ item.desc }}）
                          </option>
                        </select>
                      </label>
                      <label class="form-group form-group--full">
                        <span>补充说明</span>
                        <textarea v-model.trim="shareForm.note" rows="1" placeholder="可补充点赞数、发布时间或作品说明"></textarea>
                      </label>
                    </div>
                    <button type="button" class="btn-primary" :disabled="!canSubmitShare" @click="submitShare">提交审核</button>
                    <p class="risk-tip">⚠️ 提交后不可修改，请谨慎填写（若发现任何形式的弄虚作假骗取奖励的行为，将拒绝审核，并取消所有活动资格。）</p>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>
    </section>
  </UserShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"

import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { userHttp } from "../../lib/http"
import { getUserToken } from "../../lib/session"

const router = useRouter()
const route = useRoute()
const { user, refreshUser } = useUserProfile()

const userCredits = computed(() => (typeof user.value?.credits === "number" ? user.value.credits : null))
const isGuest = computed(() => !getUserToken())

const activePage = ref("classroom")
const activePlatform = ref("douyin")
const feedback = reactive({ text: "", tone: "info" })

const tabs = [
  { key: "classroom", label: "全班免费查" },
  { key: "share", label: "分享领红包" },
]

const shareTasks = ref([
  { key: "wechat", label: "分享朋友圈", desc: "将平台海报和检测体验分享到朋友圈", reward: 5000, status: "ready" },
  { key: "qq", label: "分享QQ空间", desc: "将平台海报分享到 QQ 空间", reward: 3000, status: "claimed" },
  { key: "weibo", label: "分享微博", desc: "发布微博并推荐论文服务", reward: 2000, status: "claimed" },
])
const classroomNotice = reactive({
  name: "大吉大利毕业群",
  level: "钻石班",
  reward: "2 张至尊版查重券",
})

const classroom = reactive({
  created: false,
  id: null,
  name: "",
  inviteCode: "",
  level: "待创建",
  memberCount: 0,
  activityScore: 0,
})

const classroomLeaderboard = ref([
  { rank: 1, name: "大吉大利毕业群", members: 46, activity: 98, level: "钻石班" },
  { rank: 2, name: "论文终稿冲刺班", members: 34, activity: 92, level: "钻石班" },
  { rank: 3, name: "教育硕士定稿小组", members: 22, activity: 87, level: "黄金班" },
])

const sharePlatforms = ref([
  { key: "weibo", name: "微博", mark: "博", tone: "weibo", rewardText: "得20元红包", status: "ready" },
  { key: "xiaohongshu", name: "小红书", mark: "红", tone: "xiaohongshu", rewardText: "得20元红包", status: "ready" },
  { key: "douyin", name: "抖音", mark: "抖", tone: "douyin", rewardText: "得20元红包", status: "ready" },
  { key: "zhihu", name: "知乎", mark: "知", tone: "zhihu", rewardText: "得20元红包", status: "submitted" },
  { key: "qq", name: "QQ", mark: "Q", tone: "qq", rewardText: "得20元红包", status: "ready" },
  { key: "wechat", name: "微信", mark: "微", tone: "wechat", rewardText: "得20元红包", status: "done" },
])

const shareRecords = ref([
  { id: "wx", platform: "微信分享", note: "朋友圈分享已通过审核", status: "done", reward: "20元红包" },
  { id: "zh", platform: "知乎分享", note: "已提交回答链接，等待审核", status: "submitted", reward: "申请档位：10元红包" },
])

const shareForm = reactive({
  link: "",
  nickname: "",
  tier: "top",
  account: "",
  realName: "",
  note: "",
})

const classroomTiers = computed(() => [
  { icon: "免", title: "10 张免费版查重券", desc: classroom.created ? `班级成员达 10 人 · 当前 ${classroom.memberCount}/10` : "班级成员达 10 人，每人可领取 10 张", tag: "待解锁" },
  { icon: "尊", title: "2 张至尊版查重券", desc: classroom.created ? `班级成员达 20 人 · 当前 ${classroom.memberCount}/20` : "班级成员达 20 人，每人可领取 2 张", tag: "待解锁" },
  { icon: "降", title: "1 张学术论文降重券", desc: classroom.created ? `班级成员达 40 人 · 当前 ${classroom.memberCount}/40` : "班级成员达 40 人，每人可领取 1 张", tag: "待解锁" },
])

const currentPlatformName = computed(() => {
  const current = sharePlatforms.value.find((item) => item.key === activePlatform.value)
  return current?.name || "微博"
})

const sharePageRules = {
  weibo: {
    rewards: [
      "1. 5元红包（获得5个及以上点赞）",
      "2. 10元红包（获得10个及以上点赞）",
      "3. 20元红包（获得20个及以上点赞）",
    ],
    stepOne: [
      "1. 带上话题「#毕业论文」和「#格物学术」",
      "2. 发布图文或视频，推荐分享格物学术，文案不低于20字",
    ],
  },
  xiaohongshu: {
    rewards: [
      "1. 5元红包（获得5个及以上点赞）",
      "2. 10元红包（获得10个及以上点赞）",
      "3. 20元红包（获得20个及以上点赞）",
    ],
    stepOne: [
      "1. 带上话题「#毕业论文」和「#格物学术」",
      "2. 发布图文或视频，推荐分享格物学术，文案不低于20字",
    ],
  },
  douyin: {
    rewards: [
      "1. 5元红包（获得5个及以上点赞）",
      "2. 10元红包（获得10个及以上点赞）",
      "3. 20元红包（获得20个及以上点赞）",
    ],
    stepOne: [
      "1. 带上话题「#毕业论文」和「#格物学术」",
      "2. 发布图文或视频，推荐分享格物学术，文案不低于20字",
    ],
  },
  zhihu: {
    rewards: [
      "1. 5元红包（获得5个及以上点赞）",
      "2. 10元红包（获得10个及以上点赞）",
      "3. 20元红包（获得20个及以上点赞）",
    ],
    stepOne: [
      "1. 带上话题「#毕业论文」和「#格物学术」",
      "2. 发布回答/文章，推荐分享格物学术，文案不低于20字",
    ],
  },
  qq: {
    rewards: [
      "1. 5元红包（获得5个及以上点赞）",
      "2. 10元红包（获得10个及以上点赞）",
      "3. 20元红包（获得20个及以上点赞）",
    ],
    stepOne: [
      "1. 带上话题「#毕业论文」和「#格物学术」",
      "2. 发布说说/空间动态，推荐分享格物学术，文案不低于20字",
    ],
  },
  wechat: {
    rewards: [
      "1. 5元红包（获得5个及以上点赞）",
      "2. 10元红包（获得10个及以上点赞）",
      "3. 20元红包（获得20个及以上点赞）",
    ],
    stepOne: [
      "1. 发布朋友圈动态，推荐分享格物学术，文案不低于20字",
      "2. 截图分享链接提交审核",
    ],
  },
}

const currentShareRule = computed(() => sharePageRules[activePlatform.value] || sharePageRules.weibo)
const currentShareRewards = computed(() => currentShareRule.value.rewards || [])
const shareTiers = computed(() => [
  { key: "base", title: "5元红包", reward: "5元红包", desc: "获得5个及以上点赞" },
  { key: "boost", title: "10元红包", reward: "10元红包", desc: "获得10个及以上点赞" },
  { key: "top", title: "20元红包", reward: "20元红包", desc: "获得20个及以上点赞" },
])
const canSubmitShare = computed(
  () =>
    Boolean(
      shareForm.link.trim() &&
      shareForm.nickname.trim() &&
      shareForm.account.trim() &&
      shareForm.realName.trim()
    )
)

const sharePlatformVisuals = {
  weibo: { mark: "博", tone: "weibo" },
  xiaohongshu: { mark: "红", tone: "xiaohongshu" },
  douyin: { mark: "抖", tone: "douyin" },
  zhihu: { mark: "知", tone: "zhihu" },
  qq: { mark: "Q", tone: "qq" },
  wechat: { mark: "微", tone: "wechat" },
}

watch(
  () => route.query.benefit,
  (value) => {
    const next = String(value || "").trim()
    if (tabs.some((item) => item.key === next)) {
      activePage.value = next
    }
  },
  { immediate: true },
)

watch(activePage, async (value) => {
  const current = String(route.query.benefit || "")
  if (value === current || (value === "classroom" && !current)) return
  const query = value === "classroom" ? { ...route.query, benefit: undefined } : { ...route.query, benefit: value }
  await router.replace({ path: route.path, query })
})

onMounted(async () => {
  if (!getUserToken()) return
  await refreshUser()
  await loadPromoCenter()
})

function setFeedback(text, tone = "info") {
  feedback.text = text
  feedback.tone = tone
}

function goLogin() {
  const redirect = encodeURIComponent(route.fullPath || "/app/referral")
  router.push(`/login?redirect=${redirect}`)
}

async function copyText(value, message) {
  try {
    await navigator.clipboard.writeText(value)
    setFeedback(message, "ok")
  } catch {
    setFeedback("复制失败，请稍后重试", "error")
  }
}

function refreshProgress() {
  loadPromoCenter()
}

async function loadPromoCenter() {
  try {
    const data = await userHttp.get("/users/me/promo-center")
    const subsidy = data?.subsidy || {}
    if (Array.isArray(subsidy.share_tasks) && subsidy.share_tasks.length) {
      shareTasks.value = subsidy.share_tasks.map((item) => ({
        key: item.key,
        label: item.label,
        desc: item.note,
        reward: Number(item.reward_credits || 0),
        status: item.status,
      }))
    }
    if (Array.isArray(data?.classroom?.leaderboard) && data.classroom.leaderboard.length) {
      classroomLeaderboard.value = data.classroom.leaderboard.map((item) => ({
        rank: item.rank,
        name: item.name,
        members: item.members,
        activity: item.activity,
        level: item.level,
      }))
    }
    if (data?.classroom?.owned) {
      classroom.created = true
      classroom.id = data.classroom.owned.id
      classroom.name = data.classroom.owned.name
      classroom.inviteCode = data.classroom.owned.invite_code
      classroom.level = data.classroom.owned.level
      classroom.memberCount = Number(data.classroom.owned.member_count || 0)
      classroom.activityScore = Number(data.classroom.owned.activity_score || 0)
    }
    if (Array.isArray(data?.share_center?.platforms) && data.share_center.platforms.length) {
      sharePlatforms.value = data.share_center.platforms.map((item) => ({
        key: item.key,
        name: item.label,
        mark: sharePlatformVisuals[item.key]?.mark || "享",
        tone: sharePlatformVisuals[item.key]?.tone || "wechat",
        rewardText: item.reward,
        status: item.status,
      }))
    }
    if (Array.isArray(data?.share_center?.records) && data.share_center.records.length) {
      shareRecords.value = data.share_center.records
    }
    setFeedback("活动进度已同步", "ok")
  } catch (error) {
    setFeedback(String(error?.message || "活动数据加载失败"), "error")
  }
}

function goBuy() {
  router.push("/app/buy")
}

async function claimSubsidy(taskKey) {
  if (isGuest.value) return goLogin()
  try {
    await userHttp.post("/users/me/promo-center/subsidy/claim", { task_key: taskKey })
    await loadPromoCenter()
    setFeedback("分享得积分任务已领取", "ok")
  } catch (error) {
    setFeedback(String(error?.message || "领取失败"), "error")
  }
}

function buildPosterSvg() {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="1200" viewBox="0 0 900 1200"><rect width="900" height="1200" rx="36" fill="#2563eb"/><text x="72" y="140" fill="#ffffff" font-size="48" font-weight="800">格物学术</text><text x="72" y="230" fill="#dbeafe" font-size="32">推荐格物学术，领取积分和卡券奖励</text><rect x="72" y="330" width="756" height="420" rx="28" fill="rgba(255,255,255,0.92)"/><text x="120" y="450" fill="#111827" font-size="44" font-weight="800">毕业论文相关服务推荐海报</text><text x="120" y="530" fill="#4b5563" font-size="24">检测 / 降AIGC率 / 降重复率</text><text x="120" y="600" fill="#4b5563" font-size="24">扫码或复制链接参与活动</text></svg>`
}

function downloadPoster() {
  const blob = new Blob([buildPosterSvg()], { type: "image/svg+xml;charset=utf-8" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = `promo-${activePage.value}.svg`
  link.click()
  URL.revokeObjectURL(url)
  setFeedback("海报已生成并开始下载", "ok")
}

async function createClassroom() {
  if (isGuest.value) return goLogin()
  try {
    await userHttp.post("/users/me/promo-center/classrooms", { name: classroom.name || "格物毕业互助班" })
    await loadPromoCenter()
    setFeedback("班级已创建，可复制口令邀请同学", "ok")
  } catch (error) {
    setFeedback(String(error?.message || "创建班级失败"), "error")
  }
}

function copyClassroomCode() {
  if (!classroom.inviteCode) return setFeedback("请先创建班级", "info")
  copyText(classroom.inviteCode, "班级口令已复制")
}

async function submitShare() {
  if (isGuest.value) return goLogin()
  if (!shareForm.link.trim()) return setFeedback("请先填写分享链接", "error")
  if (!shareForm.nickname.trim()) return setFeedback("请先填写平台昵称", "error")
  if (!shareForm.account.trim()) return setFeedback("请先填写领取奖励的支付宝号", "error")
  if (!shareForm.realName.trim()) return setFeedback("请先填写支付宝认证姓名", "error")
  try {
    await userHttp.post("/users/me/promo-center/shares", {
      platform: activePlatform.value,
      tier_key: shareForm.tier,
      share_link: shareForm.link,
      account_name: shareForm.account,
      real_name: shareForm.realName,
      note: shareForm.note,
    })
    shareForm.link = ""
    shareForm.nickname = ""
    shareForm.account = ""
    shareForm.realName = ""
    shareForm.note = ""
    await loadPromoCenter()
    setFeedback("分享任务已提交，等待后台人工审核与打款", "ok")
  } catch (error) {
    setFeedback(String(error?.message || "提交审核失败"), "error")
  }
}
</script>

<style scoped>
.promo-page{display:grid;padding:8px 0;background:#fff}
.activity-wrap{display:block;background:#fff;border-radius:20px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:none;backdrop-filter:none}
.activity-wrap--center{width:100%;max-width:1380px;margin:0 auto}
.activity-content{padding:16px 18px;background:#fff}
.activity-layout{display:grid;grid-template-columns:180px minmax(0,1fr);gap:16px;align-items:start}
.activity-sidebar{position:sticky;top:16px;align-self:start;padding:6px;border-radius:18px;border:1px solid #e5e7eb;background:linear-gradient(180deg,#fff 0%,#f8fbff 100%)}
.activity-main{display:grid;gap:10px;min-width:0}
.activity-topbar__nav{list-style:none;display:grid;grid-template-columns:1fr;gap:8px}
.activity-topbar__nav li{min-width:0}
.activity-topbar__nav button{width:100%;display:flex;align-items:center;justify-content:flex-start;min-height:44px;padding:11px 14px;border-radius:14px;font-size:13px;font-weight:600;letter-spacing:.02em;color:#52627d;text-decoration:none;transition:all .18s ease;cursor:pointer;border:1px solid transparent;background:transparent;text-align:left}
.activity-topbar__nav button:hover{background:#f8fafc;color:#10294b;border-color:#e2e8f0}
.activity-topbar__nav button.is-active{background:#fff;color:#1d4ed8;font-weight:700;box-shadow:none;border-color:#dbeafe}
.activity-feedback{width:min(100%,1260px);margin:0 auto 10px;padding:10px 14px;border-radius:14px;border:1px solid #dbeafe;background:#fff;color:#1d4ed8;font-size:13px;box-shadow:none}
.activity-feedback.is-error{color:#1d4ed8;border-color:#dbeafe;background:#fff}
.activity-feedback.is-ok{color:#1d4ed8;border-color:#dbeafe;background:#fff}
.activity-page{display:grid;gap:12px;max-width:1165px;width:100%;aspect-ratio:auto;margin:0 auto;padding:16px 18px;border-radius:20px;border:1px solid #e5e7eb;background:#fff;box-sizing:border-box;box-shadow:none}
.page-title-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:2px}
.page-title-bar--center{justify-content:center;text-align:center}
.page-title-bar h2{font-size:24px;font-weight:800;color:#10294b;letter-spacing:-.02em}
.page-title-bar .subtitle{font-size:13px;color:#5d7393;margin-top:5px;line-height:1.6}
.activity-page--share{gap:10px;padding:14px 16px}
.activity-page--share .page-title-bar h2{font-size:22px}
.activity-page--share .page-title-bar .subtitle{font-size:12px;margin-top:2px;line-height:1.45}
.subsidy-simple{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(220px,.85fr);gap:12px}
.subsidy-simple__hero{background:linear-gradient(135deg,#1d4ed8 0%,#2563eb 55%,#60a5fa 100%);border-radius:14px;padding:18px 20px;color:#fff}
.subsidy-simple__eyebrow{display:inline-flex;align-items:center;min-height:24px;padding:0 10px;border-radius:999px;background:rgba(255,255,255,.18);font-size:11px;font-weight:700;letter-spacing:.08em}
.subsidy-simple__hero h3{margin:12px 0 6px;font-size:24px;line-height:1.2;font-weight:800}
.subsidy-simple__hero p{font-size:13px;line-height:1.7;color:rgba(255,255,255,.88)}
.subsidy-code-row{display:grid;grid-template-columns:180px minmax(0,1fr);gap:10px;margin-top:14px}
.subsidy-code-box{display:grid;gap:4px;padding:12px 14px;border-radius:12px;background:rgba(255,255,255,.95);color:#1e3a8a}
.subsidy-code-box span{font-size:11px;color:#5b6b8a}
.subsidy-code-box strong{font-size:22px;font-weight:800;color:#0f172a;line-height:1.2}
.subsidy-code-box--link strong{font-size:12px;font-weight:700;color:#1e3a8a;word-break:break-all}
.subsidy-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
.subsidy-simple__stats{display:grid;gap:10px}
.subsidy-stat-card{display:grid;gap:6px;padding:16px 18px;border-radius:12px;border:1px solid #dbeafe;background:#fff}
.subsidy-stat-card span{font-size:12px;color:#64748b}
.subsidy-stat-card strong{font-size:28px;font-weight:800;color:#0f172a;line-height:1}
.subsidy-stat-card small{font-size:12px;color:#6b7280;line-height:1.6}
.subsidy-guide{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.subsidy-guide__item{padding:14px 16px;border-radius:12px;border:1px solid #e5e7eb;background:#fff}
.subsidy-guide__item strong{display:block;font-size:14px;color:#111827;margin-bottom:6px}
.subsidy-guide__item p{font-size:12px;color:#6b7280;line-height:1.7}
.jf-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
.jf-header-l{display:flex;align-items:center;gap:16px}
.jf-total-label{font-size:13px;color:#6b7280}
.jf-total-num{font-size:22px;font-weight:900;color:#1d4ed8}
.jf-total-unit{font-size:13px;color:#6b7280}
.jf-header-r{display:flex;gap:10px;align-items:center}
.jf-rule-link{font-size:13px;color:#2563eb;cursor:pointer;background:transparent;border:none;text-decoration:underline}
.refresh-btn{display:flex;align-items:center;gap:5px;font-size:12px;color:#5d7393;cursor:pointer;border:1px solid #d7e6ff;padding:7px 14px;border-radius:999px;background:#fff}
.refresh-btn:hover{background:#eff6ff}
.jf-pipeline{display:flex;align-items:stretch;margin-bottom:12px;border-radius:12px;overflow:hidden;border:1px solid #e5e7eb;background:#fff}
.jf-stage{flex:1;padding:18px 16px 14px;border-right:1px solid #e5e7eb;cursor:pointer;transition:background .15s;position:relative;text-align:left;background:#fff;border-top:none;border-bottom:none;border-left:none}
.jf-stage:last-child{border-right:none}
.jf-stage:hover{background:#f9fafb}
.jf-stage.active{background:linear-gradient(135deg,#f8fbff,#eef5ff)}
.jf-stage.active::after{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;background:#2563eb}
.jf-stage-num{font-size:11px;color:#9ca3af;font-weight:600;letter-spacing:.05em;margin-bottom:6px}
.jf-stage-reward{font-size:20px;font-weight:900;color:#1d4ed8;line-height:1}
.jf-stage-cond{font-size:12px;color:#6b7280;margin-top:5px;line-height:1.4}
.jf-stage-badge{display:inline-block;font-size:10px;font-weight:700;padding:2px 7px;border-radius:99px;margin-top:6px}
.badge-on{background:#e0edff;color:#1d4ed8}
.badge-lock{background:#f3f4f6;color:#9ca3af}
.jf-progress-wrap{background:#e5e7eb;border-radius:99px;height:6px;margin-bottom:24px;overflow:hidden}
.jf-progress-bar{height:6px;border-radius:99px;background:linear-gradient(90deg,#1d4ed8,#60a5fa);transition:width .6s ease}
.rule-box,.detail-card,.reward-card,.steps-card,.submit-card,.lb-card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:16px 18px;box-shadow:none}
.reward-card,.submit-card{width:100%;max-width:none}
.submit-card{margin:0 auto}
.rule-box{display:grid;gap:10px}
.rule-box article strong{display:block;font-size:13px;color:#111827;margin-bottom:3px}
.rule-box article p{font-size:12px;color:#6b7280;line-height:1.7}
.stage-panel-title{font-size:15px;font-weight:700;color:#111827;margin-bottom:14px}
.task-list,.promo-list{display:flex;flex-direction:column;gap:10px}
.task-row,.promo-item{display:flex;align-items:center;gap:14px;background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:15px 20px}
.task-info,.tier-cond{flex:1}
.task-name{font-size:14px;font-weight:600;margin-bottom:3px}
.task-desc,.tier-cond div{font-size:12px;color:#6b7280}
.task-pts,.tier-money{font-size:15px;font-weight:800;color:#1d4ed8;white-space:nowrap}
.task-btn,.btn-primary,.btn-ghost{display:inline-flex;align-items:center;justify-content:center;padding:9px 20px;border-radius:999px;font-size:13px;font-weight:700;cursor:pointer;border:none}
.task-btn{background:#2563eb;color:#fff}
.task-btn.done{background:#eef5ff;color:#1d4ed8}
.poster-down{display:flex;align-items:center;justify-content:center;gap:7px;margin-top:12px;font-size:13px;color:#2563eb;cursor:pointer;background:transparent;border:none}
.locked-panel{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:24px;text-align:center}
.locked-title{font-size:15px;font-weight:700;color:#374151;margin-bottom:6px}
.locked-desc{font-size:13px;color:#6b7280;line-height:1.6}
.invite-stats{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px 20px;display:flex;align-items:center;gap:24px;flex-wrap:wrap}
.invite-stat-item{text-align:center}
.invite-stat-num{font-size:20px;font-weight:900;color:#111827}
.invite-stat-label{font-size:11px;color:#6b7280;margin-top:2px}
.invite-sep{width:1px;height:36px;background:#e5e7eb}
.invite-actions{margin-left:auto;display:flex;gap:10px}
.btn-primary{background:#2563eb;color:#fff;box-shadow:none}
.btn-ghost{background:#fff;color:#5d7393;border:1px solid #d7e6ff}
.detail-card__head{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px}
.detail-card__head h3{font-size:15px;color:#111827}
.detail-card__head small{font-size:12px;color:#6b7280}
.detail-table{display:grid;gap:0}
.detail-table__head,.detail-table__row{display:grid;grid-template-columns:1.4fr .8fr .8fr;gap:12px;padding:12px 0;border-bottom:1px solid #f3f4f6;font-size:13px}
.detail-table__head{font-weight:700;color:#374151}
.detail-table__row{color:#6b7280}
.class-show-wrap{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;justify-content:center;align-items:start}
.share-layout{display:grid;grid-template-columns:minmax(0,1fr);gap:8px;align-items:start;max-width:none;width:100%;margin:0 auto}
.share-layout__left,.share-layout__right{display:grid;gap:12px}
.class-hero{background:#fff;border:1px solid #e5e7eb;border-radius:20px;padding:22px 22px;color:#10294b;margin-bottom:12px;box-shadow:none}
.class-hero__eyebrow{display:inline-flex;align-items:center;min-height:26px;padding:0 12px;border-radius:999px;background:#fff;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;border:1px solid #dbeafe;color:#1d4ed8}
.class-hero h1{max-width:520px;font-size:13px;font-weight:400;line-height:1.8;margin:8px 0 4px;color:#355070;white-space:normal}
.class-hero p{font-size:10px;opacity:1;max-width:520px;line-height:1.6;color:#6b7f99}
.class-hero__stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}
.class-hero__stats article{padding:9px 11px;border-radius:16px;background:#fff;border:1px solid #e5e7eb}
.class-hero__stats span{display:block;font-size:11px;opacity:1;margin-bottom:6px;color:#64748b}
.class-hero__stats strong{display:block;font-size:18px;font-weight:800;line-height:1.2;color:#10294b}
.class-tiers{display:flex;flex-direction:column;gap:7px}
.class-tier{display:flex;align-items:center;gap:12px;background:#fff;border-radius:16px;padding:12px 15px;border:1px solid #e5e7eb}
.class-tier-icon{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:#fff;color:#1d4ed8;font-weight:900;border:1px solid #dbeafe}
.class-tier-title{font-size:14px;font-weight:700;color:#111827;margin-bottom:3px}
.class-tier-cond{font-size:12px;color:#6b7280;line-height:1.6}
.class-tier-tag{margin-left:auto;font-size:11px;padding:5px 10px;border-radius:999px;font-weight:800;background:#fff;color:#5d7393;border:1px solid #e5e7eb}
.create-btn-big{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:12px;background:#2563eb;color:#fff;border:none;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;margin-top:10px;box-shadow:none}
.class-room-box{background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:13px;margin-top:10px;display:grid;gap:8px}
.class-room-box strong{font-size:14px;color:#1e3a8a}
.class-room-box p{font-size:12px;color:#4b5563;line-height:1.6}
.class-room-actions{display:flex;gap:10px}
.lb-card h3,.reward-card h4,.steps-card h4,.submit-card h4{font-size:14px;font-weight:800;margin-bottom:10px;color:#14345f}
.lb-row{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid #f3f4f6;font-size:13px}
.lb-row:last-child{border-bottom:none}
.lb-rank{width:24px;text-align:center;font-weight:700;font-size:14px}
.lb-info{flex:1;min-width:0}
.lb-name{font-weight:600;font-size:13px}
.lb-meta{font-size:11px;color:#9ca3af;margin-top:1px}
.lb-level{font-size:10px;padding:2px 7px;border-radius:99px;font-weight:700;white-space:nowrap;background:#fff;color:#1d4ed8;border:1px solid #dbeafe}
.share-plat-tabs{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin:0 auto 8px;max-width:none;width:100%}
.share-plat-tabs--center{justify-content:center}
.plat-tab{display:flex;align-items:center;gap:9px;padding:9px 11px;border:1.5px solid #e5e7eb;border-radius:16px;cursor:pointer;background:#fff;min-width:0;transition:all .18s ease;text-align:left;position:relative;box-shadow:none}
.plat-tab:hover{border-color:#bfdbfe;background:#fff;transform:none}
.plat-tab.active{border-color:#2563eb;background:#fff;box-shadow:none}
.plat-tab__icon{width:30px;height:30px;border-radius:999px;color:#fff;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:800;flex-shrink:0}
.plat-tab__icon.is-weibo{background:#e6162d}
.plat-tab__icon.is-xiaohongshu{background:#ff2442}
.plat-tab__icon.is-douyin{background:#161823}
.plat-tab__icon.is-zhihu{background:#1677ff}
.plat-tab__icon.is-qq{background:#12b7f5}
.plat-tab__icon.is-wechat{background:#07c160}
.plat-tab__body{display:grid;gap:2px}
.plat-tab__body strong{font-size:12px;color:#374151;line-height:1.2}
.plat-tab__body small{font-size:10px;color:#1d4ed8;font-weight:700;line-height:1.2}
.plat-tab__body em{font-size:10px;font-style:normal;color:#6b7280;line-height:1.2}
.plat-tab__check{position:absolute;right:8px;bottom:8px;width:16px;height:16px;border-radius:999px;background:#2563eb;color:#fff;display:flex;align-items:center;justify-content:center;font-size:10px}
.activity-page--share .share-plat-tabs{gap:6px;margin-bottom:6px}
.activity-page--share .plat-tab{gap:8px;padding:7px 9px;border-radius:14px}
.activity-page--share .plat-tab__icon{width:26px;height:26px;font-size:11px}
.activity-page--share .plat-tab__body strong{font-size:11px}
.activity-page--share .plat-tab__body small,
.activity-page--share .plat-tab__body em{font-size:9px}
.activity-page--share .share-layout__left{gap:8px}
.activity-page--share .reward-card,
.activity-page--share .submit-card{padding:12px 14px;border-radius:14px}
.activity-page--share .reward-card h4,
.activity-page--share .submit-card h4{font-size:13px;margin-bottom:8px}
.task-table{display:grid}
.task-table__row{display:grid;grid-template-columns:108px 1fr;gap:12px;padding:7px 0;border-bottom:1px solid #eef3f9}
.task-table__row:last-child{border-bottom:none}
.task-table__row span{font-size:12px;color:#6b7280}
.task-table__row strong{font-size:12px;color:#374151;line-height:1.5;font-weight:500}
.task-table__reward-list{display:flex;flex-direction:column;gap:2px}
.task-table__row--compact{align-items:center}
.reward-inline-text{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.activity-page--share .task-table__row{grid-template-columns:96px 1fr;gap:10px;padding:5px 0}
.activity-page--share .task-table__row span,
.activity-page--share .task-table__row strong{font-size:11px;line-height:1.35}
.activity-page--share .reward-inline-text{font-size:10px;letter-spacing:-.01em}
.tier-row{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid #f3f4f6}
.tier-row:last-child{border-bottom:none}
.step-row{display:flex;gap:10px;margin-bottom:12px}
.step-row:last-child{margin-bottom:0}
.steps-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.step-num{min-width:58px;height:28px;border-radius:14px;background:#dbeafe;color:#2563eb;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;flex-shrink:0;margin-top:2px}
.step-body{display:grid;gap:4px}
.step-title{font-size:13px;font-weight:700}
.step-link{font-size:12px;color:#2563eb}
.step-desc{font-size:11px;color:#6b7280;line-height:1.6}
.submit-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.form-group--full{grid-column:1 / -1}
.form-group{display:grid;gap:4px;margin-bottom:4px}
.form-group span{font-size:12px;font-weight:600;color:#374151}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:9px 12px;border:1px solid #e5e7eb;border-radius:12px;font-size:12px;font-family:inherit;outline:none;background:#fff}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:#60a5fa;box-shadow:0 0 0 4px rgba(191,219,254,.5)}
.activity-page--share .submit-grid{gap:6px}
.activity-page--share .form-group{gap:3px;margin-bottom:2px}
.activity-page--share .form-group span{font-size:11px}
.activity-page--share .form-group input,
.activity-page--share .form-group select,
.activity-page--share .form-group textarea{padding:7px 10px;border-radius:10px;font-size:11px}
.activity-page--share .form-group textarea{min-height:38px;resize:none}
.radio-list{display:grid;gap:6px}
.radio-item{display:flex;align-items:center;gap:8px;font-size:11px;color:#4b5563}
.submit-card .btn-primary{display:flex;min-width:148px;margin:4px auto 0}
.risk-tip{font-size:10px;color:#6b7280;display:flex;gap:5px;margin-top:6px;line-height:1.4}
.activity-page--share .submit-card .btn-primary{min-width:132px;margin-top:2px;padding:8px 18px}
.activity-page--share .risk-tip{font-size:9px;margin-top:4px;line-height:1.3}
@media (max-width:1100px){.promo-page{height:auto;min-height:unset;max-height:none}.activity-layout{grid-template-columns:1fr}.activity-sidebar{position:static;top:auto}.activity-topbar__nav{grid-template-columns:repeat(2,minmax(0,1fr))}.activity-page{max-width:980px;height:auto;min-height:auto;aspect-ratio:auto;padding:14px 16px;overflow:visible}.class-show-wrap,.share-layout,.steps-grid,.submit-grid,.subsidy-simple,.subsidy-guide{grid-template-columns:1fr}.activity-content{padding:18px;overflow:visible}}
@media (max-width:720px){.jf-header,.page-title-bar,.invite-stats,.class-room-actions,.promo-actions,.subsidy-actions{flex-direction:column;align-items:stretch}.jf-pipeline,.subsidy-code-row{display:grid;grid-template-columns:1fr}.stage-rail,.detail-table__head,.detail-table__row,.task-table__row,.steps-grid,.submit-grid,.activity-topbar__nav{grid-template-columns:1fr}.share-plat-tabs{display:grid;grid-template-columns:1fr}.plat-tab{min-width:0}.activity-content{padding:16px}.activity-sidebar{padding:5px}.activity-topbar__nav{gap:6px}.activity-topbar__nav button{min-height:36px;padding:8px 10px;font-size:11px}}
</style>
