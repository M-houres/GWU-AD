<template>
  <AdminShell title="算法综合配置" subtitle="用一张表统一管理平台、任务、版本和运行方式。">
    <div class="space-y-4">
      <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 class="text-base font-semibold text-[#1f2d3a]">全局运行模式</h3>
            <p class="mt-1 text-sm leading-6 text-[#5b6771]">{{ globalModeHint }}</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button class="rounded-lg bg-[#edf2f6] px-3 py-2 text-sm text-[#344250]" @click="refreshAll">刷新全页</button>
            <button
              v-if="canManageAlgo"
              class="rounded-lg border border-[#cbd5de] bg-white px-3 py-2 text-sm text-[#344250]"
              @click="openUploadDialog()"
            >
              上传算法包
            </button>
            <button
              v-if="canManageAlgo"
              class="rounded-lg border border-[#0f7a5f] bg-[#0f7a5f] px-3 py-2 text-sm text-white"
              @click="openPlatformDialog"
            >
              新增平台
            </button>
          </div>
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
      </section>

      <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 class="text-base font-semibold text-[#1f2d3a]">平台与任务综合表</h3>
            <p class="mt-1 text-xs leading-5 text-[#5f6d79]">每行就是一个“平台 + 任务”，直接改平台状态、任务状态、当前版本、模式和超时。</p>
          </div>
          <div class="text-xs text-[#6b7782]">平台数 {{ platformCount }} · 配置行 {{ tableRows.length }}</div>
        </div>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="border-b border-[#e1e6eb] text-left text-[#5a6671]">
                <th class="px-2 py-2">平台</th>
                <th class="px-2 py-2">任务</th>
                <th class="px-2 py-2">平台状态</th>
                <th class="px-2 py-2">任务状态</th>
                <th class="px-2 py-2">当前版本</th>
                <th class="px-2 py-2">最新版本</th>
                <th class="px-2 py-2">运行模式</th>
                <th class="px-2 py-2">超时</th>
                <th class="px-2 py-2">更新时间</th>
                <th class="px-2 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in tableRows" :key="row.rowKey" class="border-b border-[#eef2f5]">
                <td class="px-2 py-2">
                  <div class="font-medium text-[#1f2d3a]">{{ row.platform_label }}</div>
                  <div class="text-xs text-[#6b7782]">{{ row.platform }}</div>
                </td>
                <td class="px-2 py-2">{{ mapFunctionType(row.task_type) }}</td>
                <td class="px-2 py-2">
                  <label class="inline-flex items-center gap-2 text-xs text-[#4e5d69]">
                    <input v-model="row.platform_enabled" :disabled="!canManageAlgo" type="checkbox" class="h-4 w-4 rounded border-[#c7d0d8]" />
                    {{ row.platform_enabled ? "启用" : "停用" }}
                  </label>
                </td>
                <td class="px-2 py-2">
                  <label class="inline-flex items-center gap-2 text-xs text-[#4e5d69]">
                    <input v-model="row.is_enabled" :disabled="!canManageAlgo || !row.platform_enabled" type="checkbox" class="h-4 w-4 rounded border-[#c7d0d8]" />
                    {{ row.is_enabled ? "开放" : "关闭" }}
                  </label>
                </td>
                <td class="px-2 py-2">
                  <select
                    v-model="row.current_version"
                    :disabled="!canManageAlgo || !row.available_versions.length"
                    class="rounded-md border border-[#cfd8e0] bg-white px-2 py-1 text-xs text-[#3f4d58]"
                  >
                    <option value="">未启用</option>
                    <option v-for="version in row.available_versions" :key="version" :value="version">{{ version }}</option>
                  </select>
                </td>
                <td class="px-2 py-2 text-xs text-[#4f5d69]">{{ row.latest_version || "-" }}</td>
                <td class="px-2 py-2">
                  <select
                    v-model="row.process_mode"
                    :disabled="!canManageAlgo"
                    class="rounded-md border border-[#cfd8e0] bg-white px-2 py-1 text-xs text-[#3f4d58]"
                  >
                    <option value="algo_only">算法包</option>
                    <option value="algo_llm">算法包 + 大模型</option>
                  </select>
                </td>
                <td class="px-2 py-2">
                  <select
                    v-model.number="row.timeout_sec"
                    :disabled="!canManageAlgo"
                    class="rounded-md border border-[#cfd8e0] bg-white px-2 py-1 text-xs text-[#3f4d58]"
                  >
                    <option :value="180">180 秒</option>
                    <option :value="300">300 秒</option>
                    <option :value="600">600 秒</option>
                    <option :value="900">900 秒</option>
                  </select>
                </td>
                <td class="px-2 py-2 text-xs text-[#6b7782]">{{ formatTime(row.updated_at) }}</td>
                <td class="px-2 py-2">
                  <div class="flex flex-wrap gap-2">
                    <button
                      type="button"
                      class="rounded-lg bg-[#0f7a5f] px-3 py-1.5 text-xs text-white disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="savingRowKey === row.rowKey || !canManageAlgo"
                      @click="saveRow(row)"
                    >
                      {{ savingRowKey === row.rowKey ? "保存中..." : "保存" }}
                    </button>
                    <button
                      type="button"
                      class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250] disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="!row.latest_version || row.current_version === row.latest_version"
                      @click="useLatest(row)"
                    >
                      使用最新
                    </button>
                    <button
                      type="button"
                      class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250]"
                      :disabled="!canManageAlgo"
                      @click="openPlatformDialog(row)"
                    >
                      编辑平台
                    </button>
                    <button
                      type="button"
                      class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250]"
                      @click="openHistoryDialog(row)"
                    >
                      历史版本
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="tableRows.length === 0">
                <td colspan="10" class="px-2 py-4 text-center text-[#6b7782]">
                  {{ loadingTable ? "综合表加载中..." : "暂无平台与任务配置数据" }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="mb-3 flex items-center justify-between gap-2">
          <h3 class="text-base font-semibold text-[#1f2d3a]">算法版本库</h3>
          <button class="rounded-lg bg-[#edf2f6] px-3 py-2 text-sm text-[#344250]" @click="loadPackages">刷新版本</button>
        </div>
        <p class="mb-3 text-xs leading-5 text-[#5f6d79]">版本库只看每个平台任务的最新上传版本；正式使用哪个版本，以综合表中的“当前版本”为准。</p>

        <div class="overflow-x-auto">
          <table class="min-w-full text-sm">
            <thead>
              <tr class="border-b border-[#e1e6eb] text-left text-[#5a6671]">
                <th class="px-2 py-2">平台</th>
                <th class="px-2 py-2">任务</th>
                <th class="px-2 py-2">当前生效版本</th>
                <th class="px-2 py-2">最新上传版本</th>
                <th class="px-2 py-2">Smoke</th>
                <th class="px-2 py-2">上传时间</th>
                <th class="px-2 py-2">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in mergedPackageRows" :key="item.key" class="border-b border-[#eef2f5]">
                <td class="px-2 py-2">{{ mapPlatform(item.platform) }}</td>
                <td class="px-2 py-2">{{ mapFunctionType(item.function_type) }}</td>
                <td class="px-2 py-2 text-xs text-[#4f5d69]">{{ item.slot?.active_version || "-" }}</td>
                <td class="px-2 py-2 text-xs text-[#4f5d69]">{{ item.latest?.version || "-" }}</td>
                <td class="px-2 py-2">{{ item.latest?.smoke_status || "-" }}</td>
                <td class="px-2 py-2">{{ formatTime(item.latest?.uploaded_at) }}</td>
                <td class="px-2 py-2">
                  <div class="flex flex-wrap gap-2">
                    <button
                      type="button"
                      class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250] disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="!item.latest || downloadingPackageKey === item.key"
                      @click="downloadLatest(item)"
                    >
                      {{ downloadingPackageKey === item.key ? "下载中..." : "下载最新" }}
                    </button>
                    <button
                      type="button"
                      class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250] disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="!item.slot?.active_version || togglingKey === `${item.key}:deactivate`"
                      @click="deactivateCurrentVersion(item)"
                    >
                      {{ togglingKey === `${item.key}:deactivate` ? "停用中..." : "停用当前版本" }}
                    </button>
                  </div>
                </td>
              </tr>
              <tr v-if="mergedPackageRows.length === 0">
                <td colspan="7" class="px-2 py-4 text-center text-[#6b7782]">
                  {{ loadingPackages ? "算法包加载中..." : "暂无算法包数据" }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div v-if="platformDialogOpen" class="fixed inset-0 z-[90] flex items-center justify-center bg-[rgba(15,23,42,0.36)] px-4">
        <div class="w-full max-w-xl rounded-2xl border border-[#d9dee4] bg-white p-5 shadow-[0_24px_60px_rgba(15,23,42,0.18)]">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-base font-semibold text-[#1f2d3a]">{{ platformDialogMode === "edit" ? "编辑平台" : "新增平台" }}</h3>
              <p class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ platformDialogMode === "edit" ? "修改平台信息后，会影响综合表展示和任务支持范围。" : "新增后会自动为勾选的任务类型生成默认执行配置。" }}</p>
            </div>
            <button type="button" class="rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250]" @click="closePlatformDialog">关闭</button>
          </div>

          <div class="mt-4 grid gap-3 md:grid-cols-2">
            <label class="space-y-1 text-sm">
              <span>平台标识</span>
              <input v-model.trim="platformForm.key" :disabled="platformDialogMode === 'edit'" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2 disabled:bg-[#f3f6f8]" placeholder="如 wanfang" />
            </label>
            <label class="space-y-1 text-sm">
              <span>平台名称</span>
              <input v-model.trim="platformForm.label" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="如 万方" />
            </label>
            <label class="space-y-1 text-sm">
              <span>AIGC 展示名称</span>
              <input v-model.trim="platformForm.aigc_label" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="如 模拟万方" />
            </label>
            <label class="space-y-1 text-sm">
              <span>排序</span>
              <input v-model.number="platformForm.sort_order" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
            </label>
          </div>

          <div class="mt-4">
            <div class="text-sm font-medium text-[#1f2d3a]">支持任务类型</div>
            <div class="mt-2 flex flex-wrap gap-2">
              <label v-for="task in taskTypeOptions" :key="task.value" class="inline-flex items-center gap-2 rounded-full bg-[#eef3f8] px-3 py-2 text-xs text-[#4e5d69]">
                <input v-model="platformForm.task_types" type="checkbox" :value="task.value" class="h-4 w-4 rounded border-[#c7d0d8]" />
                {{ task.label }}
              </label>
            </div>
          </div>

          <div class="mt-4 flex flex-wrap items-center justify-between gap-3">
            <label class="inline-flex items-center gap-2 text-sm text-[#4e5d69]">
              <input v-model="platformForm.enabled" type="checkbox" class="h-4 w-4 rounded border-[#c7d0d8]" />
              平台启用
            </label>
            <button
              type="button"
              class="rounded-lg bg-[#0f7a5f] px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="savingPlatform"
              @click="submitPlatform"
            >
              {{ savingPlatform ? "保存中..." : "保存平台" }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="uploadDialogOpen" class="fixed inset-0 z-[90] flex items-center justify-center bg-[rgba(15,23,42,0.36)] px-4">
        <div class="w-full max-w-xl rounded-2xl border border-[#d9dee4] bg-white p-5 shadow-[0_24px_60px_rgba(15,23,42,0.18)]">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-base font-semibold text-[#1f2d3a]">上传算法包</h3>
              <p class="mt-1 text-xs leading-5 text-[#5f6d79]">上传 zip 算法包后，可在综合表里选择当前版本。</p>
            </div>
            <button type="button" class="rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250]" @click="closeUploadDialog">关闭</button>
          </div>

          <div class="mt-4 grid gap-3 md:grid-cols-2">
            <label class="space-y-1 text-sm">
              <span>平台</span>
              <select v-model="uploadForm.platform" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2">
                <option v-for="platform in platformConfigs" :key="platform.key" :value="platform.key">{{ platform.label }} / {{ platform.key }}</option>
              </select>
            </label>
            <label class="space-y-1 text-sm">
              <span>任务类型</span>
              <select v-model="uploadForm.function_type" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2">
                <option v-for="task in taskTypeOptions" :key="task.value" :value="task.value">{{ task.label }}</option>
              </select>
            </label>
            <label class="space-y-1 text-sm md:col-span-2">
              <span>算法包文件</span>
              <input type="file" accept=".zip" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" @change="onUploadFileChange" />
            </label>
            <label class="inline-flex items-center gap-2 text-sm text-[#4e5d69] md:col-span-2">
              <input v-model="uploadForm.activate" type="checkbox" class="h-4 w-4 rounded border-[#c7d0d8]" />
              上传后直接启用
            </label>
          </div>

          <div class="mt-4 flex justify-end">
            <button
              type="button"
              class="rounded-lg bg-[#0f7a5f] px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="uploadingPackage"
              @click="submitUpload"
            >
              {{ uploadingPackage ? "上传中..." : "开始上传" }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="historyDialogOpen" class="fixed inset-0 z-[90] flex items-center justify-center bg-[rgba(15,23,42,0.36)] px-4">
        <div class="w-full max-w-4xl rounded-2xl border border-[#d9dee4] bg-white p-5 shadow-[0_24px_60px_rgba(15,23,42,0.18)]">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h3 class="text-base font-semibold text-[#1f2d3a]">历史版本</h3>
              <p class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ historyTitle }}</p>
            </div>
            <button type="button" class="rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250]" @click="closeHistoryDialog">关闭</button>
          </div>

          <div class="mt-4 overflow-x-auto">
            <table class="min-w-full text-sm">
              <thead>
                <tr class="border-b border-[#e1e6eb] text-left text-[#5a6671]">
                  <th class="px-2 py-2">版本</th>
                  <th class="px-2 py-2">名称</th>
                  <th class="px-2 py-2">Smoke</th>
                  <th class="px-2 py-2">上传时间</th>
                  <th class="px-2 py-2">状态</th>
                  <th class="px-2 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in historyItems" :key="`${item.platform}:${item.function_type}:${item.version}`" class="border-b border-[#eef2f5]">
                  <td class="px-2 py-2">{{ item.version }}</td>
                  <td class="px-2 py-2 text-xs text-[#4f5d69]">{{ item.name || "-" }}</td>
                  <td class="px-2 py-2">{{ item.smoke_status || "-" }}</td>
                  <td class="px-2 py-2">{{ formatTime(item.uploaded_at) }}</td>
                  <td class="px-2 py-2 text-xs text-[#4f5d69]">{{ item.active ? "当前使用" : "历史版本" }}</td>
                  <td class="px-2 py-2">
                    <div class="flex flex-wrap gap-2">
                      <button
                        type="button"
                        class="rounded border border-[#0f7a5f] bg-[#e8f4ef] px-2 py-1 text-xs text-[#0f6c53] disabled:cursor-not-allowed disabled:opacity-60"
                        :disabled="item.active || activatingHistoryVersion === item.version || !canManageAlgo"
                        @click="activateHistoryVersion(item)"
                      >
                        {{ activatingHistoryVersion === item.version ? "切换中..." : item.active ? "当前版本" : "设为当前" }}
                      </button>
                      <button
                        type="button"
                        class="rounded border border-[#cbd5de] bg-white px-2 py-1 text-xs text-[#344250] disabled:cursor-not-allowed disabled:opacity-60"
                        :disabled="downloadingPackageKey === `${item.platform}:${item.function_type}:${item.version}`"
                        @click="downloadHistoryItem(item)"
                      >
                        {{ downloadingPackageKey === `${item.platform}:${item.function_type}:${item.version}` ? "下载中..." : "下载" }}
                      </button>
                    </div>
                  </td>
                </tr>
                <tr v-if="historyItems.length === 0">
                  <td colspan="6" class="px-2 py-4 text-center text-[#6b7782]">{{ historyLoading ? "历史版本加载中..." : "暂无历史版本" }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <p v-if="hintText" class="text-sm text-[#106c4f]">{{ hintText }}</p>
      <p v-if="errorText" class="text-sm text-[#af3f33]">{{ errorText }}</p>
    </div>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"

import AdminShell from "../../components/AdminShell.vue"
import { downloadAxiosBlobResponse } from "../../lib/download"
import { adminHttp } from "../../lib/http"
import { mapTaskPlatform } from "../../lib/taskPlatform"
import { adminHasPermission } from "../../lib/session"

const taskTypeOptions = [
  { value: "aigc_detect", label: "AIGC检测" },
  { value: "dedup", label: "降重复率" },
  { value: "rewrite", label: "降AIGC率" },
]

const rows = ref([])
const slots = ref([])
const executionConfigs = ref([])
const tableRows = ref([])
const platformConfigs = ref([])
const systemSwitch = ref({
  current_mode: "LLM_PLUS_ALGO",
  llm_enabled: false,
  llm_fail_count: 0,
  llm_fail_threshold: 3,
  updated_at: "",
})

const savingRowKey = ref("")
const switchingMode = ref("")
const togglingKey = ref("")
const downloadingPackageKey = ref("")
const hintText = ref("")
const errorText = ref("")
const loadingPackages = ref(false)
const loadingTable = ref(false)
const platformDialogOpen = ref(false)
const savingPlatform = ref(false)
const platformDialogMode = ref("create")
const uploadDialogOpen = ref(false)
const uploadingPackage = ref(false)
const selectedUploadFile = ref(null)
const historyDialogOpen = ref(false)
const historyItems = ref([])
const historyLoading = ref(false)
const historyTarget = ref(null)
const activatingHistoryVersion = ref("")

const platformForm = reactive({
  key: "",
  label: "",
  aigc_label: "",
  sort_order: 10,
  enabled: true,
  task_types: ["aigc_detect", "dedup", "rewrite"],
})

const uploadForm = reactive({
  platform: "",
  function_type: "aigc_detect",
  activate: true,
})

const canManageAlgo = computed(() => adminHasPermission("algo:manage"))
const canManageSystem = computed(() => adminHasPermission("system:manage"))
const platformCount = computed(() => platformConfigs.value.length)
const currentGlobalModeLabel = computed(() => (systemSwitch.value.current_mode === "LLM_PLUS_ALGO" ? "算法包 + 大模型" : "算法包模式"))
const globalModeHint = computed(() => {
  if (systemSwitch.value.current_mode === "LLM_PLUS_ALGO") {
    return "系统允许按任务执行配置进入大模型增强；大模型异常时会自动回落到算法包。"
  }
  return "系统当前统一走算法包，不进入大模型。"
})
const historyTitle = computed(() => {
  const target = historyTarget.value
  if (!target) {
    return ""
  }
  return `${target.platform_label || mapPlatform(target.platform)} / ${mapFunctionType(target.task_type || target.function_type)}`
})

const latestPackageMap = computed(() => {
  const map = new Map()
  for (const row of rows.value) {
    const key = buildRowKey(row.platform, row.function_type)
    const current = map.get(key)
    if (!current || isRowNewer(row, current)) {
      map.set(key, row)
    }
  }
  return map
})

const versionsByKey = computed(() => {
  const map = new Map()
  for (const row of rows.value) {
    const key = buildRowKey(row.platform, row.function_type)
    if (!map.has(key)) {
      map.set(key, [])
    }
    const list = map.get(key)
    if (!list.includes(row.version)) {
      list.push(row.version)
    }
  }
  for (const list of map.values()) {
    list.sort((a, b) => String(b).localeCompare(String(a), "zh-CN", { numeric: true, sensitivity: "base" }))
  }
  return map
})

const mergedPackageRows = computed(() => {
  const merged = new Map()
  for (const slot of slots.value) {
    const key = buildRowKey(slot.platform, slot.function_type)
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
    }
  }
  return Array.from(merged.values()).sort((a, b) => buildRowKey(a.platform, a.function_type).localeCompare(buildRowKey(b.platform, b.function_type), "zh-CN"))
})

onMounted(async () => {
  await refreshAll()
})

async function refreshAll() {
  await Promise.allSettled([loadTable(), loadPackages(), loadSystemContext()])
}

async function loadTable() {
  loadingTable.value = true
  errorText.value = ""
  try {
    const data = await adminHttp.get("/admin/algo-config/table")
    platformConfigs.value = Array.isArray(data.platforms) ? data.platforms : []
    executionConfigs.value = Array.isArray(data.items) ? data.items : []
    rebuildTableRows()
  } catch (error) {
    errorText.value = error.message || "加载综合配置失败"
  } finally {
    loadingTable.value = false
  }
}

async function loadPackages() {
  loadingPackages.value = true
  errorText.value = ""
  try {
    const data = await adminHttp.get("/admin/algo-packages")
    rows.value = data.items || []
    slots.value = data.slots || []
    rebuildTableRows()
  } catch (error) {
    rows.value = []
    slots.value = []
    rebuildTableRows()
    errorText.value = error.message || "加载算法包失败"
  } finally {
    loadingPackages.value = false
  }
}

async function loadSystemContext() {
  try {
    systemSwitch.value = await adminHttp.get("/admin/switch/current")
  } catch (error) {
    errorText.value = error.message || "加载全局模式失败"
  }
}

async function saveRow(row) {
  savingRowKey.value = row.rowKey
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/algo-config/platforms", {
      key: row.platform,
      label: row.platform_label,
      aigc_label: row.task_type === "aigc_detect" ? row.platform_label : `模拟${row.platform_label}`,
      enabled: Boolean(row.platform_enabled),
      sort_order: platformConfigs.value.find((item) => item.key === row.platform)?.sort_order || 100,
      task_types: platformConfigs.value.find((item) => item.key === row.platform)?.task_types || taskTypeOptions.map((item) => item.value),
    })
    const saved = await adminHttp.put(`/admin/execution-configs/${row.task_type}/${row.platform}`, {
      process_mode: row.process_mode,
      is_enabled: Boolean(row.is_enabled),
      timeout_sec: Number(row.timeout_sec) || 300,
      active_version: row.current_version || undefined,
    })
    Object.assign(row, {
      current_version: saved.current_version || "",
      latest_version: row.latest_version,
      updated_at: saved.updated_at,
      updated_by: saved.updated_by,
    })
    hintText.value = `已保存：${row.platform_label} / ${mapFunctionType(row.task_type)}`
    await Promise.all([loadTable(), loadPackages()])
  } catch (error) {
    errorText.value = error.message || "保存综合配置失败"
  } finally {
    savingRowKey.value = ""
  }
}

