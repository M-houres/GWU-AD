<template>
  <AdminShell title="小程序配置" subtitle="小程序配置独立维护，保存后可直接用于微信开发者工具联调。">
    <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <section class="rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="mb-4 border-b border-[#e6ebef] pb-4">
          <div class="text-[11px] uppercase tracking-[0.16em] text-[#73808b]">Mini Program</div>
          <h3 class="mt-2 text-xl font-semibold text-[#1b2730]">微信小程序参数</h3>
          <p class="mt-2 text-sm leading-6 text-[#5b6771]">本页统一管理小程序登录、域名、支付和上线信息，不再和短信/登录配置混在一起。</p>
        </div>

        <p v-if="!canManage" class="rounded-xl border border-[#e7d4b1] bg-white px-3 py-2 text-sm text-[#7a5a2c]">
          当前账号仅有查看权限，无法保存小程序配置。
        </p>

        <fieldset class="space-y-5" :disabled="saving || !canManage">
          <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
            <div class="text-sm font-semibold text-[#1f2c35]">基础配置</div>
            <div class="mt-3 grid gap-3 md:grid-cols-2">
              <label class="inline-flex items-center gap-2 text-sm md:col-span-2">
                <input v-model="form.enabled" type="checkbox" />
                启用小程序配置
              </label>
              <label class="space-y-1 text-sm"><span>小程序 AppID</span><input v-model.trim="form.app_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>小程序 AppSecret</span><input v-model.trim="form.app_secret" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>小程序原始ID</span><input v-model.trim="form.original_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm">
                <span>发布环境</span>
                <select v-model="form.env_version" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2">
                  <option value="develop">develop</option>
                  <option value="trial">trial</option>
                  <option value="release">release</option>
                </select>
              </label>
            </div>
          </section>

          <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
            <div class="text-sm font-semibold text-[#1f2c35]">登录与支付</div>
            <div class="mt-3 grid gap-3 md:grid-cols-2">
              <label class="inline-flex items-center gap-2 text-sm md:col-span-2">
                <input v-model="form.wechat_miniprogram_login_enabled" type="checkbox" />
                启用小程序登录
              </label>
              <label class="space-y-1 text-sm"><span>登录 AppID</span><input v-model.trim="form.wechat_miniprogram_app_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="留空默认复用小程序 AppID" /></label>
              <label class="space-y-1 text-sm"><span>登录 AppSecret</span><input v-model.trim="form.wechat_miniprogram_app_secret" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="留空默认复用小程序 AppSecret" /></label>
              <label class="inline-flex items-center gap-2 text-sm md:col-span-2">
                <input v-model="form.wechat_miniprogram_payment_enabled" type="checkbox" />
                启用小程序支付
              </label>
              <label class="space-y-1 text-sm md:col-span-2"><span>支付回调地址</span><input v-model.trim="form.payment_notify_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://your-domain.example.com/api/v1/billing/notify/wechatpay" /></label>
            </div>
          </section>

          <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
            <div class="text-sm font-semibold text-[#1f2c35]">域名与后端</div>
            <div class="mt-3 grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm md:col-span-2"><span>后端 API 地址</span><input v-model.trim="form.api_base_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://api.example.com/api/v1" /></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>官网地址（可选）</span><input v-model.trim="form.web_base_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://www.example.com" /></label>
              <label class="space-y-1 text-sm"><span>request 域名</span><input v-model.trim="form.request_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://api.example.com" /></label>
              <label class="space-y-1 text-sm"><span>uploadFile 域名</span><input v-model.trim="form.upload_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>downloadFile 域名</span><input v-model.trim="form.download_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>WebSocket 域名</span><input v-model.trim="form.ws_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>业务域名</span><input v-model.trim="form.business_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://www.example.com" /></label>
            </div>
          </section>

          <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
            <div class="text-sm font-semibold text-[#1f2c35]">合规与发布信息</div>
            <div class="mt-3 grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>备案号</span><input v-model.trim="form.icp_filing_no" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>客服电话</span><input v-model.trim="form.contact_phone" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>联系邮箱</span><input v-model.trim="form.contact_email" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm md:col-span-2">
                <span>上线备注</span>
                <textarea v-model.trim="form.publish_note" rows="3" maxlength="500" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea>
              </label>
            </div>
          </section>
        </fieldset>

        <div class="mt-5 flex flex-wrap gap-2 border-t border-[#e6ebef] pt-4">
          <button class="rounded-xl px-4 py-2 text-sm" :disabled="saving || !canManage" @click="save">
            {{ saving ? "保存中..." : "保存小程序配置" }}
          </button>
          <button class="rounded-xl px-4 py-2 text-sm" @click="load">重新加载</button>
        </div>

        <p v-if="hintText" class="mt-3 text-sm text-[#0f6f54]">{{ hintText }}</p>
        <p v-if="errorText" class="mt-3 text-sm text-[#b24439]">{{ errorText }}</p>
      </section>

      <aside class="space-y-4">
        <article class="rounded-2xl border border-[#d9dee4] bg-white p-4">
          <div class="text-[11px] uppercase tracking-[0.16em] text-[#73808b]">部署检查</div>
          <div class="mt-3 space-y-2 text-sm">
            <div class="rounded-xl border border-[#e2e8ee] bg-white px-3 py-2">1. AppID / AppSecret：{{ checklist.app ? "已填写" : "未完成" }}</div>
            <div class="rounded-xl border border-[#e2e8ee] bg-white px-3 py-2">2. API/域名：{{ checklist.domain ? "已填写" : "未完成" }}</div>
            <div class="rounded-xl border border-[#e2e8ee] bg-white px-3 py-2">3. 登录链路：{{ checklist.login ? "已就绪" : "未就绪" }}</div>
            <div class="rounded-xl border border-[#e2e8ee] bg-white px-3 py-2">4. 支付链路：{{ checklist.payment ? "已就绪" : "按需配置" }}</div>
          </div>
        </article>
        <article class="rounded-2xl border border-[#d9dee4] bg-white p-4">
          <div class="text-[11px] uppercase tracking-[0.16em] text-[#73808b]">平台操作顺序</div>
          <ol class="mt-3 list-decimal space-y-2 pl-5 text-sm text-[#42515d]">
            <li>微信公众平台绑定小程序并确认主体资质。</li>
            <li>在“开发管理-开发设置”配置 request/upload/download/ws 合法域名。</li>
            <li>微信开发者工具导入 `miniapp/`，把 `config/env.js` 指向线上 API。</li>
            <li>联调登录、下单、支付回调和任务下载，再提交审核发布。</li>
          </ol>
        </article>
      </aside>
    </div>
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
  enabled: false,
  app_id: "",
  app_secret: "",
  original_id: "",
  env_version: "release",
  api_base_url: "",
  web_base_url: "",
  request_domain: "",
  upload_domain: "",
  download_domain: "",
  ws_domain: "",
  business_domain: "",
  icp_filing_no: "",
  contact_phone: "",
  contact_email: "",
  publish_note: "",
  wechat_miniprogram_login_enabled: false,
  wechat_miniprogram_app_id: "",
  wechat_miniprogram_app_secret: "",
  wechat_miniprogram_payment_enabled: false,
  payment_notify_url: "",
})

