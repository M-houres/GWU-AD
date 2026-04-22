<template>
  <UserShell
    title="AIGC检测"
    subtitle="上传文档后提交检测，系统将按模拟知网、模拟维普规则生成一份全文报告。"
    :credits="userCredits"
    :hide-topbar="true"
    :hide-header-title="true"
    :disable-notice-dialog="true"
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
                        <div class="aigc-platform-row">
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
                          <div class="aigc-official-links">
                            <a
                              v-for="entry in officialAigcLinks"
                              :key="entry.label"
                              :href="entry.url"
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              {{ entry.label }}
                            </a>
                          </div>
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

      <WorkbenchTaskFeed task-type="aigc_detect" />
    </section>

    <BuyCreditsPanel v-if="showBuy" @paid="afterPaid" />
  </UserShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import WorkbenchTaskFeed from "../../components/WorkbenchTaskFeed.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { createTaskSubmitHandler } from "../../lib/taskSubmitFlow"
import { userHttp } from "../../lib/http"
import { createTaskSubmitIdempotencyKey } from "../../lib/taskSubmitRecovery"
import { derivePaperTitleFromFilename, shouldAutoFillPaperTitle } from "../../lib/paperTitle"
import { AIGC_PLATFORM_OPTIONS } from "../../lib/taskPlatform"
import { ensureUserLogin } from "../../lib/requireLogin"
import { getUserToken, setUserInfo } from "../../lib/session"

const router = useRouter()
const route = useRoute()
const showBuy = ref(false)
const { user, refreshUser } = useUserProfile()
const userCredits = computed(() => {
  const value = user.value && (user.value.balance_fen ?? user.value.credits)
  return typeof value === "number" ? value : null
})
const pageHeadQuotaText = "多平台仿真检测，提交后自动生成全文报告并可在记录页持续查看进度。"
const submitQuotaHint = "AIGC 检测每天前 6 篇可按免费额度抵扣；超出后按字符数直接扣点，当前默认 1 字符 = 1 点数。提交后可在检测记录页查看进度、回看结果并下载报告。"

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
const officialAigcLinks = [
  { label: "知网官方查AIGC率", url: "https://cx.cnki.net/" },
  { label: "维普官方查AIGC率", url: "https://aigc.cqvip.com/" },
]

const features = [
  {
    icon: "1",
    title: "多平台仿真检测",
    desc: "按模拟知网、模拟维普两套口径输出结果，重点覆盖常见学术论文与课程作业场景。",
  },
  {
    icon: "2",
    title: "全文报告输出",
    desc: "每次任务输出一份完整全文报告，便于统一归档和后续人工复核。",
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
const autoFilledTitle = ref("")
const errorText = ref("")
const successText = ref("")
const activeSubmitToken = ref(0)
let activeSubmitController = null

onMounted(async () => {
  if (getUserToken()) {
    await refreshUser()
  }
  const platform = String(route.query.platform || "")
  if (platformCards.some((item) => item.value === platform)) {
    form.platform = platform
  }
})

onUnmounted(() => {
  activeSubmitToken.value += 1
  activeSubmitController?.abort()
  activeSubmitController = null
})

function beginSubmitGuard() {
  activeSubmitToken.value += 1
  activeSubmitController?.abort()
  activeSubmitController = new AbortController()
  return {
    token: activeSubmitToken.value,
    signal: activeSubmitController.signal,
  }
}

function isActiveSubmit(token) {
  return activeSubmitToken.value === token
}

function finishSubmitGuard(token) {
  if (isActiveSubmit(token)) {
    activeSubmitController = null
  }
}

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
  const detectedTitle = derivePaperTitleFromFilename(file.name)
  if (detectedTitle && shouldAutoFillPaperTitle(form.title, autoFilledTitle.value)) {
    form.title = detectedTitle
    autoFilledTitle.value = detectedTitle
    fieldErrors.title = ""
  }
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
  if (!validateForm()) {
    errorText.value = "请先完成必填项后再提交"
    return
  }
  await runSubmitTask()
}

const runSubmitTask = createTaskSubmitHandler({
  ensureAuthenticated: () => ensureUserLogin(router, route, "/app/detect"),
  submittingRef: submitting,
  errorTextRef: errorText,
  successTextRef: successText,
  beginSubmitGuard,
  isActiveSubmit,
  finishSubmitGuard,
  refreshUser,
  applyUserBalance: (balanceAfter) => {
    const current = user.value && typeof user.value === "object" ? user.value : {}
    const next = { ...current, credits: balanceAfter, balance_fen: balanceAfter }
    user.value = next
    setUserInfo(next)
  },
  router,
  recordPath: "/app/detect/records",
  recordLabel: "检测记录页",
  onInsufficientCredits: () => {
    showBuy.value = true
  },
  buildSnapshot: () => ({
    taskType: "aigc_detect",
    platform: String(form.platform || "cnki"),
    paper: paperFile.value,
    paperTitle: form.title.trim(),
    authors: form.authors.trim(),
    sourceFilename: paperFile.value?.name || "",
    userHttp,
  }),
  buildSubmitOnce: ({ snapshot, submittedAt, signal }) => {
    snapshot.idempotencyKey = createTaskSubmitIdempotencyKey({
      taskType: snapshot.taskType,
      platform: snapshot.platform,
      paperTitle: snapshot.paperTitle,
      authors: snapshot.authors,
      sourceFilename: snapshot.sourceFilename,
      submittedAt,
    })
    return () => {
      const payload = new FormData()
      payload.append("task_type", snapshot.taskType)
      payload.append("platform", snapshot.platform)
      payload.append("paper", snapshot.paper)
      payload.append("paper_title", snapshot.paperTitle)
      payload.append("authors", snapshot.authors)
      return userHttp.post("/tasks/submit", payload, {
        timeout: 120000,
        signal,
        headers: {
          "X-Idempotency-Key": snapshot.idempotencyKey,
        },
      })
    }
  },
})

async function afterPaid() {
  await refreshUser()
}
</script>

<style scoped>
</style>


