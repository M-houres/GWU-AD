<template>
  <UserShell
    title="降AIGC率"
    subtitle="上传文档后提交任务，系统将按平台规则自动完成降AIGC率处理并生成记录。"
    :credits="userCredits"
    :hide-topbar="true"
    :hide-header-title="true"
    :disable-notice-dialog="true"
    @buy="showBuy = !showBuy"
  >
    <section class="uploadPage_content uploadPage_content--compact">
      <p v-if="errorText" class="aigc-alert aigc-alert--danger">{{ errorText }}</p>
      <p v-if="successText" class="aigc-alert aigc-alert--success">{{ successText }}</p>

      <section class="aigc-page-head">
        <h2 class="aigc-page-head__title">上传降AIGC率处理文档</h2>
        <p class="aigc-page-head__quota">在尽量保留原文观点与表达逻辑的基础上，重点削弱AIGC痕迹并提升文本自然度。</p>
      </section>
      <div class="aigc-page-head__divider" aria-hidden="true"></div>

      <div class="uploadLiterature_content">
        <div class="uploadLit_content panels-container">
          <div class="uploadLit_content_l">
            <div class="uploadLit_tabCon">
              <div class="uploadFormContent">
                <div class="uploadForm_con">
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
                    <div class="aigc-group__title-row">
                      <h3 class="aigc-group__title"><span class="aigc-required">*</span>上传文件</h3>
                      <button
                        class="aigc-mode-switch"
                        type="button"
                        @click="switchInputMode(inputMode === 'file' ? 'paste' : 'file')"
                      >
                        {{ inputMode === "file" ? "粘贴文本" : "返回上传" }}
                      </button>
                    </div>

                    <template v-if="inputMode === 'file'">
                      <label
                        class="aigc-upload"
                        :class="{ 'is-dragging': dragMain, 'is-error': fieldErrors.paper }"
                        @dragenter.prevent="dragMain = true"
                        @dragover.prevent="dragMain = true"
                        @dragleave.prevent="dragMain = false"
                        @drop.prevent="onMainDrop"
                      >
                        <input class="hidden" type="file" accept=".docx" @change="onPaperInput" />
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
                          <p class="aigc-upload__title">请上传待处理文件，或<span>点击上传</span></p>
                          <p class="aigc-upload__subtitle">仅支持 .docx</p>
                        </div>
                      </label>
                      <p class="aigc-upload__ext">单文件上限 20MB</p>
                      <p v-if="paperFile" class="aigc-upload__file">
                        {{ paperFile.name }}（{{ humanSize(paperFile.size) }}）
                        <button type="button" @click="clearPaper">移除</button>
                      </p>
                      <p v-if="fieldErrors.paper" class="aigc-field-error">{{ fieldErrors.paper }}</p>
                    </template>

                    <template v-else>
                      <div class="aigc-snippet-workspace">
                        <article class="aigc-snippet-pane">
                          <h4>粘贴片段原文</h4>
                          <textarea
                            v-model="snippetInput"
                            class="aigc-input aigc-input--snippet"
                            placeholder="请粘贴需要降AIGC率的文本片段（至少10个字符）"
                          />
                          <p v-if="fieldErrors.snippet" class="aigc-field-error">{{ fieldErrors.snippet }}</p>
                          <div class="aigc-snippet-actions">
                            <button
                              class="aigc-submit-action__button"
                              type="button"
                              :disabled="snippetSubmitting"
                              @click="submitSnippetTask"
                            >
                              {{ snippetSubmitting ? "生成中..." : "一键生成" }}
                            </button>
                          </div>
                        </article>
                        <article class="aigc-snippet-pane">
                          <h4>降后结果</h4>
                          <textarea
                            :value="snippetOutput"
                            class="aigc-input aigc-input--snippet"
                            readonly
                            placeholder="生成完成后会在这里展示结果"
                          />
                        </article>
                      </div>
                    </template>
                  </section>

                  <div v-if="inputMode === 'file'" class="submitBtnCon">
                    <button class="aigc-submit-action__button" type="button" :disabled="submitting" @click="submitTask">
                      {{ submitting ? "提交中..." : "提交降AIGC率" }}
                    </button>
                  </div>
                  <p class="aigc-submit-tip">{{ pricingHint }}</p>
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
                <h3>降AIGC率服务</h3>
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

      <WorkbenchTaskFeed task-type="rewrite" />
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
import { TASK_PLATFORM_OPTIONS } from "../../lib/taskPlatform"
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

const form = reactive({
  platform: "cnki",
})

const platformCards = TASK_PLATFORM_OPTIONS
const pricingHint = ref("任务按字符数直接扣点，默认 1 字符 = 1 点数。提交后可在降AIGC率记录页查看状态、失败原因和结果下载。")