function useLatest(row) {
  if (!row.latest_version) {
    return
  }
  row.current_version = row.latest_version
}

function openPlatformDialog(row = null) {
  platformDialogOpen.value = true
  if (row) {
    platformDialogMode.value = "edit"
    const current = platformConfigs.value.find((item) => item.key === row.platform) || {}
    platformForm.key = current.key || row.platform
    platformForm.label = current.label || row.platform_label || row.platform
    platformForm.aigc_label = current.aigc_label || `模拟${platformForm.label}`
    platformForm.sort_order = Number(current.sort_order) || 100
    platformForm.enabled = Boolean(current.enabled)
    platformForm.task_types = Array.isArray(current.task_types) && current.task_types.length ? [...current.task_types] : taskTypeOptions.map((item) => item.value)
    return
  }
  platformDialogMode.value = "create"
  platformForm.key = ""
  platformForm.label = ""
  platformForm.aigc_label = ""
  platformForm.sort_order = platformConfigs.value.length + 10
  platformForm.enabled = true
  platformForm.task_types = taskTypeOptions.map((item) => item.value)
}

function closePlatformDialog() {
  platformDialogOpen.value = false
}

async function submitPlatform() {
  savingPlatform.value = true
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/algo-config/platforms", {
      key: platformForm.key,
      label: platformForm.label,
      aigc_label: platformForm.aigc_label || `模拟${platformForm.label}`,
      sort_order: Number(platformForm.sort_order) || 100,
      enabled: Boolean(platformForm.enabled),
      task_types: platformForm.task_types,
    })
    closePlatformDialog()
    hintText.value = `${platformDialogMode.value === "edit" ? "平台已更新" : "平台已新增"}：${platformForm.label || platformForm.key}`
    await loadTable()
  } catch (error) {
    errorText.value = error.message || `${platformDialogMode.value === "edit" ? "更新平台失败" : "新增平台失败"}`
  } finally {
    savingPlatform.value = false
  }
}