const checklist = computed(() => {
  const appReady = Boolean(String(form.value.app_id || "").trim() && String(form.value.app_secret || "").trim())
  const domainReady = Boolean(String(form.value.api_base_url || "").trim() && String(form.value.request_domain || "").trim())
  const loginReady = !form.value.wechat_miniprogram_login_enabled
    || Boolean(
      String(form.value.wechat_miniprogram_app_id || form.value.app_id || "").trim()
      && String(form.value.wechat_miniprogram_app_secret || form.value.app_secret || "").trim()
    )
  const paymentReady = !form.value.wechat_miniprogram_payment_enabled || Boolean(String(form.value.payment_notify_url || "").trim())
  return {
    app: appReady,
    domain: domainReady,
    login: loginReady,
    payment: paymentReady,
  }
})

onMounted(load)

async function load() {
  hintText.value = ""
  errorText.value = ""
  try {
    const data = await adminHttp.get("/admin/configs/miniapp")
    form.value = {
      ...form.value,
      ...(data.value || {}),
      enabled: data.value?.enabled === true,
      wechat_miniprogram_login_enabled: data.value?.wechat_miniprogram_login_enabled === true,
      wechat_miniprogram_payment_enabled: data.value?.wechat_miniprogram_payment_enabled === true,
      env_version: ["develop", "trial", "release"].includes(String(data.value?.env_version || "").toLowerCase())
        ? String(data.value.env_version).toLowerCase()
        : "release",
    }
  } catch (error) {
    errorText.value = error.message || "加载小程序配置失败"
  }
}

async function save() {
  if (!canManage.value) {
    errorText.value = "当前账号无配置管理权限"
    return
  }
  if (form.value.enabled && (!String(form.value.app_id || "").trim() || !String(form.value.app_secret || "").trim())) {
    errorText.value = "启用小程序配置时需填写 AppID 与 AppSecret"
    return
  }
  if (form.value.wechat_miniprogram_login_enabled) {
    const loginAppId = String(form.value.wechat_miniprogram_app_id || form.value.app_id || "").trim()
    const loginSecret = String(form.value.wechat_miniprogram_app_secret || form.value.app_secret || "").trim()
    if (!loginAppId || !loginSecret) {
      errorText.value = "启用小程序登录时需填写登录 AppID/AppSecret（可复用基础配置）"
      return
    }
  }
  saving.value = true
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post("/admin/configs/miniapp", {
      ...form.value,
      app_id: String(form.value.app_id || "").trim().slice(0, 128),
      app_secret: String(form.value.app_secret || "").trim().slice(0, 256),
      original_id: String(form.value.original_id || "").trim().slice(0, 128),
      api_base_url: String(form.value.api_base_url || "").trim().slice(0, 256),
      web_base_url: String(form.value.web_base_url || "").trim().slice(0, 256),
      request_domain: String(form.value.request_domain || "").trim().slice(0, 256),
      upload_domain: String(form.value.upload_domain || "").trim().slice(0, 256),
      download_domain: String(form.value.download_domain || "").trim().slice(0, 256),
      ws_domain: String(form.value.ws_domain || "").trim().slice(0, 256),
      business_domain: String(form.value.business_domain || "").trim().slice(0, 256),
      payment_notify_url: String(form.value.payment_notify_url || "").trim().slice(0, 256),
      icp_filing_no: String(form.value.icp_filing_no || "").trim().slice(0, 128),
      contact_phone: String(form.value.contact_phone || "").trim().slice(0, 32),
      contact_email: String(form.value.contact_email || "").trim().slice(0, 128),
      publish_note: String(form.value.publish_note || "").trim().slice(0, 500),
      env_version: String(form.value.env_version || "release").trim().toLowerCase(),
      enabled: form.value.enabled === true,
      wechat_miniprogram_login_enabled: form.value.wechat_miniprogram_login_enabled === true,
      wechat_miniprogram_payment_enabled: form.value.wechat_miniprogram_payment_enabled === true,
    })
    await load()
    hintText.value = "小程序配置已保存并生效。"
  } catch (error) {
    errorText.value = error.message || "保存失败"
  } finally {
    saving.value = false
  }
}
</script>

