<template>
  <div class="identity-bar">
    <label for="actor-input">我是</label>
    <input id="actor-input" v-model="identity.name" placeholder="输入你的名字（本机记住）" />
  </div>
</template>
<script setup>
import { identity } from '../identity'
</script>
