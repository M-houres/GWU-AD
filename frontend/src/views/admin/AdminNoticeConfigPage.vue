<template>
  <AdminShell title="公告配置" subtitle="公告内容独立维护，保存后前端自动更新。">
    <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
      <div class="mb-4 border-b border-[#e6ebef] pb-4">
        <div class="text-[11px] uppercase tracking-[0.16em] text-[#73808b]">Notice Settings</div>
        <h3 class="mt-2 text-xl font-semibold text-[#1b2730]">站内公告配置</h3>
        <p class="mt-2 text-sm leading-6 text-[#5b6771]">该配置将同步到前端公告按钮与顶部摘要，不再和登录配置混在一起。</p>
      </div>

      <p v-if="!canManage" class="rounded-xl border border-[#e7d4b1] bg-white px-3 py-2 text-sm text-[#7a5a2c]">
        当前账号仅有查看权限，无法保存公告配置。
      </p>

      <fieldset class="space-y-4" :disabled="saving || !canManage">
        <label class="inline-flex items-center gap-2 text-sm">
          <input v-model="form.enabled" type="checkbox" />
          启用公告
        </label>

        <div class="grid gap-3 md:grid-cols-2">
          <label class="space-y-1 text-sm">
            <span>公告标题（32字内）</span>
            <input v-model.trim="form.title" maxlength="32" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
          </label>
          <label class="space-y-1 text-sm">
            <span>公告级别</span>
            <select v-model="form.level" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2">
              <option value="info">普通</option>
              <option value="important">重要</option>
              <option value="warning">警示</option>
              <option value="success">提示</option>
            </select>
          </label>
        </div>

        <label class="space-y-1 text-sm">
          <span>公告正文（2000字内）</span>
          <textarea v-model.trim="form.content" rows="6" maxlength="2000" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea>
        </label>
        <div class="text-right text-xs text-[#6a7681]">{{ String(form.content || "").length }}/2000</div>

        <label class="space-y-1 text-sm">
          <span>顶部摘要（140字内）</span>
          <textarea v-model.trim="form.header_text" rows="2" maxlength="140" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea>
        </label>
        <div class="text-right text-xs text-[#6a7681]">{{ String(form.header_text || "").length }}/140</div>

        <div class="rounded-xl border border-[#dde4ea] bg-white px-3 py-2 text-xs text-[#4b5b66]">
          当前版本：v{{ Number(form.version || 1) }} · 最近更新时间：{{ formatTime(form.updated_at) || "未发布" }}
        </div>
      </fieldset>

      <div class="mt-5 flex flex-wrap gap-2 border-t border-[#e6ebef] pt-4">
        <button class="rounded-xl px-4 py-2 text-sm" :disabled="saving || !canManage" @click="save">
          {{ saving ? "保存中..." : "保存公告配置" }}
        </button>
        <button class="rounded-xl px-4 py-2 text-sm" @click="load">重新加载</button>
      </div>

      <p v-if="hintText" class="mt-3 text-sm text-[#0f6f54]">{{ hintText }}</p>
      <p v-if="errorText" class="mt-3 text-sm text-[#b24439]">{{ errorText }}</p>
    </section>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"

const canManage = computed(() => adminHasPermission("configs:manage"))
const saving = ref(false)
const hintText = ref("")
const errorText = ref("")
const form = ref({
  enabled: true,
  title: "系统公告",
  content: "平台系统持续优化中，任务提交后请在个人中心查看处理进度。",
  header_text: "平台系统持续优化中，任务提交后请在个人中心查看处理进度。",
  level: "info",
  version: 1,
  updated_at: "",
})

onMounted(load)

async function load() {
  hintText.value = ""
  errorText.value = ""
  try {
    const data = await adminHttp.get("/admin/configs/notice")
    form.value = {
      enabled: data.value?.enabled !== false,
      title: String(data.value?.title || "系统公告").slice(0, 32),
      content: String(data.value?.content || "").slice(0, 2000),
      header_text: String(data.value?.header_text || data.value?.content || "").slice(0, 140),
      level: ["info", "important", "warning", "success"].includes(String(data.value?.level || "").toLowerCase())
        ? String(data.value.level).toLowerCase()
        : "info",
      version: Number(data.value?.version || 1),
      updated_at: String(data.value?.updated_at || ""),
    }
  } catch (error) {
    errorText.value = error.message || "加载公告配置失败"
  }
}

async function save() {
  if (!canManage.value) {
    errorText.value = "当前账号无配置管理权限"
    return
  }
  if (!String(form.value.title || "").trim()) {
    errorText.value = "公告标题不能为空"
    return
  }
  if (!String(form.value.content || "").trim()) {
    errorText.value = "公告正文不能为空"
    return
  }
  saving.value = true
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/configs/notice", {
      enabled: form.value.enabled !== false,
      title: String(form.value.title || "").trim().slice(0, 32),
      content: String(form.value.content || "").trim().slice(0, 2000),
      header_text: String(form.value.header_text || form.value.content || "").trim().slice(0, 140),
      level: String(form.value.level || "info").trim().toLowerCase(),
      version: Number(form.value.version || 1),
      updated_at: String(form.value.updated_at || ""),
    })
    await load()
    hintText.value = "公告配置已保存并生效。"
  } catch (error) {
    errorText.value = error.message || "保存失败"
  } finally {
    saving.value = false
  }
}

function formatTime(value) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
</script>

