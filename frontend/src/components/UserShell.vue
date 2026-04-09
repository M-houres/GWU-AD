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
        <div v-if="!isNavigationReady" class="menu-loading-placeholder" aria-hidden="true"></div>
        <ul v-else class="el-menu">
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
          <button v-if="showNoticeEntry" type="button" class="header-notice-btn" @click="isNoticeDialogOpen = true">公告</button>
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

    <div v-if="showNoticeEntry && isNoticeDialogOpen" class="notice-dialog-mask" @click.self="isNoticeDialogOpen = false">
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
import { clearUserSession, getUserNavigationConfig, getUserToken, setUserNavigationConfig } from "../lib/session"
import { normalizeUserNavigationConfig } from "../lib/userNavigation"

const props = defineProps({
  title: {
    type: String,
    default: "",
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
const cachedNavigation = getUserNavigationConfig()
const navigationState = ref(cachedNavigation ? normalizeUserNavigationConfig(cachedNavigation) : normalizeUserNavigationConfig())
const isNavigationReady = ref(Boolean(cachedNavigation))
const noticeState = ref({
  enabled: true,
  title: "系统公告",
  content: DEFAULT_HEADER_NOTICE_TEXT,
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
const showNoticeEntry = computed(() => noticeState.value.enabled)
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
  const normalized = normalizeUserNavigationConfig(raw)
  navigationState.value = normalized
  setUserNavigationConfig(normalized)
  isNavigationReady.value = true
}

function applyNotice(raw) {
  const content = String(raw?.content || raw?.header_text || DEFAULT_HEADER_NOTICE_TEXT).trim() || DEFAULT_HEADER_NOTICE_TEXT
  noticeState.value = {
    enabled: raw?.enabled !== false,
    title: String(raw?.title || "系统公告").trim() || "系统公告",
    content,
    updated_at: String(raw?.updated_at || "").trim(),
  }
  if (!noticeState.value.enabled) {
    isNoticeDialogOpen.value = false
  }
}

function startNoticeSync() {
  stopNoticeSync()
  loadShellOptions()
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
  --shell-paper: #ffffff;
  --shell-paper-soft: #f6f9ff;
  --shell-paper-deep: #ebf2ff;
  --shell-edge: rgba(172, 198, 244, 0.42);
  --shell-edge-strong: rgba(30, 91, 223, 0.36);
  --shell-ink: #1b3458;
  --shell-ink-soft: #567195;
  --shell-ink-faint: #8096b4;
  --shell-accent: #1e5bdf;
  --shell-accent-strong: #184ec8;
  --shell-accent-deep: #143f9d;
  --shell-shadow: 0 22px 46px rgba(30, 91, 223, 0.18);
  --shell-shadow-soft: 0 14px 28px rgba(30, 91, 223, 0.12);
  --shell-band:
    linear-gradient(
      135deg,
      #3b82f6 0%,
      #397ff5 12%,
      #3478f3 24%,
      #2d6ff0 38%,
      #2563eb 52%,
      #225be4 66%,
      #1d4ed8 82%,
      #2563eb 100%
    );
  --sider-width: 236px;
  min-height: 100vh;
  display: grid;
  grid-template-columns: var(--sider-width) minmax(0, 1fr);
  position: relative;
  background: var(--shell-band);
  color: var(--shell-ink);
}

.sider-wrap {
  position: sticky;
  top: 0;
  height: 100vh;
  display: flex;
  flex-direction: column;
  border-right: 0;
  background: transparent;
  box-shadow: none;
}

.sider-brand {
  padding: 24px 20px 18px;
  border-bottom: 0;
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
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.1em;
  box-shadow:
    0 12px 24px rgba(13, 44, 119, 0.18),
    inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.brand-copy {
  display: grid;
  gap: 2px;
}

.brand-copy strong {
  font-size: 18px;
  line-height: 1.2;
  font-weight: 700;
  color: #ffffff;
  letter-spacing: 0.02em;
}

.brand-copy span {
  font-size: 11px;
  line-height: 1.2;
  color: rgba(239, 245, 255, 0.72);
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
  padding: 0 14px;
  list-style: none;
  display: grid;
  gap: 14px;
}

.menu-loading-placeholder {
  min-height: 248px;
  margin: 0 14px;
  border-radius: 24px;
  border: 0;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0.12)),
    repeating-linear-gradient(
      180deg,
      transparent 0,
      transparent 22px,
      rgba(255, 255, 255, 0.12) 22px,
      rgba(255, 255, 255, 0.12) 34px
    );
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.16);
}

.menu-wrapper {
  list-style: none;
}

.menu-link {
  display: block;
  text-decoration: none;
}

.nav-divider {
  display: none;
}

.el-menu-item {
  list-style: none;
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  margin: 0;
  min-height: 46px;
  padding: 12px 16px;
  border-radius: 14px;
  border: 0;
  color: rgba(245, 249, 255, 0.9);
  background: rgba(255, 255, 255, 0.12);
  transition:
    background-color 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease,
    transform 0.16s ease,
    box-shadow 0.16s ease;
}

.el-menu-item:hover {
  background: rgba(255, 255, 255, 0.22);
  transform: translateY(-1px) scale(1.015);
  box-shadow: 0 16px 28px rgba(12, 42, 112, 0.18);
}

.el-menu-item.is-active {
  background: rgba(255, 255, 255, 0.96);
  color: var(--shell-accent);
  box-shadow: 0 18px 30px rgba(12, 42, 112, 0.22);
}

.el-menu-item.is-disabled {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(233, 241, 255, 0.48);
  opacity: 0.88;
  cursor: default;
}

.el-menu-item.is-disabled:hover {
  transform: none;
  background: rgba(255, 255, 255, 0.08);
  box-shadow: none;
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
  background: rgba(255, 255, 255, 0.16);
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
  background: transparent;
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
  background: transparent;
  border-bottom: 0;
  box-shadow: none;
  backdrop-filter: blur(12px);
}

.header-title {
  min-width: 0;
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
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
  gap: 12px;
}

.header-notice-btn,
.header-link {
  min-height: 34px;
  padding: 0 15px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.12);
  color: rgba(245, 249, 255, 0.92);
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

.header-topup {
  min-height: 34px;
  padding: 0 15px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.26);
  background: rgba(255, 255, 255, 0.95);
  color: var(--shell-accent);
  font-size: 12.5px;
  font-weight: 700;
  line-height: 1;
  cursor: pointer;
  box-shadow: 0 12px 24px rgba(15, 44, 120, 0.18);
  transition:
    background-color 0.16s ease,
    color 0.16s ease,
    border-color 0.16s ease,
    transform 0.16s ease,
    box-shadow 0.16s ease;
}

.header-notice-btn:hover,
.header-link:hover,
.header-link--muted:hover {
  background: rgba(255, 255, 255, 0.18);
  color: #ffffff;
  border-color: rgba(255, 255, 255, 0.24);
  transform: translateY(-1px);
}

.header-topup:hover {
  background: #ffffff;
  color: var(--shell-accent-deep);
  border-color: rgba(255, 255, 255, 0.3);
  transform: translateY(-1px);
  box-shadow: 0 14px 26px rgba(15, 44, 120, 0.2);
}

.header-notice-btn:active,
.header-link:active,
.header-link--muted:active {
  background: rgba(255, 255, 255, 0.14);
  color: #ffffff;
  transform: translateY(0);
}

.header-topup:active {
  background: rgba(255, 255, 255, 0.92);
  color: var(--shell-accent-deep);
  transform: translateY(0);
}

.header-link--muted {
  background: transparent;
}

.main-wrap {
  flex: 1;
  min-width: 0;
  padding: 24px;
  background: #ffffff;
}

.main-content {
  min-width: 0;
  max-width: 1280px;
  margin: 0 auto;
  display: grid;
  gap: 16px;
}

.navbarCon {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: #ffffff;
  border: 0;
  border-radius: var(--radius-card);
  box-shadow: 0 10px 22px rgba(30, 91, 223, 0.06);
}

.app-breadcrumb {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-size: 13px;
  color: var(--shell-ink-faint);
}

.app-breadcrumb .no-redirect {
  min-width: 0;
  font-size: 15px;
  color: var(--shell-ink);
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.navbarCon_right button {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid rgba(214, 226, 248, 0.92);
  background: rgba(255, 255, 255, 0.96);
  color: var(--shell-ink-soft);
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
  background: rgba(244, 248, 255, 0.98);
  border-color: rgba(163, 191, 237, 0.92);
  transform: translateY(-1px);
}

.app-main,
.app-main-con {
  min-width: 0;
}

.app-main-con {
  position: relative;
}

.header-notice-btn:focus-visible,
.header-topup:focus-visible,
.header-link:focus-visible,
.navbarCon_right button:focus-visible,
.menu-link:focus-visible .el-menu-item {
  outline: 2px solid rgba(86, 129, 191, 0.48);
  outline-offset: 2px;
}

.notice-dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 999;
  background: rgba(24, 47, 86, 0.2);
  display: grid;
  place-items: center;
  padding: 16px;
}

.notice-dialog {
  width: min(560px, 100%);
  border-radius: 14px;
  border: 1px solid rgba(214, 226, 248, 0.92);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(240, 247, 255, 0.96));
  box-shadow: var(--shell-shadow);
  overflow: hidden;
}