function openUploadDialog(row = null) {
  uploadDialogOpen.value = true
  uploadForm.platform = row?.platform || platformConfigs.value[0]?.key || ""
  uploadForm.function_type = row?.task_type || "aigc_detect"
  uploadForm.activate = true
  selectedUploadFile.value = null
}

function closeUploadDialog() {
  uploadDialogOpen.value = false
  selectedUploadFile.value = null
}

function onUploadFileChange(event) {
  const file = event?.target?.files?.[0] || null
  selectedUploadFile.value = file
}

async function submitUpload() {
  if (!selectedUploadFile.value) {
    errorText.value = "请先选择 zip 算法包文件"
    return
  }
  uploadingPackage.value = true
  hintText.value = ""
  errorText.value = ""
  try {
    const formData = new FormData()
    formData.append("platform", uploadForm.platform)
    formData.append("function_type", uploadForm.function_type)
    formData.append("activate", String(Boolean(uploadForm.activate)))
    formData.append("file", selectedUploadFile.value)
    await adminHttp.post("/admin/algo-packages/upload", formData)
    closeUploadDialog()
    hintText.value = `算法包已上传：${mapPlatform(uploadForm.platform)} / ${mapFunctionType(uploadForm.function_type)}`
    await Promise.all([loadPackages(), loadTable()])
  } catch (error) {
    errorText.value = error.message || "上传算法包失败"
  } finally {
    uploadingPackage.value = false
  }
}

