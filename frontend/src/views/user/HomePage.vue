<template>
  <div class="gw-home-v3">
    <header class="gw-home-v3__nav">
      <RouterLink to="/" class="gw-home-v3__brand" aria-label="格物学术首页">
        <span class="gw-home-v3__brand-mark">GW</span>
        <span class="gw-home-v3__brand-name">格物学术</span>
      </RouterLink>

      <nav class="gw-home-v3__links" aria-label="主页导航">
        <RouterLink class="gw-home-v3__link gw-home-v3__link--solid" :to="entryPath">{{ entryText }}</RouterLink>
      </nav>
    </header>

    <main class="gw-home-v3__main">
      <section class="gw-home-v3__hero" aria-labelledby="home-title">
        <p class="gw-home-v3__kicker">五个功能页面自动轮播</p>
        <h1 id="home-title">一屏查看论文处理全流程能力</h1>
        <p class="gw-home-v3__lead">
          首页只保留五个核心功能卡片：降AIGC、降重复率、AIGC检测、智能审稿、答辩服务。
          自动轮播，支持手动切换，不再是长文本堆叠。
        </p>
      </section>

      <section
        class="gw-home-v3__carousel"
        aria-label="功能轮播"
        @mouseenter="pauseAutoPlay"
        @mouseleave="resumeAutoPlay"
      >
        <div class="gw-home-v3__toolbar">
          <div class="gw-home-v3__toolbar-title">
            <p>功能导航</p>
            <strong>{{ activeSlide + 1 }} / {{ slides.length }}</strong>
          </div>

          <div class="gw-home-v3__controls">
            <button type="button" aria-label="上一张" @click="prevSlide">上一张</button>
            <button type="button" aria-label="下一张" @click="nextSlide">下一张</button>
          </div>
        </div>

        <div class="gw-home-v3__viewport">
          <div class="gw-home-v3__track" :style="trackStyle">
            <article v-for="(slide, index) in slides" :key="slide.key" class="gw-home-v3__card">
              <div class="gw-home-v3__card-head">
                <span class="gw-home-v3__index">{{ String(index + 1).padStart(2, "0") }}</span>
                <h2>{{ slide.title }}</h2>
              </div>

              <p class="gw-home-v3__desc">{{ slide.desc }}</p>

              <ul class="gw-home-v3__points">
                <li v-for="point in slide.points" :key="point">{{ point }}</li>
              </ul>

              <div class="gw-home-v3__actions">
                <RouterLink class="gw-home-v3__action" :to="slide.path">{{ slide.cta }}</RouterLink>
              </div>
            </article>
          </div>
        </div>

        <div class="gw-home-v3__tabs" role="tablist" aria-label="轮播切换">
          <button
            v-for="(slide, index) in slides"
            :key="slide.key"
            type="button"
            :class="{ 'is-active': index === activeSlide }"
            :aria-label="`切换到 ${slide.title}`"
            :aria-selected="index === activeSlide"
            @click="goSlide(index)"
          >
            {{ slide.short }}
          </button>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import { RouterLink } from "vue-router"

import { getUserToken } from "../../lib/session"

const hasToken = computed(() => Boolean(getUserToken()))
const entryPath = computed(() => (hasToken.value ? "/app/detect" : "/login"))
const entryText = computed(() => (hasToken.value ? "进入工作台" : "登录"))

const slides = [
  {
    key: "rewrite",
    short: "降AIGC",
    title: "降AIGC",
    desc: "针对疑似 AI 特征段落进行重写优化，尽量保留原意并降低风险。",
    points: ["支持报告联动", "任务进度实时可见", "结果可下载复核"],
    cta: "进入降AIGC",
    path: "/app/rewrite",
  },
  {
    key: "dedup",
    short: "降重复率",
    title: "降重复率",
    desc: "围绕重复高风险内容做表达重构，兼顾可读性与学术表达规范。",
    points: ["支持查重报告辅助", "重点段落优先处理", "任务历史统一归档"],
    cta: "进入降重复率",
    path: "/app/dedup",
  },
  {
    key: "detect",
    short: "AIGC检测",
    title: "AIGC检测",
    desc: "提交后快速识别文本风险，输出可追溯检测结果并进入记录页。",
    points: ["多平台策略检测", "结果结构统一", "历史记录可追踪"],
    cta: "进入AIGC检测",
    path: "/app/detect",
  },
  {
    key: "review",
    short: "智能审稿",
    title: "智能审稿",
    desc: "从结构、表达、逻辑维度给出审稿建议，提升修改效率。",
    points: ["问题定位清晰", "审稿建议结构化", "便于人工复核"],
    cta: "进入智能审稿",
    path: "/app/review",
  },
  {
    key: "defense",
    short: "答辩服务",
    title: "答辩服务",
    desc: "围绕答辩场景梳理材料与问答，提升准备效率与表达稳定性。",
    points: ["答辩重点提炼", "问答场景辅助", "资料统一管理"],
    cta: "进入答辩服务",
    path: "/app/defense",
  },
]

const activeSlide = ref(0)
let timer = null

const trackStyle = computed(() => ({
  transform: `translateX(-${activeSlide.value * 100}%)`,
}))

