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
                  <div class="subtitle">创建班级后邀请同学加入，按人数提升班级等级，分享任务奖励请以“分享得积分”为准</div>
                </div>
              </div>

              <div class="class-show-wrap">
                <div>
                  <div class="class-hero">
                  <div class="class-hero__eyebrow">班级裂变福利</div>
                    <h1>创建班级后邀请同学加入，按人数逐步提升班级等级与成长进度。当前版本不发放班级卡券，活动奖励以实际到账记录为准。</h1>
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
                    <div class="class-progress">
                      <div class="class-progress__head">
                        <span>班级成长进度</span>
                        <strong>{{ classroom.created ? Math.min(classroom.memberCount, 40) : 0 }}/40</strong>
                      </div>
                      <div class="class-progress__track">
                        <div class="class-progress__bar" :style="{ width: `${classroomProgressPercent}%` }" />
                      </div>
                    </div>
                  </div>

                  <div class="class-tiers">
                    <div v-for="item in classroomTiers" :key="item.title" class="class-tier">
                      <div class="class-tier-icon">{{ item.icon }}</div>
                      <div>
                        <div class="class-tier-title">{{ item.title }}</div>
                        <div class="class-tier-cond">{{ item.desc }}</div>
                        <div class="class-tier-reward">{{ item.reward }}</div>
                      </div>
                      <span class="class-tier-tag" :class="{ 'is-unlocked': item.unlocked }">{{ item.tag }}</span>
                    </div>
                  </div>

                  <div v-if="!classroom.created || classroom.role === 'owner'" class="class-form-card">
                    <label class="class-form-field">
                      <span>班级名称</span>
                      <input
                        v-model.trim="classroomDraftName"
                        type="text"
                        maxlength="120"
                        placeholder="例如：论文终稿冲刺班"
                        :disabled="creatingClassroom"
                      />
                    </label>
                    <button type="button" class="create-btn-big" :disabled="creatingClassroom" @click="createClassroom">
                      {{ creatingClassroom ? "处理中..." : classroom.created ? "刷新我的班级状态" : "立即创建班级，全班免费查" }}
                    </button>
                  </div>

                  <div v-if="!classroom.created" class="class-form-card">
                    <label class="class-form-field">
                      <span>已有班级口令？输入后直接加入</span>
                      <input
                        v-model.trim="joinInviteCode"
                        type="text"
                        maxlength="24"
                        placeholder="例如：CLABC123"
                        :disabled="joiningClassroom"
                      />
                    </label>
                    <button type="button" class="create-btn-big create-btn-big--secondary" :disabled="joiningClassroom" @click="joinClassroomByCode">
                      {{ joiningClassroom ? "加入中..." : "加入班级，参与组队成长" }}
                    </button>
                  </div>

                  <div v-if="classroom.created" class="class-room-box">
                    <article>
                      <strong>{{ classroom.name }}</strong>
                      <p>{{ classroomRoleLabel }} · {{ classroom.level }} · {{ classroom.memberCount }} 人 · 活跃度 {{ classroom.activityScore }}</p>
                    </article>
                    <article>
                      <strong>入班口令：{{ classroom.inviteCode }}</strong>
                      <p>{{ classroom.role === "owner" ? "复制口令或邀请文案，继续拉同学进班。" : "把口令发给同学即可加入同一班级。" }}</p>
                    </article>
                    <div class="class-room-actions">
                      <button type="button" class="btn-ghost" @click="copyClassroomCode">复制口令</button>
                      <button v-if="classroom.role === 'owner'" type="button" class="btn-ghost" @click="copyClassroomInviteText">复制邀请文案</button>
                    </div>
                    <p v-if="classroom.role !== 'owner'" class="class-lock-tip">你已加入班级，当前版本暂不支持切换到其他班级。</p>
                  </div>
                </div>
              </div>
            </section>

            <section v-else-if="activePage === 'fission'" class="activity-page activity-page--fission">
              <div class="page-title-bar page-title-bar--center">
                <div>
                  <h2>分享得积分</h2>
                  <div class="subtitle">分享专属网站链接邀请新用户使用，按登录与转化解锁奖励</div>
                </div>
              </div>

              <div class="fission-metrics">
                <article class="fission-metric">
                  <span>累计邀请登录</span>
                  <strong>{{ fissionStats.inviteLoginCount }}</strong>
                  <small>每邀请 1 位新用户登录奖励 2000 积分</small>
                </article>
                <article class="fission-metric">
                  <span>邀请首单转化</span>
                  <strong>{{ fissionStats.firstOrderCount }}</strong>
                  <small>完成首单可解锁券包奖励</small>
                </article>
                <article class="fission-metric">
                  <span>已获积分估算</span>
                  <strong>{{ fissionStats.estimatedCredits }}</strong>
                  <small>按当前登录转化自动估算</small>
                </article>
              </div>

              <div class="fission-progress">
                <div class="fission-progress__head">
                  <span>分享进度</span>
                  <strong>{{ fissionCompletedCount }}/{{ fissionStages.length }} 已达成 · 下一目标：{{ fissionNextMilestone }}</strong>
                </div>
                <div class="fission-progress__track">
                  <div class="fission-progress__bar" :style="{ width: `${fissionProgressPercent}%` }" />
                </div>
                <div class="fission-stage-list">
                  <article v-for="stage in fissionStages" :key="stage.key" class="fission-stage" :class="{ 'is-done': stage.done }">
                    <div class="fission-stage__title">
                      <strong>{{ stage.title }}</strong>
                      <span>{{ stage.done ? "已达成" : "进行中" }}</span>
                    </div>
                    <p>{{ stage.desc }}</p>
                    <small>{{ stage.reward }}</small>
                  </article>
                </div>
              </div>

              <div class="fission-layout">
                <div class="fission-card">
                  <h4>我的专属邀请</h4>
                  <div class="fission-code-grid">
                    <article>
                      <span>邀请码</span>
                      <strong>{{ fissionInvite.code || "登录后生成" }}</strong>
                    </article>
                    <article>
                      <span>邀请链接</span>
                      <strong class="fission-link">{{ fissionInvite.link || "登录后生成专属链接" }}</strong>
                    </article>
                  </div>
                  <div class="fission-actions">
                    <button type="button" class="btn-primary" @click="copyFissionInviteLink">复制邀请链接</button>
                    <button type="button" class="btn-ghost" @click="copyFissionInviteText">复制邀请文案</button>
                    <button type="button" class="btn-ghost" @click="copyFissionInviteCode">复制邀请码</button>
                  </div>
                  <p v-if="isGuest" class="fission-guest-tip">当前为游客模式，登录后可生成你的专属邀请链接和二维码。</p>
                </div>

                <div class="fission-card fission-card--qrcode">
                  <h4>邀请二维码</h4>
                  <div class="fission-qrcode">
                    <img v-if="fissionInvite.qrcodeDataUrl" :src="fissionInvite.qrcodeDataUrl" alt="邀请二维码" />
                    <span v-else>登录后生成二维码</span>
                  </div>
                </div>
              </div>

              <div class="fission-card">
                <div class="detail-card__head">
                  <h4>最新奖励动态</h4>
                  <small>{{ fissionRewardRecords.length }} 条</small>
                </div>
                <div v-if="fissionRewardRecords.length" class="fission-reward-list">
                  <article v-for="(item, index) in fissionRewardRecords" :key="`${item.title}-${index}`" class="fission-reward-item">
                    <div>
                      <strong>{{ item.title }}</strong>
                      <p>{{ item.note }}</p>
                    </div>
                    <span>{{ item.reward }}</span>
                  </article>
                </div>
                <p v-else class="share-empty">暂无奖励动态，邀请新用户登录后会自动记录在这里。</p>
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
                    <em>{{ resolveShareStatusMeta(item.status).label }}</em>
                  </div>
                  <div v-if="activePlatform === item.key" class="plat-tab__check">✓</div>
                </button>
              </div>

              <div class="share-layout">
                <div class="share-layout__left">
                  <div class="share-status-card">
                    <div class="share-status-card__head">
                      <strong>{{ currentPlatformName }}当前进度</strong>
                      <span class="share-status-tag" :class="`is-${currentShareStatusMeta.tone}`">{{ currentShareStatusMeta.label }}</span>
                    </div>
                    <p>{{ currentShareStatusMeta.desc }}</p>
                    <small v-if="currentPlatformSubmitTip">{{ currentPlatformSubmitTip }}</small>
                  </div>

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
                        <input v-model.trim="shareForm.link" type="text" placeholder="填写分享后的链接（链接必须为可访问地址）" :disabled="shareFormDisabled" />
                      </label>
                      <label class="form-group">
                        <span>输入平台昵称</span>
                        <input v-model.trim="shareForm.nickname" type="text" placeholder="请输入账号昵称（提交后不可修改哦，请谨慎填写）" :disabled="shareFormDisabled" />
                      </label>
                      <label class="form-group">
                        <span>输入领取奖励的支付宝号</span>
                        <input v-model.trim="shareForm.account" type="text" placeholder="请输入支付宝号（提交后不可修改哦，请谨慎填写）" :disabled="shareFormDisabled" />
                      </label>
                      <label class="form-group">
                        <span>输入支付宝认证姓名</span>
                        <input v-model.trim="shareForm.realName" type="text" placeholder="请输入支付宝认证姓名（用于打款时的身份验证）" :disabled="shareFormDisabled" />
                      </label>
                      <label class="form-group form-group--full">
                        <span>选择符合条件的奖励</span>
                        <select v-model="shareForm.tier" :disabled="shareFormDisabled">
                          <option v-for="item in shareTiers" :key="item.key" :value="item.key">
                            {{ item.reward }}（{{ item.desc }}）
                          </option>
                        </select>
                      </label>
                      <label class="form-group form-group--full">
                        <span>补充说明</span>
                        <textarea v-model.trim="shareForm.note" rows="1" placeholder="可补充点赞数、发布时间或作品说明" :disabled="shareFormDisabled"></textarea>
                      </label>
                    </div>
                    <button type="button" class="btn-primary" :disabled="!canSubmitShare" @click="submitShare">{{ shareSubmitButtonText }}</button>
                    <p class="risk-tip">⚠️ 提交后不可修改，请谨慎填写（若发现任何形式的弄虚作假骗取奖励的行为，将拒绝审核，并取消所有活动资格。）</p>
                  </div>
                </div>

                <div class="share-layout__right">
                  <div class="detail-card">
                    <div class="detail-card__head">
                      <h3>我的提交记录</h3>
                      <small>{{ normalizedShareRecords.length }} 条</small>
                    </div>
                    <div v-if="normalizedShareRecords.length" class="share-record-list">
                      <article v-for="item in normalizedShareRecords" :key="item.id" class="share-record-item">
                        <div class="share-record-item__main">
                          <strong>{{ item.platform }} · {{ item.reward }}</strong>
                          <p>{{ item.note }}</p>
                          <small v-if="item.submitNote">提交备注：{{ item.submitNote }}</small>
                        </div>
                        <span class="share-status-tag" :class="`is-${item.statusTone}`">{{ item.statusLabel }}</span>
                      </article>
                    </div>
                    <p v-else class="share-empty">还没有提交记录，先选一个平台提交审核。</p>
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
  { key: "fission", label: "分享得积分" },
  { key: "share", label: "分享领红包" },
]