const features = [
  {
    icon: "1",
    title: "语义保持优化",
    desc: "围绕疑似AI特征段落进行结构重写与句式调整，在尽量保持核心观点和学术表达的基础上优化文本表现。",
  },
  {
    icon: "2",
    title: "平台规则适配",
    desc: "按所选平台执行处理策略，同一入口下完成一致化操作，减少重复调整成本。",
  },
  {
    icon: "3",
    title: "重点段落优先优化",
    desc: "围绕高风险表达与可疑段落进行针对性处理，减少重复返工，提升整体验收效率。",
  },
  {
    icon: "4",
    title: "过程可追踪",
    desc: "每次提交均生成任务记录，可持续查看处理进度、回溯结果并下载文档，便于复核与交付。",
  },
]

const fieldErrors = reactive({
  paper: "",
  snippet: "",
})

const dragMain = ref(false)
const paperFile = ref(null)
const inputMode = ref("file")
const snippetInput = ref("")
const snippetOutput = ref("")
const snippetSubmitting = ref(false)
const submitting = ref(false)
const errorText = ref("")
const successText = ref("")
const activeSubmitToken = ref(0)
let activeSubmitController = null
let disposed = false

onMounted(async () => {
  const jobs = []
  if (getUserToken()) jobs.push(refreshUser())
  const platform = String(route.query.platform || "")
  if (platformCards.some((item) => item.value === platform)) {
    form.platform = platform
  }
  await Promise.all(jobs)
})

