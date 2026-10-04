import { reactive, watch } from 'vue'

const KEY = 'wishclaim.actor'

export const identity = reactive({ name: localStorage.getItem(KEY) || '' })

watch(() => identity.name, (v) => {
  const n = (v || '').trim()
  if (n) localStorage.setItem(KEY, n)
  else localStorage.removeItem(KEY)
})

export const me = () => identity.name.trim()