const fissionInvite = reactive({
  code: "",
  link: "",
  qrcodeDataUrl: "",
})

const fissionStats = reactive({
  inviteLoginCount: 0,
  firstOrderCount: 0,
  estimatedCredits: 0,
})

const fissionRewardRecords = ref([])

const shareTasks = ref([
  { key: "wechat", label: "分享朋友圈", desc: "将平台海报和检测体验分享到朋友圈", reward: 5000, status: "ready" },
  { key: "qq", label: "分享QQ空间", desc: "将平台海报分享到 QQ 空间", reward: 3000, status: "claimed" },
  { key: "weibo", label: "分享微博", desc: "发布微博并推荐论文服务", reward: 2000, status: "claimed" },
])

const classroom = reactive({
  created: false,
  id: null,
  name: "",
  inviteCode: "",
  role: "member",
  level: "待创建",
  memberCount: 0,
  activityScore: 0,
})
const classroomDraftName = ref("")
const joinInviteCode = ref("")
const creatingClassroom = ref(false)
const joiningClassroom = ref(false)
const submittingShare = ref(false)

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

const classroomTierRules = [
  {
    icon: "Ⅰ",
    threshold: 5,
    title: "5人成团（白银班）",
    reward: "已上线激励：成员去“分享得积分”，每邀请1位新用户登录可得 +2000 积分（个人到账）。",
  },
  {
    icon: "Ⅱ",
    threshold: 20,
    title: "20人进阶（黄金班）",
    reward: "已上线激励：20人班级更易形成裂变，积分奖励按成员个人邀请效果实时累计。",
  },
  {
    icon: "Ⅲ",
    threshold: 40,
    title: "40人满阶（钻石班）",
    reward: "已上线激励：冲刺邀请登录与首单转化，奖励以系统到账记录和审核结果为准。",
  },
]

