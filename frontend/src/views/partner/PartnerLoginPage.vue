<template>
  <div class="partner-login">
    <section class="partner-login__shell">
      <article class="partner-login__intro">
        <p class="partner-login__eyebrow">渠道门户</p>
        <h1 class="partner-login__title">免密进入渠道后台</h1>
        <p class="partner-login__desc">渠道端统一通过专属门户链接进入，不再需要账号密码。</p>

        <div class="partner-login__tips">
          <div class="partner-login__tip-card">
            <strong>通常会收到</strong>
            <span>专属门户链接</span>
            <span>推广链接</span>
            <span>小程序路径</span>
          </div>
          <div class="partner-login__tip-card">
            <strong>进入后可做的事</strong>
            <span>查看收益和订单</span>
            <span>复制推广信息</span>
            <span>新建直属下级</span>
          </div>
        </div>
      </article>

      <section class="partner-login__card">
        <header class="partner-login__card-head">
          <h2>粘贴门户链接</h2>
          <span>粘贴平台发给你的专属门户链接，系统会自动完成进入。</span>
        </header>

        <form class="partner-login__form" @submit.prevent="submitEntry">
          <label class="partner-login__field">
            <span>粘贴专属门户链接</span>
            <textarea
              v-model.trim="portalLink"
              class="partner-login__textarea"
              placeholder="例如：https://xxx.com/app/partner/login-entry/xxxxx"
            />
          </label>

          <button class="partner-login__submit" :disabled="loading">
            {{ loading ? "进入中..." : "进入渠道后台" }}
          </button>
        </form>

        <p v-if="errorText" class="partner-login__error">{{ errorText }}</p>

        <div class="partner-login__helper">
          <span>如果没有门户链接，请让上级或平台重新发送。</span>
          <span>如果链接失效，请让上级或平台刷新后重新发送。</span>
        </div>
      </section>
    </section>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { partnerHttp } from "../../lib/http"
import { resolvePartnerRedirect } from "../../lib/redirect"
import { setPartnerInfo, setPartnerRefreshToken, setPartnerToken } from "../../lib/session"

const route = useRoute()
const router = useRouter()

const portalLink = ref("")
const loading = ref(false)
const errorText = ref("")

function extractPortalCredential(rawValue) {
  const raw = String(rawValue || "").trim()
  if (!raw) return null
  const candidates = [raw]
  if (raw.includes("?")) {
    candidates.push(raw.slice(raw.indexOf("?") + 1))
  }
  for (const item of candidates) {
    try {
      const url = new URL(item)
      const channelCode = String(url.searchParams.get("ch") || url.searchParams.get("channel_code") || "").trim()
      const portalToken = String(url.searchParams.get("pk") || url.searchParams.get("portal_token") || "").trim()
      if (channelCode && portalToken) {
        return { channelCode, portalToken }
      }
    } catch {}
    const params = new URLSearchParams(item.startsWith("?") ? item.slice(1) : item)
    const channelCode = String(params.get("ch") || params.get("channel_code") || "").trim()
    const portalToken = String(params.get("pk") || params.get("portal_token") || "").trim()
    if (channelCode && portalToken) {
      return { channelCode, portalToken }
    }
  }
  return null
}

async function exchangeByCredential({ channelCode, portalToken }) {
  loading.value = true
  errorText.value = ""
  try {
    const data = await partnerHttp.post("/partners/portal/auth/exchange", {
      channel_code: channelCode,
      portal_token: portalToken,
    })
    setPartnerToken(data.token)
    setPartnerRefreshToken(data.refresh_token)
    setPartnerInfo(data.channel || null)
    await router.replace(resolvePartnerRedirect(route.query.redirect, "/app/partner"))
  } catch (error) {
    errorText.value = error.message || "渠道登录失败"
  } finally {
    loading.value = false
  }
}

async function submitEntry() {
  const credential = extractPortalCredential(portalLink.value)
  if (!credential) {
    errorText.value = "请输入完整的专属门户链接"
    return
  }
  await exchangeByCredential(credential)
}
</script>

<style scoped>
.partner-login {
  min-height: 100vh;
  min-height: 100svh;
  padding: 24px;
  background:
    radial-gradient(circle at 14% 18%, rgba(22, 101, 216, 0.18), transparent 30%),
    radial-gradient(circle at 82% 20%, rgba(59, 130, 246, 0.18), transparent 26%),
    linear-gradient(180deg, #eef4ff 0%, #f8fbff 100%);
}

.partner-login__shell {
  width: min(1080px, 100%);
  margin: 0 auto;
  min-height: calc(100vh - 48px);
  min-height: calc(100svh - 48px);
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(360px, 0.95fr);
  gap: 18px;
  align-items: center;
}

.partner-login__intro,
.partner-login__card {
  border-radius: 24px;
  border: 1px solid #d8e3f5;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 24px 56px rgba(18, 52, 92, 0.12);
}

.partner-login__intro {
  padding: 30px;
}

.partner-login__eyebrow {
  margin: 0 0 10px;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.partner-login__title {
  margin: 0;
  color: #0f2747;
  font-size: 42px;
  line-height: 1.04;
}

.partner-login__desc {
  margin: 14px 0 0;
  color: #597090;
  font-size: 15px;
  line-height: 1.8;
}

.partner-login__tips {
  margin-top: 24px;
  display: grid;
  gap: 14px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.partner-login__tip-card {
  display: grid;
  gap: 8px;
  padding: 16px;
  border-radius: 18px;
  border: 1px solid #dbe6f5;
  background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
}

.partner-login__tip-card strong {
  color: #12345c;
  font-size: 15px;
}

.partner-login__tip-card span {
  color: #5c6f8d;
  font-size: 13px;
  line-height: 1.7;
}

.partner-login__card {
  padding: 28px 24px;
}

.partner-login__card-head {
  display: grid;
  gap: 6px;
  margin-bottom: 20px;
}

.partner-login__card-head h2 {
  margin: 0;
  color: #0f2747;
  font-size: 26px;
}

.partner-login__card-head span {
  color: #627490;
  font-size: 13px;
}

.partner-login__form {
  display: grid;
  gap: 14px;
}

.partner-login__field {
  display: grid;
  gap: 8px;
}

.partner-login__field span {
  color: #2d4c73;
  font-size: 13px;
  font-weight: 700;
}

.partner-login__textarea {
  min-height: 118px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid #c8d7ea;
  background: #fff;
  color: #12345c;
  font-size: 14px;
  line-height: 1.7;
  resize: vertical;
}

.partner-login__textarea:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.12);
}

.partner-login__submit {
  min-height: 48px;
  border: 0;
  border-radius: 14px;
  background: linear-gradient(135deg, #1457cc 0%, #0c73d6 100%);
  color: #fff;
  font-weight: 800;
  cursor: pointer;
}

.partner-login__submit:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.partner-login__error {
  margin: 14px 0 0;
  color: #b42318;
  font-size: 13px;
  line-height: 1.7;
}

.partner-login__helper {
  margin-top: 14px;
  display: grid;
  gap: 6px;
}

.partner-login__helper span {
  color: #607290;
  font-size: 12px;
  line-height: 1.7;
}

@media (max-width: 860px) {
  .partner-login {
    padding: 14px;
  }

  .partner-login__shell {
    min-height: auto;
    grid-template-columns: 1fr;
  }

  .partner-login__title {
    font-size: 34px;
  }

  .partner-login__tips {
    grid-template-columns: 1fr;
  }
}
</style>
