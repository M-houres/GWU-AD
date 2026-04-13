import { computed, onMounted, onUnmounted, ref, watch } from "vue"

const DEFAULT_BREAKPOINT = 1024

function readStoredCollapse(storageKey, defaultCollapsed) {
  if (typeof window === "undefined") return Boolean(defaultCollapsed)
  try {
    const raw = window.localStorage.getItem(storageKey)
    if (raw === "1") return true
    if (raw === "0") return false
  } catch {}
  return Boolean(defaultCollapsed)
}

function writeStoredCollapse(storageKey, collapsed) {
  if (typeof window === "undefined") return
  try {
    window.localStorage.setItem(storageKey, collapsed ? "1" : "0")
  } catch {}
}

export function useShellLayout(options = {}) {
  const {
    storageKey = "shell_layout_collapsed",
    mobileBreakpoint = DEFAULT_BREAKPOINT,
    defaultCollapsed = false,
  } = options

  const isMobile = ref(false)
  const isCollapsed = ref(readStoredCollapse(storageKey, defaultCollapsed))
  const isDrawerOpen = ref(false)

  const isCollapsedDesktop = computed(() => !isMobile.value && isCollapsed.value)

  function syncViewport() {
    if (typeof window === "undefined") return
    const nextMobile = window.innerWidth < mobileBreakpoint
    if (nextMobile !== isMobile.value) {
      isMobile.value = nextMobile
      if (nextMobile) {
        isDrawerOpen.value = false
      }
    }
  }

  function setCollapsed(nextValue) {
    const normalized = Boolean(nextValue)
    isCollapsed.value = normalized
    writeStoredCollapse(storageKey, normalized)
  }

  function toggleSidebar() {
    if (isMobile.value) {
      isDrawerOpen.value = !isDrawerOpen.value
      return
    }
    setCollapsed(!isCollapsed.value)
  }

  function openDrawer() {
    if (isMobile.value) {
      isDrawerOpen.value = true
    }
  }

  function closeDrawer() {
    isDrawerOpen.value = false
  }

  function handleKeydown(event) {
    if (event.key === "Escape") {
      closeDrawer()
    }
  }

  onMounted(() => {
    syncViewport()
    window.addEventListener("resize", syncViewport, { passive: true })
    window.addEventListener("keydown", handleKeydown)
  })

  onUnmounted(() => {
    if (typeof document !== "undefined") {
      document.body.style.overflow = ""
    }
    window.removeEventListener("resize", syncViewport)
    window.removeEventListener("keydown", handleKeydown)
  })

  watch(
    [isMobile, isDrawerOpen],
    ([mobile, drawerOpen]) => {
      if (typeof document === "undefined") return
      document.body.style.overflow = mobile && drawerOpen ? "hidden" : ""
    },
    { immediate: true }
  )

  return {
    isMobile,
    isCollapsed,
    isCollapsedDesktop,
    isDrawerOpen,
    setCollapsed,
    toggleSidebar,
    openDrawer,
    closeDrawer,
  }
}
