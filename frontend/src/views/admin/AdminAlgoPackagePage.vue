<template>
  <AdminShell title="算法包与策略" subtitle="保留必要开关与配置，按槽位查看最新算法包。">
    <div class="space-y-4">
      <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 class="text-base font-semibold text-[#1f2d3a]">全局运行模式</h3>
            <p class="mt-1 text-sm leading-6 text-[#5b6771]">{{ globalModeHint }}</p>
          </div>
          <button class="rounded-lg bg-[#edf2f6] px-3 py-2 text-sm text-[#344250]" @click="loadSystemContext">刷新状态</button>
        </div>

        <div class="mt-3 flex flex-wrap items-center gap-2">
          <span
            class="rounded-full px-3 py-1 text-sm font-semibold"
            :class="systemSwitch.current_mode === 'LLM_PLUS_ALGO' ? 'bg-[#e8f4ef] text-[#0f6c53]' : 'bg-[#fff4ef] text-[#b24b35]'"
          >
            {{ currentGlobalModeLabel }}
          </span>
          <span class="rounded-full bg-[#eef3f8] px-3 py-1 text-xs text-[#556470]">
            LLM {{ systemSwitch.llm_enabled ? "已启用" : "未启用" }}
          </span>
          <span class="rounded-full bg-[#eef3f8] px-3 py-1 text-xs text-[#556470]">
            失败计数 {{ systemSwitch.llm_fail_count }}/{{ systemSwitch.llm_fail_threshold }}
          </span>
        </div>

        <div v-if="canManageSystem" class="mt-3 flex flex-wrap gap-2">
          <button
            class="rounded-lg border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
            :class="systemSwitch.current_mode === 'LLM_PLUS_ALGO' ? 'border-[#0f7a5f] bg-[#0f7a5f] text-white' : 'border-[#cfd8e0] bg-white text-[#344250]'"
            :disabled="switchingMode === 'LLM_PLUS_ALGO'"
            @click="switchSystemMode('LLM_PLUS_ALGO')"
          >
            {{ switchingMode === 'LLM_PLUS_ALGO' ? "切换中..." : "切到算法包 + 大模型" }}
          </button>
          <button
            class="rounded-lg border px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60"
            :class="systemSwitch.current_mode === 'ALGO_ONLY' ? 'border-[#111111] bg-[#111111] text-white' : 'border-[#cfd8e0] bg-white text-[#344250]'"
            :disabled="switchingMode === 'ALGO_ONLY'"
            @click="switchSystemMode('ALGO_ONLY')"
          >
            {{ switchingMode === 'ALGO_ONLY' ? "切换中..." : "切到算法包模式" }}
          </button>
        </div>
        <p v-else class="mt-3 text-xs leading-5 text-[#6b7782]">当前账号没有系统模式切换权限，仅可查看状态。</p>
      </section>

      <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h3 class="text-base font-semibold text-[#1f2d3a]">处理策略配置</h3>
          <button class="rounded-lg bg-[#edf2f6] px-3 py-2 text-sm text-[#344250]" @click="loadStrategies">刷新</button>
        </div>
        <p class="mb-3 text-xs leading-5 text-[#5f6d79]">每行对应一个槽位，直接设置目标模式、开放状态和超时，点保存即可生效。</p>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="border-b border-[#e1e6eb] text-left text-[#5a6671]">
                <th class="px-2 py-2">平台</th>
                <th class="px-2 py-2">功能类型</th>
                <th class="px-2 py-2">目标模式</th>
                <th class="px-2 py-2">对用户开放</th>
                <th class="px-2 py-2">超时</th>
                <th class="px-2 py-2">当前激活算法包</th>
                <th class="px-2 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="cell in strategyCards" :key="buildStrategyKey(cell)" class="border-b border-[#eef2f5]">
                <td class="px-2 py-2">{{ mapPlatform(cell.platform) }}</td>
                <td class="px-2 py-2">{{ mapFunctionType(cell.task_type) }}</td>
                <td class="px-2 py-2">
                  <select
                    v-model="cell.process_mode"
                    :disabled="!canManageAlgo"
                    class="rounded-md border border-[#cfd8e0] bg-white px-2 py-1 text-xs text-[#3f4d58]"
                  >
                    <option value="algo_only">算法包</option>
                    <option value="algo_llm">算法包 + 大模型</option>
                  </select>
                </td>
                <td class="px-2 py-2">
                  <label class="inline-flex items-center gap-2 text-xs text-[#4e5d69]">
                    <input v-model="cell.is_enabled" :disabled="!canManageAlgo" type="checkbox" class="h-4 w-4 rounded border-[#c7d0d8]" />
                    {{ cell.is_enabled ? "已开放" : "已关闭" }}
                  </label>
                </td>
                <td class="px-2 py-2">
                  <select
                    v-model.number="cell.timeout_sec"
                    :disabled="!canManageAlgo"
                    class="rounded-md border border-[#cfd8e0] bg-white px-2 py-1 text-xs text-[#3f4d58]"
                  >
                    <option :value="180">180 秒</option>
                    <option :value="300">300 秒</option>
                    <option :value="600">600 秒</option>
                    <option :value="900">900 秒</option>
                  </select>
                </td>
                <td class="px-2 py-2 text-xs text-[#4f5d69]">
                  {{ cell.active_package?.name || "-" }} {{ cell.active_package?.version || "" }}
                </td>
                <td class="px-2 py-2">
                  <button
                    type="button"
                    class="rounded-lg bg-[#0f7a5f] px-3 py-1.5 text-xs text-white disabled:cursor-not-allowed disabled:opacity-60"
                    :disabled="savingStrategyKey === buildStrategyKey(cell) || !canManageAlgo"
                    @click="saveStrategy(cell)"
                  >
                    {{ savingStrategyKey === buildStrategyKey(cell) ? "保存中..." : "保存" }}
                  </button>
                </td>
              </tr>
              <tr v-if="strategyCards.length === 0">
                <td colspan="7" class="px-2 py-4 text-center text-[#6b7782]">
                  {{ loadingStrategies ? "策略加载中..." : "暂无策略数据" }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h3 class="text-base font-semibold text-[#1f2d3a]">槽位与最新算法包</h3>
          <button class="rounded-lg bg-[#edf2f6] px-3 py-2 text-sm text-[#344250]" @click="loadPackages">刷新</button>
        </div>
        <p class="mb-3 text-xs leading-5 text-[#5f6d79]">每个槽位只展示最新上传版本，避免在历史版本中反复筛选。</p>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="border-b border-[#e1e6eb] text-left text-[#5a6671]">
                <th class="px-2 py-2">平台</th>
                <th class="px-2 py-2">功能类型</th>
                <th class="px-2 py-2">当前生效版本</th>
                <th class="px-2 py-2">最新上传版本</th>
                <th class="px-2 py-2">Smoke</th>
                <th class="px-2 py-2">上传时间</th>
                <th class="px-2 py-2">状态</th>
                <th class="px-2 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in mergedPackageRows" :key="item.key" class="border-b border-[#eef2f5]">
                <td class="px-2 py-2">{{ mapPlatform(item.platform) }}</td>
                <td class="px-2 py-2">{{ mapFunctionType(item.function_type) }}</td>
                <td class="px-2 py-2 text-xs text-[#4f5d69]">
                  {{ item.slot?.active_name || "-" }} {{ item.slot?.active_version || "" }}
                </td>
                <td class="px-2 py-2 text-xs text-[#4f5d69]">
                  {{ item.latest?.name || "-" }} {{ item.latest?.version || "" }}
                </td>
                <td class="px-2 py-2">{{ item.latest?.smoke_status || "-" }}</td>
                <td class="px-2 py-2">{{ formatTime(item.latest?.uploaded_at) }}</td>
                <td class="px-2 py-2 text-xs" :class="latestStatusClass(item)">
                  {{ latestStatusText(item) }}
                </td>
                <td class="px-2 py-2">
                  <div v-if="canManageAlgo" class="flex flex-wrap gap-2">
                    <button
                      type="button"
                      class="rounded border border-[#0f7a5f] bg-[#e8f4ef] px-2 py-1 text-xs text-[#0f6c53] disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="!item.latest || isLatestActive(item) || togglingKey === `${item.key}:activate`"
                      @click="activateLatest(item)"
                    >
                      {{ togglingKey === `${item.key}:activate` ? "启用中..." : isLatestActive(item) ? "已是最新" : "启用最新" }}
                    </button>
                    <button
                      type="button"
                      class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250] disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="!item.slot?.active_version || togglingKey === `${item.key}:deactivate`"
                      @click="deactivateSlot(item)"
                    >
                      {{ togglingKey === `${item.key}:deactivate` ? "停用中..." : "停用槽位" }}
                    </button>
                    <button
                      type="button"
                      class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250] disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="!item.latest || downloadingPackageKey === item.key"
                      @click="downloadLatest(item)"
                    >
                      {{ downloadingPackageKey === item.key ? "下载中..." : "下载最新" }}
                    </button>
                  </div>
                  <span v-else class="text-xs text-[#53626d]">只读</span>
                </td>
              </tr>
              <tr v-if="mergedPackageRows.length === 0">
                <td colspan="8" class="px-2 py-4 text-center text-[#6b7782]">
                  {{ loadingPackages ? "算法包加载中..." : "暂无算法包数据" }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <p v-if="hintText" class="text-sm text-[#106c4f]">{{ hintText }}</p>
      <p v-if="errorText" class="text-sm text-[#af3f33]">{{ errorText }}</p>
    </div>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { downloadAxiosBlobResponse } from "../../lib/download"
import { adminHttp } from "../../lib/http"
import { mapTaskPlatform } from "../../lib/taskPlatform"
import { adminHasPermission } from "../../lib/session"

const rows = ref([])
const slots = ref([])
const strategyCards = ref([])
const systemSwitch = ref({
  current_mode: "LLM_PLUS_ALGO",
  llm_enabled: false,
  llm_fail_count: 0,
  llm_fail_threshold: 3,
  updated_at: "",
})
const savingStrategyKey = ref("")
const switchingMode = ref("")
const togglingKey = ref("")
const downloadingPackageKey = ref("")
const hintText = ref("")
const errorText = ref("")
const loadingPackages = ref(false)
const loadingStrategies = ref(false)

const canManageAlgo = computed(() => adminHasPermission("algo:manage"))
const canManageSystem = computed(() => adminHasPermission("system:manage"))
const currentGlobalModeLabel = computed(() => (systemSwitch.value.current_mode === "LLM_PLUS_ALGO" ? "算法包 + 大模型" : "算法包模式"))
const globalModeHint = computed(() => {
  if (systemSwitch.value.current_mode === "LLM_PLUS_ALGO") {
    return "系统允许按策略进入大模型增强；大模型异常时会自动回落到算法包。"
  }
  return "系统当前统一走算法包，不进入大模型。"
})

const platformOrder = {
  cnki: 1,
  vip: 2,
  paperpass: 3,
}

const taskTypeOrder = {
  aigc_detect: 1,
  rewrite: 2,
  dedup: 3,
}

const latestPackageMap = computed(() => {
  const map = new Map()
  for (const row of rows.value) {
    const key = buildSlotKey(row.platform, row.function_type)
    const current = map.get(key)
    if (!current || isRowNewer(row, current)) {
      map.set(key, row)
    }
  }
  return map
})

const mergedPackageRows = computed(() => {
  const merged = new Map()
  for (const slot of slots.value) {
    const key = buildSlotKey(slot.platform, slot.function_type)
    merged.set(key, {
      key,
      platform: slot.platform,
      function_type: slot.function_type,
      slot,
      latest: latestPackageMap.value.get(key) || null,
    })
  }

  for (const [key, latest] of latestPackageMap.value.entries()) {
    if (!merged.has(key)) {
      merged.set(key, {
        key,
        platform: latest.platform,
        function_type: latest.function_type,
        slot: null,
        latest,
      })
      continue
    }
    merged.get(key).latest = latest
  }

  return Array.from(merged.values()).sort((a, b) => {
    const taskDiff = (taskTypeOrder[a.function_type] || 99) - (taskTypeOrder[b.function_type] || 99)
    if (taskDiff !== 0) {
      return taskDiff
    }
    return (platformOrder[a.platform] || 99) - (platformOrder[b.platform] || 99)
  })
})

onMounted(async () => {
  await Promise.allSettled([loadPackages(), loadStrategies(), loadSystemContext()])
})

async function loadPackages() {
  loadingPackages.value = true
  errorText.value = ""
  try {
    const data = await adminHttp.get("/admin/algo-packages")
    rows.value = data.items || []
    slots.value = data.slots || []
  } catch (error) {
    rows.value = []
    slots.value = []
    errorText.value = error.message || "加载算法包失败"
  } finally {
    loadingPackages.value = false
  }
}

async function loadStrategies() {
  loadingStrategies.value = true
  errorText.value = ""
  try {
    const data = await adminHttp.get("/admin/strategies")
    const items = Array.isArray(data.items) ? data.items : []
    strategyCards.value = items
      .map((item) => ({
        ...item,
        process_mode: item.process_mode === "algo_llm" ? "algo_llm" : "algo_only",
        is_enabled: Boolean(item.is_enabled),
        timeout_sec: Number(item.timeout_sec) > 0 ? Number(item.timeout_sec) : 300,
      }))
      .sort((a, b) => {
        const taskDiff = (taskTypeOrder[a.task_type] || 99) - (taskTypeOrder[b.task_type] || 99)
        if (taskDiff !== 0) {
          return taskDiff
        }
        return (platformOrder[a.platform] || 99) - (platformOrder[b.platform] || 99)
      })
  } catch (error) {
    strategyCards.value = []
    errorText.value = error.message || "加载策略失败"
  } finally {
    loadingStrategies.value = false
  }
}

async function loadSystemContext() {
  try {
    systemSwitch.value = await adminHttp.get("/admin/switch/current")
  } catch (error) {
    errorText.value = error.message || "加载全局模式失败"
  }
}

async function saveStrategy(cell) {
  const key = buildStrategyKey(cell)
  savingStrategyKey.value = key
  hintText.value = ""
  errorText.value = ""
  try {
    const payload = {
      process_mode: cell.process_mode,
      is_enabled: Boolean(cell.is_enabled),
      timeout_sec: Number(cell.timeout_sec) || 300,
    }
    const saved = await adminHttp.put(`/admin/strategies/${cell.task_type}/${cell.platform}`, payload)
    Object.assign(cell, {
      process_mode: saved.process_mode,
      is_enabled: Boolean(saved.is_enabled),
      timeout_sec: Number(saved.timeout_sec) || 300,
      active_package: saved.active_package || cell.active_package || null,
      updated_at: saved.updated_at,
      updated_by: saved.updated_by,
    })
    hintText.value = `策略已保存：${mapPlatform(cell.platform)} / ${mapFunctionType(cell.task_type)}`
  } catch (error) {
    errorText.value = error.message || "保存策略失败"
  } finally {
    savingStrategyKey.value = ""
  }
}

async function switchSystemMode(mode) {
  if (!canManageSystem.value || switchingMode.value) {
    return
  }
  const label = mode === "LLM_PLUS_ALGO" ? "算法包 + 大模型" : "算法包模式"
  if (!window.confirm(`确认把系统全局模式切换为“${label}”吗？`)) {
    return
  }
  switchingMode.value = mode
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/switch/mode", { mode })
    await loadSystemContext()
    hintText.value = `全局模式已切换为：${label}`
  } catch (error) {
    errorText.value = error.message || "切换全局模式失败"
  } finally {
    switchingMode.value = ""
  }
}

