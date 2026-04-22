<template>
  <div class="app-shell" :class="{ 'is-mobile': isMobile }">
    <header class="header-wrap" :class="{ 'is-elevated': isHeaderElevated }">
      <div class="header-left">
        <RouterLink to="/app/detect" class="brand-home" aria-label="格物学术首页" title="格物学术">
          <span class="brand-mark">GW</span>
          <div class="brand-copy">
            <strong>格物学术</strong>
          </div>
        </RouterLink>
      </div>

      <div class="header-center">
        <div v-if="!isNavigationReady" class="menu-loading-placeholder" aria-hidden="true"></div>
        <nav v-else class="top-nav-scroll" aria-label="主导航">
          <div class="top-nav-track">
            <div class="top-nav-primary">
              <template v-for="item in visibleTopMenus" :key="item.path">
                <div v-if="item.disabled" class="top-nav-link is-disabled" aria-disabled="true">
                  <i class="siderIcon">
                    <component :is="item.icon" :size="17" />
                  </i>
                  <span class="subMenu_title_box">{{ item.label }}</span>
                  <span v-if="item.badge" class="menu-beta-badge">{{ item.badge }}</span>
                </div>
                <RouterLink v-else :to="item.path" class="menu-link">
                  <div class="top-nav-link" :class="{ 'is-active': isMenuActive(item.path) }">
                    <i class="siderIcon">
                      <component :is="item.icon" :size="17" />
                    </i>
                    <span class="subMenu_title_box">{{ item.label }}</span>
                    <span v-if="item.badge" class="menu-beta-badge">{{ item.badge }}</span>
                  </div>
                </RouterLink>
              </template>
              <div v-if="overflowTopMenus.length" ref="navMoreRef" class="top-more">
                <button
                  type="button"
                  class="top-btn top-btn--more top-btn--nav-more"
                  :class="{ 'is-active': isNavMoreOpen }"
                  aria-label="更多导航"
                  title="更多导航"
                  @click="toggleNavMore"
                >
                  <MoreHorizontal :size="16" />
                  <span>更多</span>
                </button>
                <div v-if="isNavMoreOpen" class="top-dropdown top-dropdown--align-right">
                  <template v-for="item in overflowTopMenus" :key="item.path">
                    <div v-if="item.disabled" class="top-dropdown__item is-disabled" aria-disabled="true">
                      {{ item.label }}
                    </div>
                    <RouterLink
                      v-else
                      :to="item.path"
                      class="top-dropdown__item top-dropdown__item--link"
                      @click="handleTopMenuNavigate"
                    >
                      {{ item.label }}
                    </RouterLink>
                  </template>
                </div>
              </div>
            </div>
            <div class="top-nav-shortcuts">
              <div v-if="showCreditsCard" class="top-credit-card">
                <span>积分余额</span>
                <strong>{{ creditsLabel }}</strong>
              </div>
              <button
                v-if="!hideAccountEntry"
                type="button"
                class="top-btn"
                :class="{ 'is-active': isPrimaryAccountActionActive }"
                @click="openAccountEntry"
              >
                <span class="top-btn__icon" aria-hidden="true">
                  <User :size="13" />
                </span>
                <span>{{ accountEntryLabel }}</span>
              </button>
            </div>
          </div>
        </nav>
      </div>

      <div class="header-right">
        <button
          v-if="hasUserToken && !isCompactMobile"
          type="button"
          class="top-btn top-btn--muted"
          @click="logout()"
        >
          <span class="top-btn__icon" aria-hidden="true">
            <User :size="13" />
          </span>
          <span>退出</span>
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
        </div>

        <div class="app-main">
          <div class="app-main-con">
            <slot />
          </div>
        </div>
      </div>
    </main>

    <div
      v-if="showNoticeEntry && isNoticeDialogOpen && !disableNoticeDialog"
      class="notice-dialog-mask"
      @click.self="isNoticeDialogOpen = false"
    >
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
import { MoreHorizontal, User } from "lucide-vue-next"
import { computed, onMounted, onUnmounted, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { userHttp } from "../lib/http"
import { clearUserSession, getUserNavigationConfig, getUserToken, setUserNavigationConfig } from "../lib/session"
import {
  DEFAULT_HEADER_NOTICE_TEXT,
  NOTICE_SEEN_STORAGE_KEY,
  USER_SHELL_GROUP_ORDER,
  formatUserShellNoticeTime,
  groupVisibleUserMenus,
  mapUserShellMenuItems,
  normalizeUserShellNotice,
  splitTopMenus,
} from "../lib/userShell"
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
    type: [Number, String],
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
  hideAccountEntry: {
    type: Boolean,
    default: false,
  },
  disableNoticeDialog: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(["buy"])

const MOBILE_BREAKPOINT = 1024
const COMPACT_BREAKPOINT = 720

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
const viewportWidth = ref(typeof window !== "undefined" ? window.innerWidth : 1440)
const isHeaderElevated = ref(false)
const isNavMoreOpen = ref(false)
const navMoreRef = ref(null)

let noticePollTimer = null

const allMenuItems = computed(() => mapUserShellMenuItems(navigationState.value.items))
const visibleMenuGroups = computed(() => groupVisibleUserMenus(allMenuItems.value, USER_SHELL_GROUP_ORDER))
const visibleMenus = computed(() => visibleMenuGroups.value.flatMap((group) => group.items))
const centerMenus = computed(() => visibleMenus.value)
const matchedMenu = computed(() => allMenuItems.value.find((item) => isRouteMatch(route.path, item.path)) || null)
const activeMenu = computed(() => matchedMenu.value || visibleMenus.value[0] || allMenuItems.value[0] || null)
const routeTitle = computed(() => props.title || String(route.meta?.title || "").trim() || activeMenu.value?.label || "工作台")
const breadcrumbTitle = computed(() => matchedMenu.value?.label || routeTitle.value || "工作台")
const shouldHideTopbar = computed(() => {
  if (props.hideTopbar) return true
  return isRouteMatch(route.path, "/app/profile")
})
const isPrimaryAccountActionActive = computed(() => (hasUserToken.value ? isRouteMatch(route.path, "/app/profile") : isRouteMatch(route.path, "/login")))
const noticeTitle = computed(() => String(noticeState.value.title || "公告"))
const showNoticeEntry = computed(() => noticeState.value.enabled)
const noticeBodyText = computed(() => {
  if (!noticeState.value.enabled) {
    return "当前暂无公告内容。"
  }
  return String(noticeState.value.content || DEFAULT_HEADER_NOTICE_TEXT)
})
const noticeUpdatedLabel = computed(() => formatUserShellNoticeTime(noticeState.value.updated_at))
const isMobile = computed(() => viewportWidth.value < MOBILE_BREAKPOINT)
const isCompactMobile = computed(() => viewportWidth.value < COMPACT_BREAKPOINT)
const topMenuLimit = computed(() => (isCompactMobile.value ? 3 : Number.POSITIVE_INFINITY))
const visibleTopMenus = computed(() => splitTopMenus(centerMenus.value, topMenuLimit.value).visibleTopMenus)
const overflowTopMenus = computed(() => splitTopMenus(centerMenus.value, topMenuLimit.value).overflowTopMenus)
const accountEntryLabel = computed(() => (hasUserToken.value ? "账户中心" : "登录"))
const showCreditsCard = computed(() => hasUserToken.value && normalizeCredits(props.credits) !== null)
const creditsLabel = computed(() => {
  const value = normalizeCredits(props.credits)
  if (value === null) return "-"
  return value.toLocaleString()
})

onMounted(() => {
  syncTokenState()
  syncViewportWidth()
  syncHeaderElevated()
  startNoticeSync()
  if (typeof window !== "undefined") {
    window.addEventListener("resize", syncViewportWidth, { passive: true })
    window.addEventListener("scroll", syncHeaderElevated, { passive: true })
  }
  if (typeof document !== "undefined") {
    document.addEventListener("click", handleDocumentClick)
  }
})

onUnmounted(() => {
  stopNoticeSync()
  if (typeof window !== "undefined") {
    window.removeEventListener("resize", syncViewportWidth)
    window.removeEventListener("scroll", syncHeaderElevated)
  }
  if (typeof document !== "undefined") {
    document.removeEventListener("click", handleDocumentClick)
  }
})

watch(
  () => route.fullPath,
  () => {
    syncTokenState()
    closeTopMenus()
  }
)

watch(
  () => overflowTopMenus.value.length,
  (length) => {
    if (!length) isNavMoreOpen.value = false
  }
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
  const normalized = normalizeUserShellNotice(raw)
  noticeState.value = {
    enabled: normalized.enabled,
    title: normalized.title,
    content: normalized.content,
    updated_at: normalized.updated_at,
  }
  if (!normalized.enabled) {
    isNoticeDialogOpen.value = false
    return
  }
  if (!normalized.hasExplicitNotice) {
    return
  }
  const nextNoticeKey = normalized.noticeKey
  if (nextNoticeKey !== readSeenNoticeKey()) {
    writeSeenNoticeKey(nextNoticeKey)
    isNoticeDialogOpen.value = true
  }
}

function startNoticeSync() {
  stopNoticeSync()
  loadShellOptions()
  noticePollTimer = window.setInterval(loadAnnouncement, 45000)
  if (typeof document !== "undefined") {
    document.addEventListener("visibilitychange", handleVisibilityChange)
  }
}

function stopNoticeSync() {
  if (noticePollTimer) {
    window.clearInterval(noticePollTimer)
    noticePollTimer = null
  }
  if (typeof document !== "undefined") {
    document.removeEventListener("visibilitychange", handleVisibilityChange)
  }
}

function handleVisibilityChange() {
  if (!document.hidden) {
    loadAnnouncement()
  }
}

function syncTokenState() {
  hasUserToken.value = Boolean(getUserToken())
}

function readSeenNoticeKey() {
  if (typeof window === "undefined") return ""
  try {
    return window.localStorage.getItem(NOTICE_SEEN_STORAGE_KEY) || ""
  } catch {
    return ""
  }
}

function writeSeenNoticeKey(value) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(NOTICE_SEEN_STORAGE_KEY, value)
  } catch {}
}