onUnmounted(() => {
  disposed = true
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

function switchInputMode(mode) {
  inputMode.value = mode === "paste" ? "paste" : "file"
  fieldErrors.paper = ""
  fieldErrors.snippet = ""
  errorText.value = ""
  successText.value = ""
  if (inputMode.value === "paste") {
    clearPaper()
  } else {
    snippetOutput.value = ""
  }
}

function onPaperInput(event) {
  const file = event.target.files?.[0] || null
  setMainFile(file)
  event.target.value = ""
}

function onMainDrop(event) {
  dragMain.value = false
  const file = event.dataTransfer?.files?.[0] || null
  setMainFile(file)
}

function setMainFile(file) {
  fieldErrors.paper = ""
  if (!file) return

  const ext = file.name.includes(".") ? file.name.slice(file.name.lastIndexOf(".")).toLowerCase() : ""
  if (ext !== ".docx") {
    fieldErrors.paper = "上传文件仅支持 .docx"
    return
  }
  if (file.size > 20 * 1024 * 1024) {
    fieldErrors.paper = "文件超过 20MB 限制"
    return
  }
  paperFile.value = file
}

function validateFileForm() {
  fieldErrors.paper = ""
  let valid = true
  if (!paperFile.value) {
    fieldErrors.paper = "请先上传文件"
    valid = false
  }
  return valid
}

function validateSnippetForm() {
  fieldErrors.snippet = ""
  const content = String(snippetInput.value || "").trim()
  if (!content) {
    fieldErrors.snippet = "请先粘贴需要处理的片段文字"
    return false
  }
  if (content.length < 10) {
    fieldErrors.snippet = "文本过短，请至少输入10个字符"
    return false
  }
  return true
}

async function submitTask() {
  if (inputMode.value === "paste") {
    await submitSnippetTask()
    return
  }
  if (!validateFileForm()) {
    errorText.value = "请先完成必填项后再提交"
    return
  }
  await runSubmitTask()
}

async function submitSnippetTask() {
  if (!ensureUserLogin(router, route, "/app/rewrite")) return
  if (snippetSubmitting.value) return
  if (!validateSnippetForm()) {
    errorText.value = "请先完成必填项后再生成"
    return
  }
  const sourceFilename = "pasted_text.txt"
  const submittedAt = Date.now()
  const idempotencyKey = createTaskSubmitIdempotencyKey({
    taskType: "rewrite",
    platform: String(form.platform || "cnki"),
    paperTitle: "",
    authors: "",
    sourceFilename,
    submittedAt,
  })

  snippetSubmitting.value = true
  errorText.value = ""
  successText.value = ""
  snippetOutput.value = "正在处理，请稍候..."

  try {
    const payload = new FormData()
    payload.append("task_type", "rewrite")
    payload.append("platform", String(form.platform || "cnki"))
    payload.append("pasted_text", String(snippetInput.value || "").trim())
    payload.append("source_filename", sourceFilename)
    const submitData = await userHttp.post("/tasks/submit", payload, {
      timeout: 120000,
      headers: { "X-Idempotency-Key": idempotencyKey },
    })
    applyUserBalanceFromSubmit(submitData)
    const output = await waitForTaskOutputText(submitData.id)
    if (disposed) return
    snippetOutput.value = output || "处理完成，但结果为空。"
    successText.value = `片段处理完成，任务 #${submitData.id}`
    await refreshUser()
  } catch (error) {
    if (disposed) return
    snippetOutput.value = ""
    errorText.value = String(error?.message || "片段处理失败，请稍后重试")
  } finally {
    snippetSubmitting.value = false
  }
}

async function waitForTaskOutputText(taskId) {
  const timeoutMs = 180000
  const intervalMs = 1200
  const startedAt = Date.now()
  while (!disposed) {
    const detail = await userHttp.get(`/tasks/${taskId}`)
    const status = String(detail?.status || "").trim().toLowerCase()
    if (status === "completed") {
      try {
        const response = await userHttp.get(`/tasks/${taskId}/download`, { responseType: "blob" })
        const text = await response.data.text()
        return String(text || "").trim()
      } catch {
        return String(detail?.result_json?.output_preview || "").trim()
      }
    }
    if (status === "failed") {
      const reason = String(detail?.error_message || "").trim()
      throw new Error(reason || "任务处理失败")
    }
    if (Date.now() - startedAt > timeoutMs) {
      throw new Error("任务处理超时，请到记录页查看任务状态")
    }
    await sleep(intervalMs)
  }
  return ""
}

function sleep(ms) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

function applyUserBalanceFromSubmit(data) {
  const balance =
    typeof data?.balance_after_fen === "number"
      ? data.balance_after_fen
      : typeof data?.balance_after === "number"
        ? data.balance_after
        : null
  if (typeof balance !== "number") return
  const current = user.value && typeof user.value === "object" ? user.value : {}
  const next = { ...current, credits: balance, balance_fen: balance }
  user.value = next
  setUserInfo(next)
}

const runSubmitTask = createTaskSubmitHandler({
  ensureAuthenticated: () => ensureUserLogin(router, route, "/app/rewrite"),
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
  recordPath: "/app/rewrite/records",
  recordLabel: "润色记录页",
  onInsufficientCredits: () => {
    showBuy.value = true
  },
  buildSnapshot: () => ({
    taskType: "rewrite",
    platform: String(form.platform || "cnki"),
    paper: paperFile.value,
    paperTitle: "",
    authors: "",
    sourceFilename: paperFile.value?.name || "",
    userHttp,
  }),
  buildSubmitOnce: ({ snapshot, submittedAt, signal }) => {
    snapshot.idempotencyKey = createTaskSubmitIdempotencyKey({
      taskType: snapshot.taskType,
      platform: snapshot.platform,
      paperTitle: "",
      authors: "",
      sourceFilename: snapshot.sourceFilename,
      submittedAt,
    })
    return () => {
      const payload = new FormData()
      payload.append("task_type", snapshot.taskType)
      payload.append("platform", snapshot.platform)
      payload.append("paper", snapshot.paper)
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
.service-top-strip {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) repeat(3, minmax(0, 0.7fr));
  gap: 14px;
  margin-bottom: 2px;
}

.service-top-strip__hero,
.service-top-strip__metric,
.service-side-step {
  border: 1px solid rgba(210, 224, 246, 0.96);
  border-radius: 20px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99) 0%, rgba(247, 251, 255, 0.99) 100%);
  box-shadow: 0 14px 28px rgba(30, 91, 223, 0.08);
}

.service-top-strip__hero {
  padding: 18px 20px;
  display: grid;
  gap: 14px;
  background:
    radial-gradient(circle at 100% 0%, rgba(255, 255, 255, 0.18), transparent 24%),
    linear-gradient(135deg, rgba(241, 247, 255, 0.98) 0%, rgba(255, 255, 255, 0.98) 100%);
}

.service-top-strip__hero--rewrite {
  border-color: rgba(103, 151, 245, 0.32);
}

.service-top-strip__eyebrow {
  display: inline-block;
  font-size: 11px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #2f67d7;
  font-weight: 700;
}

.service-top-strip__hero h3 {
  margin: 8px 0 0;
  font-size: 28px;
  line-height: 1.15;
  color: #17385f;
}

.service-top-strip__hero p {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.75;
  color: #627a95;
}

.service-top-strip__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.service-top-strip__chips strong {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid rgba(199, 216, 242, 0.96);
  background: rgba(255, 255, 255, 0.84);
  display: inline-flex;
  align-items: center;
  color: #20456e;
  font-size: 12px;
}

.service-top-strip__metric {
  padding: 16px;
  display: grid;
  align-content: start;
  gap: 6px;
}

.service-top-strip__metric span {
  color: #67809d;
  font-size: 12px;
}

.service-top-strip__metric strong {
  color: #17385f;
  font-size: 24px;
  line-height: 1.08;
}

.service-top-strip__metric em {
  color: #69819d;
  font-size: 12px;
  line-height: 1.65;
  font-style: normal;
}

.service-side-steps {
  display: grid;
  gap: 10px;
}

.service-side-step {
  padding: 14px 15px;
  display: grid;
  gap: 6px;
}

.service-side-step span {
  color: #2f67d7;
  font-size: 11px;
  letter-spacing: 0.12em;
  font-weight: 700;
}

.service-side-step strong {
  color: #17385f;
  font-size: 15px;
}

.service-side-step p {
  margin: 0;
  color: #69819d;
  font-size: 12px;
  line-height: 1.65;
}

@media (max-width: 1200px) {
  .service-top-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .service-top-strip__hero {
    grid-column: 1 / -1;
  }
}

@media (max-width: 768px) {
  .service-top-strip {
    grid-template-columns: 1fr;
  }

  .service-top-strip__hero h3 {
    font-size: 24px;
  }
}
</style>
