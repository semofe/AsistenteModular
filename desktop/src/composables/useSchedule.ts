import { ref, type Ref } from 'vue'
import { getReminders, getRoutines, getScheduledEvents, addReminder, deleteReminder, addRoutine, deleteRoutine, type Reminder, type Routine } from '../services/backend'
import type { ChatItem } from '../types/chat'

export function useSchedule(messages: Ref<ChatItem[]>, speak: (text: string) => Promise<void>) {
  const reminders = ref<Reminder[]>([])
  const reminderTitle = ref('')
  const reminderAt = ref('')
  const reminderAction = ref<'notify' | 'open_access'>('notify')
  const reminderAccessId = ref('')
  const routines = ref<Routine[]>([])
  const routineName = ref('')
  const routineTime = ref('09:00')
  const routineAccessIds = ref<string[]>([])
  const routineDays = ref<number[]>([0, 1, 2, 3, 4, 5, 6])
  const scheduleBusy = ref(false)

  async function refreshSchedule(): Promise<void> {
    try {
      const [savedReminders, savedRoutines] = await Promise.all([getReminders(), getRoutines()])
      reminders.value = savedReminders
      routines.value = savedRoutines
    } catch (error) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Agenda: ${String(error)}` })
    }
  }

  async function pollScheduledEvents(): Promise<void> {
    try {
      const events = await getScheduledEvents()
      for (const text of events) {
        messages.value.push({ id: crypto.randomUUID(), role: 'assistant', text })
        void speak(text)
      }
    } catch { /* The backend can be starting; the next poll retries. */ }
  }

  async function storeReminder(): Promise<void> {
    if (!reminderTitle.value.trim() || !reminderAt.value) return
    scheduleBusy.value = true
    try {
      const entry = await addReminder({
        title: reminderTitle.value.trim(), due_at: new Date(reminderAt.value).toISOString(),
        action_type: reminderAction.value,
        access_id: reminderAction.value === 'open_access' ? reminderAccessId.value || null : null
      })
      reminders.value = [...reminders.value, entry].sort((a, b) => a.due_at.localeCompare(b.due_at))
      reminderTitle.value = ''; reminderAt.value = ''; reminderAccessId.value = ''
    } catch (error) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Recordatorio: ${String(error)}` })
    } finally { scheduleBusy.value = false }
  }

  async function removeReminder(entry: Reminder): Promise<void> {
    scheduleBusy.value = true
    try { await deleteReminder(entry.id); reminders.value = reminders.value.filter((item) => item.id !== entry.id) }
    catch (error) { messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Recordatorio: ${String(error)}` }) }
    finally { scheduleBusy.value = false }
  }

  function toggleRoutineDay(day: number): void {
    routineDays.value = routineDays.value.includes(day)
      ? routineDays.value.filter((item) => item !== day)
      : [...routineDays.value, day].sort()
  }

  async function storeRoutine(): Promise<void> {
    if (!routineName.value.trim() || !routineAccessIds.value.length || !routineDays.value.length) return
    scheduleBusy.value = true
    try {
      const entry = await addRoutine({ name: routineName.value.trim(), time_of_day: routineTime.value, days: routineDays.value, access_ids: routineAccessIds.value })
      routines.value = [...routines.value, entry].sort((a, b) => a.time_of_day.localeCompare(b.time_of_day))
      routineName.value = ''; routineAccessIds.value = []
    } catch (error) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Rutina: ${String(error)}` })
    } finally { scheduleBusy.value = false }
  }

  async function removeRoutine(entry: Routine): Promise<void> {
    scheduleBusy.value = true
    try { await deleteRoutine(entry.id); routines.value = routines.value.filter((item) => item.id !== entry.id) }
    catch (error) { messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Rutina: ${String(error)}` }) }
    finally { scheduleBusy.value = false }
  }


  return { reminders, reminderTitle, reminderAt, reminderAction, reminderAccessId, routines, routineName, routineTime, routineAccessIds, routineDays, scheduleBusy, refreshSchedule, pollScheduledEvents, storeReminder, removeReminder, toggleRoutineDay, storeRoutine, removeRoutine }
}
