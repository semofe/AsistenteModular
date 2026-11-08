import { ref, type Ref } from 'vue'
import { getMemories, addMemory, deleteMemory, type MemoryEntry } from '../services/backend'
import type { ChatItem } from '../types/chat'

export function useMemory(messages: Ref<ChatItem[]>) {
  const memories = ref<MemoryEntry[]>([])
  const memoryDraft = ref('')
  const memoryBusy = ref(false)

  async function refreshMemory(): Promise<void> {
    try { memories.value = await getMemories() } catch (error) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Memoria: ${String(error)}` })
    }
  }

  async function storeMemory(): Promise<void> {
    if (!memoryDraft.value.trim()) return
    memoryBusy.value = true
    try {
      const entry = await addMemory(memoryDraft.value.trim())
      memories.value.unshift(entry)
      memoryDraft.value = ''
    } catch (error) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Memoria: ${String(error)}` })
    } finally { memoryBusy.value = false }
  }

  async function removeMemory(entry: MemoryEntry): Promise<void> {
    memoryBusy.value = true
    try {
      await deleteMemory(entry.id)
      memories.value = memories.value.filter((item) => item.id !== entry.id)
    } catch (error) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Memoria: ${String(error)}` })
    } finally { memoryBusy.value = false }
  }


  return { memories, memoryDraft, memoryBusy, refreshMemory, storeMemory, removeMemory }
}