async function activateLatest(item) {
  if (!canManageAlgo.value || !item.latest || isLatestActive(item)) {
    return
  }
  if (!window.confirm(`确认启用最新版本 ${item.latest.version}（${mapPlatform(item.platform)} / ${mapFunctionType(item.function_type)}）吗？`)) {
    return
  }
  togglingKey.value = `${item.key}:activate`
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/algo-packages/activate", {
      platform: item.platform,
      function_type: item.function_type,
      version: item.latest.version,
    })
    hintText.value = `已启用最新版本：${mapPlatform(item.platform)} / ${mapFunctionType(item.function_type)} @ ${item.latest.version}`
    await Promise.all([loadPackages(), loadStrategies()])
  } catch (error) {
    errorText.value = error.message || "启用最新算法包失败"
  } finally {
    togglingKey.value = ""
  }
}

async function deactivateSlot(item) {
  if (!canManageAlgo.value || !item.slot?.active_version) {
    return
  }
  if (!window.confirm(`确认停用槽位 ${mapPlatform(item.platform)} / ${mapFunctionType(item.function_type)} 当前版本吗？`)) {
    return
  }
  togglingKey.value = `${item.key}:deactivate`
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/algo-packages/deactivate", {
      platform: item.platform,
      function_type: item.function_type,
    })
    hintText.value = `已停用槽位：${mapPlatform(item.platform)} / ${mapFunctionType(item.function_type)}`
    await Promise.all([loadPackages(), loadStrategies()])
  } catch (error) {
    errorText.value = error.message || "停用算法包失败"
  } finally {
    togglingKey.value = ""
  }
}

