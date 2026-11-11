<script setup lang="ts">
import type { ChatItem } from '../../types/chat'
defineProps<{ messages: ChatItem[] }>()
</script>

<template>
  <section class="conversation">
      <article v-for="message in messages" :key="message.id" :class="message.role">
        <span>{{ message.text }}</span>
        <small v-if="message.usage && (message.usage.total > 0 || message.usage.responseMs > 0)">
          <span v-if="message.usage.total > 0">
            {{ message.usage.total }} tokens · {{ message.usage.input }} entrada ·
            {{ message.usage.output }} salida<span v-if="message.usage.thinking > 0">
              · {{ message.usage.thinking }} razonamiento</span> · sesión {{ message.usage.session }}
          </span>
          <span v-if="message.usage.responseMs > 0" :class="{ 'usage-separator': message.usage.total > 0 }">
            Tiempo de respuesta: {{ (message.usage.responseMs / 1000).toFixed(2) }} s
          </span>
        </small>
      </article>
  </section>
</template>
