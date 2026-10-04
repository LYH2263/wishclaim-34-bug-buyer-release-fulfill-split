<template>
  <div v-if="parties.claimer || fallback" class="pin">
    <span class="pin-claimer">📌 认领人 {{ parties.claimer || '—' }}</span>
    <span v-if="parties.dual" class="pin-buyer">🛍 代买人 {{ parties.buyer }}</span>
  </div>
</template>
<script setup>
import { computed } from 'vue'
const props = defineProps({ wish: Object, fallback: Boolean })
const parties = computed(() => props.wish.parties || { claimer: null, buyer: null, dual: false })
</script>