async function downloadLatest(item) {
  if (!item.latest) {
    return
  }
  downloadingPackageKey.value = item.key
  hintText.value = ""
  errorText.value = ""
  try {
    const response = await adminHttp.get("/admin/algo-packages/download", {
      params: {
        platform: item.latest.platform,
        function_type: item.latest.function_type,
        version: item.latest.version,
      },
      responseType: "blob",
    })
    downloadAxiosBlobResponse(response, `algo_package_${item.latest.platform}_${item.latest.function_type}_${item.latest.version}.zip`)
    hintText.value = `算法包已开始下载：${mapPlatform(item.latest.platform)} / ${mapFunctionType(item.latest.function_type)} @ ${item.latest.version}`
  } catch (error) {
    errorText.value = error.message || "下载算法包失败"
  } finally {
    downloadingPackageKey.value = ""
  }
}

function mapPlatform(platform) {
  return mapTaskPlatform(platform)
}

function mapFunctionType(type) {
  const mapping = {
    aigc_detect: "AIGC检测",
    dedup: "降重复率",
    rewrite: "降AIGC率",
  }
  return mapping[type] || type
}

function buildSlotKey(platform, functionType) {
  return `${platform}:${functionType}`
}

function buildStrategyKey(cell) {
  return `${cell.task_type}:${cell.platform}`
}

