<template>
  <div class="app-shell">
    <aside class="sider-wrap">
      <div class="sider-brand">
        <RouterLink to="/app/detect" class="brand-home" aria-label="格物学术首页">
          <span class="brand-mark">GW</span>
          <div class="brand-copy">
            <strong>格物学术</strong>
            <span>Academic Workspace</span>
          </div>
        </RouterLink>
      </div>

      <div class="scrollbar-wrapper">
        <ul class="el-menu">
          <template v-for="(group, groupIndex) in visibleMenuGroups" :key="group.key">
            <li v-for="item in group.items" :key="item.path" class="menu-wrapper">
              <div v-if="item.disabled" class="el-menu-item is-disabled" aria-disabled="true">
                <i class="siderIcon">
                  <component :is="item.icon" :size="16" />
                </i>
                <span class="subMenu_title_box">{{ item.label }}</span>
                <span v-if="item.badge" class="menu-beta-badge">{{ item.badge }}</span>
              </div>
              <RouterLink v-else :to="item.path" class="menu-link">
                <div class="el-menu-item" :class="{ 'is-active': isMenuActive(item.path) }">
                  <i class="siderIcon">
                    <component :is="item.icon" :size="16" />
                  </i>
                  <span class="subMenu_title_box">{{ item.label }}</span>
                  <span v-if="item.badge" class="menu-beta-badge">{{ item.badge }}</span>
                </div>
              </RouterLink>
            </li>
            <li v-if="groupIndex < visibleMenuGroups.length - 1" class="nav-divider" aria-hidden="true"></li>
          </template>
        </ul>
      </div>
    </aside>

    <div class="shell-main">
      <header class="header-wrap">
        <div class="header-title" :class="{ 'header-title--hidden': shouldHideHeaderTitle }">{{ routeTitle }}</div>

        <div class="header-right">
          <button type="button" class="header-notice-btn" @click="isNoticeDialogOpen = true">公告</button>
          <button type="button" class="header-topup" @click="hasUserToken ? goBuy() : goLogin()">充值</button>
          <button type="button" class="header-link" @click="hasUserToken ? goProfile() : goLogin()">
            {{ hasUserToken ? "个人中心" : "登录" }}
          </button>
          <button type="button" class="header-link header-link--muted" @click="hasUserToken ? logout() : goRegister()">
            {{ hasUserToken ? "退出" : "注册" }}
          </button>
        </div>
      </header>

      <main class="main-wrap">
        <div class="main-content">
          <div v-if="!shouldHideTopbar" class="navbarCon">
            <div class="app-breadcrumb">
              <span>{{ breadcrumbTitle }}</span>
              <span class="no-redirect">{{ routeTitle }}</span>
            </div>
            <div class="navbarCon_right">
              <button type="button" @click="router.back()">返回</button>
            </div>
          </div>

          <div class="app-main">
            <div class="app-main-con">
              <slot />
            </div>
          </div>
        </div>
      </main>
    </div>

    <div v-if="isNoticeDialogOpen" class="notice-dialog-mask" @click.self="isNoticeDialogOpen = false">
      <div class="notice-dialog" role="dialog" aria-modal="true" aria-label="公告">
        <div class="notice-dialog__head">
          <h3>{{ noticeTitle }}</h3>
          <button type="button" @click="isNoticeDialogOpen = false">关闭</button>
        </div>
        <p v-if="noticeUpdatedLabel" class="notice-dialog__meta">最近更新：{{ noticeUpdatedLabel }}</p>
        <p class="notice-dialog__body">{{ noticeBodyText }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { Bot, FilePenLine, FileSearch2, Gift, ScanSearch, ShieldCheck } from "lucide-vue-next"
import { computed, onMounted, onUnmounted, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { userHttp } from "../lib/http"
import { clearUserSession, getUserToken } from "../lib/session"
import { normalizeUserNavigationConfig } from "../lib/userNavigation"

const props = defineProps({
  title: {
    type: String,
    default: "",
  },
  subtitle: {
    type: String,
    default: "",
  },
  credits: {
    type: Number,
    default: null,
  },
  hideTopbar: {
    type: Boolean,
    default: false,
  },
  hideHeaderTitle: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(["buy"])

const DEFAULT_HEADER_NOTICE_TEXT = "平台系统持续优化中，任务提交后请在个人中心查看处理进度。"
const GROUP_ORDER = ["core", "lab", "account"]
const MENU_ICON_MAP = {
  rewrite: FilePenLine,
  dedup: FileSearch2,
  detect: ScanSearch,
  review: Bot,
  defense: ShieldCheck,
  referral: Gift,
}

const router = useRouter()
const route = useRoute()
const hasUserToken = ref(false)
const isNoticeDialogOpen = ref(false)
const navigationState = ref(normalizeUserNavigationConfig())
const noticeState = ref({
  enabled: true,
  title: "系统公告",
  content: DEFAULT_HEADER_NOTICE_TEXT,
  header_text: DEFAULT_HEADER_NOTICE_TEXT,
  level: "info",
  version: 1,
  updated_at: "",
})
let noticePollTimer = null

const allMenuItems = computed(() =>
  navigationState.value.items.map((item) => ({
    ...item,
    icon: MENU_ICON_MAP[item.key] || FilePenLine,
  }))
)
const visibleMenuGroups = computed(() =>
  GROUP_ORDER.map((key) => ({
    key,
    items: allMenuItems.value.filter((item) => item.group === key && item.visible),
  })).filter((group) => group.items.length)
)
const visibleMenus = computed(() => visibleMenuGroups.value.flatMap((group) => group.items))
const matchedMenu = computed(() => allMenuItems.value.find((item) => isRouteMatch(route.path, item.path)) || null)
const activeMenu = computed(() => matchedMenu.value || visibleMenus.value[0] || allMenuItems.value[0] || null)
const routeTitle = computed(() => props.title || String(route.meta?.title || "").trim() || activeMenu.value?.label || "工作台")
const breadcrumbTitle = computed(() => matchedMenu.value?.label || routeTitle.value || "工作台")
const shouldHideHeaderTitle = computed(() => {
  if (props.hideHeaderTitle) return true
  return isRouteMatch(route.path, "/app/profile") || isRouteMatch(route.path, "/app/referral")
})
const shouldHideTopbar = computed(() => {
  if (props.hideTopbar) return true
  return isRouteMatch(route.path, "/app/profile") || isRouteMatch(route.path, "/app/referral")
})
const noticeTitle = computed(() => String(noticeState.value.title || "公告"))
const noticeBodyText = computed(() => {
  if (!noticeState.value.enabled) {
    return "当前暂无公告内容。"
  }
  return String(noticeState.value.content || DEFAULT_HEADER_NOTICE_TEXT)
})
const noticeUpdatedLabel = computed(() => formatNoticeTime(noticeState.value.updated_at))

onMounted(() => {
  syncTokenState()
  startNoticeSync()
})

onUnmounted(() => {
  stopNoticeSync()
})

watch(
  () => route.fullPath,
  () => syncTokenState()
)

async function loadShellOptions() {
  try {
    const data = await userHttp.get("/auth/options")
    applyShellOptions(data)
  } catch {
    applyNavigation()
  }
}

async function loadAnnouncement() {
  try {
    const data = await userHttp.get("/auth/announcement")
    applyNotice(data)
  } catch {
    try {
      const data = await userHttp.get("/auth/options")
      applyShellOptions(data)
    } catch {
      applyNotice({})
    }
  }
}

function applyShellOptions(raw) {
  applyNotice(raw?.notice || raw)
  applyNavigation(raw?.user_navigation)
}

function applyNavigation(raw) {
  navigationState.value = normalizeUserNavigationConfig(raw)
}

function applyNotice(raw) {
  const levelRaw = String(raw?.level || "").trim().toLowerCase()
  const level = ["info", "important", "warning", "success"].includes(levelRaw) ? levelRaw : "info"
  const content = String(raw?.content || raw?.header_text || DEFAULT_HEADER_NOTICE_TEXT).trim() || DEFAULT_HEADER_NOTICE_TEXT
  const headerText = String(raw?.header_text || content).trim() || DEFAULT_HEADER_NOTICE_TEXT
  let version = Number(raw?.version || 1)
  if (!Number.isFinite(version) || version < 1) version = 1
  noticeState.value = {
    enabled: raw?.enabled !== false,
    title: String(raw?.title || "系统公告").trim() || "系统公告",
    content,
    header_text: headerText,
    level,
    version: Math.floor(version),
    updated_at: String(raw?.updated_at || "").trim(),
  }
}

function startNoticeSync() {
  stopNoticeSync()
  loadShellOptions()
  loadAnnouncement()
  noticePollTimer = window.setInterval(loadAnnouncement, 45000)
  document.addEventListener("visibilitychange", handleVisibilityChange)
}

function stopNoticeSync() {
  if (noticePollTimer) {
    window.clearInterval(noticePollTimer)
    noticePollTimer = null
  }
  document.removeEventListener("visibilitychange", handleVisibilityChange)
}

function handleVisibilityChange() {
  if (!document.hidden) {
    loadAnnouncement()
  }
}

function formatNoticeTime(value) {
  if (!value) return ""
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return ""
  }
  const pad = (num) => String(num).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function syncTokenState() {
  hasUserToken.value = Boolean(getUserToken())
}

function logout() {
  clearUserSession()
  hasUserToken.value = false
  router.push("/login")
}

function goBuy() {
  emit("buy")
  router.push("/app/buy")
}

function goProfile() {
  router.push("/app/profile")
}

function goLogin() {
  const redirect = encodeURIComponent(route.fullPath || "/app/detect")
  router.push(`/login?redirect=${redirect}`)
}

function goRegister() {
  const redirect = encodeURIComponent(route.fullPath || "/app/detect")
  router.push(`/register?redirect=${redirect}`)
}

function isMenuActive(path) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function isRouteMatch(currentPath, targetPath) {
  return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`)
}
</script>

<style scoped>
.app-shell {
  --sider-width: 236px;
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--sider-width) minmax(0, 1fr);
  background: linear-gradient(180deg, #fafafa 0%, #ffffff 100%);
  color: var(--text-main);
}

.sider-wrap {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e3e3e3;
  background:
    linear-gradient(180deg, #ffffff 0%, #fbfbfb 46%, #f6f6f6 100%);
  box-shadow: 12px 0 28px rgba(0, 0, 0, 0.04);
}

.sider-brand {
  padding: 24px 20px 18px;
  border-bottom: 1px solid #ececec;
}

.brand-home {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  text-decoration: none;
}

.brand-mark {
  width: 40px;
  height: 40px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #111111;
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.brand-copy {
  display: grid;
  gap: 2px;
}

.brand-copy strong {
  font-size: 18px;
  line-height: 1.2;
  font-weight: 700;
  color: #111111;
  letter-spacing: 0.02em;
}

.brand-copy span {
  font-size: 11px;
  line-height: 1.2;
  color: #6c6c6c;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.scrollbar-wrapper {
  flex: 1;
  overflow: auto;
  padding: 18px 0 20px;
}

.el-menu {
  margin: 0;
  padding: 0;
  list-style: none;
}

.menu-wrapper {
  list-style: none;
}

.menu-link {
  display: block;
  text-decoration: none;
}

.nav-divider {
  margin: 10px 20px;
  border-top: 1px solid #e7e7e7;
  list-style: none;
}

.el-menu-item {
  list-style: none;
  display: flex;
  align-items: center;
  gap: 10px;
  width: calc(100% - 28px);
  margin: 0 14px;
  min-height: 46px;
  padding: 12px 16px;
  border-radius: 14px;
  border: 1px solid transparent;
  color: #1a1a1a;
  background: transparent;
  transition:
    background-color 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease,
    box-shadow 0.16s ease;
}

.el-menu-item:hover {
  background: #f3f3f3;
  border-color: #e1e1e1;
  transform: translateY(-1px);
}

.el-menu-item.is-active {
  background: #111111;
  border-color: #111111;
  color: #ffffff;
  box-shadow: 0 12px 20px rgba(0, 0, 0, 0.12);
}

.el-menu-item.is-disabled {
  background: #ffffff;
  border-color: #ededed;
  color: #505050;
  opacity: 0.88;
  cursor: default;
}

.el-menu-item.is-disabled:hover {
  transform: none;
  background: #ffffff;
  border-color: #ededed;
}

.siderIcon {
  display: inline-flex;
  align-items: center;
  color: currentColor;
  flex-shrink: 0;
}

.subMenu_title_box {
  min-width: 0;
  flex: 1;
  color: inherit;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.4;
}

.menu-beta-badge {
  flex-shrink: 0;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.08);
  color: currentColor;
  font-size: 11px;
  line-height: 1;
  padding: 5px 8px;
}

.shell-main {
  min-width: 0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header-wrap {
  position: sticky;
  top: 0;
  z-index: 50;
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.92);
  border-bottom: 1px solid #e7e7e7;
  backdrop-filter: blur(12px);
}

.header-title {
  min-width: 0;
  font-size: 18px;
  font-weight: 700;
  color: #111111;
  letter-spacing: 0.04em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.header-title--hidden {
  visibility: hidden;
}

.header-right {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.header-notice-btn,
.header-topup,
.header-link {
  min-height: 34px;
  padding: 0 13px;
  border-radius: 10px;
  border: 1px solid #111111;
  background: #111111;
  color: #ffffff;
  font-size: 12.5px;
  font-weight: 600;
  line-height: 1;
  cursor: pointer;
  transition:
    background-color 0.16s ease,
    color 0.16s ease,
    border-color 0.16s ease,
    transform 0.16s ease;
}

.header-notice-btn:hover,
.header-topup:hover,
.header-link:hover,
.header-link--muted:hover {
  background: #ffffff;
  color: #111111;
  border-color: #111111;
  transform: translateY(-1px);
}

.header-notice-btn:active,
.header-topup:active,
.header-link:active,
.header-link--muted:active {
  background: #111111;
  color: #ffffff;
  transform: translateY(0);
}

.main-wrap {
  flex: 1;
  min-width: 0;
  padding: 24px;
}

.main-content {
  min-width: 0;
  max-width: 1280px;
  margin: 0 auto;
  display: grid;
  gap: 14px;
}

.navbarCon {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 14px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 247, 247, 0.94)),
    linear-gradient(135deg, rgba(0, 0, 0, 0.03), transparent 46%);
  border: 1px solid rgba(0, 0, 0, 0.12);
  border-radius: var(--radius-card);
  box-shadow: 0 10px 22px rgba(0, 0, 0, 0.06);
}

.app-breadcrumb {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 13px;
  color: #5d5d5d;
}

.app-breadcrumb .no-redirect {
  min-width: 0;
  font-size: 15px;
  color: #111111;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.navbarCon_right button {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #d0d0d0;
  background: #ffffff;
  color: #1f1f1f;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition:
    background-color 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease;
}

.navbarCon_right button:hover {
  background: #f3f3f3;
  border-color: #9e9e9e;
  transform: translateY(-1px);
}

.app-main,
.app-main-con {
  min-width: 0;
}

.header-notice-btn:focus-visible,
.header-topup:focus-visible,
.header-link:focus-visible,
.navbarCon_right button:focus-visible,
.menu-link:focus-visible .el-menu-item {
  outline: 2px solid rgba(0, 0, 0, 0.55);
  outline-offset: 2px;
}

.notice-dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(0, 0, 0, 0.45);
  display: grid;
  place-items: center;
  padding: 16px;
}

.notice-dialog {
  width: min(560px, 100%);
  border-radius: 14px;
  border: 1px solid #d9d9d9;
  background: #ffffff;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.16);
  overflow: hidden;
}

.notice-dialog__head {
  min-height: 54px;
  padding: 0 14px;
  border-bottom: 1px solid #e5e5e5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.notice-dialog__head h3 {
  margin: 0;
  font-size: 18px;
  color: #000000;
}

.notice-dialog__head button {
  min-height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid #000000;
  background: #000000;
  color: #ffffff;
  cursor: pointer;
}

.notice-dialog__meta {
  margin: 0;
  padding: 10px 14px 0;
  font-size: 12px;
  color: #666666;
}

.notice-dialog__body {
  margin: 0;
  padding: 16px 14px 18px;
  color: #111111;
  line-height: 1.8;
  white-space: pre-wrap;
}

@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .header-wrap {
    backdrop-filter: none;
  }
}

@media (max-width: 980px) {
  .app-shell {
    display: block;
  }

  .sider-wrap {
    position: static;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid #e7e7e7;
    box-shadow: none;
  }

  .scrollbar-wrapper {
    overflow-x: auto;
    padding: 10px 0 12px;
  }

  .el-menu {
    display: flex;
    min-width: max-content;
    padding: 0 8px;
  }

  .nav-divider {
    width: 1px;
    margin: 10px 8px;
    border-top: 0;
    border-left: 1px solid #e7e7e7;
  }

  .el-menu-item {
    width: auto;
    min-width: 140px;
    margin: 0 4px;
  }

  .header-wrap {
    min-height: auto;
    padding: 10px 12px;
    flex-direction: column;
    align-items: flex-start;
  }

  .header-right {
    width: 100%;
  }

  .main-wrap {
    padding: 14px 12px;
  }
}

@media (max-width: 768px) {
  .brand-copy span {
    display: none;
  }

  .header-right {
    gap: 6px;
  }

  .header-notice-btn,
  .header-topup,
  .header-link {
    min-height: 32px;
    padding: 0 10px;
    font-size: 12px;
  }

  .navbarCon {
    padding: 8px 10px;
  }
}
</style>
