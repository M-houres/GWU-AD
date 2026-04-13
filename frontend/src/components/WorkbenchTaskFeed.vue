<template>
  <section class="workbench-feed">
    <div class="workbench-feed__head">
      <div>
        <h3 class="workbench-feed__title">{{ panelMeta.title }}</h3>
        <p class="workbench-feed__lead">{{ panelMeta.lead }}</p>
      </div>
      <div class="workbench-feed__actions">
        <button class="scholar-button scholar-button--secondary" type="button" @click="loadTasks">刷新</button>
        <button class="scholar-button" type="button" @click="goRecords">查看全部记录</button>
      </div>
    </div>

    <template v-if="hasUserToken">
      <div class="workbench-feed__summary">
        <article v-for="item in summaryCards" :key="item.label" class="workbench-feed__summary-card">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <small>{{ item.hint }}</small>
        </article>
      </div>

      <div v-if="loading" class="scholar-note">正在加载最近任务...</div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { userHttp } from "../lib/http"
import { getUserToken } from "../lib/session"
import { isTaskProcessingStatus } from "../lib/taskStatus"

const props = defineProps({
  taskType: {
    type: String,
    required: true,
  },
})

const router = useRouter()
const route = useRoute()
const loading = ref(false)
const tasks = ref([])
const hasUserToken = computed(() => Boolean(getUserToken()))
let pollTimer = null

const panelMetaMap = {
  aigc_detect: {
    title: "最近 AIGC 检测记录",
    lead: "提交检测后，最新任务会直接出现在这里，方便你快速判断风险和下载报告。",
    recordsPath: "/app/detect/records",
    uploadPath: "/app/detect",
    detailTitle: "AIGC 检测结果",
  },
  rewrite: {
    title: "最近降AIGC率记录",
    lead: "这里展示你最近的降AIGC率任务，方便快速查看改动幅度、完成状态和结果文件。",
    recordsPath: "/app/rewrite/records",
    uploadPath: "/app/rewrite",
    detailTitle: "降AIGC率结果",
  },
  dedup: {
    title: "最近降重复率记录",
    lead: "最近提交的降重任务会按时间倒序展示，方便你快速看结果、下载文件和继续处理。",
    recordsPath: "/app/dedup/records",
    uploadPath: "/app/dedup",
    detailTitle: "降重复率结果",
  },
}

const panelMeta = computed(() => panelMetaMap[props.taskType] || panelMetaMap.aigc_detect)

const summaryCards = computed(() => {
  const all = tasks.value.length
  const processing = tasks.value.filter((item) => isTaskProcessingStatus(item.status)).length
  const completed = tasks.value.filter((item) => item.status === "completed").length
  const failed = tasks.value.filter((item) => item.status === "failed").length
  return [
    { label: "最近任务", value: all, hint: "当前工作台内最近记录" },
    { label: "处理中", value: processing, hint: "自动轮询刷新" },
    { label: "已完成", value: completed, hint: "可直接查看结果" },
    { label: "失败", value: failed, hint: "建议检查失败原因" },
  ]
})

onMounted(() => {
  loadTasks()
  startPolling()
})

onUnmounted(() => stopPolling())

async function loadTasks() {
  if (!hasUserToken.value) {
    tasks.value = []
    return
  }
  loading.value = true
  try {
    const data = await userHttp.get("/tasks/my", {
      params: {
        task_type: props.taskType,
        page: 1,
        page_size: 12,
      },
    })
    const items = Array.isArray(data?.items) ? data.items : []
    tasks.value = [...items].sort((a, b) => String(b.created_at).localeCompare(String(a.created_at)))
  } finally {
    loading.value = false
  }
}

function startPolling() {
  stopPolling()
  if (!hasUserToken.value) return
  pollTimer = window.setInterval(() => {
    if (tasks.value.some((item) => isTaskProcessingStatus(item.status))) {
      loadTasks()
    }
  }, 4000)
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

function goRecords() {
  router.push(panelMeta.value.recordsPath)
}

function goUpload() {
  router.push(panelMeta.value.uploadPath)
}

function goLogin() {
  const redirect = encodeURIComponent(route.fullPath || panelMeta.value.uploadPath)
  router.push(`/login?redirect=${redirect}`)
}
</script>

<style scoped>
.workbench-feed {
  margin-top: 24px;
  border: 1px solid rgba(173, 187, 209, 0.22);
  border-radius: 28px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(245, 249, 255, 0.96)),
    linear-gradient(145deg, rgba(76, 118, 215, 0.06), transparent 28%);
  box-shadow: 0 18px 34px rgba(32, 76, 164, 0.08);
  padding: 22px;
}

.workbench-feed__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.workbench-feed__title {
  font-size: 24px;
  line-height: 1.2;
  color: #193357;
}

.workbench-feed__lead {
  margin: 8px 0 0;
  font-size: 14px;
  line-height: 1.8;
  color: #5b6f90;
  max-width: 760px;
}

.workbench-feed__actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.workbench-feed__summary {
  margin-top: 18px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.workbench-feed__summary-card {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border-radius: 20px;
  border: 1px solid rgba(163, 183, 221, 0.24);
  background: rgba(255, 255, 255, 0.92);
}

.workbench-feed__summary-card span {
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #6a7f9f;
}

.workbench-feed__summary-card strong {
  font-size: 26px;
  line-height: 1;
  color: #14345d;
}

.workbench-feed__summary-card small {
  font-size: 12px;
  line-height: 1.6;
  color: #61789b;
}

@media (max-width: 960px) {
  .workbench-feed {
    padding: 18px;
  }

  .workbench-feed__head {
    flex-direction: column;
  }

  .workbench-feed__actions {
    width: 100%;
    justify-content: flex-start;
  }

  .workbench-feed__summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .workbench-feed {
    margin-top: 18px;
    padding: 16px 14px;
    border-radius: 22px;
  }

  .workbench-feed__title {
    font-size: 21px;
  }

  .workbench-feed__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .workbench-feed__actions > * {
    width: 100%;
  }

  .workbench-feed__summary {
    grid-template-columns: 1fr 1fr;
    gap: 10px;
  }

  .workbench-feed__summary-card {
    padding: 14px;
  }

  .workbench-feed__summary-card strong {
    font-size: 22px;
  }
}
</style>