function latestStatusText(item) {
  if (!item.latest) {
    return "暂无算法包"
  }
  if (!item.slot?.active_version) {
    return "可启用"
  }
  if (item.slot.active_version === item.latest.version) {
    return "已使用最新"
  }
  return `可升级（当前 ${item.slot.active_version}）`
}

function latestStatusClass(item) {
  if (!item.latest) {
    return "text-[#6b7782]"
  }
  if (isLatestActive(item)) {
    return "text-[#106c4f]"
  }
  return "text-[#9a5a00]"
}

function isLatestActive(item) {
  return Boolean(item.latest && item.slot?.active_version && item.latest.version === item.slot.active_version)
}

function isRowNewer(nextRow, currentRow) {
  const nextTs = parseTime(nextRow.uploaded_at)
  const currentTs = parseTime(currentRow.uploaded_at)
  if (nextTs !== currentTs) {
    return nextTs > currentTs
  }
  const versionCompare = String(nextRow.version || "").localeCompare(String(currentRow.version || ""), "zh-CN", { numeric: true, sensitivity: "base" })
  return versionCompare > 0
}

function parseTime(value) {
  const time = Date.parse(String(value || ""))
  return Number.isFinite(time) ? time : 0
}

function formatTime(value) {
  return value ? String(value).slice(0, 19).replace("T", " ") : "-"
}
</script>
