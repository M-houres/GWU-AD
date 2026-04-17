<template>
  <div class="admin-login">
    <section class="admin-login__card">
      <header class="admin-login__head">
        <p class="admin-login__eyebrow">管理后台</p>
        <h1 class="admin-login__title">管理员登录</h1>
      </header>

      <form class="admin-login__form" @submit.prevent="login">
        <label class="admin-login__field">
          <span>用户名</span>
          <input
            v-model.trim="username"
            autocomplete="username"
            placeholder="请输入管理员用户名"
          />
        </label>

        <label class="admin-login__field">
          <span>密码</span>
          <input
            v-model.trim="password"
            type="password"
            autocomplete="current-password"
            placeholder="请输入密码"
          />
        </label>

        <button class="admin-login__submit" :disabled="loading">
          {{ loading ? "登录中..." : "登录后台" }}
        </button>
      </form>

      <p v-if="errorText" class="admin-login__error">{{ errorText }}</p>
    </section>
  </div>
</template>

<script setup>
import { ref } from "vue"
import { useRoute, useRouter } from "vue-router"

import { adminHttp } from "../../lib/http"
import { resolveAdminRedirect } from "../../lib/redirect"
import { setAdminInfo, setAdminRefreshToken, setAdminToken } from "../../lib/session"

const router = useRouter()
const route = useRoute()

const username = ref("")
const password = ref("")
const loading = ref(false)
const errorText = ref("")

async function login() {
  errorText.value = ""
  loading.value = true
  try {
    const data = await adminHttp.post("/admin/auth/login", {
      username: username.value,
      password: password.value,
    })
    setAdminToken(data.token)
    setAdminRefreshToken(data.refresh_token)
    setAdminInfo(data.admin || null)
    router.push(resolveAdminRedirect(route.query.redirect, "/admin/dashboard"))
  } catch (error) {
    errorText.value = error.message || "登录失败"
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.admin-login {
  min-height: 100vh;
  min-height: 100svh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: #f3f6fb;
}

.admin-login__card {
  width: min(100%, 420px);
  border: 1px solid #dbe3ee;
  border-radius: 14px;
  background: #ffffff;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
  padding: 28px 24px;
}

.admin-login__head {
  margin-bottom: 20px;
}

.admin-login__eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  color: #475569;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.admin-login__title {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
  color: #0f172a;
}

.admin-login__form {
  display: grid;
  gap: 14px;
}

.admin-login__field {
  display: grid;
  gap: 8px;
}

.admin-login__field span {
  font-size: 13px;
  color: #334155;
  font-weight: 600;
}

.admin-login__field input {
  height: 42px;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
  color: #0f172a;
  background: #ffffff;
  transition: border-color 0.16s ease, box-shadow 0.16s ease;
}

.admin-login__field input:focus {
  outline: none;
  border-color: #2563eb;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.14);
}

.admin-login__submit {
  height: 42px;
  border: 1px solid #1d4ed8;
  border-radius: 10px;
  background: #2563eb;
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.16s ease, border-color 0.16s ease;
}

.admin-login__submit:hover:not(:disabled) {
  background: #1d4ed8;
  border-color: #1e40af;
}

.admin-login__submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.admin-login__error {
  margin: 12px 0 0;
  color: #b91c1c;
  font-size: 13px;
}

@media (max-width: 640px) {
  .admin-login {
    padding: 14px;
  }

  .admin-login__card {
    padding: 22px 16px;
  }
}
</style>
