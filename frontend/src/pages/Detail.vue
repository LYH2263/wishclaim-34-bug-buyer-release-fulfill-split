<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p>{{ w.note }}</p>
    <p class="tag">状态 {{ w.status }} · {{ w.data_quality }}</p>
    <PinParty :wish="w" fallback />
    <p class="tag">当前身份：{{ me() || '未署名（请在左上角菜单署名）' }}</p>
    <p v-if="err" class="err">{{ err }}</p>

    <input v-if="!claimed" v-model="buyer" placeholder="代买人（可选，留空则仅自己认领）" />
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button :disabled="!canClaim" @click="claim">认领锁定</button>
      <button class="ghost" :disabled="!canRelease" @click="release">释放</button>
      <button class="ghost" :disabled="!canFulfill" @click="fulfill">核销完成</button>
    </div>

    <template v-if="claimed">
      <input v-model="newName" placeholder="转让给（新认领人名字）" />
      <button class="ghost" :disabled="!canTransfer || !newName.trim()" @click="transfer">转让认领人</button>
    </template>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { identity, me } from '../identity'
import { errText } from '../errors'
import PinParty from '../components/PinParty.vue'

const props = defineProps({ id: String })
const w = ref({})
const buyer = ref('')
const newName = ref('')
const err = ref('')

const claimed = computed(() => w.value.status === 'claimed')
const isClaimer = computed(() => !!w.value.claimer && w.value.claimer === me())
const isBuyer = computed(() => !!w.value.buyer && w.value.buyer === me())
const canClaim = computed(() => !!me() && !claimed.value)
const canRelease = computed(() => claimed.value && isClaimer.value)
const canFulfill = computed(() => claimed.value && (isClaimer.value || isBuyer.value))
const canTransfer = computed(() => claimed.value && isClaimer.value)

async function load() { w.value = await api('/wishes/' + props.id) }
async function claim() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/claim', {
      method: 'POST',
      body: JSON.stringify({ claimer: identity.name, buyer: buyer.value || undefined }),
    })
    await load()
  } catch (e) { err.value = errText(e) }
}
async function release() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/release', { method: 'POST', body: JSON.stringify({ actor: identity.name }) })
    await load()
  } catch (e) { err.value = errText(e) }
}
async function fulfill() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/fulfill', { method: 'POST', body: JSON.stringify({ actor: identity.name }) })
    await load()
  } catch (e) { err.value = errText(e) }
}
async function transfer() {
  err.value = ''
  try {
    await api('/wishes/' + props.id + '/transfer', {
      method: 'POST',
      body: JSON.stringify({ actor: identity.name, new_claimer: newName.value }),
    })
    newName.value = ''
    await load()
  } catch (e) { err.value = errText(e) }
}
onMounted(load)
</script>