function syncViewportWidth() {
  if (typeof window === "undefined") return
  viewportWidth.value = window.innerWidth
}

function syncHeaderElevated() {
  if (typeof window === "undefined") return
  isHeaderElevated.value = window.scrollY > 8
}

function handleDocumentClick(event) {
  const target = event.target
  if (!isTargetInside(navMoreRef.value, target)) {
    isNavMoreOpen.value = false
  }
}

function isTargetInside(root, target) {
  if (!root || !target || typeof root.contains !== "function") return false
  return root.contains(target)
}

function closeTopMenus() {
  isNavMoreOpen.value = false
}

function toggleNavMore() {
  isNavMoreOpen.value = !isNavMoreOpen.value
}

function handleTopMenuNavigate() {
  isNavMoreOpen.value = false
}

function openAccountEntry() {
  hasUserToken.value ? goProfile() : goLogin()
}

async function logout() {
  try {
    await userHttp.post("/auth/logout")
  } catch {}
  clearUserSession()
  hasUserToken.value = false
  router.push("/login")
}

function goProfile() {
  router.push("/app/profile")
}

function goLogin() {
  const redirect = encodeURIComponent(route.fullPath || "/app/detect")
  router.push(`/login?redirect=${redirect}`)
}

function isMenuActive(path) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function isRouteMatch(currentPath, targetPath) {
  return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`)
}

function normalizeCredits(value) {
  if (value === null || value === undefined || value === "") return null
  const num = Number(value)
  if (!Number.isFinite(num)) return null
  return Math.max(0, Math.floor(num))
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
  --shell-shadow: 0 20px 40px rgba(30, 91, 223, 0.12);
  --shell-shadow-soft: 0 10px 22px rgba(30, 91, 223, 0.08);
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
  min-height: 100vh;
  min-height: 100svh;
  display: flex;
  flex-direction: column;
  background: var(--shell-band);
  color: var(--shell-ink);
}

.header-wrap {
  position: sticky;
  top: 0;
  z-index: 90;
  min-height: 64px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  padding: 10px 24px;
  background: linear-gradient(135deg, rgba(43, 104, 228, 0.96) 0%, rgba(30, 91, 223, 0.95) 100%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(12px);
  transition: box-shadow 0.18s ease;
}

.header-wrap.is-elevated {
  box-shadow: 0 12px 26px rgba(8, 31, 88, 0.28);
}

.header-left {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.brand-home {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  min-width: 0;
  flex-shrink: 0;
}

.brand-mark {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.24);
  color: #ffffff;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
  box-shadow: none;
}

.brand-copy strong {
  display: block;
  color: #ffffff;
  font-size: 18px;
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: 0.03em;
}

.top-btn {
  min-height: 40px;
  padding: 0 6px;
  border-radius: 0;
  border: 0;
  background: transparent;
  color: rgba(255, 255, 255, 0.9);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 14px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
  cursor: pointer;
  transition:
    color 0.16s ease,
    opacity 0.16s ease;
}

.top-btn__icon {
  width: 18px;
  height: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  background: rgba(255, 255, 255, 0.1);
  flex: 0 0 auto;
}

.top-btn:hover {
  color: #ffffff;
  opacity: 1;
}

.top-btn.is-active {
  color: #ffffff;
  text-decoration: none;
}

.top-btn.is-primary {
  font-weight: 700;
}

.top-btn--muted {
  background: transparent;
  color: rgba(255, 255, 255, 0.78);
}

.top-btn--more {
  padding-inline: 4px;
}

.top-more {
  position: relative;
}

.top-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  min-width: 132px;
  padding: 8px;
  border-radius: 12px;
  border: 1px solid rgba(214, 226, 248, 0.92);
  background: #ffffff;
  box-shadow: var(--shell-shadow-soft);
  z-index: 40;
  display: grid;
  gap: 6px;
}

.top-dropdown--align-right {
  left: auto;
  right: 0;
}

.top-dropdown__item {
  min-height: 40px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: rgba(247, 250, 255, 0.96);
  color: var(--shell-ink-soft);
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  cursor: pointer;
  transition:
    background-color 0.16s ease,
    border-color 0.16s ease,
    color 0.16s ease;
}

.top-dropdown__item:hover {
  background: #ffffff;
  color: var(--shell-ink);
  border-color: rgba(30, 91, 223, 0.16);
}

.top-dropdown__item.is-disabled {
  opacity: 0.62;
  cursor: not-allowed;
}

.header-center {
  min-width: 0;
}

.menu-loading-placeholder {
  height: 40px;
  border-radius: 999px;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.18) 0%, rgba(255, 255, 255, 0.28) 30%, rgba(255, 255, 255, 0.18) 60%),
    transparent;
  background-size: 220px 100%;
  animation: menu-loading-wave 1.6s linear infinite;
}

@keyframes menu-loading-wave {
  0% {
    background-position: 0 0;
  }
  100% {
    background-position: 220px 0;
  }
}

.top-nav-scroll {
  overflow-x: auto;
  overflow-y: hidden;
  white-space: nowrap;
  scrollbar-width: thin;
}

.top-nav-scroll::-webkit-scrollbar {
  height: 5px;
}

.top-nav-scroll::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.35);
}

.top-nav-track {
  min-width: 100%;
  width: max-content;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.top-nav-primary,
.top-nav-shortcuts {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.top-credit-card {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.34);
  background: rgba(255, 255, 255, 0.15);
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  line-height: 1;
}

.top-credit-card span {
  font-size: 12px;
  font-weight: 600;
  opacity: 0.92;
}

.top-credit-card strong {
  font-size: 14px;
  font-weight: 700;
}

.menu-link {
  text-decoration: none;
}

.top-nav-link {
  min-height: 44px;
  padding: 0 8px;
  border-radius: 0;
  border: 0;
  background: transparent;
  color: rgba(255, 255, 255, 0.9);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition:
    color 0.16s ease,
    opacity 0.16s ease;
}

.top-nav-link:hover {
  color: #ffffff;
  opacity: 1;
}

.top-nav-link.is-active {
  color: #ffffff;
  text-decoration: underline;
  text-decoration-thickness: 2px;
  text-underline-offset: 6px;
}

.top-nav-link.is-disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.siderIcon {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
}

.subMenu_title_box {
  font-size: 18px;
  font-weight: 700;
  line-height: 1;
}

.menu-beta-badge {
  border-radius: 999px;
  padding: 4px 8px;
  font-size: 11px;
  line-height: 1;
  background: rgba(255, 255, 255, 0.22);
  color: currentColor;
}

.header-right {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.main-wrap {
  flex: 1;
  min-width: 0;
  min-height: 0;
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
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 12px;
  padding: 12px 16px;
  background: #ffffff;
  border-radius: var(--radius-card);
  box-shadow: 0 10px 22px rgba(30, 91, 223, 0.06);
}

.app-breadcrumb {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
  font-size: 13px;
  color: var(--shell-ink-faint);
}

.app-breadcrumb .no-redirect {
  min-width: 0;
  font-size: 24px;
  color: var(--shell-ink);
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.app-main,
.app-main-con {
  min-width: 0;
}

.app-main-con {
  position: relative;
}

.top-btn:focus-visible,
.top-nav-link:focus-visible,
.top-dropdown__item:focus-visible {
  outline: 2px solid rgba(255, 255, 255, 0.72);
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

@media (max-width: 1279px) {
  .header-wrap {
    padding-inline: 16px;
    gap: 12px;
  }

  .app-breadcrumb .no-redirect {
    font-size: 20px;
  }

  .main-wrap {
    padding: 18px 16px calc(22px + env(safe-area-inset-bottom, 0px));
  }
}

@media (max-width: 1023px) {
  .brand-copy strong {
    font-size: 16px;
  }

  .top-btn,
  .top-nav-link,
  .top-dropdown__item {
    min-height: 40px;
  }

  .subMenu_title_box {
    font-size: 17px;
  }
}

@media (max-width: 720px) {
  .header-wrap {
    min-height: 56px;
    padding: calc(6px + env(safe-area-inset-top, 0px)) 12px 6px;
    gap: 8px;
  }

  .brand-copy {
    display: none;
  }

  .brand-mark {
    width: 34px;
    height: 34px;
    border-radius: 11px;
    font-size: 11px;
  }

  .top-btn,
  .top-nav-link,
  .top-dropdown__item {
    min-height: 44px;
    font-size: 12px;
  }

  .top-btn {
    padding-inline: 10px;
  }

  .top-btn--more {
    padding-inline: 9px;
  }

  .top-btn--more span {
    display: none;
  }

  .top-nav-link {
    padding-inline: 12px;
  }

  .subMenu_title_box {
    font-size: 15px;
  }

  .main-wrap {
    padding: 14px 12px calc(18px + env(safe-area-inset-bottom, 0px));
  }

  .navbarCon {
    padding: 12px;
    align-items: center;
  }

  .app-breadcrumb {
    font-size: 12px;
  }

  .app-breadcrumb .no-redirect {
    font-size: 18px;
  }
}
</style>
