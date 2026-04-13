<template>
  <UserShell title="" subtitle="" :credits="userCredits" :hide-topbar="true" :hide-header-title="true" @buy="noop">
    <BuyCreditsPanel @paid="afterPaid" />
  </UserShell>
</template>

<script setup>
import { computed, onMounted } from "vue"

import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { getUserToken } from "../../lib/session"

const { user, refreshUser } = useUserProfile()
const userCredits = computed(() => {
  const value = user.value && user.value.credits
  return typeof value === "number" ? value : null
})

onMounted(async () => {
  if (!getUserToken()) return
  await refreshUser()
})

async function afterPaid() {
  if (getUserToken()) {
    await refreshUser()
  }
}

function noop() {}
</script>