const classroomTiers = computed(() => {
  const current = classroom.created ? Number(classroom.memberCount || 0) : 0
  return classroomTierRules.map((item) => {
    const unlocked = current >= item.threshold
    const left = Math.max(item.threshold - current, 0)
    return {
      ...item,
      unlocked,
      desc: classroom.created
        ? (unlocked ? `已达 ${item.threshold} 人，班级等级已解锁` : `班级成员达 ${item.threshold} 人 · 还差 ${left} 人`)
        : `班级成员达 ${item.threshold} 人，解锁下一等级`,
      tag: unlocked ? "已解锁" : `差 ${left} 人`,
    }
  })
})

const nextClassroomTarget = computed(() => {
  if (!classroom.created) {
    return "5 人起解锁"
  }
  const current = Number(classroom.memberCount || 0)
  const next = classroomTierRules.find((item) => current < item.threshold)
  if (!next) {
    return "已达最高档"
  }
  return `还差 ${next.threshold - current} 人`
})

const classroomProgressPercent = computed(() => {
  const current = classroom.created ? Number(classroom.memberCount || 0) : 0
  const progressBase = Math.min(Math.max(current, 0), 40)
  return Math.round((progressBase / 40) * 100)
})

const classroomRoleLabel = computed(() => (classroom.role === "owner" ? "班级创建者" : "班级成员"))

const fissionStages = computed(() => {
  const inviteCount = Number(fissionStats.inviteLoginCount || 0)
  const firstOrderCount = Number(fissionStats.firstOrderCount || 0)
  const hasInviteBase = Boolean(String(fissionInvite.code || "").trim())
  return [
    {
      key: "seed",
      title: "发布专属邀请链接",
      desc: "复制你的专属邀请链接并分享给同学或社群。",
      reward: "完成分享起点",
      done: hasInviteBase,
    },
    {
      key: "login_1",
      title: "邀请 1 位新用户登录",
      desc: "任意新用户通过你的链接完成登录。",
      reward: "+2000 积分",
      done: inviteCount >= 1,
    },
    {
      key: "login_3",
      title: "邀请 3 位新用户登录",
      desc: "累计邀请 3 位新用户成功登录。",
      reward: "+6000 积分（累计）",
      done: inviteCount >= 3,
    },
    {
      key: "first_order",
      title: "促成 1 位首单转化",
      desc: "被邀请用户完成首笔下单支付。",
      reward: "至尊查重券 / AIGC 检测券 / 降重券",
      done: firstOrderCount >= 1,
    },
    {
      key: "login_10",
      title: "邀请 10 位新用户登录",
      desc: "持续扩散，累计邀请 10 位新用户登录。",
      reward: "+20000 积分（累计）",
      done: inviteCount >= 10,
    },
  ]
})

const fissionCompletedCount = computed(() => fissionStages.value.filter((item) => item.done).length)
const fissionProgressPercent = computed(() => Math.round((fissionCompletedCount.value / Math.max(fissionStages.value.length, 1)) * 100))
const fissionNextMilestone = computed(() => {
  const next = fissionStages.value.find((item) => !item.done)
  return next ? next.title : "全部达成"
})

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
      !submittingShare.value &&
      currentPlatformCanSubmit.value &&
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

const shareStatusVisuals = {
  ready: { label: "可提交", tone: "ready", desc: "当前平台还未提交，完成内容发布后可立即提交审核。" },
  submitted: { label: "审核中", tone: "submitted", desc: "资料已提交，运营正在审核中。审核通过后会进入打款队列。" },
  approved: { label: "待打款", tone: "approved", desc: "审核已通过，等待人工发放红包。" },
  paid: { label: "已打款", tone: "paid", desc: "红包已发放，到账后可在账户余额查看。" },
  rejected: { label: "未通过", tone: "rejected", desc: "审核未通过，请修改内容后重新提交。" },
}

function resolveShareStatusMeta(status) {
  return shareStatusVisuals[String(status || "").trim().toLowerCase()] || shareStatusVisuals.ready
}

const currentPlatformItem = computed(() => {
  return sharePlatforms.value.find((item) => item.key === activePlatform.value) || null
})

