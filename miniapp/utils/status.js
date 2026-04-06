const TASK_STATUS_LABELS = {
  pending: "排队中",
  running: "处理中",
  completed: "已完成",
  failed: "失败",
  closed: "已关闭",
}

const ORDER_STATUS_LABELS = {
  created: "待支付",
  paid: "已支付",
  closed: "已关闭",
  refunded: "已退款",
}

function normalizeStatus(status) {
  return String(status || "").trim().toLowerCase()
}

function getTaskStatusText(status) {
  const key = normalizeStatus(status)
  return TASK_STATUS_LABELS[key] || "未知状态"
}

function getOrderStatusText(status) {
  const key = normalizeStatus(status)
  return ORDER_STATUS_LABELS[key] || "未知状态"
}

function getBizMessage(body, fallback = "请求失败") {
  if (!body) return fallback
  if (typeof body === "string") return body
  if (typeof body.message === "string" && body.message.trim()) return body.message.trim()
  if (typeof body.detail === "string" && body.detail.trim()) return body.detail.trim()
  return fallback
}

function toFriendlyError(error, fallback = "操作失败") {
  if (!error) return fallback
  if (typeof error === "string") return error
  if (typeof error.message === "string" && error.message.trim()) return error.message.trim()
  return fallback
}

function parseWxPayError(error) {
  const errMsg = String((error && error.errMsg) || (error && error.message) || "").toLowerCase()
  if (errMsg.includes("cancel")) return "你已取消支付"
  if (errMsg.includes("requestpayment")) return "支付未完成，请重试"
  return "支付调用失败，请稍后重试"
}

module.exports = {
  normalizeStatus,
  getTaskStatusText,
  getOrderStatusText,
  getBizMessage,
  toFriendlyError,
  parseWxPayError,
}