async function openHistoryDialog(row) {
  historyDialogOpen.value = true
  historyTarget.value = row
  historyLoading.value = true
  historyItems.value = []
  try {
    const data = await adminHttp.get("/admin/algo-packages/history", {
      params: {
        platform: row.platform,
        function_type: row.task_type || row.function_type,
      },
    })
    historyItems.value = Array.isArray(data.items) ? data.items : []
  } catch (error) {
    historyItems.value = []
    errorText.value = error.message || "加载历史版本失败"
  } finally {
    historyLoading.value = false
  }
}

function closeHistoryDialog() {
  historyDialogOpen.value = false
  historyItems.value = []
  historyTarget.value = null
  activatingHistoryVersion.value = ""
}

async function activateHistoryVersion(item) {
  activatingHistoryVersion.value = item.version
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/algo-packages/activate", {
      platform: item.platform,
      function_type: item.function_type,
      version: item.version,
    })
    hintText.value = `已切换当前版本：${mapPlatform(item.platform)} / ${mapFunctionType(item.function_type)} @ ${item.version}`
    await Promise.all([loadPackages(), loadTable()])
    if (historyTarget.value) {
      await openHistoryDialog(historyTarget.value)
    }
  } catch (error) {
    errorText.value = error.message || "切换历史版本失败"
  } finally {
    activatingHistoryVersion.value = ""
  }
}

