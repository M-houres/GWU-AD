<template>
  <UserShell
    title="AIGC检测"
    subtitle="上传文档后提交检测，系统将按模拟知网、模拟维普、模拟PaperPass规则生成简洁报告与全文报告。"
    :credits="userCredits"
    :hide-topbar="true"
    :hide-header-title="true"
    @buy="showBuy = !showBuy"
  >
    <section class="uploadPage_content">
      <p v-if="errorText" class="aigc-alert aigc-alert--danger">{{ errorText }}</p>
      <p v-if="successText" class="aigc-alert aigc-alert--success">{{ successText }}</p>

      <section class="aigc-page-head">
        <h2 class="aigc-page-head__title">上传 AIGC 待检测文档</h2>
        <p class="aigc-page-head__quota">{{ pageHeadQuotaText }}</p>
      </section>
      <div class="aigc-page-head__divider" aria-hidden="true"></div>
      <section class="aigc-free-banner">
        <div class="aigc-free-banner__badge">AIGC 检测权益</div>
        <div class="aigc-free-banner__body">
          <h3>每日前 {{ quotaLimit }} 篇免费检测</h3>
          <p>{{ quotaBannerText }}</p>
        </div>
        <div class="aigc-free-banner__side">
          <strong>{{ quotaBannerValue }}</strong>
          <span>{{ quotaBannerLabel }}</span>
        </div>
      </section>

      <div class="uploadLiterature_content">
        <div class="uploadLit_content panels-container">
          <div class="uploadLit_content_l">
            <div class="uploadLit_tabCon">
              <div class="uploadFormContent">
                <div class="uploadForm_con">
                  <section class="aigc-group">
                    <h3 class="aigc-group__title"><span class="aigc-required">*</span>主文稿</h3>
                    <label
                      class="aigc-upload"
                      :class="{ 'is-dragging': dragActive, 'is-error': fieldErrors.paper }"
                      @dragenter.prevent="dragActive = true"
                      @dragover.prevent="dragActive = true"
                      @dragleave.prevent="dragActive = false"
                      @drop.prevent="onDrop"
                    >
                      <input class="hidden" type="file" accept=".docx,.pdf,.txt" @change="onPaperInput" />
                      <div class="aigc-upload__inner">
                        <div class="aigc-upload__icon" aria-hidden="true">
                          <svg viewBox="0 0 24 24">
                            <path
                              d="M6 2h8l4 4v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Zm7 1.5V7h3.5L13 3.5ZM8.5 12.5h7M8.5 16h7"
                              fill="none"
                              stroke="currentColor"
                              stroke-linecap="round"
                              stroke-linejoin="round"
                              stroke-width="1.6"
                            />
                          </svg>
                        </div>
                        <p class="aigc-upload__title">请将待检测文档拖拽至区域，或<span>点击上传</span></p>
                      </div>
                    </label>
                    <p class="aigc-upload__ext">支持 .docx / .pdf / .txt，单文件上限 20MB</p>
                    <p class="aigc-upload__note">基于大量数据训练，仿版与官方结果相差一般在10%以内</p>
                    <p v-if="paperFile" class="aigc-upload__file">
                      {{ paperFile.name }}（{{ humanSize(paperFile.size) }}）
                      <button type="button" @click="clearPaper">移除</button>
                    </p>
                    <p v-if="fieldErrors.paper" class="aigc-field-error">{{ fieldErrors.paper }}</p>
                  </section>

                  <section class="aigc-group">
                    <div class="aigc-field-row aigc-field-row--platform">
                      <label class="aigc-field-row__label"><span class="aigc-required">*</span>平台选择</label>
                      <div class="aigc-field-row__body">
                        <div class="aigc-platform-grid aigc-platform-grid--inline">
                          <button
                            v-for="item in platformCards"
                            :key="item.value"
                            type="button"
                            class="aigc-platform-card"
                            :class="{ 'is-active': form.platform === item.value }"
                            @click="form.platform = item.value"
                          >
                            <div class="aigc-platform-card__name">{{ item.label }}</div>
                          </button>
                        </div>
                      </div>
                    </div>
                  </section>

                  <section class="aigc-group">
                    <div class="aigc-field-row">
                      <label class="aigc-field-row__label"><span class="aigc-required">*</span>篇名</label>
                      <div class="aigc-field-row__body">
                        <input
                          v-model="form.title"
                          class="aigc-input aigc-input--required"
                          :class="{ 'is-error': fieldErrors.title }"
                          type="text"
                          maxlength="300"
                          placeholder="请输入准确的文章篇名，信息将显示在检测报告单中"
                        />
                        <div class="aigc-counter">{{ form.title.length }}/300</div>
                      </div>
                    </div>
                    <p v-if="fieldErrors.title" class="aigc-field-error">{{ fieldErrors.title }}</p>
                  </section>

                  <section class="aigc-group">
                    <div class="aigc-field-row">
                      <label class="aigc-field-row__label"><span class="aigc-required">*</span>作者</label>
                      <div class="aigc-field-row__body">
                        <input
                          v-model="form.authors"
                          class="aigc-input aigc-input--required"
                          :class="{ 'is-error': fieldErrors.authors }"
                          type="text"
                          maxlength="200"
                          placeholder='请填写作者信息，多位作者用 ";" 分隔'
                        />
                        <div class="aigc-counter">{{ form.authors.length }}/200</div>
                      </div>
                    </div>
                    <p v-if="fieldErrors.authors" class="aigc-field-error">{{ fieldErrors.authors }}</p>
                  </section>

                  <div class="submitBtnCon">
                    <button class="aigc-submit-action__button" type="button" :disabled="submitting" @click="submitTask">
                      {{ submitting ? "提交中..." : "提交检测" }}
                    </button>
                  </div>
                  <p class="aigc-submit-tip">{{ submitQuotaHint }}</p>
                </div>
              </div>
            </div>
          </div>

          <div class="uploadLit_content_r panel-right">
            <div class="uploadLit_content_right">
              <section class="aigc-side__law">
                对于代写、剽窃、伪造等学术不端行为，《中华人民共和国学位法》第三十七条进行了明确规定。
                <a href="https://www.news.cn/legal/20240426/8fc9b903147a477a9dab550518d4ff80/c.html" target="_blank" rel="noopener noreferrer">详情&gt;&gt;</a>
                <a href="https://news.cctv.com/2024/04/26/ARTIxCmi4wUMPigs46qnoMeJ240426.shtml" target="_blank" rel="noopener noreferrer">相关报道&gt;&gt;</a>
              </section>

              <section class="aigc-side__brand">
                <h3>AIGC检测服务</h3>
              </section>

              <section class="aigc-feature-list features-list">
                <article v-for="item in features" :key="item.title" class="aigc-feature-item">
                  <div class="aigc-feature-item__dot">{{ item.icon }}</div>
                  <div>
                    <h4>{{ item.title }}</h4>
                    <p>{{ item.desc }}</p>
                  </div>
                </article>
              </section>
            </div>
          </div>
        </div>
      </div>
    </section>

    <BuyCreditsPanel v-if="showBuy" @paid="afterPaid" />
  </UserShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { userHttp } from "../../lib/http"
