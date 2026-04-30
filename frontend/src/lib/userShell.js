import { FilePenLine, FileSearch2, Megaphone, ScanSearch } from "lucide-vue-next"
import { formatBeijingDateTime } from "./dateTime"

export const DEFAULT_HEADER_NOTICE_TEXT = "平台系统持续优化中，任务提交后请在账户中心查看处理进度。"
export const NOTICE_SEEN_STORAGE_KEY = "wuhong_user_notice_seen_key"
export const USER_SHELL_GROUP_ORDER = ["core"]

const MENU_ICON_MAP = {
  rewrite: FilePenLine,
  dedup: FileSearch2,
  detect: ScanSearch,
  promo_center: Megaphone,
}

export function mapUserShellMenuItems(items = []) {
  return items.map((item) => ({
    ...item,
    label: item.key === "promo_center" ? "推广领积分" : item.label,
    icon: MENU_ICON_MAP[item.key] || FilePenLine,
  }))
}

export function groupVisibleUserMenus(items = [], groupOrder = USER_SHELL_GROUP_ORDER) {
  return groupOrder
    .map((key) => ({
      key,
      items: items.filter((item) => item.group === key && item.visible),
    }))
    .filter((group) => group.items.length)
}

export function splitTopMenus(items = [], limit = Number.POSITIVE_INFINITY) {
  return {
    visibleTopMenus: items.slice(0, limit),
    overflowTopMenus: items.slice(limit),
  }
}

export function normalizeUserShellNotice(raw) {
  const content = String(raw?.content || raw?.header_text || DEFAULT_HEADER_NOTICE_TEXT).trim() || DEFAULT_HEADER_NOTICE_TEXT
  const title = String(raw?.title || "系统公告").trim() || "系统公告"
  const updatedAt = String(raw?.updated_at || "").trim()
  const enabled = raw?.enabled !== false
  const version = Number.parseInt(String(raw?.version ?? raw?.notice_version ?? ""), 10)
  const hasExplicitNotice = Boolean(raw && (raw.content || raw.header_text || raw.title || raw.updated_at))
  const noticeKey = Number.isFinite(version) && version > 0 ? `notice_v_${version}` : `${title}__${content}`
  return {
    enabled,
    title,
    content,
    updated_at: updatedAt,
    hasExplicitNotice,
    noticeKey,
  }
}

export function formatUserShellNoticeTime(value) {
  return formatBeijingDateTime(value, { placeholder: "", withSeconds: false })
}
