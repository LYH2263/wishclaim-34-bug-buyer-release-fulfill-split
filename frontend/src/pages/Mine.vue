<template>
  <div class="wall">
    <h1 class="serif">我的认领</h1>
    <p v-if="!me()" class="tag">先点左上角 ☰ 菜单署名，就能看到你认领或代买的单子。</p>
    <template v-else>
      <p class="tag">当前身份：{{ me() }}（含认领与代买）</p>
      <article v-for="w in rows" :key="w.id" class="card">
        <h3>{{ w.title }}</h3>
        <span class="tag">{{ w.status }} · 到期 {{ w.expires_at }}</span>
        <PinParty :wish="w" />
      </article>
    </template>
  </div>
</template>
<script setup>
import { ref, watch, onMounted } from 'vue'
import { api } from '../api'
import { identity, me } from '../identity'
import PinParty from '../components/PinParty.vue'
const rows = ref([])
async function load() {
  if (!me()) { rows.value = []; return }
  rows.value = await api('/mine?actor=' + encodeURIComponent(me()))
}
watch(() => identity.name, load)
onMounted(load)
</script>