import {
  isTaskSubmitNetworkError,
  isTaskSubmitTimeoutError,
  recoverSubmittedTask,
} from "../../lib/taskSubmitRecovery"
import { AIGC_PLATFORM_OPTIONS } from "../../lib/taskPlatform"
import { ensureUserLogin } from "../../lib/requireLogin"
import { getUserToken } from "../../lib/session"

const router = useRouter()
const route = useRoute()
const showBuy = ref(false)
const { user, refreshUser } = useUserProfile()
const DEFAULT_AIGC_DAILY_FREE_LIMIT = 6

const userCredits = computed(() => {
  const value = user.value && user.value.credits
  return typeof value === "number" ? value : null
})

const form = reactive({
  platform: "cnki",
  title: "",
  authors: "",
})

const fieldErrors = reactive({
  paper: "",
  title: "",
  authors: "",
})

const platformCards = AIGC_PLATFORM_OPTIONS

const features = [
  {
    icon: "1",
    title: "多平台仿真检测",
    desc: "按模拟知网、模拟维普、模拟PaperPass三套口径输出结果，重点覆盖常见学术论文与课程作业场景。",
  },
  {
    icon: "2",
    title: "双报告输出",
    desc: "每次任务同时整理简洁报告与全文报告，便于快速判断和继续人工复核。",
  },
  {
    icon: "3",
    title: "结果差异可控",
    desc: "核心指标结合样本报告持续校准，仿版与参考平台的常见浮动一般控制在可接受范围内。",
  },
  {
    icon: "4",
    title: "可靠的安全保障",
    desc: "尊重并保护用户隐私和数据安全，采用加密技术，确保论文在上传和检测过程中不会被泄露。",
  },
]

