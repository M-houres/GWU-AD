<template>
  <div class="scholar-page shell-frame" :class="{ 'shell-frame--mobile': isMobile, 'shell-frame--drawer-open': isDrawerOpen }">
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
          <div class="scholar-brand admin-brand-block">
            <div class="scholar-brand__eyebrow">管理后台</div>
            <div class="admin-brand">
              <span class="admin-brand__mark">
                <img src="/brand-logo.png" alt="格物学术 Logo" />
              </span>
              <span class="admin-brand__name">格物学术</span>
            </div>
            <p class="scholar-brand__lead">用户、任务、订单与系统配置</p>
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

        <nav class="scholar-nav">
          <RouterLink
            v-for="item in allMenus"
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
              <div class="scholar-topbar__title">{{ title }}</div>
            </div>

            <div class="scholar-topbar__status">
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
  LayoutDashboard,
  ListTodo,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  ReceiptText,
  Settings2,
  Users,
  X,
} from "lucide-vue-next"
import { computed, watch } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

import { useShellLayout } from "../composables/useShellLayout"
import { adminHttp } from "../lib/http"
import { adminHasPermission, clearAdminSession } from "../lib/session"

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

const sidebarToggleIcon = computed(() => (isCollapsedDesktop.value ? PanelLeftOpen : PanelLeftClose))
const sidebarToggleLabel = computed(() => (isCollapsedDesktop.value ? "展开后台导航" : "折叠后台导航"))
const mobileMenuLabel = computed(() => (isDrawerOpen.value ? "关闭后台导航" : "打开后台导航"))

const menuDefs = [
  { path: "/admin/dashboard", label: "总览看板", permission: "dashboard:view", icon: LayoutDashboard },
  { path: "/admin/users", label: "用户管理", permission: "users:view", icon: Users },
  { path: "/admin/tasks", label: "任务管理", permission: "tasks:view", icon: ListTodo },
  { path: "/admin/orders", label: "订单管理", permission: "orders:view", icon: ReceiptText },
  { path: "/admin/partners", label: "渠道返佣", permission: "orders:view", icon: Boxes },
  { path: "/admin/configs", label: "配置中心", permission: "configs:view", icon: Settings2 },
]

const allMenus = computed(() => menuDefs.filter((item) => adminHasPermission(item.permission)))

watch(
  () => route.fullPath,
  () => closeDrawer()
)

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
  background: rgba(15, 23, 42, 0.36);
  backdrop-filter: blur(3px);
}

.scholar-shell--admin {
  --admin-sidebar-width: 268px;
  display: block;
  min-height: 100vh;
  min-height: 100svh;
  transition: none;
}

.scholar-shell--admin.scholar-shell--collapsed {
  --admin-sidebar-width: 84px;
}

.scholar-sidebar--admin {
  position: fixed;
  inset: 0 auto 0 0;
  width: var(--admin-sidebar-width);
  height: 100vh;
  height: 100svh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 18px 14px;
  border: 1px solid #dbe3ee !important;
  border-radius: 0 !important;
  background: #ffffff !important;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.08) !important;
  transition: width 0.2s ease, transform 0.2s ease;
  z-index: 80;
}

.scholar-sidebar--admin::before,
.scholar-sidebar--admin::after {
  display: none !important;
}

.scholar-sidebar__header-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  flex-shrink: 0;
  padding-bottom: 8px;
}

.admin-brand-block {
  margin-bottom: 10px;
  padding-left: 0;
}

.scholar-brand__eyebrow {
  margin-bottom: 6px;
  font-size: 11px;
  color: #64748b !important;
  letter-spacing: 0.12em;
}

.admin-brand {
  margin-top: 6px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.admin-brand__mark {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.admin-brand__mark img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
  border-radius: inherit;
}

.admin-brand__name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0;
  color: #0f172a !important;
}

.scholar-brand__lead {
  margin-top: 8px;
  color: #64748b !important;
  font-size: 12px;
  line-height: 1.6;
}

.scholar-sidebar__actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.scholar-shell__toggle {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid #d5dee9;
  background: #ffffff;
  color: #334155;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease;
}

.scholar-shell__toggle:hover {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}

.scholar-nav {
  margin-top: 16px;
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 12px;
  overflow-y: auto;
  padding-right: 4px;
}

.scholar-nav__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.scholar-sidebar--admin .scholar-nav__item {
  min-height: 48px;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #dbe3ee !important;
  background: #ffffff !important;
  color: #334155 !important;
  box-shadow: none !important;
  justify-content: flex-start;
}

.scholar-sidebar--admin .scholar-nav__item:hover,
.scholar-sidebar--admin .scholar-nav__item:focus,
.scholar-sidebar--admin .scholar-nav__item:active {
  border-color: #93c5fd !important;
  background: #f8fbff !important;
  color: #1f2937 !important;
  box-shadow: none !important;
}

.scholar-sidebar--admin .scholar-nav__item.is-active {
  border-color: #93c5fd !important;
  background: #eff6ff !important;
  color: #1d4ed8 !important;
}

.scholar-sidebar--admin .scholar-nav__item.is-active::before {
  background: #1d4ed8 !important;
}

.scholar-sidebar--admin .scholar-nav__item .scholar-nav__label {
  color: inherit !important;
  font-size: 13px;
  line-height: 1.4;
}

.scholar-topbar__meta {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
}

.scholar-main {
  margin-left: var(--admin-sidebar-width);
  min-height: 100vh;
  min-height: 100svh;
  transition: margin-left 0.2s ease;
}

.scholar-topbar__left {
  display: flex;
  align-items: center;
}

.scholar-topbar__intro {
  min-width: 0;
}

.scholar-topbar__title {
  margin: 0;
}

.scholar-topbar__status {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
}

.scholar-topbar__logout {
  min-height: 34px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid #d5dee9;
  background: #ffffff;
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease;
}

.scholar-topbar__logout:hover {
  border-color: #93c5fd;
  background: #eff6ff;
  color: #1d4ed8;
}

.scholar-shell--collapsed .scholar-sidebar__header-row {
  justify-content: space-between;
}

.scholar-shell--collapsed .scholar-brand__lead,
.scholar-shell--collapsed .admin-brand__name,
.scholar-shell--collapsed .scholar-nav__label {
  display: none;
}

.scholar-shell--collapsed .scholar-brand {
  margin-bottom: 8px;
  padding-left: 0;
}

.scholar-shell--collapsed .scholar-nav__item {
  justify-content: center;
  gap: 0;
  min-height: 44px;
  padding-inline: 10px;
}

@media (max-width: 1023px) {
  .scholar-shell--admin {
    display: grid;
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
    padding: 18px 14px;
    border-radius: 0 16px 16px 0 !important;
    transform: translateX(-104%);
    box-shadow: 0 20px 38px rgba(15, 23, 42, 0.2) !important;
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

  .scholar-main {
    margin-left: 0;
    min-height: auto;
  }

  .scholar-topbar__meta {
    grid-template-columns: auto minmax(0, 1fr) auto;
  }
}

@media (max-width: 720px) {
  .scholar-shell--admin {
    padding-inline: 10px;
  }

  .scholar-topbar__meta {
    gap: 10px;
  }

  .scholar-topbar__title {
    font-size: 22px;
  }

  .admin-brand__name {
    font-size: 15px;
  }
}
</style>
