import { createRouter, createWebHistory } from 'vue-router'

import { resolveAdminRedirect, resolvePartnerRedirect, resolveUserRedirect } from '../lib/redirect'
import { capturePartnerTrackingFromQuery } from '../lib/partnerTracking'
import { adminHasPermission, getAdminInfo, getAdminToken, getPartnerToken, getUserToken } from '../lib/session'

const AdminLoginPage = () => import('../views/admin/AdminLoginPage.vue')
const AdminOrderPage = () => import('../views/admin/AdminOrderPage.vue')
const AdminTaskPage = () => import('../views/admin/AdminTaskPage.vue')
const AdminUserPage = () => import('../views/admin/AdminUserPage.vue')
const AdminUserDetailPage = () => import('../views/admin/AdminUserDetailPage.vue')
const AdminDashboardPage = () => import('../views/admin/AdminDashboardPage.vue')
const AdminConfigPage = () => import('../views/admin/AdminConfigPage.vue')
const AdminPartnerPage = () => import('../views/admin/AdminPartnerPage.vue')
const AdminPromoReviewPage = () => import('../views/admin/AdminPromoReviewPage.vue')
const LoginPage = () => import('../views/user/LoginPage.vue')
const UserBuyPage = () => import('../views/user/UserBuyPage.vue')
const UserProfilePage = () => import('../views/user/UserProfilePage.vue')
const UserDetectPage = () => import('../views/user/UserDetectPage.vue')
const UserDetectRecordsPage = () => import('../views/user/UserDetectRecordsPage.vue')
const UserRewritePage = () => import('../views/user/UserRewritePage.vue')
const UserRewriteRecordsPage = () => import('../views/user/UserRewriteRecordsPage.vue')
const UserDedupPage = () => import('../views/user/UserDedupPage.vue')
const UserDedupRecordsPage = () => import('../views/user/UserDedupRecordsPage.vue')
const UserPromoCenterPage = () => import('../views/user/UserPromoCenterPage.vue')
const PartnerLoginPage = () => import('../views/partner/PartnerLoginPage.vue')
const PartnerPortalPage = () => import('../views/partner/PartnerPortalPage.vue')
const TermsPage = () => import('../views/user/TermsPage.vue')
const PrivacyPage = () => import('../views/user/PrivacyPage.vue')

const adminEntryRoutes = [
  { path: '/admin/dashboard', permission: 'dashboard:view' },
  { path: '/admin/users', permission: 'users:view' },
  { path: '/admin/tasks', permission: 'tasks:view' },
  { path: '/admin/orders', permission: 'orders:view' },
  { path: '/admin/partners', permission: 'orders:view' },
  { path: '/admin/promo-reviews', permission: 'users:view' },
  { path: '/admin/configs', permission: 'configs:view' },
]

// Pages that can be browsed without login; action buttons inside these pages
// still enforce login through `ensureUserLogin`.
const userGuestBrowsablePaths = new Set([
  '/app/detect',
  '/app/dedup',
  '/app/rewrite',
  '/app/buy',
  '/app/promo-center',
  '/app/partner',
])