.notice-dialog__head {
  min-height: 54px;
  padding: 0 14px;
  border-bottom: 1px solid rgba(164, 186, 218, 0.42);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.notice-dialog__head h3 {
  margin: 0;
  font-size: 18px;
  color: var(--shell-ink);
}

.notice-dialog__head button {
  min-height: 32px;
  padding: 0 10px;
  border-radius: 8px;
  border: 1px solid rgba(30, 91, 223, 0.88);
  background: linear-gradient(135deg, #4a84ff 0%, #2d70f0 28%, #1e5bdf 58%, #184ec8 100%);
  color: #ffffff;
  cursor: pointer;
}

.notice-dialog__meta {
  margin: 0;
  padding: 10px 14px 0;
  font-size: 12px;
  color: var(--shell-ink-faint);
}

.notice-dialog__body {
  margin: 0;
  padding: 16px 14px 18px;
  color: var(--shell-ink-soft);
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
    border-bottom: 1px solid rgba(164, 186, 218, 0.38);
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
    gap: 10px;
  }

  .nav-divider {
    width: 1px;
    margin: 10px 8px;
    border-top: 0;
    border-left: 1px solid rgba(164, 186, 218, 0.3);
  }

  .el-menu-item {
    width: auto;
    min-width: 140px;
    margin: 0;
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
    gap: 8px;
  }

  .header-notice-btn,
  .header-topup,
  .header-link {
    min-height: 32px;
    padding: 0 12px;
    font-size: 12px;
  }

  .navbarCon {
    padding: 8px 10px;
  }
}
</style>