function nextSlide() {
  activeSlide.value = (activeSlide.value + 1) % slides.length
}

function prevSlide() {
  activeSlide.value = (activeSlide.value - 1 + slides.length) % slides.length
}

function goSlide(index) {
  activeSlide.value = index
}

function startAutoPlay() {
  stopAutoPlay()
  timer = setInterval(nextSlide, 3800)
}

function stopAutoPlay() {
  if (!timer) return
  clearInterval(timer)
  timer = null
}

function pauseAutoPlay() {
  stopAutoPlay()
}

function resumeAutoPlay() {
  startAutoPlay()
}

onMounted(() => {
  startAutoPlay()
})

onUnmounted(() => {
  stopAutoPlay()
})
</script>

<style scoped>
.gw-home-v3 {
  min-height: 100vh;
  background: #ffffff;
  color: #111111;
}

.gw-home-v3__nav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 24px;
  background: #ffffff;
}

.gw-home-v3__brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
  color: #111111;
}

.gw-home-v3__brand-mark {
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

.gw-home-v3__brand-name {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.gw-home-v3__links {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.gw-home-v3__link {
  min-height: 36px;
  padding: 0 13px;
  border-radius: 999px;
  border: 1px solid #111111;
  background: #111111;
  color: #ffffff;
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

.gw-home-v3__main {
  max-width: 1140px;
  margin: 0 auto;
  padding: 30px 24px 44px;
  display: grid;
  gap: 20px;
}

.gw-home-v3__hero {
  border: 1px solid #d9d9d9;
  border-radius: 18px;
  padding: clamp(22px, 4vw, 34px);
  background: #ffffff;
}

.gw-home-v3__kicker {
  margin: 0;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #333333;
}

.gw-home-v3__hero h1 {
  margin: 12px 0 0;
  font-size: clamp(28px, 4vw, 44px);
  line-height: 1.14;
}

.gw-home-v3__lead {
  margin: 12px 0 0;
  max-width: 860px;
  color: #333333;
  line-height: 1.76;
  font-size: 15px;
}

.gw-home-v3__carousel {
  border: 1px solid #d9d9d9;
  border-radius: 18px;
  background: #ffffff;
  padding: 14px;
}

.gw-home-v3__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 4px 2px 12px;
}

.gw-home-v3__toolbar-title {
  display: grid;
  gap: 6px;
}

.gw-home-v3__toolbar-title p {
  margin: 0;
  font-size: 12px;
  color: #333333;
  letter-spacing: 0.08em;
}

.gw-home-v3__toolbar-title strong {
  font-size: 22px;
  line-height: 1;
}

.gw-home-v3__controls {
  display: inline-flex;
  gap: 8px;
}

.gw-home-v3__controls button {
  min-height: 34px;
  padding: 0 12px;
  border-radius: 9px;
  border: 1px solid #111111;
  background: #111111;
  color: #ffffff;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.gw-home-v3__viewport {
  overflow: hidden;
  border-radius: 12px;
}

.gw-home-v3__track {
  display: flex;
  transition: transform 0.45s ease;
}

.gw-home-v3__card {
  min-width: 100%;
  border: 1px solid #d9d9d9;
  border-radius: 12px;
  padding: clamp(16px, 3vw, 24px);
  background: #ffffff;
  display: grid;
  gap: 12px;
}

.gw-home-v3__card-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.gw-home-v3__index {
  min-width: 42px;
  height: 28px;
  border-radius: 999px;
  background: #111111;
  color: #ffffff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
}

.gw-home-v3__card h2 {
  margin: 0;
  font-size: clamp(24px, 3vw, 36px);
  line-height: 1.18;
}

.gw-home-v3__desc {
  margin: 0;
  color: #333333;
  line-height: 1.74;
  font-size: 15px;
}

.gw-home-v3__points {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 8px;
}

.gw-home-v3__points li {
  min-height: 36px;
  padding: 0 12px;
  border-radius: 10px;
  border: 1px solid #d9d9d9;
  display: flex;
  align-items: center;
  color: #111111;
  font-size: 14px;
}

.gw-home-v3__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.gw-home-v3__action {
  min-height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid #111111;
  background: #111111;
  color: #ffffff;
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

.gw-home-v3__tabs {
  margin-top: 12px;
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.gw-home-v3__tabs button {
  min-height: 34px;
  border-radius: 10px;
  border: 1px solid #111111;
  background: #111111;
  color: #ffffff;
  font-size: 12px;
  font-weight: 700;
  padding: 0 8px;
  cursor: pointer;
  white-space: nowrap;
}

.gw-home-v3__tabs button.is-active {
  background: #ffffff;
  color: #111111;
}

@media (max-width: 900px) {
  .gw-home-v3__tabs {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 680px) {
  .gw-home-v3__nav {
    padding: 12px 14px;
  }

  .gw-home-v3__main {
    padding: 14px 14px 26px;
  }

  .gw-home-v3__tabs {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .gw-home-v3__controls {
    width: 100%;
  }

  .gw-home-v3__controls button {
    flex: 1;
  }

  .gw-home-v3__toolbar {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
