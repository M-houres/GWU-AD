<template>
  <article class="partner-tree-node" :class="{ 'partner-tree-node--clickable': clickable }">
    <button
      v-if="clickable"
      type="button"
      class="partner-tree-node__main partner-tree-node__main--button"
      @click="$emit('select', node)"
    >
      <div class="partner-tree-node__head">
        <div>
          <strong>{{ titleText }}</strong>
          <span>{{ subtitleText }}</span>
        </div>
        <b>{{ rateText }}</b>
      </div>
      <div class="partner-tree-node__chips">
        <span>{{ statusText }}</span>
        <span>直属下级 {{ Number(node.child_count || 0) }}</span>
        <span>我的客户 {{ Number(node.self_summary?.user_count || node.user_count || 0) }}</span>
        <span>团队客户 {{ Number(node.team_summary?.user_count || 0) }}</span>
      </div>
      <div class="partner-tree-node__stats">
        <div>
          <span>待结算</span>
          <strong>{{ formatFenToCny(node.pending_rebate_fen) }}</strong>
        </div>
        <div>
          <span>已结算</span>
          <strong>{{ formatFenToCny(node.settled_rebate_fen) }}</strong>
        </div>
        <div>
          <span>团队订单</span>
          <strong>{{ Number(node.subtree_summary?.order_count || 0) }}</strong>
        </div>
      </div>
    </button>
    <div v-else class="partner-tree-node__main">
      <div class="partner-tree-node__head">
        <div>
          <strong>{{ titleText }}</strong>
          <span>{{ subtitleText }}</span>
        </div>
        <b>{{ rateText }}</b>
      </div>
      <div class="partner-tree-node__chips">
        <span>{{ statusText }}</span>
        <span>直属下级 {{ Number(node.child_count || 0) }}</span>
        <span>我的客户 {{ Number(node.self_summary?.user_count || node.user_count || 0) }}</span>
        <span>团队客户 {{ Number(node.team_summary?.user_count || 0) }}</span>
      </div>
      <div class="partner-tree-node__stats">
        <div>
          <span>待结算</span>
          <strong>{{ formatFenToCny(node.pending_rebate_fen) }}</strong>
        </div>
        <div>
          <span>已结算</span>
          <strong>{{ formatFenToCny(node.settled_rebate_fen) }}</strong>
        </div>
        <div>
          <span>团队订单</span>
          <strong>{{ Number(node.subtree_summary?.order_count || 0) }}</strong>
        </div>
      </div>
    </div>

    <div v-if="Array.isArray(node.children) && node.children.length" class="partner-tree-node__children">
      <PartnerChannelTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :clickable="clickable"
        @select="$emit('select', $event)"
      />
    </div>
  </article>
</template>

<script setup>
import { computed } from "vue"

defineOptions({ name: "PartnerChannelTreeNode" })

const props = defineProps({
  node: {
    type: Object,
    required: true,
  },
  clickable: {
    type: Boolean,
    default: false,
  },
})

defineEmits(["select"])

const titleText = computed(() => `${formatLevel(props.node?.level)} · ${String(props.node?.name || "-")}`)
const subtitleText = computed(() => {
  const code = String(props.node?.channel_code || "").trim()
  const parent = String(props.node?.parent_channel_name || "").trim() || "平台直营"
  return [code, `上级 ${parent}`].filter(Boolean).join(" · ")
})
const rateText = computed(() => `${(Number(props.node?.default_rebate_rate_bp || 0) / 100).toFixed(2)}%`)
const statusText = computed(() => (String(props.node?.status || "").toLowerCase() === "active" ? "启用中" : "已停用"))

function formatLevel(value) {
  const level = Number(value || 1)
  if (level === 1) return "一级渠道"
  if (level === 2) return "二级渠道"
  if (level === 3) return "三级渠道"
  return `L${level}`
}

function formatFenToCny(value) {
  const amount = Number(value || 0) / 100
  return `¥${amount.toFixed(2)}`
}
</script>

<style scoped>
.partner-tree-node {
  display: grid;
  gap: 10px;
}

.partner-tree-node__main {
  border: 1px solid #d8e3f6;
  border-radius: 16px;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 100%);
  padding: 14px;
  display: grid;
  gap: 10px;
}

.partner-tree-node__main--button {
  width: 100%;
  text-align: left;
  cursor: pointer;
}

.partner-tree-node--clickable .partner-tree-node__main:hover {
  border-color: #9ebbf2;
  box-shadow: 0 10px 20px rgba(20, 87, 204, 0.08);
}

.partner-tree-node__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.partner-tree-node__head strong {
  display: block;
  color: #12345c;
  font-size: 15px;
}

.partner-tree-node__head span {
  display: block;
  margin-top: 4px;
  color: #6a7d99;
  font-size: 12px;
  line-height: 1.5;
}

.partner-tree-node__head b {
  color: #1658cb;
  font-size: 18px;
}

.partner-tree-node__chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.partner-tree-node__chips span {
  padding: 4px 8px;
  border-radius: 999px;
  background: #eef4ff;
  color: #4d6691;
  font-size: 12px;
}

.partner-tree-node__stats {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.partner-tree-node__stats div {
  border-radius: 12px;
  background: #f4f8ff;
  padding: 10px 12px;
}

.partner-tree-node__stats span {
  display: block;
  color: #627492;
  font-size: 12px;
}

.partner-tree-node__stats strong {
  display: block;
  margin-top: 5px;
  color: #14345f;
  font-size: 18px;
}

.partner-tree-node__children {
  position: relative;
  margin-left: 24px;
  padding-left: 18px;
  display: grid;
  gap: 10px;
}

.partner-tree-node__children::before {
  content: "";
  position: absolute;
  left: 4px;
  top: 2px;
  bottom: 2px;
  width: 2px;
  border-radius: 999px;
  background: linear-gradient(180deg, #c8d9f8 0%, #e3ebfb 100%);
}

@media (max-width: 720px) {
  .partner-tree-node__head,
  .partner-tree-node__stats {
    grid-template-columns: 1fr;
  }

  .partner-tree-node__head {
    display: grid;
  }

  .partner-tree-node__children {
    margin-left: 10px;
    padding-left: 14px;
  }
}
</style>
