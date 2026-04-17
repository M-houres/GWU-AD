<template>
  <AdminShell title="配置中心" subtitle="运营填写后即可生效，支持审计与就绪检查">
    <div class="admin-config-layout">
      <section class="admin-config-sidebar rounded-2xl border border-[#d9dee4] bg-white p-4">
        <div class="text-[11px] uppercase tracking-[0.18em] text-[#73808b]">配置导航</div>
        <div class="admin-config-tabs mt-3 space-y-2">
          <button
            v-for="tab in tabs"
            :key="tab.key"
            class="admin-config-tab-btn w-full rounded-2xl border px-3 py-3 text-left transition"
            :class="[activeTab === tab.key ? 'border-[#0f7a5f] bg-[linear-gradient(150deg,#edf7f3,#f8fcfb)]' : 'border-[#d6dee6] bg-white hover:border-[#9ab8ac]', { 'is-active': activeTab === tab.key }]"
            @click="activeTab = tab.key"
          >
            <div class="flex items-start justify-between gap-2">
              <div>
                <div class="text-sm font-semibold text-[#1f2c35]">{{ tab.label }}</div>
                <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ tab.desc }}</div>
              </div>
              <span class="rounded-full px-2 py-1 text-[11px]" :class="chipClass(readinessMap[tab.key]?.status)">
                {{ readinessLabel(readinessMap[tab.key]?.status) }}
              </span>
            </div>
          </button>
        </div>
      </section>

      <section class="admin-config-main rounded-2xl border border-[#d9dee4] bg-white p-5">
        <div class="border-b border-[#e6ebef] pb-4">
          <div class="text-[11px] uppercase tracking-[0.18em] text-[#73808b]">{{ currentGuide.code }}</div>
          <h3 class="mt-2 text-xl font-semibold text-[#18242b]">{{ currentTab.label }}</h3>
          <p class="mt-2 text-sm leading-6 text-[#5b6771]">{{ currentGuide.lead }}</p>
          <p
            v-if="readinessMap[activeTab]?.message"
            class="mt-3 rounded-xl border border-[#dce4eb] bg-white px-3 py-2 text-sm text-[#415160]"
          >
            当前状态：{{ readinessMap[activeTab]?.message }}
          </p>
        </div>
        <p
          v-if="!canManageConfigs"
          class="mt-4 rounded-xl border border-[#f0debf] bg-[#fff8ea] px-3 py-2 text-sm text-[#7c5a2e]"
        >
          当前账号仅有查看权限。若需修改配置，请由超级管理员授予“配置管理”权限。
        </p>

        <fieldset class="mt-5 space-y-4" :disabled="!canManageConfigs || saving">
          <template v-if="activeTab === 'llm'">
            <label class="inline-flex items-center gap-2 text-sm"><input v-model="forms.llm.enabled" type="checkbox" /> 启用大模型增强</label>
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <button
                v-for="item in llmProviders"
                :key="item.value"
                type="button"
                class="rounded-2xl border px-3 py-3 text-left text-sm transition"
                :class="[forms.llm.provider === item.value ? 'border-[#0f7a5f] bg-[linear-gradient(150deg,#edf7f3,#f8fcfb)]' : 'border-[#d6dee6] bg-white hover:border-[#9ab8ac]', { 'is-active': forms.llm.provider === item.value }]"
                @click="pickLlm(item.value)"
              >
                <div class="font-semibold text-[#21303a]">{{ item.label }}</div>
                <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ item.desc }}</div>
              </button>
            </div>
            <div class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>模型名</span><input v-model="forms.llm.model" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>Base URL</span><input v-model="forms.llm.base_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>API Key</span><input v-model="forms.llm.api_key" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>超时（秒）</span><input v-model.number="forms.llm.timeout_seconds" type="number" min="5" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>重试次数</span><input v-model.number="forms.llm.retry_attempts" type="number" min="1" max="5" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>退避基线（秒）</span><input v-model.number="forms.llm.retry_backoff_seconds" type="number" min="0.1" max="5" step="0.1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>最大输出 Tokens</span><input v-model.number="forms.llm.max_output_tokens" type="number" min="128" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>温度</span><input v-model.number="forms.llm.temperature" type="number" min="0" max="2" step="0.1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
            </div>
          </template>

          <template v-else-if="activeTab === 'payment'">
            <label class="inline-flex items-center gap-2 text-sm"><input v-model="forms.payment.test_mode" type="checkbox" /> 联调模式（测试）</label>
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
              <button
                v-for="item in paymentProviders"
                :key="item.value"
                type="button"
                class="rounded-2xl border px-3 py-3 text-left text-sm transition"
                :class="[forms.payment.provider === item.value ? 'border-[#0f7a5f] bg-[linear-gradient(150deg,#edf7f3,#f8fcfb)]' : 'border-[#d6dee6] bg-white hover:border-[#9ab8ac]', { 'is-active': forms.payment.provider === item.value }]"
                @click="forms.payment.provider = item.value"
              >
                <div class="font-semibold text-[#21303a]">{{ item.label }}</div>
                <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ item.desc }}</div>
              </button>
            </div>
            <p
              v-if="paymentProviderUnsupported"
              class="rounded-xl border border-[#f0d5cf] bg-[#fff6f3] px-3 py-2 text-sm text-[#9a4a3b]"
            >
              当前支付通道配置已过时，请切换为微信支付、支付宝或 Mock 联调。
            </p>
            <div v-if="isWechatPay" class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>AppID</span><input v-model="forms.payment.app_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>商户号</span><input v-model="forms.payment.merchant_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>商户证书序列号</span><input v-model="forms.payment.merchant_serial_no" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>APIv3 Key</span><input v-model="forms.payment.api_v3_key" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>公网回调地址或域名</span><input v-model="forms.payment.notify_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://your.domain" /></label>
              <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-2 text-xs leading-5 text-[#4f5d69] md:col-span-2">
                实际微信回调地址：{{ paymentNotifyPreview }}
              </div>
              <label class="space-y-1 text-sm md:col-span-2"><span>商户私钥 PEM</span><textarea v-model="forms.payment.merchant_private_key_pem" rows="4" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea></label>
              <label class="space-y-1 text-sm"><span>微信支付公钥 ID</span><input v-model="forms.payment.wechatpay_public_key_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>微信支付公钥</span><textarea v-model="forms.payment.wechatpay_public_key" rows="4" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea></label>
            </div>
            <div v-else-if="isAlipay" class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>支付宝 AppID</span><input v-model="forms.payment.app_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>支付宝网关</span><input v-model="forms.payment.gateway_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://openapi.alipay.com/gateway.do" /></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>公网回调地址或域名</span><input v-model="forms.payment.notify_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://your.domain" /></label>
              <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-2 text-xs leading-5 text-[#4f5d69] md:col-span-2">
                实际支付宝回调地址：{{ paymentNotifyPreview }}
              </div>
              <label class="space-y-1 text-sm md:col-span-2"><span>应用私钥 PEM</span><textarea v-model="forms.payment.app_private_key_pem" rows="4" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>支付宝公钥 PEM</span><textarea v-model="forms.payment.alipay_public_key" rows="4" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea></label>
            </div>
          </template>

          <template v-else-if="activeTab === 'billing'">
            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">任务计费（按字符）</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">计费口径：任务实际扣费 = 字符数 × 单价。AIGC 检测每天前 6 篇免费，超出后按单价计费。建议按典型字数（1k/5k/8k）先做换算。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-3">
                <label class="space-y-1 text-sm"><span>AIGC 单价</span><input v-model.number="forms.billing.aigc_rate" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
                <label class="space-y-1 text-sm"><span>降重单价</span><input v-model.number="forms.billing.dedup_rate" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
                <label class="space-y-1 text-sm"><span>降AIGC率单价</span><input v-model.number="forms.billing.rewrite_rate" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              </div>
            </section>

            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div class="text-sm font-semibold text-[#1f2c35]">充值套餐（前台展示）</div>
                  <div class="mt-1 text-xs leading-5 text-[#5f6d79]">运营只需要在这里配置套餐名称、价格、积分和简介，前台购买页会自动同步。</div>
                </div>
                <button class="rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250]" @click="addBillingPackage">
                  新增套餐
                </button>
              </div>
              <div class="mt-3 space-y-3">
                <article
                  v-for="(pkg, idx) in forms.billing.packages"
                  :key="`pkg-${idx}`"
                  class="rounded-2xl border border-[#d6dfe7] bg-white p-3"
                >
                  <div class="grid gap-3 md:grid-cols-6">
                    <label class="space-y-1 text-sm md:col-span-2">
                      <span>套餐名称</span>
                      <input v-model.trim="pkg.name" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="例如：标准包" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>价格（元）</span>
                      <input v-model.number="pkg.price" type="number" min="0.01" step="0.01" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>积分</span>
                      <input v-model.number="pkg.credits" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>标签（可选）</span>
                      <input v-model.trim="pkg.badge" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="新手推荐" />
                    </label>
                    <div class="flex items-end justify-end">
                      <button
                        class="rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250] disabled:opacity-50"
                        :disabled="forms.billing.packages.length <= 1"
                        @click="removeBillingPackage(idx)"
                      >
                        删除
                      </button>
                    </div>
                    <label class="space-y-1 text-sm md:col-span-5">
                      <span>套餐介绍</span>
                      <input v-model.trim="pkg.description" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="给普通运营人员看的简介，前台会展示" />
                    </label>
                    <label class="inline-flex items-center gap-2 text-sm md:col-span-1">
                      <input v-model="pkg.enabled" type="checkbox" />
                      前台启用
                    </label>
                  </div>
                </article>
              </div>
            </section>
          </template>

          <template v-else-if="activeTab === 'login'">
            <div class="grid gap-3 md:grid-cols-4">
              <button
                v-for="item in smsProviders"
                :key="item.value"
                type="button"
                class="rounded-2xl border px-3 py-3 text-left text-sm transition"
                :class="[forms.login.sms_provider === item.value ? 'border-[#0f7a5f] bg-[linear-gradient(150deg,#edf7f3,#f8fcfb)]' : 'border-[#d6dee6] bg-white hover:border-[#9ab8ac]', { 'is-active': forms.login.sms_provider === item.value }]"
                @click="forms.login.sms_provider = item.value"
              >
                <div class="font-semibold text-[#21303a]">{{ item.label }}</div>
                <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ item.desc }}</div>
              </button>
            </div>
            <label class="inline-flex items-center gap-2 text-sm"><input v-model="forms.login.debug_code_enabled" type="checkbox" /> 开发环境返回 debug_code</label>
            <div v-if="forms.login.sms_provider === 'custom_webhook'" class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>短信网关 URL</span><input v-model="forms.login.sms_gateway_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://your-sms-gateway.example.com/send" /></label>
              <label class="space-y-1 text-sm"><span>短信网关 API Key（可选）</span><input v-model="forms.login.sms_api_key" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>短信模板 ID / Code</span><input v-model="forms.login.sms_template_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>短信签名</span><input v-model="forms.login.sms_sign_name" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
            </div>
            <div v-else-if="forms.login.sms_provider === 'tencent_sms'" class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>SmsSdkAppId</span><input v-model="forms.login.sms_sdk_app_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>腾讯云 Region</span><input v-model="forms.login.sms_region" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="ap-guangzhou" /></label>
              <label class="space-y-1 text-sm"><span>短信模板 ID</span><input v-model="forms.login.sms_template_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>短信签名</span><input v-model="forms.login.sms_sign_name" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>SecretId</span><input v-model="forms.login.sms_access_key_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>SecretKey</span><input v-model="forms.login.sms_access_key_secret" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
            </div>
            <div v-else-if="forms.login.sms_provider === 'aliyun_sms'" class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>阿里云 RegionId</span><input v-model="forms.login.sms_aliyun_region_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="cn-hangzhou" /></label>
              <label class="space-y-1 text-sm"><span>短信模板 CODE</span><input v-model="forms.login.sms_template_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>短信签名</span><input v-model="forms.login.sms_sign_name" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>AccessKeyId</span><input v-model="forms.login.sms_access_key_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>AccessKeySecret</span><input v-model="forms.login.sms_access_key_secret" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
            </div>
            <div v-else class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm text-[#4f5d69]">
              SMS login is disabled. Enable WeChat login or debug_code to keep at least one login path.
            </div>
            <label class="inline-flex items-center gap-2 text-sm"><input v-model="forms.login.wechat_login_enabled" type="checkbox" /> 启用微信扫码登录</label>
            <div v-if="forms.login.wechat_login_enabled" class="grid gap-3 md:grid-cols-2">
              <label class="space-y-1 text-sm"><span>微信 AppID</span><input v-model="forms.login.wechat_app_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm"><span>微信 AppSecret</span><input v-model="forms.login.wechat_app_secret" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              <label class="space-y-1 text-sm md:col-span-2"><span>微信回调地址</span><input v-model="forms.login.wechat_redirect_uri" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
            </div>
            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">新用户与风控参数</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">保存后立即生效，用于控制注册赠送积分和登录风控阈值。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <label class="space-y-1 text-sm">
                  <span>新用户初始积分</span>
                  <input v-model.number="forms.login.new_user_initial_credits" type="number" min="0" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>验证码最大重试次数</span>
                  <input v-model.number="forms.login.max_code_retry" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>手机号锁定分钟数</span>
                  <input v-model.number="forms.login.phone_lock_minutes" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>发送验证码 IP 限流（1小时）</span>
                  <input v-model.number="forms.login.send_code_ip_1h_limit" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm md:col-span-2">
                  <span>登录请求 IP 限流（10分钟）</span>
                  <input v-model.number="forms.login.login_ip_10m_limit" type="number" min="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
              </div>
            </section>
          </template>

          <template v-else-if="activeTab === 'miniapp'">
            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">基础配置</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <label class="inline-flex items-center gap-2 text-sm md:col-span-2">
                  <input v-model="forms.miniapp.enabled" type="checkbox" />
                  启用小程序配置
                </label>
                <label class="space-y-1 text-sm">
                  <span>小程序 AppID</span>
                  <input v-model.trim="forms.miniapp.app_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>小程序 AppSecret</span>
                  <input v-model.trim="forms.miniapp.app_secret" type="password" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>原始 ID</span>
                  <input v-model.trim="forms.miniapp.original_id" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>环境版本</span>
                  <select v-model="forms.miniapp.env_version" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2">
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
                  <input v-model="forms.miniapp.wechat_miniprogram_login_enabled" type="checkbox" />
                  启用小程序登录
                </label>
                <label class="space-y-1 text-sm">
                  <span>登录 AppID</span>
                  <input
                    v-model.trim="forms.miniapp.wechat_miniprogram_app_id"
                    class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"
                    placeholder="留空默认复用小程序 AppID"
                  />
                </label>
                <label class="space-y-1 text-sm">
                  <span>登录 AppSecret</span>
                  <input
                    v-model.trim="forms.miniapp.wechat_miniprogram_app_secret"
                    type="password"
                    class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"
                    placeholder="留空默认复用小程序 AppSecret"
                  />
                </label>
                <label class="inline-flex items-center gap-2 text-sm md:col-span-2">
                  <input v-model="forms.miniapp.wechat_miniprogram_payment_enabled" type="checkbox" />
                  启用小程序支付
                </label>
                <label class="space-y-1 text-sm md:col-span-2">
                  <span>支付回调地址</span>
                  <input
                    v-model.trim="forms.miniapp.payment_notify_url"
                    class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"
                    placeholder="https://your-domain.example.com/api/v1/billing/notify/wechatpay"
                  />
                </label>
              </div>
            </section>

            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">域名与后端</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <label class="space-y-1 text-sm md:col-span-2">
                  <span>后端 API 地址</span>
                  <input v-model.trim="forms.miniapp.api_base_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://api.example.com/api/v1" />
                </label>
                <label class="space-y-1 text-sm md:col-span-2">
                  <span>官网地址（可选）</span>
                  <input v-model.trim="forms.miniapp.web_base_url" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://www.example.com" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>request 域名</span>
                  <input v-model.trim="forms.miniapp.request_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://api.example.com" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>uploadFile 域名</span>
                  <input v-model.trim="forms.miniapp.upload_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>downloadFile 域名</span>
                  <input v-model.trim="forms.miniapp.download_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>WebSocket 域名</span>
                  <input v-model.trim="forms.miniapp.ws_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm md:col-span-2">
                  <span>业务域名</span>
                  <input v-model.trim="forms.miniapp.business_domain" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" placeholder="https://www.example.com" />
                </label>
              </div>
            </section>

            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">合规与发布信息</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <label class="space-y-1 text-sm">
                  <span>备案号</span>
                  <input v-model.trim="forms.miniapp.icp_filing_no" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm">
                  <span>客服电话</span>
                  <input v-model.trim="forms.miniapp.contact_phone" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm md:col-span-2">
                  <span>联系邮箱</span>
                  <input v-model.trim="forms.miniapp.contact_email" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                </label>
                <label class="space-y-1 text-sm md:col-span-2">
                  <span>上线备注</span>
                  <textarea v-model.trim="forms.miniapp.publish_note" rows="3" maxlength="500" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"></textarea>
                </label>
              </div>
            </section>
          </template>

          <template v-else-if="activeTab === 'user_navigation'">
            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">左侧导航编排</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">控制前台左侧功能顺序与显示状态。个人中心已从左侧移除，保留顶部入口。</div>
              <div class="mt-3 space-y-3">
                <article
                  v-for="(item, index) in forms.user_navigation.items"
                  :key="item.key"
                  class="rounded-2xl border border-[#d6dfe7] bg-[#fbfcfd] p-4"
                >
                  <div class="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <div class="text-sm font-semibold text-[#21303a]">{{ index + 1 }}. {{ item.label }}</div>
                      <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ navGroupLabel(item.group) }} · {{ item.path }}</div>
                      <div v-if="item.badge || item.disabled" class="mt-2 inline-flex rounded-full bg-[#eef2f5] px-2 py-1 text-[11px] text-[#4e5b67]">
                        {{ item.badge || "受限功能" }}
                      </div>
                    </div>
                    <div class="flex flex-wrap items-center gap-2">
                      <label class="inline-flex items-center gap-2 rounded-xl border border-[#d6dee6] bg-white px-3 py-2 text-sm text-[#30404d]">
                        <input v-model="item.visible" type="checkbox" />
                        前台显示
                      </label>
                      <button
                        type="button"
                        class="rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250] disabled:opacity-50"
                        :disabled="index === 0"
                        @click="moveUserNavItem(index, -1)"
                      >
                        上移
                      </button>
                      <button
                        type="button"
                        class="rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250] disabled:opacity-50"
                        :disabled="index === forms.user_navigation.items.length - 1"
                        @click="moveUserNavItem(index, 1)"
                      >
                        下移
                      </button>
                    </div>
                  </div>
                </article>
              </div>
            </section>
            <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm leading-6 text-[#4f5d69]">
              “格物学术”品牌位于左侧导航顶部，固定展示，不参与功能隐藏。
            </div>
          </template>
        </fieldset>

        <div class="mt-5 flex flex-wrap gap-2 border-t border-[#e6ebef] pt-4">
          <button
            class="rounded-xl bg-[#0f7a5f] px-4 py-2 text-sm text-white disabled:opacity-60"
            :disabled="saving || !canManageConfigs"
            @click="saveCurrent"
          >
            {{ canManageConfigs ? (saving ? "保存中..." : `保存${currentTab.label}`) : "仅查看" }}
          </button>
          <button class="rounded-xl bg-[#edf2f6] px-4 py-2 text-sm text-[#344250]" @click="reloadCurrent">重新加载</button>
        </div>
        <p v-if="hintText" class="mt-3 text-sm text-[#106c4f]">{{ hintText }}</p>
        <p v-if="errorText" class="mt-3 text-sm text-[#af3f33]">{{ errorText }}</p>
      </section>

      <section class="admin-config-guide space-y-4">
        <article class="rounded-2xl border border-[#d9dee4] bg-white p-4">
          <div class="text-[11px] uppercase tracking-[0.18em] text-[#73808b]">使用说明</div>
          <h4 class="mt-2 text-sm font-semibold text-[#1b2730]">{{ currentGuide.title }}</h4>
          <p class="mt-3 text-sm leading-6 text-[#596671]">{{ currentGuide.desc }}</p>
          <div class="mt-4 space-y-2">
            <div v-for="item in currentGuide.checklist" :key="item" class="rounded-xl border border-[#e3e8ed] bg-[#fbfcfd] px-3 py-2 text-sm leading-6 text-[#384853]">{{ item }}</div>
          </div>
        </article>
        <article class="rounded-2xl border border-[#d9dee4] bg-white p-4">
          <div class="text-[11px] uppercase tracking-[0.18em] text-[#73808b]">官方文档</div>
          <div class="mt-3 space-y-2">
            <a v-for="doc in currentGuide.docs" :key="doc.href" :href="doc.href" target="_blank" rel="noreferrer" class="block rounded-xl border border-[#e3e8ed] bg-[#fbfcfd] px-3 py-2 text-sm text-[#125f4b] underline underline-offset-4">{{ doc.label }}</a>
          </div>
        </article>
      </section>
    </div>
  </AdminShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import AdminShell from "../../components/AdminShell.vue"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"
import { normalizeUserNavigationConfig, USER_NAV_GROUP_LABELS } from "../../lib/userNavigation"

const tabs = [
  { key: "login", label: "登录配置", desc: "短信与微信登录" },
  { key: "payment", label: "支付配置", desc: "微信支付 / 支付宝" },
  { key: "billing", label: "计费规则", desc: "按字符扣费" },
  { key: "user_navigation", label: "前台导航", desc: "左侧功能编排" },
  { key: "llm", label: "大模型配置", desc: "国内外主流模型" },
  { key: "miniapp", label: "小程序配置", desc: "参数与域名" },
]

const llmProviders = [
  { value: "openai", label: "OpenAI", desc: "官方接口" },
  { value: "anthropic", label: "Anthropic", desc: "Claude Messages" },
  { value: "gemini", label: "Gemini", desc: "Google generateContent" },
  { value: "deepseek", label: "DeepSeek", desc: "官方兼容接口" },
  { value: "qwen", label: "通义千问", desc: "百炼兼容模式" },
  { value: "doubao", label: "豆包 / 方舟", desc: "Ark 兼容模式" },
  { value: "moonshot", label: "Kimi", desc: "Moonshot 官方接口" },
  { value: "zhipu", label: "智谱 GLM", desc: "智谱兼容接口" },
  { value: "custom_openai", label: "自定义兼容", desc: "手填 OpenAI 兼容网关" },
]

const llmPresets = {
  openai: { base_url: "https://api.openai.com/v1", model: "gpt-4o-mini" },
  anthropic: { base_url: "https://api.anthropic.com/v1", model: "claude-3-5-sonnet-latest" },
  gemini: { base_url: "https://generativelanguage.googleapis.com/v1beta", model: "gemini-2.0-flash" },
  deepseek: { base_url: "https://api.deepseek.com", model: "deepseek-chat" },
  qwen: { base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1", model: "qwen-plus" },
  doubao: { base_url: "https://ark.cn-beijing.volces.com/api/v3", model: "" },
  moonshot: { base_url: "https://api.moonshot.cn/v1", model: "moonshot-v1-8k" },
  zhipu: { base_url: "https://open.bigmodel.cn/api/paas/v4", model: "glm-4-flash" },
  custom_openai: { base_url: "", model: "" },
}

const paymentProviders = [
  { value: "wechatpay_v3", label: "微信支付 V3", desc: "官方 Native 收款" },
  { value: "alipay", label: "支付宝", desc: "官方预创建二维码" },
  { value: "mock", label: "Mock 联调", desc: "仅开发联调" },
]

const smsProviders = [
  { value: "custom_webhook", label: "自建短信", desc: "自有短信网关" },
  { value: "tencent_sms", label: "腾讯云短信", desc: "官方 API" },
  { value: "aliyun_sms", label: "阿里云短信", desc: "官方 API" },
  { value: "disabled", label: "关闭短信", desc: "仅微信或 debug" },
]

const defaultBillingPackages = [
  {
    name: "入门包",
    price: 9.9,
    credits: 10000,
    description: "适合单篇检测与初稿优化，低门槛启动。",
    badge: "新手推荐",
    enabled: true,
  },
  {
    name: "标准包",
    price: 39,
    credits: 50000,
    description: "适合毕业季高频使用，兼顾成本和处理量。",
    badge: "运营主推",
    enabled: true,
  },
  {
    name: "专业包",
    price: 128,
    credits: 200000,
    description: "适合团队批量处理，单位成本更优。",
    badge: "高性价比",
    enabled: true,
  },
  {
    name: "年费包",
    price: 388,
    credits: 1000000,
    description: "适合长期运营或机构使用，大额度稳定供给。",
    badge: "长期使用",
    enabled: true,
  },
]

const defaultMiniappConfig = {
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
}

const guideMap = {
  login: {
    code: "Access Setup",
    lead: "至少保证短信、微信扫码、debug_code 中一种可用。",
    title: "先打通登录链路",
    desc: "保存后前台登录页会立即按最新配置切换。",
    checklist: [
      "生产环境建议至少保留 1 个正式登录方式。",
      "微信扫码登录回调必须是公网 HTTPS。",
    ],
    docs: [
      { label: "微信开放平台 网站应用登录", href: "https://developers.weixin.qq.com/doc/oplatform/Website_App/WeChat_Login/Wechat_Login.html" },
      { label: "微信小程序 wx.login", href: "https://developers.weixin.qq.com/miniprogram/dev/api/open-api/login/wx.login.html" },
      { label: "腾讯云短信 SendSms", href: "https://cloud.tencent.com/document/product/382/55981" },
      { label: "阿里云短信 SendSms", href: "https://help.aliyun.com/zh/sms/developer-reference/api-dysmsapi-2017-05-25-sendsms" },
    ],
  },
  payment: {
    code: "Revenue Setup",
    lead: "关闭联调模式后才会走真实支付。正式支付必须依赖公网回调。",
    title: "真实收款必须可回调",
    desc: "本地前后端联调不等于真实收款，正式支付需要公网 HTTPS 域名。",
    checklist: [
      "微信支付需要商户号、商户私钥、APIv3 Key。",
      "支付宝需要应用私钥、支付宝公钥、AppID。",
    ],
    docs: [
      { label: "微信支付 Native 下单", href: "https://pay.wechatpay.cn/doc/v3/merchant/4012791898" },
      { label: "微信支付 回调通知", href: "https://pay.wechatpay.cn/doc/v3/merchant/4012071382" },
      { label: "支付宝预创建订单", href: "https://opendocs.alipay.com/apis/api_1/alipay.trade.precreate" },
      { label: "支付宝开放平台", href: "https://opendocs.alipay.com/open/00f0fa" },
    ],
  },
  billing: {
    code: "Pricing Setup",
    lead: "同时配置任务单价和充值套餐，前台会自动同步。",
    title: "定价直接影响转化",
    desc: "任务按字符计费，套餐按价格兑积分。运营填完即可上线生效。",
    checklist: [
      "三类单价必须都大于 0。",
      "至少启用 1 个套餐，并补充用户易懂的套餐介绍。",
    ],
    docs: [
      { label: "微信支付 开发文档", href: "https://pay.wechatpay.cn/doc/v3/merchant/4012791898" },
      { label: "支付宝 开发文档", href: "https://opendocs.alipay.com/apis/api_1/alipay.trade.precreate" },
    ],
  },
  user_navigation: {
    code: "Frontend Navigation",
    lead: "在后台直接控制左侧功能顺序与是否展示，前台刷新后立即生效。",
    title: "前台导航统一编排",
    desc: "这里只控制左侧导航展示，不会删除页面路由。个人中心入口已固定从顶部进入。",
    checklist: [
      "至少保留 1 个前台功能可见，避免用户进入后无导航可用。",
      "“开发中”功能可以保留展示，也可以直接隐藏。",
    ],
    docs: [],
  },
  llm: {
    code: "Model Setup",
    lead: "支持 OpenAI、Anthropic、Gemini、DeepSeek、Qwen、豆包、Kimi、智谱和自定义兼容接口。",
    title: "先选提供商，再填模型与密钥",
    desc: "保存后新任务直接按这里的模型参数调用。",
    checklist: [
      "Base URL 建议保持默认，除非你明确在用代理。",
      "模型名必须和所购通道一致。",
    ],
    docs: [
      { label: "OpenAI API", href: "https://platform.openai.com/docs/api-reference" },
      { label: "Anthropic Messages API", href: "https://docs.anthropic.com/en/api/messages-examples" },
      { label: "Google Gemini API", href: "https://ai.google.dev/gemini-api/docs/text-generation" },
      { label: "DeepSeek API", href: "https://api-docs.deepseek.com/api/create-chat-completion" },
      { label: "阿里云百炼 OpenAI 兼容", href: "https://help.aliyun.com/zh/model-studio/openai-compatible-api" },
      { label: "火山引擎 Ark OpenAI 兼容", href: "https://www.volcengine.com/docs/82379/1298454" },
      { label: "智谱 OpenAI SDK 兼容", href: "https://bigmodel.cn/dev/howuse/model" },
      { label: "Moonshot API", href: "https://platform.moonshot.cn/docs/api-reference" },
    ],
  },
  miniapp: {
    code: "Mini Program Setup",
    lead: "在配置中心统一维护小程序 AppID、域名白名单和登录支付开关。",
    title: "小程序参数集中配置",
    desc: "保存后后端会直接使用该配置，便于 Web 与小程序共用同一套服务。",
    checklist: [
      "至少填写小程序 AppID 与 AppSecret。",
      "request/upload/download/ws 域名需与微信后台一致。",
      "启用小程序支付时需配置支付回调地址。",
    ],
    docs: [
      { label: "微信小程序 开发文档", href: "https://developers.weixin.qq.com/miniprogram/dev/framework/" },
      { label: "微信小程序 合法域名配置", href: "https://developers.weixin.qq.com/miniprogram/dev/devtools/projectconfig.html" },
      { label: "微信小程序 登录时序", href: "https://developers.weixin.qq.com/miniprogram/dev/framework/open-ability/login.html" },
    ],
  },
}

const activeTab = ref("login")
const route = useRoute()
const router = useRouter()
const forms = ref({
  llm: {
    enabled: false,
    provider: "openai",
    base_url: "",
    model: "",
    api_key: "",
    timeout_seconds: 25,
    retry_attempts: 3,
    retry_backoff_seconds: 0.8,
    max_output_tokens: 2048,
    temperature: 0.3,
  },
  payment: { provider: "wechatpay_v3", test_mode: true, notify_url: "" },
  billing: { aigc_rate: 1, dedup_rate: 2, rewrite_rate: 2, packages: cloneBillingPackages() },
  login: {
    sms_provider: "custom_webhook",
    sms_api_key: "",
    sms_gateway_url: "",
    sms_template_id: "",
    sms_sign_name: "",
    sms_sdk_app_id: "",
    sms_region: "ap-guangzhou",
    sms_aliyun_region_id: "cn-hangzhou",
    sms_access_key_id: "",
    sms_access_key_secret: "",
    debug_code_enabled: false,
    wechat_login_enabled: false,
    wechat_app_id: "",
    wechat_app_secret: "",
    wechat_redirect_uri: "",
    new_user_initial_credits: 5000,
    max_code_retry: 3,
    phone_lock_minutes: 5,
    send_code_ip_1h_limit: 30,
    login_ip_10m_limit: 120,
  },
  user_navigation: normalizeUserNavigationConfig(),
  miniapp: normalizeMiniappConfig(defaultMiniappConfig),
})

const readinessMap = ref({})
const hintText = ref("")
const errorText = ref("")
const saving = ref(false)

const currentTab = computed(() => tabs.find((tab) => tab.key === activeTab.value) || tabs[0])
const currentGuide = computed(() => guideMap[activeTab.value] || guideMap.login)
const isWechatPay = computed(() => ["wechat", "wechatpay_v3"].includes(forms.value.payment.provider))
const isAlipay = computed(() => forms.value.payment.provider === "alipay")
const canManageConfigs = computed(() => adminHasPermission("configs:manage"))
const paymentProviderUnsupported = computed(() => {
  const provider = String(forms.value.payment.provider || "")
  return Boolean(provider) && !paymentProviders.some((item) => item.value === provider)
})
const paymentNotifyPreview = computed(() => resolvePaymentNotifyPreview())

onMounted(async () => {
  const tabFromQuery = String(route.query.tab || "").trim()
  if (tabFromQuery && tabs.some((tab) => tab.key === tabFromQuery)) {
    activeTab.value = tabFromQuery
  }
  await Promise.all([loadAll(), loadReadiness()])
})

watch(
  () => route.query.tab,
  (value) => {
    const tab = String(value || "").trim()
    if (tab && tabs.some((item) => item.key === tab)) {
      activeTab.value = tab
    }
  }
)

watch(activeTab, async (tab) => {
  const current = String(route.query.tab || "")
  if (tab === current) return
  const query = tab === "login" ? { ...route.query, tab: undefined } : { ...route.query, tab }
  await router.replace({ path: "/admin/configs", query })
})

function chipClass(status) {
  if (status === "ready") return "bg-[#e8f5ef] text-[#106c4f]"
  if (status === "error") return "bg-[#fff0ee] text-[#b24439]"
  return "bg-[#eef2f5] text-[#5e6c78]"
}

function readinessLabel(status) {
  if (status === "ready") return "已就绪"
  if (status === "error") return "需补齐"
  return "待确认"
}

async function loadAll() {
  await Promise.all(tabs.map((tab) => loadTab(tab.key)))
}

async function loadTab(category) {
  const data = await adminHttp.get(`/admin/configs/${category}`)
  forms.value[category] = data.value || {}
  if (category === "billing") {
    forms.value.billing = normalizeBillingForm(forms.value.billing)
  }
  if (category === "login") {
    forms.value.login.sms_region = forms.value.login.sms_region || "ap-guangzhou"
    forms.value.login.sms_aliyun_region_id = forms.value.login.sms_aliyun_region_id || "cn-hangzhou"
    forms.value.login.new_user_initial_credits = Number(forms.value.login.new_user_initial_credits ?? 5000)
    forms.value.login.max_code_retry = Number(forms.value.login.max_code_retry ?? 3)
    forms.value.login.phone_lock_minutes = Number(forms.value.login.phone_lock_minutes ?? 5)
    forms.value.login.send_code_ip_1h_limit = Number(forms.value.login.send_code_ip_1h_limit ?? 30)
    forms.value.login.login_ip_10m_limit = Number(forms.value.login.login_ip_10m_limit ?? 120)
  }
  if (category === "llm") {
    forms.value.llm.timeout_seconds = Number(forms.value.llm.timeout_seconds ?? 25)
    forms.value.llm.retry_attempts = Number(forms.value.llm.retry_attempts ?? 3)
    forms.value.llm.retry_backoff_seconds = Number(forms.value.llm.retry_backoff_seconds ?? 0.8)
    forms.value.llm.max_output_tokens = Number(forms.value.llm.max_output_tokens ?? 2048)
    forms.value.llm.temperature = Number(forms.value.llm.temperature ?? 0.3)
  }
  if (category === "miniapp") {
    forms.value.miniapp = normalizeMiniappConfig(forms.value.miniapp)
  }
  if (category === "user_navigation") {
    forms.value.user_navigation = normalizeUserNavigationConfig(forms.value.user_navigation)
  }
}

async function loadReadiness() {
  const data = await adminHttp.get("/admin/configs/readiness")
  const map = {}
  for (const item of data.items || []) {
    map[item.category] = item
  }
  readinessMap.value = map
}

async function reloadCurrent() {
  await Promise.all([loadTab(activeTab.value), loadReadiness()])
  hintText.value = "已重新加载当前板块配置。"
  errorText.value = ""
}

function pickLlm(provider) {
  const current = llmPresets[forms.value.llm.provider] || { base_url: "", model: "" }
  const next = llmPresets[provider] || { base_url: "", model: "" }
  if (!forms.value.llm.base_url || forms.value.llm.base_url === current.base_url) {
    forms.value.llm.base_url = next.base_url
  }
  if (!forms.value.llm.model || forms.value.llm.model === current.model) {
    forms.value.llm.model = next.model
  }
  forms.value.llm.provider = provider
}

function validateCurrent() {
  if (activeTab.value === "billing") {
    const { aigc_rate, dedup_rate, rewrite_rate, packages } = normalizeBillingForm(forms.value.billing)
    if (!(aigc_rate > 0) || !(dedup_rate > 0) || !(rewrite_rate > 0)) {
      return "计费单价必须大于 0"
    }
    if (!Array.isArray(packages) || packages.length === 0) {
      return "至少需要配置 1 个套餐"
    }
    if (!packages.some((pkg) => pkg.enabled)) {
      return "至少需要启用 1 个套餐"
    }
    const names = new Set()
    for (const pkg of packages) {
      if (!pkg.name) return "套餐名称不能为空"
      if (names.has(pkg.name)) return `套餐名称重复：${pkg.name}`
      names.add(pkg.name)
      if (!(Number(pkg.price) > 0)) return `套餐 ${pkg.name} 价格必须大于 0`
      if (!(Number(pkg.credits) > 0)) return `套餐 ${pkg.name} 积分必须大于 0`
    }
  }
  if (activeTab.value === "user_navigation") {
    const items = normalizeUserNavigationConfig(forms.value.user_navigation).items
    if (!items.some((item) => item.visible)) {
      return "前台导航至少需要展示 1 个功能"
    }
  }
  if (activeTab.value === "payment" && isWechatPay.value && forms.value.payment.api_v3_key && String(forms.value.payment.api_v3_key).length !== 32) {
    return "微信支付 APIv3 Key 必须是 32 位"
  }
  if (activeTab.value === "payment" && isAlipay.value && forms.value.payment.app_private_key_pem && !forms.value.payment.alipay_public_key) {
    return "支付宝已填写应用私钥时，需要同时填写支付宝公钥"
  }
  if (activeTab.value === "payment" && !forms.value.payment.test_mode && forms.value.payment.provider === "mock") {
    return "关闭联调模式后不能选择 mock"
  }
  if (activeTab.value === "llm") {
    const cfg = forms.value.llm || {}
    if (Number(cfg.retry_attempts) < 1 || Number(cfg.retry_attempts) > 5) {
      return "LLM 重试次数必须在 1 到 5 之间"
    }
    if (Number(cfg.retry_backoff_seconds) < 0.1 || Number(cfg.retry_backoff_seconds) > 5) {
      return "LLM 退避基线必须在 0.1 到 5 秒之间"
    }
  }
  if (activeTab.value === "login") {
    const cfg = forms.value.login || {}
    if (Number(cfg.new_user_initial_credits) < 0) {
      return "新用户初始积分不能小于 0"
    }
    if (Number(cfg.max_code_retry) < 1) {
      return "验证码最大重试次数不能小于 1"
    }
    if (Number(cfg.phone_lock_minutes) < 1) {
      return "手机号锁定分钟数不能小于 1"
    }
    if (Number(cfg.send_code_ip_1h_limit) < 1) {
      return "发送验证码 IP 限流不能小于 1"
    }
    if (Number(cfg.login_ip_10m_limit) < 1) {
      return "登录请求 IP 限流不能小于 1"
    }
  }
  if (activeTab.value === "miniapp") {
    const cfg = normalizeMiniappConfig(forms.value.miniapp)
    if (cfg.enabled && (!cfg.app_id || !cfg.app_secret)) {
      return "启用小程序配置时必须填写 AppID 与 AppSecret"
    }
    if (cfg.wechat_miniprogram_login_enabled) {
      const loginAppId = cfg.wechat_miniprogram_app_id || cfg.app_id
      const loginSecret = cfg.wechat_miniprogram_app_secret || cfg.app_secret
      if (!loginAppId || !loginSecret) {
        return "启用小程序登录时，需填写登录 AppID/AppSecret（可复用基础配置）"
      }
    }
    if (cfg.wechat_miniprogram_payment_enabled && !cfg.payment_notify_url) {
      return "启用小程序支付时，请填写支付回调地址"
    }
  }
  return ""
}

function payloadFor(category) {
  if (category === "user_navigation") {
    const normalized = normalizeUserNavigationConfig(forms.value.user_navigation)
    return {
      items: normalized.items.map((item, index) => ({
        key: item.key,
        visible: Boolean(item.visible),
        order: index + 1,
      })),
    }
  }
  const payload = { ...(forms.value[category] || {}) }
  if (category === "billing") {
    const normalized = normalizeBillingForm(payload)
    payload.packages = normalized.packages.map((pkg) => ({
      name: pkg.name,
      price: Number(pkg.price),
      credits: Number(pkg.credits),
      description: pkg.description,
      badge: pkg.badge,
      enabled: Boolean(pkg.enabled),
    }))
  }
  if (category === "payment" && payload.provider === "alipay" && payload.app_private_key_pem) {
    payload.api_key = payload.app_private_key_pem
  }
  if (category === "llm") {
    payload.timeout_seconds = Number(payload.timeout_seconds)
    payload.retry_attempts = Number(payload.retry_attempts)
    payload.retry_backoff_seconds = Number(payload.retry_backoff_seconds)
    payload.max_output_tokens = Number(payload.max_output_tokens)
    payload.temperature = Number(payload.temperature)
  }
  if (category === "miniapp") {
    const normalized = normalizeMiniappConfig(payload)
    payload.enabled = normalized.enabled
    payload.wechat_miniprogram_login_enabled = normalized.wechat_miniprogram_login_enabled
    payload.wechat_miniprogram_payment_enabled = normalized.wechat_miniprogram_payment_enabled
    payload.env_version = normalized.env_version
    payload.app_id = normalized.app_id.slice(0, 128)
    payload.app_secret = normalized.app_secret.slice(0, 256)
    payload.original_id = normalized.original_id.slice(0, 128)
    payload.api_base_url = normalized.api_base_url.slice(0, 256)
    payload.web_base_url = normalized.web_base_url.slice(0, 256)
    payload.request_domain = normalized.request_domain.slice(0, 256)
    payload.upload_domain = normalized.upload_domain.slice(0, 256)
    payload.download_domain = normalized.download_domain.slice(0, 256)
    payload.ws_domain = normalized.ws_domain.slice(0, 256)
    payload.business_domain = normalized.business_domain.slice(0, 256)
    payload.payment_notify_url = normalized.payment_notify_url.slice(0, 256)
    payload.icp_filing_no = normalized.icp_filing_no.slice(0, 128)
    payload.contact_phone = normalized.contact_phone.slice(0, 32)
    payload.contact_email = normalized.contact_email.slice(0, 128)
    payload.publish_note = normalized.publish_note.slice(0, 500)
    payload.wechat_miniprogram_app_id = normalized.wechat_miniprogram_app_id.slice(0, 128)
    payload.wechat_miniprogram_app_secret = normalized.wechat_miniprogram_app_secret.slice(0, 256)
  }
  return payload
}

function cloneBillingPackages(packages = defaultBillingPackages) {
  return (Array.isArray(packages) ? packages : defaultBillingPackages).map((pkg) => ({
    name: String(pkg?.name || "").trim(),
    price: Number(pkg?.price || 0),
    credits: Number(pkg?.credits || 0),
    description: String(pkg?.description || "").trim(),
    badge: String(pkg?.badge || "").trim(),
    enabled: pkg?.enabled !== false,
  }))
}

function normalizeBillingForm(raw) {
  const source = raw && typeof raw === "object" ? raw : {}
  return {
    aigc_rate: Number(source.aigc_rate) || 1,
    dedup_rate: Number(source.dedup_rate) || 2,
    rewrite_rate: Number(source.rewrite_rate) || 2,
    packages: cloneBillingPackages(source.packages),
  }
}

function normalizeMiniappConfig(raw) {
  const source = { ...defaultMiniappConfig, ...(raw || {}) }
  const envVersion = String(source.env_version || "release").toLowerCase()
  return {
    enabled: source.enabled === true,
    app_id: String(source.app_id || "").trim(),
    app_secret: String(source.app_secret || "").trim(),
    original_id: String(source.original_id || "").trim(),
    env_version: ["develop", "trial", "release"].includes(envVersion) ? envVersion : "release",
    api_base_url: String(source.api_base_url || "").trim(),
    web_base_url: String(source.web_base_url || "").trim(),
    request_domain: String(source.request_domain || "").trim(),
    upload_domain: String(source.upload_domain || "").trim(),
    download_domain: String(source.download_domain || "").trim(),
    ws_domain: String(source.ws_domain || "").trim(),
    business_domain: String(source.business_domain || "").trim(),
    icp_filing_no: String(source.icp_filing_no || "").trim(),
    contact_phone: String(source.contact_phone || "").trim(),
    contact_email: String(source.contact_email || "").trim(),
    publish_note: String(source.publish_note || "").trim(),
    wechat_miniprogram_login_enabled: source.wechat_miniprogram_login_enabled === true,
    wechat_miniprogram_app_id: String(source.wechat_miniprogram_app_id || "").trim(),
    wechat_miniprogram_app_secret: String(source.wechat_miniprogram_app_secret || "").trim(),
    wechat_miniprogram_payment_enabled: source.wechat_miniprogram_payment_enabled === true,
    payment_notify_url: String(source.payment_notify_url || "").trim(),
  }
}

function addBillingPackage() {
  if (!Array.isArray(forms.value.billing.packages)) {
    forms.value.billing.packages = []
  }
  forms.value.billing.packages.push({
    name: "",
    price: 9.9,
    credits: 10000,
    description: "",
    badge: "",
    enabled: true,
  })
}

function removeBillingPackage(index) {
  if (!Array.isArray(forms.value.billing.packages)) {
    return
  }
  forms.value.billing.packages.splice(index, 1)
}

function navGroupLabel(group) {
  return USER_NAV_GROUP_LABELS[group] || group || "未分组"
}

function moveUserNavItem(index, delta) {
  const items = forms.value.user_navigation?.items
  if (!Array.isArray(items)) {
    return
  }
  const nextIndex = index + delta
  if (nextIndex < 0 || nextIndex >= items.length) {
    return
  }
  const [current] = items.splice(index, 1)
  items.splice(nextIndex, 0, current)
  forms.value.user_navigation.items = items.map((item, order) => ({
    ...item,
    order: order + 1,
  }))
}

function resolvePaymentNotifyPreview() {
  const notify = String(forms.value.payment.notify_url || "").trim()
  const provider = String(forms.value.payment.provider || "").toLowerCase()
  if (!notify) return "未填写"
  let base = notify
  try {
    const parsed = new URL(notify)
    const path = parsed.pathname || "/"
    if (path === "/" || path === "") {
      if (provider === "alipay") {
        base = notify.replace(/\/+$/, "") + "/api/v1/billing/notify/alipay"
      } else {
        base = notify.replace(/\/+$/, "") + "/api/v1/billing/notify/wechatpay"
      }
    }
    return base
  } catch {
    return "回调地址格式不合法"
  }
}

async function saveCurrent() {
  if (!canManageConfigs.value) {
    errorText.value = "当前账号仅有查看权限，无法保存配置。"
    hintText.value = ""
    return
  }
  const checkError = validateCurrent()
  if (checkError) {
    errorText.value = checkError
    return
  }
  saving.value = true
  hintText.value = ""
  errorText.value = ""
  try {
    await adminHttp.post(`/admin/configs/${activeTab.value}`, payloadFor(activeTab.value), { timeout: 45000 })
    const refreshResults = await Promise.allSettled([loadTab(activeTab.value), loadReadiness()])
    const refreshFailed = refreshResults.some((item) => item.status === "rejected")
    hintText.value = refreshFailed
      ? `${currentTab.value.label}已保存。页面状态刷新稍后同步。`
      : `${currentTab.value.label}已保存并生效。`
  } catch (error) {
    errorText.value = error.message || "保存失败"
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.admin-config-layout {
  display: grid;
  gap: 16px;
  grid-template-columns: 220px minmax(0, 1fr) 300px;
}

.admin-config-sidebar,
.admin-config-main,
.admin-config-guide {
  min-width: 0;
}

.admin-config-tab-btn {
  min-width: 0;
}

@media (max-width: 1279px) {
  .admin-config-layout {
    grid-template-columns: 220px minmax(0, 1fr);
  }

  .admin-config-guide {
    grid-column: 1 / -1;
  }
}

@media (max-width: 768px) {
  .admin-config-layout {
    grid-template-columns: 1fr;
  }

  .admin-config-sidebar,
  .admin-config-main,
  .admin-config-guide {
    padding: 14px;
  }

  .admin-config-tabs {
    display: flex;
    gap: 10px;
    overflow-x: auto;
    padding-bottom: 4px;
    margin-right: -4px;
  }

  .admin-config-tabs::-webkit-scrollbar {
    display: none;
  }

  .admin-config-tab-btn {
    flex: 0 0 240px;
    width: 240px !important;
  }
}
</style>

