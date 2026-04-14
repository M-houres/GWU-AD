<template>
  <div class="scholar-page academic-shell-enter shell-frame" :class="{ 'shell-frame--mobile': isMobile, 'shell-frame--drawer-open': isDrawerOpen }">
    <button
      v-if="isMobile && isDrawerOpen"
      type="button"
      class="shell-backdrop"
      aria-label="关闭后台导航"
      @click="closeDrawer"
    ></button>

    <div
      class="scholar-shell scholar-shell--admin"
      :class="{ 'scholar-shell--collapsed': isCollapsedDesktop, 'scholar-shell--mobile': isMobile, 'scholar-shell--drawer-open': isDrawerOpen }"
    >
      <aside class="scholar-sidebar scholar-sidebar--admin" :class="{ 'is-open': isDrawerOpen }">
        <div class="scholar-sidebar__header-row">
          <div class="scholar-brand">
            <div class="scholar-brand__eyebrow">运营后台</div>
            <div class="admin-brand">
              <span class="admin-brand__mark">GW</span>
              <span class="admin-brand__name">格物学术</span>
            </div>
            <p class="scholar-brand__lead">统一管理用户、任务、订单、推广、配置与审计，支持多管理员协同运营。</p>
          </div>

          <div class="scholar-sidebar__actions">
            <button
              v-if="!isMobile"
              type="button"
              class="scholar-shell__toggle"
              :aria-label="sidebarToggleLabel"
              :title="sidebarToggleLabel"
              @click="toggleSidebar"
            >
              <component :is="sidebarToggleIcon" :size="18" />
            </button>
            <button
              v-else
              type="button"
              class="scholar-shell__toggle"
              aria-label="关闭后台导航"
              title="关闭后台导航"
              @click="closeDrawer"
            >
              <X :size="18" />
            </button>
          </div>
        </div>

        <section v-if="coreMenus.length" class="scholar-sidebar__section">
          <div class="scholar-sidebar__label">核心运营</div>
          <nav class="scholar-nav">
            <RouterLink
              v-for="item in coreMenus"
              :key="item.path"
              :to="item.path"
              class="scholar-nav__item"
              :title="isCollapsedDesktop ? item.label : ''"
              :class="{ 'is-active': isMenuActive(item.path) }"
            >
              <span class="scholar-nav__icon">
                <component :is="item.icon" :size="16" />
              </span>
              <span class="scholar-nav__label">{{ item.label }}</span>
            </RouterLink>
          </nav>
        </section>

        <section v-if="advancedMenus.length" class="scholar-sidebar__section">
          <div class="scholar-sidebar__label">系统能力</div>
          <nav class="scholar-nav">
            <RouterLink
              v-for="item in advancedMenus"
              :key="item.path"
              :to="item.path"
              class="scholar-nav__item"
              :title="isCollapsedDesktop ? item.label : ''"
              :class="{ 'is-active': isMenuActive(item.path) }"
            >
              <span class="scholar-nav__icon">
                <component :is="item.icon" :size="16" />
              </span>
              <span class="scholar-nav__label">{{ item.label }}</span>
            </RouterLink>
          </nav>
        </section>

        <div class="scholar-rail-card scholar-rail-card--accent" :class="{ 'is-condensed': isCollapsedDesktop }">
          <div class="scholar-rail-card__eyeline">当前账号</div>
          <div class="scholar-rail-card__headline">{{ isCollapsedDesktop ? adminShortLabel : (adminInfo?.username || "未登录") }}</div>
          <div class="scholar-rail-card__body">
            角色：{{ roleLabel }}
            <br />
            模式：{{ systemModeText }}
          </div>
          <div class="scholar-inline-actions" style="margin-top: 12px">
            <button class="scholar-button scholar-button--secondary scholar-button--block" type="button" @click="logout">退出后台</button>
          </div>
        </div>
      </aside>

      <div class="scholar-main">
        <header class="scholar-topbar">
          <div class="scholar-topbar__meta">
            <div class="scholar-topbar__left">
              <button
                v-if="isMobile"
                type="button"
                class="scholar-shell__toggle"
                :aria-label="mobileMenuLabel"
                :title="mobileMenuLabel"
                @click="toggleSidebar"
              >
                <Menu :size="18" />
              </button>
            </div>

            <div class="scholar-topbar__intro">
              <div class="scholar-topbar__eyebrow">当前模块</div>
              <div class="scholar-topbar__title">{{ title }}</div>
              <p class="scholar-topbar__lead">{{ subtitle || "后台配置尽量收敛到页面维护，减少依赖环境变量的手工操作。" }}</p>
            </div>

            <div class="scholar-topbar__status">
              <span class="scholar-badge scholar-badge--info">{{ roleLabel }}</span>
              <span class="scholar-badge" :class="systemModeBadgeClass">{{ systemModeText }}</span>
              <button type="button" class="scholar-topbar__logout" @click="logout">退出后台</button>
            </div>
          </div>
        </header>

        <main class="scholar-content">
          <slot />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  Boxes,
  Gift,
  LayoutDashboard,
  ListTodo,
  Megaphone,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  ReceiptText,
  ScrollText,
  Settings2,
  ShieldCheck,
  Users,
  X,
} from "lucide-vue-next"
import { computed, onMounted, ref, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { useShellLayout } from "../composables/useShellLayout"
import { adminHttp } from "../lib/http"
import { adminHasPermission, clearAdminSession, getAdminInfo } from "../lib/session"

defineProps({
  title: {
    type: String,
    default: "后台",
  },
  subtitle: {
    type: String,
    default: "",
  },
})

const router = useRouter()
const route = useRoute()
const {
  isMobile,
  isCollapsedDesktop,
  isDrawerOpen,
  toggleSidebar,
  closeDrawer,
} = useShellLayout({ storageKey: "wuhong_admin_shell_collapsed" })
const adminInfo = ref(getAdminInfo())
const systemMode = ref("LLM_PLUS_ALGO")

const roleLabel = computed(() => {
  if (adminInfo.value?.role === "super_admin") {
    return "超级管理员"
  }
  return "普通管理员"
})

const adminShortLabel = computed(() => {
  const text = String(adminInfo.value?.username || "后台").trim()
  return text.slice(0, 2).toUpperCase()
})

const sidebarToggleIcon = computed(() => (isCollapsedDesktop.value ? PanelLeftOpen : PanelLeftClose))
const sidebarToggleLabel = computed(() => (isCollapsedDesktop.value ? "展开后台导航" : "折叠后台导航"))
const mobileMenuLabel = computed(() => (isDrawerOpen.value ? "关闭后台导航" : "打开后台导航"))

const coreMenuDefs = [
  { path: "/admin/dashboard", label: "总览看板", permission: "dashboard:view", icon: LayoutDashboard },
  { path: "/admin/users", label: "用户管理", permission: "users:view", icon: Users },
  { path: "/admin/tasks", label: "任务管理", permission: "tasks:view", icon: ListTodo },
  { path: "/admin/orders", label: "订单管理", permission: "orders:view", icon: ReceiptText },
  { path: "/admin/referrals", label: "推广管理", permission: "referrals:view", icon: Gift },
  { path: "/admin/configs/notice", label: "公告配置", permission: "configs:view", icon: Megaphone },
  { path: "/admin/logs", label: "系统日志", permission: "logs:view", icon: ScrollText },
]

const advancedMenuDefs = [
  { path: "/admin/algo-packages", label: "算法配置", permission: "algo:view", icon: Boxes },
  { path: "/admin/configs", label: "配置中心", permission: "configs:view", icon: Settings2 },
  { path: "/admin/admin-users", label: "权限管理", permission: "admins:view", icon: ShieldCheck },
]

const coreMenus = computed(() => coreMenuDefs.filter((item) => adminHasPermission(item.permission)))
const advancedMenus = computed(() => advancedMenuDefs.filter((item) => adminHasPermission(item.permission)))

const systemModeText = computed(() => {
  if (systemMode.value === "ALGO_ONLY") {
    return "算法降级模式"
  }
  return "大模型 + 算法"
})

const systemModeBadgeClass = computed(() => {
  if (systemMode.value === "ALGO_ONLY") {
    return "scholar-badge--danger"
  }
  return "scholar-badge--success"
})

onMounted(loadSystemStatus)

watch(
  () => route.fullPath,
  () => closeDrawer()
)

async function loadSystemStatus() {
  if (!adminHasPermission("dashboard:view")) {
    return
  }
  try {
    const data = await adminHttp.get("/admin/switch/current")
    systemMode.value = data.current_mode || "LLM_PLUS_ALGO"
  } catch {
    systemMode.value = "LLM_PLUS_ALGO"
  }
}

async function logout() {
  try {
    await adminHttp.post("/admin/auth/logout")
  } catch {}
  clearAdminSession()
  router.push("/admin/login")
}

function isMenuActive(path) {
  return isRouteMatch(route.path, path)
}

function isRouteMatch(currentPath, targetPath) {
  if (targetPath === "/admin/users") {
    return currentPath === targetPath || currentPath.startsWith("/admin/users/")
  }
  if (targetPath === "/admin/configs") {
    return currentPath === targetPath
  }
  return currentPath === targetPath || currentPath.startsWith(`${targetPath}/`)
}
</script>

<style scoped>
.shell-frame {
  position: relative;
  min-height: 100vh;
  min-height: 100svh;
}

.shell-backdrop {
  position: fixed;
  inset: 0;
  z-index: 79;
  border: 0;
  background: rgba(10, 24, 51, 0.42);
  backdrop-filter: blur(4px);
}

.scholar-shell--admin {
  --admin-sidebar-width: 292px;
  grid-template-columns: var(--admin-sidebar-width) minmax(0, 1fr);
  min-height: 100vh;
  min-height: 100svh;
  transition: grid-template-columns 0.22s ease;
}

.scholar-shell--admin.scholar-shell--collapsed {
  --admin-sidebar-width: 104px;
}

.scholar-sidebar--admin {
  transition: transform 0.22s ease;
  z-index: 80;
}

.scholar-sidebar__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.scholar-sidebar__actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.scholar-shell__toggle {
  width: 38px;
  height: 38px;
  border-radius: 12px;
  border: 1px solid #d9d9d9;
  background: #ffffff;
  color: #111111;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    background-color 0.16s ease,
    box-shadow 0.16s ease;
}

.scholar-shell__toggle:hover {
  transform: translateY(-1px);
  border-color: #bfc8d4;
  background: #ffffff;
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.08);
}