const submitting = ref(false)
const dragActive = ref(false)
const paperFile = ref(null)
const errorText = ref("")
const successText = ref("")
const quotaInfo = ref(null)

const quotaLimit = computed(() => {
  const raw = Number(quotaInfo.value?.daily_free_limit)
  return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_AIGC_DAILY_FREE_LIMIT
})

const quotaRemaining = computed(() => {
  const raw = Number(quotaInfo.value?.free_remaining_today)
  return Number.isFinite(raw) && raw >= 0 ? raw : null
})

const quotaUsed = computed(() => {
  const raw = Number(quotaInfo.value?.free_used_today)
  return Number.isFinite(raw) && raw >= 0 ? raw : null
})

const pageHeadQuotaText = computed(() => {
  if (quotaRemaining.value == null) {
    return `AIGC 检测每日前 ${quotaLimit.value} 篇免费，登录后可实时查看今日剩余次数。`
  }
  return `今日免费检测剩余 ${quotaRemaining.value} / ${quotaLimit.value} 篇，超出后按字数计费。`
})

const quotaBannerText = computed(() => {
  if (quotaRemaining.value == null || quotaUsed.value == null) {
    return `当前 AIGC 检测每日前 ${quotaLimit.value} 篇可免费提交，超出免费次数后系统会按字数计费。`
  }
  if (quotaRemaining.value <= 0) {
    return `今日 ${quotaLimit.value} 篇免费次数已用完，继续提交仍可检测，但会按字数计费。`
  }
  return `今日已免费使用 ${quotaUsed.value} 篇，当前还可免费检测 ${quotaRemaining.value} 篇，本次提交会优先抵扣免费次数。`
})

const quotaBannerValue = computed(() => {
  if (quotaRemaining.value == null) {
    return `${quotaLimit.value} 篇`
  }
  return `${quotaRemaining.value} / ${quotaLimit.value}`
})

const quotaBannerLabel = computed(() => (quotaRemaining.value == null ? "每日免费额度" : "今日剩余免费次数"))

const submitQuotaHint = computed(() => {
  if (quotaRemaining.value == null) {
    return `提醒：AIGC 检测每日前 ${quotaLimit.value} 篇免费，登录后会自动显示实时剩余次数。`
  }
  if (quotaRemaining.value <= 0) {
    return "提醒：今日免费次数已用完，当前继续提交会按字数计费。"
  }
  return `提醒：当前还可免费检测 ${quotaRemaining.value} 篇，本次提交将优先抵扣今日免费额度。`
})

onMounted(async () => {
  if (getUserToken()) {
    await Promise.all([refreshUser(), loadQuotaInfo()])
  }
  const platform = String(route.query.platform || "")
  if (platformCards.some((item) => item.value === platform)) {
    form.platform = platform
  }
})

function humanSize(size) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function clearPaper() {
  paperFile.value = null
  fieldErrors.paper = ""
}

function onPaperInput(event) {
  const file = event.target.files?.[0] || null
  setPaperFile(file)
  event.target.value = ""
}

function onDrop(event) {
  dragActive.value = false
  const file = event.dataTransfer?.files?.[0] || null
  setPaperFile(file)
}

function setPaperFile(file) {
  fieldErrors.paper = ""
  errorText.value = ""
  if (!file) return

  const ext = file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")).toLowerCase() : ""
  if (![".docx", ".pdf", ".txt"].includes(ext)) {
    fieldErrors.paper = "仅支持 .docx / .pdf / .txt 文件"
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    fieldErrors.paper = "文件超过 20MB 限制"
    return
  }
  paperFile.value = file
}

function validateForm() {
  fieldErrors.paper = ""
  fieldErrors.title = ""
  fieldErrors.authors = ""

  let valid = true
  if (!paperFile.value) {
    fieldErrors.paper = "请先上传检测文档"
    valid = false
  }
  if (!form.title.trim()) {
    fieldErrors.title = "请填写篇名"
    valid = false
  }
  if (!form.authors.trim()) {
    fieldErrors.authors = "请填写作者"
    valid = false
  }
  return valid
}

