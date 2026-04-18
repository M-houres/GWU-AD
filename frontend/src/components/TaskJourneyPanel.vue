<template>
  <section class="task-journey">
    <div class="task-journey__steps">
      <article v-for="step in steps" :key="step.title" class="task-journey__step">
        <div class="task-journey__index">{{ step.index }}</div>
        <strong class="task-journey__label">{{ step.title }}</strong>
      </article>
    </div>
  </section>
</template>

<script setup>
const props = defineProps({
  steps: {
    type: Array,
    default: () => [
      { index: "01", title: "任务提交" },
      { index: "02", title: "通用点数扣除" },
      { index: "03", title: "任务处理" },
      { index: "04", title: "下载结果" },
    ],
  },
})
</script>

<style scoped>
.task-journey{
  margin:18px 0 22px;
  padding:14px 16px;
  border:1px solid rgba(17,17,17,.08);
  border-radius:22px;
  background:linear-gradient(180deg,#fff 0%,#f7faff 100%);
}
.task-journey__steps{
  display:flex;
  flex-wrap:wrap;
  justify-content:center;
  gap:12px;
}
.task-journey__step{
  display:flex;
  align-items:center;
  justify-content:center;
  gap:10px;
  flex:0 1 168px;
  min-width:0;
  padding:12px 14px;
  border-radius:18px;
  border:1px solid rgba(17,17,17,.06);
  background:#fff;
  text-align:center;
}
.task-journey__index{
  flex:0 0 38px;
  width:38px;
  height:38px;
  border-radius:11px;
  display:grid;
  place-items:center;
  background:#edf4ff;
  color:#1d4ed8;
  font-size:12px;
  font-weight:800;
}
.task-journey__label{
  display:block;
  min-width:0;
  font-size:14px;
  line-height:1.2;
  color:#10294b;
  text-align:center;
  white-space:nowrap;
}
@media (max-width:1100px){
  .task-journey__step{
    flex-basis:calc(50% - 6px);
  }
}
@media (max-width:720px){
  .task-journey{padding:16px}
  .task-journey__step{
    flex-basis:100%;
  }
  .task-journey__label{
    white-space:normal;
  }
}
</style>