.scholar-nav__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.scholar-topbar__meta {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: flex-start;
  gap: 16px;
}

.scholar-topbar__left {
  display: flex;
  align-items: center;
}

.scholar-topbar__intro {
  min-width: 0;
}

.scholar-topbar__status {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 10px;
}

.scholar-topbar__logout {
  min-height: 34px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid #d0d0d0;
  background: #ffffff;
  color: #111111;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform 0.16s ease,
    border-color 0.16s ease,
    background-color 0.16s ease;
}

.scholar-topbar__logout:hover {
  transform: translateY(-1px);
  border-color: #bfc8d4;
}

.admin-brand {
  margin-top: 10px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.admin-brand__mark {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  background: #111111;
  color: #ffffff;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.admin-brand__name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #111111;
}

.scholar-sidebar .scholar-nav__item,
.scholar-sidebar .scholar-nav__item:hover,
.scholar-sidebar .scholar-nav__item:focus,
.scholar-sidebar .scholar-nav__item:focus-visible,
.scholar-sidebar .scholar-nav__item:active,
.scholar-sidebar .scholar-nav__item.is-active,
.scholar-sidebar .scholar-nav__item:visited {
  background: #ffffff !important;
  color: #000000 !important;
  border-color: #d0d0d0 !important;
  box-shadow: none !important;
}

.scholar-sidebar .scholar-nav__item .scholar-nav__label {
  color: #000000 !important;
}

.scholar-sidebar .scholar-nav__item.is-active::before {
  background: #000000 !important;
}

.scholar-sidebar .scholar-rail-card,
.scholar-sidebar .scholar-rail-card--accent {
  background: #ffffff !important;
  border: 1px solid #d9d9d9 !important;
  color: #111111 !important;
}

.scholar-sidebar .scholar-rail-card::before,
.scholar-sidebar .scholar-rail-card::after {
  display: none !important;
  content: none !important;
}

.scholar-sidebar .scholar-rail-card__eyeline,
.scholar-sidebar .scholar-rail-card__headline,
.scholar-sidebar .scholar-rail-card__body,
.scholar-sidebar .scholar-rail-card__label,
.scholar-sidebar .scholar-rail-card__value,
.scholar-sidebar .scholar-rail-card__metric span,
.scholar-sidebar .scholar-rail-card__metric strong {
  color: #111111 !important;
}

.scholar-sidebar .scholar-rail-card__metric {
  background: #ffffff !important;
  border: 1px solid #d9d9d9 !important;
}

.scholar-shell--collapsed .scholar-sidebar__header-row {
  justify-content: center;
}

.scholar-shell--collapsed .scholar-sidebar__actions,
.scholar-shell--collapsed .scholar-sidebar__label,
.scholar-shell--collapsed .scholar-brand__lead,
.scholar-shell--collapsed .admin-brand__name,
.scholar-shell--collapsed .scholar-nav__label,
.scholar-shell--collapsed .scholar-rail-card__eyeline,
.scholar-shell--collapsed .scholar-rail-card__body,
.scholar-shell--collapsed .scholar-inline-actions {
  display: none;
}

.scholar-shell--collapsed .scholar-brand {
  margin-bottom: 14px;
  padding-left: 0;
}

.scholar-shell--collapsed .admin-brand {
  justify-content: center;
}

.scholar-shell--collapsed .scholar-nav__item {
  justify-content: center;
  gap: 0;
  padding-inline: 14px;
}

.scholar-shell--collapsed .scholar-rail-card {
  padding: 14px 10px;
}

.scholar-shell--collapsed .scholar-rail-card__headline {
  margin-top: 0;
  font-size: 16px;
  text-align: center;
  letter-spacing: 0.06em;
}

@media (max-width: 1023px) {
  .scholar-shell--admin {
    grid-template-columns: 1fr;
    padding: 14px 12px calc(18px + env(safe-area-inset-bottom, 0px));
  }

  .scholar-sidebar--admin {
    position: fixed;
    inset: 0 auto 0 0;
    width: min(82vw, 320px);
    max-height: none;
    height: 100vh;
    height: 100svh;
    border-radius: 0 28px 28px 0;
    transform: translateX(-104%);
    box-shadow: 0 24px 44px rgba(8, 26, 66, 0.26);
  }

  .scholar-sidebar--admin.is-open {
    transform: translateX(0);
  }

  .scholar-topbar {
    position: sticky;
    top: 0;
    z-index: 70;
    padding: calc(18px + env(safe-area-inset-top, 0px)) 16px 18px;
  }

  .scholar-topbar__meta {
    grid-template-columns: auto minmax(0, 1fr);
  }

  .scholar-topbar__status {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}

@media (max-width: 720px) {
  .scholar-shell--admin {
    padding-inline: 10px;
  }

  .scholar-topbar__meta {
    gap: 12px;
  }

  .scholar-topbar__title {
    font-size: 26px;
  }

  .scholar-topbar__lead {
    font-size: 13px;
    line-height: 1.7;
  }

  .scholar-topbar__status {
    gap: 8px;
  }
}
</style>