async function submitTask() {
  if (!ensureUserLogin(router, route, "/app/detect")) return

  if (!validateForm()) {
    errorText.value = "请先完成必填项后再提交"
    return
  }

  submitting.value = true
  errorText.value = ""
  successText.value = ""
  const submittedAt = Date.now()

  try {
    const payload = new FormData()
    payload.append("task_type", "aigc_detect")
    payload.append("platform", form.platform)
    payload.append("paper", paperFile.value)
    payload.append("paper_title", form.title.trim())
    payload.append("authors", form.authors.trim())

    const data = await userHttp.post("/tasks/submit", payload, {
      timeout: 120000,
    })
    quotaInfo.value = data?.billing?.quota || quotaInfo.value

    successText.value = `提交成功，任务 #${data.id} 已创建`
    try {
      await refreshUser()
    } catch (refreshError) {
      console.warn("task_submit_refresh_user_failed", refreshError)
    }
    router.push({ path: "/app/detect/records", query: { focus: String(data.id) } })
  } catch (error) {
    if (isTaskSubmitTimeoutError(error) || isTaskSubmitNetworkError(error)) {
      const recoveredTask = await recoverSubmittedTask({
        taskType: "aigc_detect",
        paperTitle: form.title.trim(),
        authors: form.authors.trim(),
        sourceFilename: paperFile.value?.name,
        submittedAt,
      })
      if (recoveredTask?.id) {
        successText.value = `提交响应中断，但任务 #${recoveredTask.id} 已创建，正在跳转记录页`
        try {
          await refreshUser()
        } catch (refreshError) {
          console.warn("task_submit_refresh_user_failed", refreshError)
        }
        router.push({ path: "/app/detect/records", query: { focus: String(recoveredTask.id) } })
        return
      }
    }
    const message = String(error?.message || "").trim()
    if (isTaskSubmitTimeoutError(error)) {
      errorText.value = "提交耗时较长，请稍后到检测记录页确认任务是否已创建"
      return
    }
    if (isTaskSubmitNetworkError(error)) {
      errorText.value = "提交未收到有效响应，请检查后端服务；也可到检测记录页查看任务是否已创建"
      return
    }
    errorText.value = message || "提交失败，请稍后重试"
  } finally {
    submitting.value = false
  }
}

async function afterPaid() {
  await refreshUser()
}

async function loadQuotaInfo() {
  if (!getUserToken()) {
    quotaInfo.value = null
    return
  }
  try {
    const data = await userHttp.get("/users/me/summary")
    quotaInfo.value = data?.aigc_quota || null
  } catch {
    quotaInfo.value = null
  }
}
</script>

<style scoped>
.aigc-free-banner {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  gap: 16px;
  align-items: center;
  margin: 0 0 22px;
  padding: 18px 22px;
  border: 1px solid rgba(180, 117, 33, 0.18);
  border-radius: 20px;
  background: linear-gradient(135deg, rgba(255, 248, 234, 0.96), rgba(255, 255, 255, 0.98));
  box-shadow: 0 16px 38px rgba(168, 118, 40, 0.08);
}

.aigc-free-banner__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: #a86722;
  color: #fffdf8;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.aigc-free-banner__body h3 {
  margin: 0;
  color: #2d210f;
  font-size: 22px;
  font-weight: 700;
}

.aigc-free-banner__body p {
  margin: 6px 0 0;
  color: rgba(45, 33, 15, 0.78);
  font-size: 14px;
  line-height: 1.7;
}

.aigc-free-banner__side {
  display: grid;
  gap: 4px;
  justify-items: end;
  min-width: 120px;
  text-align: right;
}

.aigc-free-banner__side strong {
  color: #8a5417;
  font-size: 28px;
  line-height: 1;
}

.aigc-free-banner__side span {
  color: rgba(45, 33, 15, 0.62);
  font-size: 12px;
}

.aigc-submit-tip {
  margin: 12px 0 0;
  color: rgba(45, 33, 15, 0.74);
  font-size: 13px;
  line-height: 1.7;
}

@media (max-width: 960px) {
  .aigc-free-banner {
    grid-template-columns: 1fr;
  }

  .aigc-free-banner__side {
    justify-items: start;
    min-width: 0;
    text-align: left;
  }
}
</style>