const currentPlatformCanSubmit = computed(() => currentPlatformItem.value?.canSubmit !== false)
const currentPlatformSubmitTip = computed(() => {
  if (!currentPlatformItem.value) return ""
  const backendTip = String(currentPlatformItem.value.submitTip || "").trim()
  if (backendTip) return backendTip
  return currentPlatformCanSubmit.value ? "当前平台可提交" : "当前平台暂不可提交"
})
const shareFormDisabled = computed(() => submittingShare.value || !currentPlatformCanSubmit.value)

const currentShareStatusMeta = computed(() => resolveShareStatusMeta(currentPlatformItem.value?.status))

const normalizedShareRecords = computed(() => {
  return shareRecords.value.map((item) => {
    const statusMeta = resolveShareStatusMeta(item.status)
    return {
      ...item,
      statusLabel: item.status_label || statusMeta.label,
      statusTone: statusMeta.tone,
      submitNote: String(item.submit_note || "").trim(),
    }
  })
})

const currentPlatformRecord = computed(() => {
  return normalizedShareRecords.value.find((item) => item.platformKey === activePlatform.value) || null
})

const shareSubmitButtonText = computed(() => {
  if (submittingShare.value) return "提交中..."
  if (!currentPlatformCanSubmit.value) {
    return currentShareStatusMeta.value.label
  }
  if (currentPlatformItem.value && String(currentPlatformItem.value.status || "") === "rejected") {
    return "更新本平台提交信息"
  }
  return "提交审核"
})

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

watch(
  () => route.query.class_code,
  (value) => {
    const inviteCode = String(value || "").trim().toUpperCase()
    if (!inviteCode) {
      return
    }
    joinInviteCode.value = inviteCode
    activePage.value = "classroom"
  },
  { immediate: true },
)

watch(activePage, async (value) => {
  const current = String(route.query.benefit || "")
  if (value === current || (value === "classroom" && !current)) return
  const query = value === "classroom" ? { ...route.query, benefit: undefined } : { ...route.query, benefit: value }
  await router.replace({ path: route.path, query })
})

watch(
  [activePlatform, currentPlatformRecord],
  () => {
    hydrateShareFormFromCurrentPlatform()
  },
  { immediate: true },
)

