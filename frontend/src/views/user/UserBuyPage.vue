<template>
  <UserShell title="" subtitle="" :credits="userBalanceFen" :hide-topbar="true" :hide-header-title="true" :hide-account-entry="true" @buy="noop">
    <section class="buy-page-shell">
      <BuyCreditsPanel @paid="afterPaid" />
    </section>
  </UserShell>
</template>

<script setup>
import { computed, onMounted } from "vue"

import BuyCreditsPanel from "../../components/BuyCreditsPanel.vue"
import UserShell from "../../components/UserShell.vue"
import { useUserProfile } from "../../composables/useUserProfile"
import { getUserToken } from "../../lib/session"

const { user, refreshUser } = useUserProfile()
const userBalanceFen = computed(() => {
  const value = user.value && (user.value.balance_fen ?? user.value.credits)
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

<style scoped>
.buy-page-shell{
  width:min(1560px,100%);
  margin:0 auto;
  padding:8px 0 18px;
}
</style>