async function downloadHistoryItem(item) {
  downloadingPackageKey.value = `${item.platform}:${item.function_type}:${item.version}`
  hintText.value = ""
  errorText.value = ""
  try {
    const response = await adminHttp.get("/admin/algo-packages/download", {
      params: {
        platform: item.platform,
        function_type: item.function_type,
        version: item.version,
      },
      responseType: "blob",
    })
    downloadAxiosBlobResponse(response, `algo_package_${item.platform}_${item.function_type}_${item.version}.zip`)
  } catch (error) {
    errorText.value = error.message || "下载历史版本失败"
  } finally {
    downloadingPackageKey.value = ""
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

async function deactivateCurrentVersion(item) {
  if (!item.slot?.active_version) {
    return
  }
  if (!window.confirm(`确认停用当前版本 ${mapPlatform(item.platform)} / ${mapFunctionType(item.function_type)} 吗？`)) {
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
    hintText.value = `已停用当前版本：${mapPlatform(item.platform)} / ${mapFunctionType(item.function_type)}`
    await Promise.all([loadPackages(), loadTable()])
  } catch (error) {
    errorText.value = error.message || "停用当前版本失败"
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
  return {
    aigc_detect: "AIGC检测",
    dedup: "降重复率",
    rewrite: "降AIGC率",
  }[type] || type
}

function buildRowKey(platform, taskType) {
  return `${platform}:${taskType}`
}

function splitRowKey(rowKey) {
  const [platform = "", taskType = ""] = String(rowKey || "").split(":")
  return { platform, taskType }
}

function getTaskTypeOrder(taskType) {
  const index = taskTypeOptions.findIndex((item) => item.value === taskType)
  return index >= 0 ? index : 999
}

function compareTableRows(left, right) {
  const leftPlatform = platformConfigs.value.find((item) => item.key === left.platform)
  const rightPlatform = platformConfigs.value.find((item) => item.key === right.platform)
  const leftSort = Number(leftPlatform?.sort_order || 999)
  const rightSort = Number(rightPlatform?.sort_order || 999)
  if (leftSort !== rightSort) {
    return leftSort - rightSort
  }
  const platformCompare = String(left.platform || "").localeCompare(String(right.platform || ""), "zh-CN")
  if (platformCompare !== 0) {
    return platformCompare
  }
  return getTaskTypeOrder(left.task_type) - getTaskTypeOrder(right.task_type)
}

function buildFallbackRow(platform, taskType) {
  const rowKey = buildRowKey(platform, taskType)
  const platformConfig = platformConfigs.value.find((item) => item.key === platform) || {}
  const latestPackage = latestPackageMap.value.get(rowKey) || null
  return {
    rowKey,
    platform,
    task_type: taskType,
    platform_enabled: Boolean(platformConfig.enabled),
    platform_label: platformConfig.label || mapPlatform(platform),
    available_versions: versionsByKey.value.get(rowKey) || [],
    current_version: "",
    latest_version: latestPackage?.version || "",
    process_mode: "algo_only",
    timeout_sec: 300,
    is_enabled: Boolean(platformConfig.enabled),
    updated_at: null,
    updated_by: null,
    active_package: null,
    latest_package: latestPackage,
  }
}

function rebuildTableRows() {
  const rowMap = new Map()
  const defaultTaskTypes = taskTypeOptions.map((item) => item.value)

  for (const platform of platformConfigs.value) {
    const taskTypes = Array.isArray(platform.task_types) && platform.task_types.length ? platform.task_types : defaultTaskTypes
    for (const taskType of taskTypes) {
      const key = buildRowKey(platform.key, taskType)
      rowMap.set(key, buildFallbackRow(platform.key, taskType))
    }
  }

  for (const item of executionConfigs.value) {
    const key = buildRowKey(item.platform, item.task_type)
    const baseRow = rowMap.get(key) || buildFallbackRow(item.platform, item.task_type)
    const platformConfig = platformConfigs.value.find((row) => row.key === item.platform) || {}
    rowMap.set(key, {
      ...baseRow,
      ...item,
      rowKey: key,
      platform_enabled: typeof platformConfig.enabled === "boolean" ? Boolean(platformConfig.enabled) : baseRow.platform_enabled,
      platform_label: platformConfig.label || baseRow.platform_label,
      available_versions: versionsByKey.value.get(key) || [],
      current_version: item.current_version || baseRow.current_version || "",
      latest_version: item.latest_version || latestPackageMap.value.get(key)?.version || baseRow.latest_version || "",
      process_mode: item.process_mode === "algo_llm" ? "algo_llm" : "algo_only",
      timeout_sec: Number(item.timeout_sec) > 0 ? Number(item.timeout_sec) : 300,
      is_enabled: typeof item.is_enabled === "boolean" ? item.is_enabled : baseRow.is_enabled,
    })
  }

  for (const slot of slots.value) {
    const key = buildRowKey(slot.platform, slot.function_type)
    if (rowMap.has(key)) {
      continue
    }
    rowMap.set(key, {
      ...buildFallbackRow(slot.platform, slot.function_type),
      current_version: slot.active_version || "",
    })
  }

  for (const key of latestPackageMap.value.keys()) {
    if (rowMap.has(key)) {
      continue
    }
    const { platform, taskType } = splitRowKey(key)
    rowMap.set(key, buildFallbackRow(platform, taskType))
  }

  tableRows.value = Array.from(rowMap.values()).sort(compareTableRows)
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