function firstAccessibleAdminRoute() {
  for (const item of adminEntryRoutes) {
    if (adminHasPermission(item.permission)) {
      return item.path
    }
  }
  return '/admin/login'
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/app/detect' },
    { path: '/home', redirect: '/app/detect' },
    { path: '/login', component: LoginPage },
    { path: '/register', component: LoginPage },
    { path: '/terms', component: TermsPage, meta: { title: '服务协议' } },
    { path: '/privacy', component: PrivacyPage, meta: { title: '隐私政策' } },
    { path: '/detect', redirect: '/app/detect' },
    { path: '/dedup', redirect: '/app/dedup' },
    { path: '/rewrite', redirect: '/app/rewrite' },
    { path: '/history', redirect: '/app/profile?tab=history' },
    { path: '/buy', redirect: '/app/buy' },
    { path: '/credits', redirect: '/app/profile?tab=credits' },
    { path: '/profile', redirect: '/app/profile' },
    { path: '/app/history', redirect: '/app/profile?tab=history' },
    { path: '/app/credits', redirect: '/app/profile?tab=credits' },
    { path: '/app/detect', component: UserDetectPage, meta: { auth: 'user', title: 'AIGC检测' } },
    { path: '/app/detect/records', component: UserDetectRecordsPage, meta: { auth: 'user', title: 'AIGC检测记录' } },
    { path: '/app/dedup', component: UserDedupPage, meta: { auth: 'user', title: '降重复率' } },
    { path: '/app/dedup/records', component: UserDedupRecordsPage, meta: { auth: 'user', title: '降重复率记录' } },
    { path: '/app/rewrite', component: UserRewritePage, meta: { auth: 'user', title: '降AIGC率' } },
    { path: '/app/rewrite/records', component: UserRewriteRecordsPage, meta: { auth: 'user', title: '降AIGC率记录' } },
    { path: '/app/buy', component: UserBuyPage, meta: { auth: 'user', title: '充值通用点数' } },
    { path: '/app/promo-center', component: UserPromoCenterPage, meta: { title: '推广中心' } },
    { path: '/app/partner/login', component: PartnerLoginPage, meta: { title: '渠道门户入口' } },
    { path: '/app/partner', component: PartnerPortalPage, meta: { auth: 'partner', title: '渠道返佣门户' } },
    { path: '/app/profile', component: UserProfilePage, meta: { auth: 'user', title: '账户中心' } },
    { path: '/admin', redirect: '/admin/dashboard' },
    { path: '/admin/login', component: AdminLoginPage },
    { path: '/admin/dashboard', component: AdminDashboardPage, meta: { auth: 'admin', title: '后台总览', adminPermission: 'dashboard:view' } },
    { path: '/admin/users', component: AdminUserPage, meta: { auth: 'admin', title: '用户管理', adminPermission: 'users:view' } },
    { path: '/admin/users/:id', component: AdminUserDetailPage, meta: { auth: 'admin', title: '用户详情', adminPermission: 'users:view' } },
    { path: '/admin/tasks', component: AdminTaskPage, meta: { auth: 'admin', title: '任务管理', adminPermission: 'tasks:view' } },
    { path: '/admin/orders', component: AdminOrderPage, meta: { auth: 'admin', title: '订单管理', adminPermission: 'orders:view' } },
    { path: '/admin/partners', component: AdminPartnerPage, meta: { auth: 'admin', title: '渠道返佣', adminPermission: 'orders:view' } },
    { path: '/admin/promo-reviews', component: AdminPromoReviewPage, meta: { auth: 'admin', title: '推广审核', adminPermission: 'users:view' } },
    { path: '/admin/configs', component: AdminConfigPage, meta: { auth: 'admin', title: '配置中心', adminPermission: 'configs:view' } },
    { path: '/admin/configs/miniapp', redirect: '/admin/configs?tab=miniapp' },
  ],
})

router.beforeEach((to) => {
  capturePartnerTrackingFromQuery(to.query)
  if ((to.path === '/login' || to.path === '/register') && getUserToken()) {
    return resolveUserRedirect(to.query.redirect, '/app/detect')
  }
  if (to.meta.auth === 'user' && !getUserToken()) {
    if (userGuestBrowsablePaths.has(to.path)) {
      return true
    }
    const redirect = encodeURIComponent(to.fullPath || '/app/detect')
    return `/login?redirect=${redirect}`
  }
  if (to.path === '/admin/login' && getAdminToken()) {
    const fallback = firstAccessibleAdminRoute()
    return resolveAdminRedirect(to.query.redirect, fallback)
  }
  if (to.path === '/app/partner/login' && getPartnerToken()) {
    return resolvePartnerRedirect(to.query.redirect, '/app/partner')
  }
  if (to.meta.auth === 'admin' && !getAdminToken()) {
    const redirect = encodeURIComponent(to.fullPath || '/admin/dashboard')
    return `/admin/login?redirect=${redirect}`
  }
  if (to.meta.auth === 'admin') {
    const admin = getAdminInfo()
    if (!admin) {
      return '/admin/login'
    }
    const requiredPermission = to.meta.adminPermission
    if (requiredPermission && !adminHasPermission(requiredPermission)) {
      const fallback = firstAccessibleAdminRoute()
      return fallback === '/admin/login' ? '/admin/login' : fallback
    }
  }
  if (to.meta.auth === 'partner' && !getPartnerToken()) {
    const redirect = encodeURIComponent(to.fullPath || '/app/partner')
    return `/app/partner/login?redirect=${redirect}`
  }
  return true
})

export default router
