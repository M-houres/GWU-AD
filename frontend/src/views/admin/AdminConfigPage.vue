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
              <div class="text-sm font-semibold text-[#1f2c35]">任务计费（通用点数 / 字符）</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">任务直接按字符数乘以整数点数单价扣费。当前默认三类任务都是 1 字符扣 1 点数。AIGC 检测每天前 6 篇免费，超出后按配置计费。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-3">
                <label class="space-y-1 text-sm"><span>AIGC 单价（点数/字符）</span><input v-model.number="forms.billing.aigc_points_per_char" type="number" min="1" step="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
                <label class="space-y-1 text-sm"><span>降重单价（点数/字符）</span><input v-model.number="forms.billing.dedup_points_per_char" type="number" min="1" step="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
                <label class="space-y-1 text-sm"><span>降AIGC率单价（点数/字符）</span><input v-model.number="forms.billing.rewrite_points_per_char" type="number" min="1" step="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" /></label>
              </div>
            </section>

            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <div class="text-sm font-semibold text-[#1f2c35]">通用点数套餐（前台展示）</div>
                    <div class="mt-1 text-xs leading-5 text-[#5f6d79]">每个套餐都要同时配置支付金额和到账通用点数，前台购买页只会展示这里配置的套餐。</div>
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
                      <span>到账通用点数</span>
                      <input v-model.number="pkg.credits" type="number" min="1" step="1" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
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

          <template v-else-if="activeTab === 'aigc_detect_strategy'">
            <section class="rounded-2xl border border-[#dce4eb] bg-[#fbfcfd] p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">MVP 范围</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">这里只决定知网和维普 AIGC 检测任务是否可用。AIGC 检测现在只走内部算法策略链，不提供版本切换或大模型模式。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                  后端只对 `aigc_detect + cnki/vip` 任务读取这里的启停配置，用户提交链路、计费链路和下载链路保持不变。
                </div>
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                  当前检测主链是纯内部特征策略：知网走段级双阈值判定，维普走段落级多特征加权，不依赖 LLM。
                </div>
              </div>
            </section>

            <section class="space-y-3">
              <article
                v-for="platform in aigcDetectStrategyPlatforms"
                :key="platform.key"
                class="rounded-2xl border border-[#dce4eb] bg-white p-4"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold text-[#1f2c35]">{{ platform.label }}</div>
                    <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ platform.desc }}</div>
                  </div>
                  <label class="inline-flex items-center gap-2 rounded-xl border border-[#d6dee6] bg-[#fbfcfd] px-3 py-2 text-sm text-[#30404d]">
                    <input v-model="forms.aigc_detect_strategy[platform.key].aigc_detect.enabled" type="checkbox" />
                    启用该平台
                  </label>
                </div>

                <div class="mt-4 rounded-xl border border-[#dce4eb] bg-[#fbfcfd] px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                  固定执行：内部算法策略链。当前平台不提供 LLM 模式，也不读取外部版本配置。
                </div>
              </article>
            </section>
          </template>

          <template v-else-if="activeTab === 'dedup_strategy'">
            <section class="rounded-2xl border border-[#dce4eb] bg-[#fbfcfd] p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">MVP 范围</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">这里只决定知网和维普降重复率任务由哪种策略处理，只保留平台启停和当前执行策略。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                  后端只对 `dedup + cnki/vip` 任务读取这里的配置，用户提交链路、计费链路和下载链路保持不变。
                </div>
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                  算法策略更稳，适合先跑规则体系；大模型策略更灵活，适合走专用 prompt，但依赖 LLM 配置可用。
                </div>
              </div>
            </section>

            <section class="space-y-3">
              <article
                v-for="platform in dedupStrategyPlatforms"
                :key="platform.key"
                class="rounded-2xl border border-[#dce4eb] bg-white p-4"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold text-[#1f2c35]">{{ platform.label }}</div>
                    <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ platform.desc }}</div>
                  </div>
                  <label class="inline-flex items-center gap-2 rounded-xl border border-[#d6dee6] bg-[#fbfcfd] px-3 py-2 text-sm text-[#30404d]">
                    <input v-model="forms.dedup_strategy[platform.key].dedup.enabled" type="checkbox" />
                    启用该平台
                  </label>
                </div>

                <div class="mt-4 grid gap-3 md:grid-cols-2">
                  <label class="space-y-1 text-sm">
                    <span>执行策略</span>
                    <select
                      v-model="forms.dedup_strategy[platform.key].dedup.active_strategy"
                      class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"
                    >
                      <option v-for="item in dedupStrategyOptions" :key="item.value" :value="item.value">
                        {{ item.label }}
                      </option>
                    </select>
                  </label>
                  <div class="rounded-xl border border-[#dce4eb] bg-[#fbfcfd] px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                    当前说明：{{ strategyDescription(forms.dedup_strategy[platform.key].dedup.active_strategy) }}
                  </div>
                </div>

                <div class="mt-4 rounded-2xl border border-[#dce4eb] bg-[#fbfcfd] p-3">
                  <div class="text-sm font-semibold text-[#1f2c35]">运行时参数（算法 + 大模型共用）</div>
                  <div class="mt-1 text-xs leading-5 text-[#5f6d79]">修改后立即影响该平台降重复率处理：分块大小、算法每块改写上限、LLM每块改写预算上限。</div>
                  <div class="mt-3 grid gap-3 md:grid-cols-2">
                    <label class="space-y-1 text-sm">
                      <span>分块最小字数</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.chunk_min_chars" type="number" min="80" max="1200" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>分块最大字数</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.chunk_max_chars" type="number" min="100" max="1600" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>算法每块最大改写数</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.algorithm_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-xs leading-5 text-[#5f6d79]">
                      LLM 每块预算上限会按段长分档：
                      ≤120、121-200、201-260、261-360、>360。
                    </div>
                    <label class="space-y-1 text-sm">
                      <span>LLM ≤120字 每块上限</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.llm_short_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>LLM 121-200字 每块上限</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.llm_medium_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>LLM 201-260字 每块上限</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.llm_standard_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>LLM 261-360字 每块上限</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.llm_long_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm md:col-span-2">
                      <span>LLM >360字 每块上限</span>
                      <input v-model.number="forms.dedup_strategy[platform.key].runtime.llm_xlong_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                  </div>
                </div>
              </article>
            </section>
          </template>

          <template v-else-if="activeTab === 'rewrite_strategy'">
            <section class="rounded-2xl border border-[#dce4eb] bg-[#fbfcfd] p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">MVP 范围</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">这里只决定知网和维普降AIGC率任务由哪种策略处理，只保留平台启停和当前执行策略。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                  后端只对 `rewrite + cnki/vip` 任务读取这里的配置，用户提交链路、计费链路和下载链路保持不变。
                </div>
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                  算法策略更稳，适合先跑规则体系；大模型策略更灵活，适合走专用 prompt，但依赖 LLM 配置可用。
                </div>
              </div>
            </section>

            <section class="space-y-3">
              <article
                v-for="platform in rewriteStrategyPlatforms"
                :key="platform.key"
                class="rounded-2xl border border-[#dce4eb] bg-white p-4"
              >
                <div class="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div class="text-sm font-semibold text-[#1f2c35]">{{ platform.label }}</div>
                    <div class="mt-1 text-xs leading-5 text-[#5f6d79]">{{ platform.desc }}</div>
                  </div>
                  <label class="inline-flex items-center gap-2 rounded-xl border border-[#d6dee6] bg-[#fbfcfd] px-3 py-2 text-sm text-[#30404d]">
                    <input v-model="forms.rewrite_strategy[platform.key].rewrite.enabled" type="checkbox" />
                    启用该平台
                  </label>
                </div>

                <div class="mt-4 grid gap-3 md:grid-cols-2">
                  <label class="space-y-1 text-sm">
                    <span>执行策略</span>
                    <select
                      v-model="forms.rewrite_strategy[platform.key].rewrite.active_strategy"
                      class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"
                    >
                      <option v-for="item in rewriteStrategyOptions" :key="item.value" :value="item.value">
                        {{ item.label }}
                      </option>
                    </select>
                  </label>
                  <div class="rounded-xl border border-[#dce4eb] bg-[#fbfcfd] px-3 py-3 text-sm leading-6 text-[#4f5d69]">
                    当前说明：{{ strategyDescription(forms.rewrite_strategy[platform.key].rewrite.active_strategy) }}
                  </div>
                </div>

                <div class="mt-4 rounded-2xl border border-[#dce4eb] bg-[#fbfcfd] p-3">
                  <div class="text-sm font-semibold text-[#1f2c35]">运行时参数（算法 + 大模型共用）</div>
                  <div class="mt-1 text-xs leading-5 text-[#5f6d79]">修改后立即影响该平台降AIGC处理：分块大小、算法每块改写上限、LLM每块改写预算上限。</div>
                  <div class="mt-3 grid gap-3 md:grid-cols-2">
                    <label class="space-y-1 text-sm">
                      <span>分块最小字数</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.chunk_min_chars" type="number" min="80" max="1200" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>分块最大字数</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.chunk_max_chars" type="number" min="100" max="1600" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>算法每块最大改写数</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.algorithm_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-xs leading-5 text-[#5f6d79]">
                      LLM 每块预算上限会按段长分档：
                      ≤120、121-200、201-260、261-360、>360。
                    </div>
                    <label class="space-y-1 text-sm">
                      <span>LLM ≤120字 每块上限</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.llm_short_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>LLM 121-200字 每块上限</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.llm_medium_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>LLM 201-260字 每块上限</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.llm_standard_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm">
                      <span>LLM 261-360字 每块上限</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.llm_long_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                    <label class="space-y-1 text-sm md:col-span-2">
                      <span>LLM >360字 每块上限</span>
                      <input v-model.number="forms.rewrite_strategy[platform.key].runtime.llm_xlong_chunk_max_changes" type="number" min="1" max="20" class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2" />
                    </label>
                  </div>
                </div>
              </article>
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
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">保存后立即生效，用于控制注册赠送通用点数和登录风控阈值。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <label class="space-y-1 text-sm">
                  <span>新用户初始通用点数</span>
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
            <section class="rounded-2xl border border-[#dce4eb] bg-[#fbfcfd] p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">MVP 验收基线</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">基线 5 只锁定 4 件事：小程序登录、小程序支付、API 域名和来源追踪。不要在这里继续扩非 MVP 能力。</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm text-[#4f5d69]">
                  登录链：启用小程序登录后，必须保证 AppID / AppSecret 完整，且 `/auth/options` 能返回开关。
                </div>
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm text-[#4f5d69]">
                  支付链：启用小程序支付后，必须配置公网 HTTPS `payment_notify_url`，下单场景走 `scene=miniprogram`。
                </div>
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm text-[#4f5d69]">
                  域名链：`api_base_url`、`request_domain` 与微信后台域名白名单必须一致。
                </div>
                <div class="rounded-xl border border-[#dce4eb] bg-white px-3 py-3 text-sm text-[#4f5d69]">
                  追踪链：用户、订单、任务、点数流水都要能在后台按 `miniapp` 来源追踪。
                </div>
              </div>
            </section>

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

          <template v-else-if="activeTab === 'promo_center'">
            <section class="rounded-2xl border border-[#dce4eb] bg-[#fbfcfd] p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">推广策略说明</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">
                前台推广中心会展示专属邀请奖励和机构合作信息。邀请码与邀请链接按登录用户动态生成，奖励积分和联系方式由这里统一配置。
              </div>
            </section>

            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">邀请奖励</div>
              <div class="mt-3 grid gap-3 md:grid-cols-2">
                <label class="inline-flex items-center gap-2 text-sm md:col-span-2">
                  <input v-model="forms.promo_center.enabled" type="checkbox" />
                  启用推广中心
                </label>
                <label class="space-y-1 text-sm">
                  <span>邀请奖励积分（邀请人/被邀请人各得）</span>
                  <input
                    v-model.number="forms.promo_center.invite_reward_points"
                    type="number"
                    min="0"
                    max="100000"
                    step="1"
                    class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2"
                  />
                </label>
                <div class="rounded-xl border border-[#dce4eb] bg-[#fbfcfd] px-3 py-3 text-xs leading-5 text-[#4f5d69]">
                  该积分值会在前台推广页实时显示，单位为通用点数。设置为 0 时，仅保留推广页联系方式展示。
                </div>
              </div>
            </section>

            <section class="rounded-2xl border border-[#dce4eb] bg-white p-4">
              <div class="text-sm font-semibold text-[#1f2c35]">机构客户合作区联系方式</div>
              <div class="mt-1 text-xs leading-5 text-[#5f6d79]">电话、微信号、邮箱每类支持配置多条，前台会按卡片形式展示。</div>

              <div class="mt-3 grid gap-3 xl:grid-cols-3">
                <article
                  v-for="contact in promoContactFields"
                  :key="contact.key"
                  class="rounded-2xl border border-[#d6dfe7] bg-[#fbfcfd] p-3"
                >
                  <div class="mb-2 flex items-center justify-between">
                    <div class="text-sm font-semibold text-[#21303a]">{{ contact.label }}</div>
                    <span class="text-xs text-[#5f6d79]">
                      {{ forms.promo_center.contacts[contact.key]?.length || 0 }}/20
                    </span>
                  </div>

                  <div class="space-y-2">
                    <div
                      v-for="(value, index) in forms.promo_center.contacts[contact.key]"
                      :key="`${contact.key}-${index}`"
                      class="flex items-center gap-2"
                    >
                      <input
                        v-model.trim="forms.promo_center.contacts[contact.key][index]"
                        class="w-full rounded-xl border border-[#ccd5dd] px-3 py-2 text-sm"
                        :placeholder="contact.placeholder"
                      />
                      <button
                        type="button"
                        class="rounded-lg bg-[#edf2f6] px-2 py-2 text-xs text-[#344250]"
                        @click="removePromoContact(contact.key, index)"
                      >
                        删除
                      </button>
                    </div>
                  </div>

                  <button
                    type="button"
                    class="mt-2 rounded-lg bg-[#edf2f6] px-3 py-2 text-xs text-[#344250] disabled:opacity-50"
                    :disabled="(forms.promo_center.contacts[contact.key]?.length || 0) >= 20"
                    @click="addPromoContact(contact.key)"
                  >
                    新增{{ contact.label }}
                  </button>
                </article>
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
import {
  AIGC_DETECT_STRATEGY_PLATFORMS,
  ADMIN_CONFIG_GUIDES,
  buildAdminConfigPayload,
  CONFIG_TABS,
  DEDUP_STRATEGY_OPTIONS,
  DEDUP_STRATEGY_PLATFORMS,
  DEFAULT_MINIAPP_CONFIG,
  DEFAULT_PROMO_CENTER_CONFIG,
  LLM_PRESETS,
  LLM_PROVIDERS,
  PAYMENT_PROVIDERS,
  REWRITE_STRATEGY_OPTIONS,
  REWRITE_STRATEGY_PLATFORMS,
  SMS_PROVIDERS,
  adminConfigReadinessChipClass,
  adminConfigReadinessLabel,
  applyLlmProviderPreset,
  cloneBillingPackages,
  createBillingPackage,
  normalizeBillingForm,
  normalizeAigcDetectStrategyConfig,
  normalizeDedupStrategyConfig,
  normalizeMiniappConfig,
  normalizePromotionCenterConfig,
  normalizeRewriteStrategyConfig,
  reorderAdminConfigItems,
  resolvePaymentNotifyPreview as resolvePaymentNotifyPreviewText,
  strategyDescription,
  validateAdminConfigCategory,
} from "../../lib/adminConfig"
import { adminHttp } from "../../lib/http"
import { adminHasPermission } from "../../lib/session"
import { normalizeUserNavigationConfig, USER_NAV_GROUP_LABELS } from "../../lib/userNavigation"

const tabs = CONFIG_TABS
const llmProviders = LLM_PROVIDERS
const llmPresets = LLM_PRESETS
const paymentProviders = PAYMENT_PROVIDERS
const smsProviders = SMS_PROVIDERS
const aigcDetectStrategyPlatforms = AIGC_DETECT_STRATEGY_PLATFORMS
const dedupStrategyPlatforms = DEDUP_STRATEGY_PLATFORMS
const dedupStrategyOptions = DEDUP_STRATEGY_OPTIONS
const rewriteStrategyPlatforms = REWRITE_STRATEGY_PLATFORMS
const rewriteStrategyOptions = REWRITE_STRATEGY_OPTIONS
const guideMap = ADMIN_CONFIG_GUIDES
const promoContactFields = [
  { key: "phone", label: "电话", placeholder: "例如：400-800-1234" },
  { key: "wechat", label: "微信号", placeholder: "例如：gewu_service_01" },
  { key: "email", label: "邮箱", placeholder: "例如：biz@gewu.example.com" },
]

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
  billing: { aigc_points_per_char: 1, dedup_points_per_char: 1, rewrite_points_per_char: 1, packages: cloneBillingPackages() },
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
  promo_center: normalizePromotionCenterConfig(DEFAULT_PROMO_CENTER_CONFIG),
  miniapp: normalizeMiniappConfig(DEFAULT_MINIAPP_CONFIG),
  aigc_detect_strategy: normalizeAigcDetectStrategyConfig(),
  dedup_strategy: normalizeDedupStrategyConfig(),
  rewrite_strategy: normalizeRewriteStrategyConfig(),
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
const paymentNotifyPreview = computed(() => resolvePaymentNotifyPreviewText(forms.value.payment))

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
  return adminConfigReadinessChipClass(status)
}

function readinessLabel(status) {
  return adminConfigReadinessLabel(status)
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
  if (category === "promo_center") {
    forms.value.promo_center = normalizePromotionCenterConfig(forms.value.promo_center)
  }
  if (category === "aigc_detect_strategy") {
    forms.value.aigc_detect_strategy = normalizeAigcDetectStrategyConfig(forms.value.aigc_detect_strategy)
  }
  if (category === "dedup_strategy") {
    forms.value.dedup_strategy = normalizeDedupStrategyConfig(forms.value.dedup_strategy)
  }
  if (category === "rewrite_strategy") {
    forms.value.rewrite_strategy = normalizeRewriteStrategyConfig(forms.value.rewrite_strategy)
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
  forms.value.llm = applyLlmProviderPreset(forms.value.llm, provider, llmPresets)
}

function validateCurrent() {
  return validateAdminConfigCategory(activeTab.value, forms.value, { normalizeUserNavigationConfig })
}

function payloadFor(category) {
  return buildAdminConfigPayload(category, forms.value, { normalizeUserNavigationConfig })
}

function addBillingPackage() {
  if (!Array.isArray(forms.value.billing.packages)) {
    forms.value.billing.packages = []
  }
  forms.value.billing.packages.push(createBillingPackage())
}

function removeBillingPackage(index) {
  if (!Array.isArray(forms.value.billing.packages)) {
    return
  }
  forms.value.billing.packages.splice(index, 1)
}

function addPromoContact(type) {
  const contacts = forms.value.promo_center?.contacts
  if (!contacts || typeof contacts !== "object") {
    forms.value.promo_center.contacts = { phone: [], wechat: [], email: [] }
  }
  const values = forms.value.promo_center.contacts[type]
  if (!Array.isArray(values)) {
    forms.value.promo_center.contacts[type] = []
  }
  if (forms.value.promo_center.contacts[type].length >= 20) {
    return
  }
  forms.value.promo_center.contacts[type].push("")
}

function removePromoContact(type, index) {
  const values = forms.value.promo_center?.contacts?.[type]
  if (!Array.isArray(values)) {
    return
  }
  values.splice(index, 1)
}

function navGroupLabel(group) {
  return USER_NAV_GROUP_LABELS[group] || group || "未分组"
}

function moveUserNavItem(index, delta) {
  const items = forms.value.user_navigation?.items
  const reordered = reorderAdminConfigItems(items, index, delta)
  if (reordered === items) {
    return
  }
  forms.value.user_navigation.items = reordered
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

