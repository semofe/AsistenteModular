<script setup lang="ts">
import type { MemoryEntry } from '../../services/backend'
defineProps<{ assistantName: string; memories: MemoryEntry[]; memoryBusy: boolean }>()
const memoryDraft = defineModel<string>('memoryDraft', { required: true })
const emit = defineEmits<{ storeMemory: []; removeMemory: [entry: MemoryEntry] }>()
</script>

<template>
<div class="access-settings">
        <div class="settings-title access-heading"><div><strong>Memoria de {{ assistantName }}</strong><small>También puedes decir “recuerda que…”</small></div></div>
        <div class="access-form">
          <input class="access-wide" v-model="memoryDraft" maxlength="1000" placeholder="Ejemplo: mi color favorito es el azul" @keyup.enter="emit('storeMemory')" />
          <button type="button" :disabled="memoryBusy || !memoryDraft.trim()" @click="emit('storeMemory')">Recordar</button>
        </div>
        <div class="access-list">
          <div v-for="memory in memories" :key="memory.id" class="access-entry memory-entry"><div><strong>{{ memory.content }}</strong><small>{{ new Date(memory.created_at).toLocaleString() }}</small></div><button type="button" class="delete-key" :disabled="memoryBusy" @click="emit('removeMemory', memory)">Olvidar</button></div>
          <small v-if="memories.length === 0">Aún no hay recuerdos guardados.</small>
        </div>
      </div>
</template>
