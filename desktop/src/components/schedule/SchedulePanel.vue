<script setup lang="ts">
import type { AccessEntry, Reminder, Routine } from '../../services/backend'
defineProps<{ accessEntries: AccessEntry[]; reminders: Reminder[]; routines: Routine[]; scheduleBusy: boolean }>()
const reminderTitle = defineModel<string>('reminderTitle', { required: true })
const reminderAt = defineModel<string>('reminderAt', { required: true })
const reminderAction = defineModel<'notify' | 'open_access'>('reminderAction', { required: true })
const reminderAccessId = defineModel<string>('reminderAccessId', { required: true })
const routineName = defineModel<string>('routineName', { required: true })
const routineTime = defineModel<string>('routineTime', { required: true })
const routineAccessIds = defineModel<string[]>('routineAccessIds', { required: true })
const routineDays = defineModel<number[]>('routineDays', { required: true })
const emit = defineEmits<{ storeReminder: []; removeReminder: [entry: Reminder]; toggleRoutineDay: [day: number]; storeRoutine: []; removeRoutine: [entry: Routine] }>()
</script>

<template>
<div class="access-settings">
        <div class="settings-title access-heading"><div><strong>Recordatorios</strong><small>Se ejecutan localmente sin Gemini.</small></div></div>
        <div class="access-form">
          <input v-model="reminderTitle" maxlength="300" placeholder="Qué recordar o hacer" />
          <input v-model="reminderAt" type="datetime-local" />
          <select v-model="reminderAction"><option value="notify">Avisar</option><option value="open_access">Abrir acceso</option></select>
          <select v-if="reminderAction === 'open_access'" v-model="reminderAccessId"><option value="">Selecciona un acceso</option><option v-for="entry in accessEntries" :key="entry.id" :value="entry.id">{{ entry.name }}</option></select>
          <button type="button" :disabled="scheduleBusy || !reminderTitle.trim() || !reminderAt || (reminderAction === 'open_access' && !reminderAccessId)" @click="emit('storeReminder')">Crear recordatorio</button>
        </div>
        <div class="access-list">
          <div v-for="reminder in reminders.filter((item) => item.status === 'pending')" :key="reminder.id" class="access-entry"><div><strong>{{ reminder.title }}</strong><small>{{ new Date(reminder.due_at).toLocaleString() }} · {{ reminder.action_type === 'open_access' ? 'abre un acceso' : 'aviso' }}</small></div><button type="button" class="delete-key" :disabled="scheduleBusy" @click="emit('removeReminder', reminder)">Eliminar</button></div>
          <small v-if="!reminders.some((item) => item.status === 'pending')">No hay recordatorios pendientes.</small>
        </div>
      </div>

      <div class="access-settings">
        <div class="settings-title access-heading"><div><strong>Rutinas</strong><small>Abren los accesos elegidos en los días y hora indicados.</small></div></div>
        <div class="access-form">
          <input v-model="routineName" maxlength="100" placeholder="Nombre: Inicio de trabajo" />
          <input v-model="routineTime" type="time" />
          <select v-model="routineAccessIds" multiple size="4" class="access-wide" aria-label="Accesos de rutina"><option v-for="entry in accessEntries" :key="entry.id" :value="entry.id">{{ entry.name }}</option></select>
          <div class="routine-days access-wide"><button v-for="(name, day) in ['L','M','X','J','V','S','D']" :key="name" type="button" :class="{ selected: routineDays.includes(day) }" @click="emit('toggleRoutineDay', day)">{{ name }}</button></div>
          <button type="button" :disabled="scheduleBusy || !routineName.trim() || !routineAccessIds.length || !routineDays.length" @click="emit('storeRoutine')">Crear rutina</button>
        </div>
        <div class="access-list">
          <div v-for="routine in routines" :key="routine.id" class="access-entry"><div><strong>{{ routine.name }}</strong><small>{{ routine.time_of_day }} · días {{ routine.days.map((day) => ['L','M','X','J','V','S','D'][day]).join(', ') }}</small></div><button type="button" class="delete-key" :disabled="scheduleBusy" @click="emit('removeRoutine', routine)">Eliminar</button></div>
          <small v-if="routines.length === 0">Aún no hay rutinas configuradas.</small>
        </div>
      </div>
</template>