onMounted(async () => {
  if (!getUserToken()) return
  await refreshUser()
  await loadPromoCenter(false)
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
  loadPromoCenter(true)
}

function applyClassroomPayload(payload) {
  if (!payload) {
    classroom.created = false
    classroom.id = null
    classroom.name = ""
    classroom.inviteCode = ""
    classroom.role = "member"
    classroom.level = "待创建"
    classroom.memberCount = 0
    classroom.activityScore = 0
    classroomDraftName.value = ""
    return
  }
  classroom.created = true
  classroom.id = payload.id
  classroom.name = payload.name || ""
  classroom.inviteCode = String(payload.invite_code || "").toUpperCase()
  classroom.role = payload.role === "owner" ? "owner" : "member"
  classroom.level = payload.level || "青铜班"
  classroom.memberCount = Number(payload.member_count || 0)
  classroom.activityScore = Number(payload.activity_score || 0)
  if (classroom.role === "owner") {
    classroomDraftName.value = classroom.name || ""
  }
}

async function loadPromoCenter(showSuccess = false) {
  try {
    const data = await userHttp.get("/users/me/promo-center")
    const invitePayload = data?.invite || {}
    fissionInvite.code = String(invitePayload.invite_code || "").toUpperCase()
    fissionInvite.link = String(invitePayload.invite_link || "")
    fissionInvite.qrcodeDataUrl = String(invitePayload.qrcode_data_url || "")

    const subsidy = data?.subsidy || {}
    fissionStats.inviteLoginCount = Number(subsidy.invite_login_count || 0)
    fissionStats.firstOrderCount = Number(subsidy.first_order_count || 0)
    fissionStats.estimatedCredits = Math.max(0, fissionStats.inviteLoginCount * 2000)

    if (Array.isArray(subsidy.ledger)) {
      fissionRewardRecords.value = subsidy.ledger.map((item) => ({
        title: String(item.title || "奖励记录"),
        note: String(item.note || ""),
        reward: String(item.reward || "-"),
      }))
    } else {
      fissionRewardRecords.value = []
    }

    if (Array.isArray(subsidy.share_tasks)) {
      shareTasks.value = subsidy.share_tasks.map((item) => ({
        key: item.key,
        label: item.label,
        desc: item.note,
        reward: Number(item.reward_credits || 0),
        status: item.status,
      }))
    }
    applyClassroomPayload(data?.classroom?.joined || data?.classroom?.owned || null)
    if (Array.isArray(data?.share_center?.platforms)) {
      sharePlatforms.value = data.share_center.platforms.map((item) => ({
        key: item.key,
        name: item.label,
        mark: sharePlatformVisuals[item.key]?.mark || "享",
        tone: sharePlatformVisuals[item.key]?.tone || "wechat",
        rewardText: item.reward,
        status: item.status || "ready",
        canSubmit: item.can_submit !== false,
        submitTip: item.submit_tip || "",
      }))
    }
    if (Array.isArray(data?.share_center?.records)) {
      shareRecords.value = data.share_center.records.map((item) => ({
        id: item.id,
        platformKey: item.platform_key,
        platform: item.platform,
        status: item.status || "ready",
        status_label: item.status_label || "",
        note: item.note || "",
        reward: item.reward || "-",
        submit_note: item.submit_note || "",
        tier_key: item.tier_key || "top",
        share_link: item.share_link || "",
        payout_account: item.payout_account || "",
        payout_name: item.payout_name || "",
      }))
    }
    if (showSuccess) {
      setFeedback("活动进度已同步", "ok")
    }
  } catch (error) {
    setFeedback(String(error?.message || "活动数据加载失败"), "error")
  }
}

function goBuy() {
  router.push("/app/buy")
}

function ensureFissionAuth() {
  if (!isGuest.value) {
    return true
  }
  goLogin()
  return false
}

async function copyFissionInviteCode() {
  if (!ensureFissionAuth()) return
  if (!fissionInvite.code) {
    setFeedback("邀请码生成中，请稍后重试", "info")
    return
  }
  await copyText(fissionInvite.code, "邀请码已复制")
}

async function copyFissionInviteLink() {
  if (!ensureFissionAuth()) return
  if (!fissionInvite.link) {
    setFeedback("邀请链接生成中，请稍后重试", "info")
    return
  }
  await copyText(fissionInvite.link, "邀请链接已复制")
}

async function copyFissionInviteText() {
  if (!ensureFissionAuth()) return
  if (!fissionInvite.link) {
    setFeedback("邀请链接生成中，请稍后重试", "info")
    return
  }
  const text = [
    "我在用格物学术做论文检测和降重，体验不错。",
    `专属邀请链接：${fissionInvite.link}`,
    `邀请码：${fissionInvite.code || "-"}`,
    "通过链接注册并登录后，你我都能解锁活动福利。",
  ].join("\n")
  await copyText(text, "邀请文案已复制")
}

async function claimSubsidy(taskKey) {
  if (isGuest.value) return goLogin()
  try {
    await userHttp.post("/users/me/promo-center/subsidy/claim", { task_key: taskKey })
    await loadPromoCenter(false)
    setFeedback("分享得积分任务已领取", "ok")
  } catch (error) {
    setFeedback(String(error?.message || "领取失败"), "error")
  }
}

async function createClassroom() {
  if (isGuest.value) return goLogin()
  if (creatingClassroom.value) return
  creatingClassroom.value = true
  try {
    const name = classroomDraftName.value.trim() || "格物毕业互助班"
    const data = await userHttp.post("/users/me/promo-center/classrooms", { name })
    applyClassroomPayload(data || null)
    await loadPromoCenter(false)
    setFeedback("班级已创建，可复制口令邀请同学", "ok")
  } catch (error) {
    setFeedback(String(error?.message || "创建班级失败"), "error")
  } finally {
    creatingClassroom.value = false
  }
}

async function joinClassroomByCode() {
  if (isGuest.value) return goLogin()
  if (joiningClassroom.value) return
  const inviteCode = joinInviteCode.value.trim().toUpperCase()
  if (!inviteCode) {
    setFeedback("请先输入班级口令", "error")
    return
  }
  joiningClassroom.value = true
  try {
    const data = await userHttp.post("/users/me/promo-center/classrooms/join", { invite_code: inviteCode })
    applyClassroomPayload(data || null)
    joinInviteCode.value = ""
    await loadPromoCenter(false)
    setFeedback(`已加入班级：${data?.name || ""}`, "ok")
  } catch (error) {
    setFeedback(String(error?.message || "加入班级失败"), "error")
  } finally {
    joiningClassroom.value = false
  }
}

function copyClassroomCode() {
  if (!classroom.inviteCode) return setFeedback("请先创建班级", "info")
  copyText(classroom.inviteCode, "班级口令已复制")
}

function copyClassroomInviteText() {
  if (!classroom.inviteCode) return setFeedback("请先创建班级", "info")
  const origin = typeof window !== "undefined" ? window.location.origin : ""
  const inviteLink = `${origin}/app/referral?benefit=classroom&class_code=${classroom.inviteCode}`
  const text = `我创建了【${classroom.name || "格物毕业互助班"}】\n入班口令：${classroom.inviteCode}\n活动页：${inviteLink}`
  copyText(text, "邀请文案已复制")
}

async function submitShare() {
  if (isGuest.value) return goLogin()
  if (submittingShare.value) return
  if (!currentPlatformCanSubmit.value) return setFeedback(currentPlatformSubmitTip.value || "当前平台暂不可提交", "info")
  if (!shareForm.link.trim()) return setFeedback("请先填写分享链接", "error")
  if (!isValidHttpUrl(shareForm.link)) return setFeedback("请填写可访问的链接，必须以 http:// 或 https:// 开头", "error")
  if (!shareForm.nickname.trim()) return setFeedback("请先填写平台昵称", "error")
  if (!shareForm.account.trim()) return setFeedback("请先填写领取奖励的支付宝号", "error")
  if (!shareForm.realName.trim()) return setFeedback("请先填写支付宝认证姓名", "error")
  if (shareForm.account.trim().length < 3) return setFeedback("支付宝账号格式不正确", "error")
  if (shareForm.realName.trim().length < 2) return setFeedback("支付宝实名格式不正确", "error")
  try {
    submittingShare.value = true
    await userHttp.post("/users/me/promo-center/shares", {
      platform: activePlatform.value,
      tier_key: shareForm.tier,
      share_link: shareForm.link,
      account_name: shareForm.account,
      real_name: shareForm.realName,
      note: buildShareSubmitNote(),
    })
    shareForm.link = ""
    shareForm.nickname = ""
    shareForm.account = ""
    shareForm.realName = ""
    shareForm.note = ""
    await loadPromoCenter(false)
    setFeedback("分享任务已提交，等待后台人工审核与打款", "ok")
  } catch (error) {
    setFeedback(String(error?.message || "提交审核失败"), "error")
  } finally {
    submittingShare.value = false
  }
}

function isValidHttpUrl(value) {
  try {
    const parsed = new URL(String(value || "").trim())
    return parsed.protocol === "http:" || parsed.protocol === "https:"
  } catch {
    return false
  }
}

function buildShareSubmitNote() {
  const nickname = shareForm.nickname.trim()
  const note = shareForm.note.trim()
  if (nickname && note) {
    return `平台昵称：${nickname}\n补充说明：${note}`
  }
  if (nickname) {
    return `平台昵称：${nickname}`
  }
  return note
}

function parseShareSubmitNote(value) {
  const text = String(value || "").trim()
  if (!text) {
    return { nickname: "", note: "" }
  }
  const nicknameMatch = text.match(/(?:^|\n)平台昵称[:：]\s*([^\n]+)/)
  const noteMatch = text.match(/(?:^|\n)补充说明[:：]\s*([\s\S]+)/)
  const nickname = String(nicknameMatch?.[1] || "").trim()
  const note = String(noteMatch?.[1] || "").trim()
  return {
    nickname,
    note: note || (nickname ? "" : text),
  }
}

function hydrateShareFormFromCurrentPlatform() {
  const record = currentPlatformRecord.value
  if (!record) {
    return
  }
  const parsed = parseShareSubmitNote(record.submitNote)
  if (!shareForm.link.trim() && record.share_link) {
    shareForm.link = record.share_link
  }
  if (!shareForm.account.trim() && record.payout_account) {
    shareForm.account = record.payout_account
  }
  if (!shareForm.realName.trim() && record.payout_name) {
    shareForm.realName = record.payout_name
  }
  if (!shareForm.nickname.trim() && parsed.nickname) {
    shareForm.nickname = parsed.nickname
  }
  if (!shareForm.note.trim() && parsed.note) {
    shareForm.note = parsed.note
  }
  const tierKey = String(record.tier_key || "").trim().toLowerCase()
  if (tierKey && shareTiers.value.some((item) => item.key === tierKey)) {
    shareForm.tier = tierKey
  }
}
</script>

<style scoped>
.promo-page{display:grid;padding:8px 0;background:#fff}
.activity-wrap{display:block;background:#fff;border-radius:20px;overflow:hidden;border:1px solid #e5e7eb;box-shadow:none;backdrop-filter:none}
.activity-wrap--center{width:100%;max-width:1680px;margin:0 auto}
.activity-content{padding:16px 18px;background:#fff}
.activity-layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:22px;align-items:start}
.activity-sidebar{position:sticky;top:16px;align-self:start;padding:6px;border-radius:18px;border:1px solid #e5e7eb;background:linear-gradient(180deg,#fff 0%,#f8fbff 100%)}
.activity-main{display:grid;gap:12px;min-width:0}
.activity-topbar__nav{list-style:none;display:grid;grid-template-columns:1fr;gap:8px}
.activity-topbar__nav li{min-width:0}
.activity-topbar__nav button{width:100%;display:flex;align-items:center;justify-content:flex-start;min-height:46px;padding:12px 15px;border-radius:14px;font-size:14px;font-weight:600;letter-spacing:.02em;color:#52627d;text-decoration:none;transition:all .18s ease;cursor:pointer;border:1px solid transparent;background:transparent;text-align:left}
.activity-topbar__nav button:hover{background:#f8fafc;color:#10294b;border-color:#e2e8f0}
.activity-topbar__nav button.is-active{background:#fff;color:#1d4ed8;font-weight:700;box-shadow:none;border-color:#dbeafe}
.activity-feedback{width:min(100%,1320px);margin:0 auto 10px;padding:11px 15px;border-radius:14px;border:1px solid #dbeafe;background:#fff;color:#1d4ed8;font-size:14px;box-shadow:none}
.activity-feedback.is-error{color:#1d4ed8;border-color:#dbeafe;background:#fff}
.activity-feedback.is-ok{color:#1d4ed8;border-color:#dbeafe;background:#fff}
.activity-page{display:grid;gap:14px;max-width:1380px;width:100%;min-height:860px;aspect-ratio:auto;margin:0 auto;padding:22px 26px;border-radius:20px;border:1px solid #e5e7eb;background:#fff;box-sizing:border-box;box-shadow:none}
.page-title-bar{display:flex;align-items:center;justify-content:space-between;margin-bottom:2px}
.page-title-bar--center{justify-content:center;text-align:center}
.page-title-bar h2{font-size:28px;font-weight:800;color:#10294b;letter-spacing:-.02em}
.page-title-bar .subtitle{font-size:15px;color:#5d7393;margin-top:5px;line-height:1.6}
.activity-page--share{gap:12px;padding:20px 22px}
.activity-page--share .page-title-bar h2{font-size:26px}
.activity-page--share .page-title-bar .subtitle{font-size:14px;margin-top:2px;line-height:1.5}
.activity-page--fission{gap:12px}
.fission-metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
.fission-metric{border:1px solid #dbeafe;border-radius:14px;background:#f8fbff;padding:12px 14px;display:grid;gap:4px}
.fission-metric span{font-size:13px;color:#5d7393}
.fission-metric strong{font-size:26px;line-height:1;color:#1d4ed8;font-weight:800}
.fission-metric small{font-size:12px;color:#64748b;line-height:1.5}
.fission-progress{border:1px solid #e5e7eb;border-radius:16px;padding:12px 14px;background:#fff;display:grid;gap:10px}
.fission-progress__head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.fission-progress__head span{font-size:13px;color:#64748b}
.fission-progress__head strong{font-size:13px;color:#1e3a8a}
.fission-progress__track{height:8px;border-radius:999px;background:#e6edf6;overflow:hidden}
.fission-progress__bar{height:100%;border-radius:999px;background:linear-gradient(90deg,#1d4ed8,#60a5fa);transition:width .3s ease}
.fission-stage-list{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px}
.fission-stage{border:1px solid #e5e7eb;border-radius:12px;padding:10px 11px;display:grid;gap:5px;background:#fff}
.fission-stage.is-done{border-color:#bfdbfe;background:#eff6ff}
.fission-stage__title{display:flex;align-items:center;justify-content:space-between;gap:6px}
.fission-stage__title strong{font-size:13px;color:#1f2937;line-height:1.4}
.fission-stage__title span{font-size:11px;color:#64748b}
.fission-stage p{margin:0;font-size:12px;color:#52627d;line-height:1.5}
.fission-stage small{font-size:12px;color:#1d4ed8;font-weight:700}
.fission-layout{display:grid;grid-template-columns:minmax(0,1.4fr) minmax(260px,.8fr);gap:10px}
.fission-card{border:1px solid #e5e7eb;border-radius:16px;background:#fff;padding:14px 15px;display:grid;gap:10px}
.fission-card h4{margin:0;font-size:15px;color:#14345f}
.fission-code-grid{display:grid;gap:8px}
.fission-code-grid article{border:1px solid #e5e7eb;border-radius:12px;padding:10px 12px;display:grid;gap:4px;background:#f8fafc}
.fission-code-grid span{font-size:12px;color:#64748b}
.fission-code-grid strong{font-size:15px;color:#111827;line-height:1.5}
.fission-link{font-size:12px !important;color:#1e3a8a !important;word-break:break-all}
.fission-actions{display:flex;gap:8px;flex-wrap:wrap}
.fission-guest-tip{margin:0;font-size:12px;color:#64748b;line-height:1.6}
.fission-card--qrcode{align-content:start}
.fission-qrcode{border:1px dashed #c7d2fe;border-radius:12px;background:#f8fbff;min-height:160px;display:flex;align-items:center;justify-content:center;padding:12px}
.fission-qrcode img{width:160px;height:160px;object-fit:contain}
.fission-qrcode span{font-size:13px;color:#64748b}
.fission-reward-list{display:grid;gap:8px}
.fission-reward-item{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;border:1px solid #e5e7eb;border-radius:12px;padding:10px 11px}
.fission-reward-item strong{font-size:13px;color:#111827}
.fission-reward-item p{margin:2px 0 0;font-size:12px;color:#64748b;line-height:1.5}
.fission-reward-item span{font-size:13px;color:#1d4ed8;font-weight:700;white-space:nowrap}
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
.class-show-wrap{display:grid;grid-template-columns:minmax(0,1fr);gap:14px;justify-content:center;align-items:start}
.share-layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:8px;align-items:start;max-width:none;width:100%;margin:0 auto}
.share-layout__left,.share-layout__right{display:grid;gap:12px}
.share-status-card{border:1px solid #dbeafe;border-radius:14px;background:#f8fbff;padding:12px 14px;display:grid;gap:6px}
.share-status-card__head{display:flex;align-items:center;justify-content:space-between;gap:8px}
.share-status-card__head strong{font-size:14px;color:#1e3a8a}
.share-status-card p{margin:0;font-size:13px;color:#52627d;line-height:1.6}
.share-status-card small{font-size:12px;color:#64748b;line-height:1.5}
.share-status-tag{display:inline-flex;align-items:center;justify-content:center;min-height:24px;padding:0 10px;border-radius:999px;font-size:11px;font-weight:700;border:1px solid #dbeafe;color:#1d4ed8;background:#fff}
.share-status-tag.is-ready{border-color:#dbeafe;color:#2563eb;background:#eff6ff}
.share-status-tag.is-submitted{border-color:#fde68a;color:#92400e;background:#fef3c7}
.share-status-tag.is-approved{border-color:#fed7aa;color:#9a3412;background:#ffedd5}
.share-status-tag.is-paid{border-color:#bbf7d0;color:#166534;background:#ecfdf3}
.share-status-tag.is-rejected{border-color:#fecaca;color:#b91c1c;background:#fef2f2}
.share-record-list{display:grid;gap:10px}
.share-record-item{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:11px 12px;border:1px solid #e5e7eb;border-radius:12px;background:#fff}
.share-record-item__main{display:grid;gap:4px;min-width:0}
.share-record-item__main strong{font-size:13px;color:#0f172a;line-height:1.4}
.share-record-item__main p{margin:0;font-size:13px;color:#475569;line-height:1.5}
.share-record-item__main small{font-size:12px;color:#64748b;line-height:1.4}
.share-empty{margin:0;font-size:13px;color:#64748b;line-height:1.6}
.class-hero{background:#fff;border:1px solid #e5e7eb;border-radius:20px;padding:22px 22px;color:#10294b;margin-bottom:12px;box-shadow:none}
.class-hero__eyebrow{display:inline-flex;align-items:center;min-height:26px;padding:0 12px;border-radius:999px;background:#fff;font-size:11px;font-weight:800;letter-spacing:.12em;text-transform:uppercase;border:1px solid #dbeafe;color:#1d4ed8}
.class-hero h1{max-width:520px;font-size:15px;font-weight:500;line-height:1.8;margin:8px 0 4px;color:#355070;white-space:normal}
.class-hero p{font-size:12px;opacity:1;max-width:520px;line-height:1.6;color:#6b7f99}
.class-hero__stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}
.class-hero__stats article{padding:9px 11px;border-radius:16px;background:#fff;border:1px solid #e5e7eb}
.class-hero__stats span{display:block;font-size:11px;opacity:1;margin-bottom:6px;color:#64748b}
.class-hero__stats strong{display:block;font-size:18px;font-weight:800;line-height:1.2;color:#10294b}
.class-progress{margin-top:10px;padding:10px 12px;border-radius:14px;border:1px solid #e5e7eb;background:#fff}
.class-progress__head{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:12px;color:#64748b}
.class-progress__head strong{font-size:12px;color:#1e3a8a}
.class-progress__track{margin-top:8px;height:8px;border-radius:999px;background:#e6edf6;overflow:hidden}
.class-progress__bar{height:100%;border-radius:999px;background:linear-gradient(90deg,#1d4ed8,#60a5fa);transition:width .3s ease}
.class-tiers{display:flex;flex-direction:column;gap:7px}
.class-tier{display:flex;align-items:center;gap:12px;background:#fff;border-radius:16px;padding:12px 15px;border:1px solid #e5e7eb}
.class-tier-icon{width:42px;height:42px;border-radius:14px;display:grid;place-items:center;background:#fff;color:#1d4ed8;font-weight:900;border:1px solid #dbeafe}
.class-tier-title{font-size:15px;font-weight:700;color:#111827;margin-bottom:3px}
.class-tier-cond{font-size:13px;color:#6b7280;line-height:1.6}
.class-tier-reward{margin-top:4px;font-size:12px;line-height:1.6;color:#1e3a8a;background:#eff6ff;border:1px solid #dbeafe;border-radius:10px;padding:6px 8px}
.class-tier-tag{margin-left:auto;font-size:11px;padding:5px 10px;border-radius:999px;font-weight:800;background:#fff;color:#5d7393;border:1px solid #e5e7eb}
.class-tier-tag.is-unlocked{background:#e8f4ef;color:#0f6c53;border-color:#b8e0cf}
.class-form-card{display:grid;gap:8px;margin-top:10px}
.class-form-field{display:grid;gap:6px}
.class-form-field span{font-size:13px;font-weight:600;color:#334155}
.class-form-field input{width:100%;padding:10px 12px;border:1px solid #d7deea;border-radius:10px;font-size:14px;outline:none}
.class-form-field input:focus{border-color:#60a5fa;box-shadow:0 0 0 4px rgba(191,219,254,.5)}
.create-btn-big{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:12px;background:#2563eb;color:#fff;border:none;border-radius:10px;font-size:16px;font-weight:700;cursor:pointer;margin-top:10px;box-shadow:none}
.create-btn-big--secondary{background:#1e40af}
.create-btn-big:disabled{opacity:.65;cursor:not-allowed}
.class-room-box{background:#fff;border:1px solid #e5e7eb;border-radius:18px;padding:13px;margin-top:10px;display:grid;gap:8px}
.class-room-box strong{font-size:14px;color:#1e3a8a}
.class-room-box p{font-size:13px;color:#4b5563;line-height:1.6}
.class-lock-tip{margin:0;color:#64748b;font-size:13px}
.class-room-actions{display:flex;gap:10px}
.lb-card h3,.reward-card h4,.steps-card h4,.submit-card h4{font-size:15px;font-weight:800;margin-bottom:10px;color:#14345f}
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
.task-table__row span{font-size:13px;color:#6b7280}
.task-table__row strong{font-size:13px;color:#374151;line-height:1.5;font-weight:500}
.task-table__reward-list{display:flex;flex-direction:column;gap:2px}
.task-table__row--compact{align-items:center}
.reward-inline-text{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.activity-page--share .task-table__row{grid-template-columns:96px 1fr;gap:10px;padding:5px 0}
.activity-page--share .task-table__row span,
.activity-page--share .task-table__row strong{font-size:12px;line-height:1.4}
.activity-page--share .reward-inline-text{font-size:11px;letter-spacing:-.01em}
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
.form-group span{font-size:13px;font-weight:600;color:#374151}
.form-group input,.form-group select,.form-group textarea{width:100%;padding:9px 12px;border:1px solid #e5e7eb;border-radius:12px;font-size:13px;font-family:inherit;outline:none;background:#fff}
.form-group input:focus,.form-group select:focus,.form-group textarea:focus{border-color:#60a5fa;box-shadow:0 0 0 4px rgba(191,219,254,.5)}
.activity-page--share .submit-grid{gap:6px}
.activity-page--share .form-group{gap:3px;margin-bottom:2px}
.activity-page--share .form-group span{font-size:12px}
.activity-page--share .form-group input,
.activity-page--share .form-group select,
.activity-page--share .form-group textarea{padding:7px 10px;border-radius:10px;font-size:12px}
.activity-page--share .form-group textarea{min-height:38px;resize:none}
.radio-list{display:grid;gap:6px}
.radio-item{display:flex;align-items:center;gap:8px;font-size:11px;color:#4b5563}
.submit-card .btn-primary{display:flex;min-width:148px;margin:4px auto 0}
.risk-tip{font-size:11px;color:#6b7280;display:flex;gap:5px;margin-top:6px;line-height:1.4}
.activity-page--share .submit-card .btn-primary{min-width:132px;margin-top:2px;padding:8px 18px}
.activity-page--share .risk-tip{font-size:10px;margin-top:4px;line-height:1.3}
@media (max-width:1100px){.promo-page{height:auto;min-height:unset;max-height:none}.activity-layout{grid-template-columns:1fr}.activity-sidebar{position:static;top:auto}.activity-topbar__nav{grid-template-columns:repeat(2,minmax(0,1fr))}.activity-page{max-width:1140px;height:auto;min-height:auto;aspect-ratio:auto;padding:16px 18px;overflow:visible}.class-show-wrap,.share-layout,.steps-grid,.submit-grid,.subsidy-simple,.subsidy-guide,.fission-layout{grid-template-columns:1fr}.fission-metrics{grid-template-columns:1fr}.fission-stage-list{grid-template-columns:repeat(2,minmax(0,1fr))}.activity-content{padding:18px;overflow:visible}}
@media (max-width:720px){.jf-header,.page-title-bar,.invite-stats,.class-room-actions,.promo-actions,.subsidy-actions,.fission-actions{flex-direction:column;align-items:stretch}.jf-pipeline,.subsidy-code-row{display:grid;grid-template-columns:1fr}.stage-rail,.detail-table__head,.detail-table__row,.task-table__row,.steps-grid,.submit-grid,.activity-topbar__nav,.fission-stage-list{grid-template-columns:1fr}.share-plat-tabs{display:grid;grid-template-columns:1fr}.plat-tab{min-width:0}.activity-content{padding:16px}.activity-sidebar{padding:5px}.activity-topbar__nav{gap:6px}.activity-topbar__nav button{min-height:38px;padding:9px 11px;font-size:12px}}
</style>
