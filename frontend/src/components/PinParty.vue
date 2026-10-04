<template>
  <div v-if="hasParties" class="pin">
    <template v-if="wish.status === 'fulfilled'">
      <span class="pin-executor">✅ 执行人 {{ wish.fulfilled_by || '—' }}</span>
    </template>
    <template v-else>
      <span class="pin-claimer">📌 认领人 {{ parties.claimer || '—' }}</span>
      <span v-if="parties.dual" class="pin-buyer">🛍 代买人 {{ parties.buyer }}</span>
    </template>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ wish: Object, fallback: Boolean })
const parties = computed(() => props.wish.parties || { claimer: null, buyer: null, dual: false })
// Wall / done / mine / detail all render this one component, so the pinned
// names can never diverge between views.
const hasParties = computed(() =>
  props.wish.status === 'fulfilled'
    ? !!props.wish.fulfilled_by
    : (parties.value.claimer || props.fallback))
</script>
