<template>
  <div class="scholar-page academic-shell-enter">
    <div class="scholar-shell scholar-shell--admin">
      <aside class="scholar-sidebar">
        <div class="scholar-brand">
          <div class="scholar-brand__eyebrow">运营后台</div>
          <div class="admin-brand">
            <span class="admin-brand__mark">GW</span>
            <span class="admin-brand__name">格物学术</span>
          </div>
          <p class="scholar-brand__lead">统一管理用户、任务、订单、推广、配置与审计，支持多管理员协同运营。</p>
        </div>

        <section v-if="coreMenus.length" class="scholar-sidebar__section">
          <div class="scholar-sidebar__label">核心运营</div>
          <nav class="scholar-nav">
            <RouterLink
              v-for="item in coreMenus"
              :key="item.path"
              :to="item.path"
              class="scholar-nav__item"
              :class="{ 'is-active': isMenuActive(item.path) }"
            >
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
              :class="{ 'is-active': isMenuActive(item.path) }"
            >
              <span class="scholar-nav__label">{{ item.label }}</span>
            </RouterLink>
          </nav>
        </section>

        <div class="scholar-rail-card scholar-rail-card--accent">
          <div class="scholar-rail-card__eyeline">当前账号</div>
          <div class="scholar-rail-card__headline">{{ adminInfo?.username || '未登录' }}</div>
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
            <div>
              <div class="scholar-topbar__eyebrow">当前模块</div>
              <div class="scholar-topbar__title">{{ title }}</div>
              <p class="scholar-topbar__lead">{{ subtitle || '后台配置尽量收敛到页面维护，减少依赖环境变量的手工操作。' }}</p>
            </div>

            <div class="scholar-topbar__status">
              <span class="scholar-badge scholar-badge--info">{{ roleLabel }}</span>
              <span class="scholar-badge" :class="systemModeBadgeClass">{{ systemModeText }}</span>
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
import { computed, onMounted, ref } from "vue"
import { RouterLink, useRoute, useRouter } from "vue-router"

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
const adminInfo = ref(getAdminInfo())
const systemMode = ref("LLM_PLUS_ALGO")

const roleLabel = computed(() => {
  if (adminInfo.value?.role === "super_admin") {
    return "超级管理员"
  }
  return "普通管理员"
})

const coreMenuDefs = [
  { path: "/admin/dashboard", label: "总览看板", permission: "dashboard:view" },
  { path: "/admin/users", label: "用户管理", permission: "users:view" },
  { path: "/admin/tasks", label: "任务管理", permission: "tasks:view" },
  { path: "/admin/orders", label: "订单管理", permission: "orders:view" },
  { path: "/admin/referrals", label: "推广管理", permission: "referrals:view" },
  { path: "/admin/configs/notice", label: "公告配置", permission: "configs:view" },
  { path: "/admin/logs", label: "系统日志", permission: "logs:view" },
]

const advancedMenuDefs = [
  { path: "/admin/algo-packages", label: "算法配置", permission: "algo:view" },
  { path: "/admin/configs", label: "配置中心", permission: "configs:view" },
  { path: "/admin/admin-users", label: "权限管理", permission: "admins:view" },
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

function logout() {
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

</style>
