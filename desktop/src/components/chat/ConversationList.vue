<script setup lang="ts">
import type { ChatItem } from '../../types/chat'
defineProps<{ messages: ChatItem[] }>()
</script>

<template>
  <section class="conversation">
      <article v-for="message in messages" :key="message.id" :class="message.role">
        <span>{{ message.text }}</span>
        <small v-if="message.usage && message.usage.total > 0">
          {{ message.usage.total }} tokens · {{ message.usage.input }} entrada ·
          {{ message.usage.output }} salida<span v-if="message.usage.thinking > 0">
            · {{ message.usage.thinking }} razonamiento</span> · sesión {{ message.usage.session }}
        </small>
      </article>
  </section>
</template>
