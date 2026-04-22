<template>
  <UserShell
    title="降重复率"
    subtitle="上传文档后提交任务，系统将按平台规则自动进行降重处理并生成结果记录。"
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
        <h2 class="aigc-page-head__title">上传降重处理文档</h2>
        <p class="aigc-page-head__quota">围绕高重复风险内容进行表达重构与语序优化，兼顾原意保留与查重率控制。</p>
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
                            placeholder="请粘贴需要降重复率的文本片段（至少10个字符）"
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
                      {{ submitting ? "提交中..." : "提交降重" }}
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
                <h3>降重复率服务</h3>
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

      <WorkbenchTaskFeed task-type="dedup" />
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
const pricingHint = ref("任务按字符数直接扣点，默认 1 字符 = 1 点数。提交后可在降重记录页查看状态、失败原因和结果下载。")

const features = [
  {
    icon: "1",
    title: "语义保持降重",
    desc: "围绕高重复段落进行表达重构与句式优化，尽量保持原意与学术语气，降低重复风险占比。",
  },
  {
    icon: "2",
    title: "段落级风险定位",
    desc: "结合平台规则识别重点章节和相似聚集段落，便于有针对性地安排修改优先级与处理顺序。",
  },
  {
    icon: "3",
    title: "命中区域重点处理",
    desc: "结合平台规则优先处理高风险与高重复段落，减少无效改写与重复返工。",
  },
  {
    icon: "4",
    title: "记录可追溯",
    desc: "处理任务自动入库并保存结果链路，可持续查看状态、回溯版本与下载，便于复核与交付留档。",
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
  if (!ensureUserLogin(router, route, "/app/dedup")) return
  if (snippetSubmitting.value) return
  if (!validateSnippetForm()) {
    errorText.value = "请先完成必填项后再生成"
    return
  }
  const sourceFilename = "pasted_text.txt"
  const submittedAt = Date.now()
  const idempotencyKey = createTaskSubmitIdempotencyKey({
    taskType: "dedup",
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
    payload.append("task_type", "dedup")
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
  ensureAuthenticated: () => ensureUserLogin(router, route, "/app/dedup"),
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
  recordPath: "/app/dedup/records",
  recordLabel: "降重记录页",
  onInsufficientCredits: () => {
    showBuy.value = true
  },
  buildSnapshot: () => ({
    taskType: "dedup",
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
