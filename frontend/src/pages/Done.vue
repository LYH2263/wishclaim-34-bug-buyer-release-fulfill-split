<template>
  <div class="wall">
    <h1 class="serif">已完成</h1>
    <article v-for="w in rows" :key="w.id" class="card">
      <h3>{{ w.title }}</h3>
      <PinParty :wish="w" />
    </article>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import PinParty from '../components/PinParty.vue'
const rows = ref([])
onMounted(async () => { rows.value = await api('/done') })
</script>
