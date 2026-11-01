<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Avatar3D from './components/avatar/Avatar3D.vue'
import {
  getLLMConfig,
  saveLLMConfig,
  syncDiscoveredApps,
  getConversationHistory,
  type LLMConfig,
  addAccessEntry,
  addMemory,
  addReminder,
  addRoutine,
  addWebsiteShortcut,
  clearBrowserConfiguration,
  clearVoiceCache,
  deleteAccessEntry,
  deleteMemory,
  deleteReminder,
  deleteRoutine,
  deleteVoiceCredential,
  getAssistantProfile,
  getConversationPreferences,
  getFileAccessPreferences,
  getFileIndex,
  getActivationSettings,
  getBrowserConfiguration,
  getAccessEntries,
  getHealth,
  getScheduledEvents,
  getMemories,
  getReminders,
  getRoutines,
  getEdgeVoices,
  getVoiceCacheStats,
  getVoiceConfiguration,
  AssistantSocket,
  openAccessEntry,
  saveVoiceCredential,
  saveAssistantProfile,
  saveConversationPreferences,
  saveFileAccessPreferences,
  refreshFileIndex,
  saveActivationSettings,
  saveAccessSpokenName,
  saveVoicePreferences,
  saveBrowserConfiguration,
  deleteWebsiteShortcut,
  synthesizeSpeech,
  transcribeAudio,
  type AssistantState,
  type ActivationSettings,
  type AccessEntry,
  type AccessKind,
  type BrowserConfig,
  type EdgeVoice,
  type FileAccessPreferences,
  type IndexedFile,
  type ServerMessage,
  type VoiceEngine,
  type WebsiteShortcut
  , type MemoryEntry
  , type Reminder
  , type Routine
} from './services/backend'

interface ChatItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  usage?: {
    input: number
    output: number
    thinking: number
    total: number
    session: number
  }
}

const llmConfig = ref<LLMConfig>({provider: 'gemini', gemini_model: 'gemini-3.6-flash', ollama_model: 'llama3.2:1b'})
const savingLLM = ref(false)
const syncingApps = ref(false)
const modelStatus = ref('')
async function updateLLM(): Promise<void> {
  savingLLM.value = true
  try {
    llmConfig.value = await saveLLMConfig(llmConfig.value)
    configured.value = Boolean((await getHealth()).provider_configured)
    modelStatus.value = 'Modelo aplicado. Ollama requiere el servicio activo y el modelo descargado.'
  } catch (error) { modelStatus.value = String(error) }
  finally { savingLLM.value = false }
}
async function detectApps(): Promise<void> {
  syncingApps.value = true
  try {
    const added = await syncDiscoveredApps()
    await refreshAccessEntries()
    modelStatus.value = `${added} aplicaciones añadidas al catálogo.`
  } catch (error) { modelStatus.value = String(error) }
  finally { syncingApps.value = false }
}
const state = ref<AssistantState>('disconnected')
const assistantName = ref('Asistente')
const assistantNameDraft = ref('')
const wakePhrase = ref('Oye Asistente')
const wakePhrases = ref(['Oye Asistente', 'Ey Asistente', 'Oeh Asistente', 'Asistente'])
const activationEnabled = ref(true)
const activationSession = ref(false)
const inactivitySeconds = ref(120)
const savingActivation = ref(false)
const savingAssistantName = ref(false)
const configured = ref(false)
const webSearchEnabled = ref(true)
const savingConversationPreferences = ref(false)
const fileAccessPreferences = ref<FileAccessPreferences>({
  folders: [],
  extensions: ['txt', 'md', 'csv', 'json', 'docx']
})
const fileAccessFolderDraft = ref('')
const fileAccessExtensionsDraft = ref('txt, md, csv, json, docx')
const savingFileAccess = ref(false)
const indexedFiles = ref<IndexedFile[]>([])
const refreshingFileIndex = ref(false)
const input = ref('')
const voiceOutput = ref(true)
const useRvc = ref(false)
const ttsEngine = ref<VoiceEngine>('edge')
const edgeVoice = ref('es-MX-DaliaNeural')
const edgeVoices = ref<EdgeVoice[]>([])
const voiceMenuOpen = ref(false)
const voiceSearch = ref('')
const recording = ref(false)
type CredentialProvider = 'gemini' | 'elevenlabs' | 'fish' | 'custom'
const settingsOpen = ref(false)
const providerKeys = ref<Record<CredentialProvider, string>>({
  gemini: '',
  elevenlabs: '',
  fish: '',
  custom: ''
})
const credentials = ref<Record<string, boolean>>({})
const elevenVoiceId = ref('')
const fishReferenceId = ref('')
const customEndpoint = ref('')
const customVoice = ref('')
const customModel = ref('')
const cacheStats = ref({ files: 0, bytes: 0, hits: 0 })
const savingCredential = ref<CredentialProvider | null>(null)
const savingPreferences = ref(false)
const accessEntries = ref<AccessEntry[]>([])
const accessName = ref('')
const accessKind = ref<AccessKind>('application')
const accessTarget = ref('')
const accessAliases = ref('')
const accessSpokenName = ref('')
const accessBusy = ref(false)
const launcherName = ref('')
const launcherTarget = ref('')
const launcherAliases = ref('')
const browserName = ref('')
const browserWord = ref('')
const browserTarget = ref('')
const browserAliases = ref('')
const browserConfigured = ref(false)
const websiteName = ref('')
const websiteUrl = ref('')
const websiteAliases = ref('')
const websites = ref<WebsiteShortcut[]>([])
const webBusy = ref(false)
const memories = ref<MemoryEntry[]>([])
const memoryDraft = ref('')
const memoryBusy = ref(false)
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
let recorder: MediaRecorder | undefined
let recordingStream: MediaStream | undefined
let chunks: Blob[] = []
let currentAudio: HTMLAudioElement | undefined
let speechPending = false
let microphoneResumeAt = 0
let activationStream: MediaStream | undefined
let activationContext: AudioContext | undefined
let activationAnalyser: AnalyserNode | undefined
let activationFrame = 0
let activationRecorder: MediaRecorder | undefined
let activationChunks: Blob[] = []
let activationStartedAt = 0
let activationSilenceAt = 0
let activationBusy = false
let discardActivationAudio = false
let inactivityTimer: number | undefined
let schedulePollTimer: number | undefined
let removeOpenSettingsListener: (() => void) | undefined
const messages = ref<ChatItem[]>([
  { id: 'welcome', role: 'assistant', text: 'Hola. El motor local está iniciando.' }
])

const canSend = computed(() => ['idle', 'dormant'].includes(state.value) && input.value.trim().length > 0)
const regularAccessEntries = computed(() => accessEntries.value.filter((entry) => entry.close_policy !== 'window'))
const launcherEntries = computed(() => accessEntries.value.filter((entry) => entry.close_policy === 'window'))
const filteredEdgeVoices = computed(() => {
  const search = voiceSearch.value.trim().toLocaleLowerCase()
  if (!search) return edgeVoices.value
  return edgeVoices.value.filter((voice) =>
    `${voice.name} ${voice.locale} ${voice.gender}`.toLocaleLowerCase().includes(search)
  )
})
const selectedVoiceLabel = computed(() => {
  const voice = edgeVoices.value.find((item) => item.name === edgeVoice.value)
  return voice ? `${voice.locale} · ${voice.name.replace('Neural', '').split('-').at(-1)}` : edgeVoice.value
})
const accessTargetPlaceholder = computed(() =>
  accessKind.value === 'application'
    ? 'Selecciona o pega una ruta .exe o .lnk…'
    : accessKind.value === 'folder'
      ? 'Selecciona o pega la ruta de una carpeta…'
      : 'Selecciona o pega la ruta de un archivo…'
)

function selectEdgeVoice(voice: EdgeVoice): void {
  edgeVoice.value = voice.name
  voiceMenuOpen.value = false
  voiceSearch.value = ''
}

type CredentialModule = 'agent' | 'voice'

const credentialProviders: Array<{ id: CredentialProvider; name: string; detail: string; module: CredentialModule }> = [
  { id: 'gemini', name: 'Gemini', detail: 'Conversación, búsqueda y memoria semántica', module: 'agent' },
  { id: 'elevenlabs', name: 'ElevenLabs', detail: 'Generación de voz', module: 'voice' },
  { id: 'fish', name: 'Fish Audio', detail: 'Generación y clonación de voz', module: 'voice' },
  { id: 'custom', name: 'API personalizada', detail: 'Proveedor TTS compatible', module: 'voice' }
]
const agentCredentialProviders = computed(() => credentialProviders.filter((provider) => provider.module === 'agent'))
const voiceCredentialProviders = computed(() => credentialProviders.filter((provider) => provider.module === 'voice'))
const cacheLabel = computed(() =>
  `${cacheStats.value.files} audios · ${(cacheStats.value.bytes / 1024 / 1024).toFixed(1)} MB · ${cacheStats.value.hits} reutilizados`
)

async function storeProviderKey(provider: CredentialProvider): Promise<void> {
  const apiKey = providerKeys.value[provider].trim()
  if (!apiKey) return
  savingCredential.value = provider
  try {
    await saveVoiceCredential(provider, apiKey)
    credentials.value[provider] = true
    providerKeys.value[provider] = ''
    if (provider === 'gemini') configured.value = Boolean((await getHealth()).provider_configured)
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Clave de ${provider} guardada de forma segura.` })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Credencial: ${String(error)}` })
  } finally {
    savingCredential.value = null
  }
}

async function removeProviderKey(provider: CredentialProvider): Promise<void> {
  savingCredential.value = provider
  try {
    const result = await deleteVoiceCredential(provider)
    credentials.value[provider] = result.configured
    providerKeys.value[provider] = ''
    if (provider === 'gemini') configured.value = Boolean((await getHealth()).provider_configured)
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'system',
      text: result.configured
        ? `La clave guardada de ${provider} se eliminó, pero sigue definida por una variable de entorno.`
        : `Clave de ${provider} eliminada.`
    })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Credencial: ${String(error)}` })
  } finally {
    savingCredential.value = null
  }
}

async function storeConversationPreferences(): Promise<void> {
  savingConversationPreferences.value = true
  try {
    const saved = await saveConversationPreferences({ web_search_enabled: webSearchEnabled.value })
    webSearchEnabled.value = saved.web_search_enabled
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: saved.web_search_enabled ? 'Búsqueda web activada.' : 'Búsqueda web desactivada.' })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Internet: ${String(error)}` })
  } finally {
    savingConversationPreferences.value = false
  }
}

async function chooseFileAccessFolder(): Promise<void> {
  if (!window.asistenteDesktop) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: 'El selector de carpetas solo está disponible en la aplicación de escritorio.' })
    return
  }
  try {
    const folder = await window.asistenteDesktop.chooseAccessTarget('folder')
    if (folder) fileAccessFolderDraft.value = folder
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Carpetas: ${String(error)}` })
  }
}

function addFileAccessFolder(): void {
  const folder = fileAccessFolderDraft.value.trim()
  if (!folder || fileAccessPreferences.value.folders.includes(folder)) return
  fileAccessPreferences.value = { ...fileAccessPreferences.value, folders: [...fileAccessPreferences.value.folders, folder] }
  fileAccessFolderDraft.value = ''
}

function removeFileAccessFolder(folder: string): void {
  fileAccessPreferences.value = {
    ...fileAccessPreferences.value,
    folders: fileAccessPreferences.value.folders.filter((item) => item !== folder)
  }
}

async function storeFileAccessPreferences(): Promise<void> {
  savingFileAccess.value = true
  try {
    const extensions = fileAccessExtensionsDraft.value.split(',').map((value) => value.trim().replace(/^\./, '')).filter(Boolean)
    const saved = await saveFileAccessPreferences({
      folders: fileAccessPreferences.value.folders,
      extensions
    })
    fileAccessPreferences.value = saved
    fileAccessExtensionsDraft.value = saved.extensions.join(', ')
    indexedFiles.value = await getFileIndex()
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Permisos guardados e índice actualizado: ${indexedFiles.value.length} archivos.` })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Lectura de archivos: ${String(error)}` })
  } finally {
    savingFileAccess.value = false
  }
}

async function updateFileIndex(): Promise<void> {
  refreshingFileIndex.value = true
  try {
    indexedFiles.value = await refreshFileIndex()
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Índice actualizado: ${indexedFiles.value.length} archivos disponibles.` })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Índice de archivos: ${String(error)}` })
  } finally {
    refreshingFileIndex.value = false
  }
}
async function storeAssistantName(): Promise<void> {
  const name = assistantNameDraft.value.trim()
  if (!name) return
  savingAssistantName.value = true
  try {
    const profile = await saveAssistantProfile(name)
    assistantName.value = profile.name
    assistantNameDraft.value = profile.name
    wakePhrase.value = profile.wake_phrase
    document.title = profile.name
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'system',
      text: `El nombre del asistente ahora es ${profile.name}.`
    })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Nombre: ${String(error)}` })
  } finally {
    savingAssistantName.value = false
  }
}

async function chooseAccessTarget(): Promise<void> {
  if (!window.asistenteDesktop) {
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'system',
      text: 'El selector de rutas solo está disponible dentro de la aplicación de Electron.'
    })
    return
  }
  try {
    const target = await window.asistenteDesktop.chooseAccessTarget(accessKind.value)
    if (target) {
      accessTarget.value = target
      if (accessKind.value === 'application' && !accessName.value.trim()) {
        const filename = target.split(/[\\/]/).at(-1) ?? ''
        accessName.value = filename.replace(/\.(?:exe|lnk)$/i, '')
      }
    }
  } catch (error) {
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'system',
      text: `Selector de ruta: ${String(error)}`
    })
  }
}

async function chooseApplicationTarget(destination: 'launcher' | 'browser'): Promise<void> {
  if (!window.asistenteDesktop) return
  try {
    const target = await window.asistenteDesktop.chooseAccessTarget(destination === 'browser' ? 'browser' : 'application')
    if (!target) return
    const filename = target.split(/[\\/]/).at(-1)?.replace(/\.(?:exe|lnk)$/i, '') ?? ''
    if (destination === 'launcher') {
      launcherTarget.value = target
      if (!launcherName.value.trim()) launcherName.value = filename
    } else {
      browserTarget.value = target
      if (!browserName.value.trim()) browserName.value = filename
      if (!browserWord.value.trim()) browserWord.value = filename
    }
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Selector de ruta: ${String(error)}` })
  }
}

async function storeLauncher(): Promise<void> {
  if (!launcherName.value.trim() || !launcherTarget.value.trim()) return
  accessBusy.value = true
  try {
    const entry = await addAccessEntry({
      name: launcherName.value.trim(), kind: 'application', target: launcherTarget.value.trim(),
      aliases: launcherAliases.value.split(',').map((value) => value.trim()).filter(Boolean),
      spoken_name: launcherName.value.trim(), close_policy: 'window'
    })
    accessEntries.value.push(entry)
    launcherName.value = ''; launcherTarget.value = ''; launcherAliases.value = ''
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Launcher: ${String(error)}` })
  } finally { accessBusy.value = false }
}

async function refreshBrowserConfiguration(): Promise<void> {
  try {
    const config = await getBrowserConfiguration()
    websites.value = config.websites
    browserConfigured.value = Boolean(config.browser)
    if (config.browser) {
      browserName.value = config.browser.name
      browserWord.value = config.browser.activation_word
      browserTarget.value = config.browser.executable
      browserAliases.value = config.browser.aliases.join(', ')
    }
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Navegador: ${String(error)}` })
  }
}

async function storeBrowser(): Promise<void> {
  if (!browserName.value.trim() || !browserWord.value.trim() || !browserTarget.value.trim()) return
  webBusy.value = true
  try {
    const saved: BrowserConfig = await saveBrowserConfiguration({
      name: browserName.value.trim(), activation_word: browserWord.value.trim(),
      executable: browserTarget.value.trim(),
      aliases: browserAliases.value.split(',').map((value) => value.trim()).filter(Boolean)
    })
    browserConfigured.value = true
    browserName.value = saved.name; browserWord.value = saved.activation_word
    browserTarget.value = saved.executable; browserAliases.value = saved.aliases.join(', ')
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Navegador: ${String(error)}` })
  } finally { webBusy.value = false }
}

async function useSystemBrowser(): Promise<void> {
  webBusy.value = true
  try {
    await clearBrowserConfiguration()
    browserConfigured.value = false
    browserName.value = ''; browserWord.value = ''; browserTarget.value = ''; browserAliases.value = ''
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Navegador: ${String(error)}` })
  } finally { webBusy.value = false }
}

async function storeWebsite(): Promise<void> {
  if (!websiteName.value.trim() || !websiteUrl.value.trim()) return
  webBusy.value = true
  try {
    const site = await addWebsiteShortcut({
      name: websiteName.value.trim(), url: websiteUrl.value.trim(),
      aliases: websiteAliases.value.split(',').map((value) => value.trim()).filter(Boolean)
    })
    websites.value.push(site)
    websites.value.sort((a, b) => a.name.localeCompare(b.name))
    websiteName.value = ''; websiteUrl.value = ''; websiteAliases.value = ''
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Página: ${String(error)}` })
  } finally { webBusy.value = false }
}

async function removeWebsite(site: WebsiteShortcut): Promise<void> {
  webBusy.value = true
  try {
    await deleteWebsiteShortcut(site.id)
    websites.value = websites.value.filter((item) => item.id !== site.id)
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Página: ${String(error)}` })
  } finally { webBusy.value = false }
}

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

function normalizeSpeech(value: string): string {
  return value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, ' ').trim()
}

function similarity(left: string, right: string): number {
  if (left === right) return 1
  const rows = Array.from({ length: left.length + 1 }, (_, index) => index)
  for (let column = 1; column <= right.length; column += 1) {
    let diagonal = rows[0]
    rows[0] = column
    for (let row = 1; row <= left.length; row += 1) {
      const previous = rows[row]
      rows[row] = Math.min(rows[row] + 1, rows[row - 1] + 1,
        diagonal + (left[row - 1] === right[column - 1] ? 0 : 1))
      diagonal = previous
    }
  }
  return 1 - rows[left.length] / Math.max(left.length, right.length, 1)
}

function commandAfterWakePhrase(text: string): string | null {
  const tokens = normalizeSpeech(text).split(' ').filter(Boolean)
  const nameTokens = normalizeSpeech(assistantName.value).split(' ').filter(Boolean)
  if (nameTokens.length === 0) return null
  const prefixTokens = new Set(['oye', 'ey', 'oeh', 'oe'])
  const hasPrefix = prefixTokens.has(tokens[0])
  const nameStart = hasPrefix ? 1 : 0
  const spokenName = tokens.slice(nameStart, nameStart + nameTokens.length).join(' ')
  const requiredSimilarity = hasPrefix ? 0.65 : 0.80
  if (similarity(spokenName, nameTokens.join(' ')) < requiredSimilarity) return null
  return tokens.slice(nameStart + nameTokens.length).join(' ')
}

function scheduleInactivity(): void {
  window.clearTimeout(inactivityTimer)
  if (!activationEnabled.value || !activationSession.value) return
  inactivityTimer = window.setTimeout(() => {
    if (settingsOpen.value || ['processing', 'speaking', 'transcribing', 'listening'].includes(state.value) || activationBusy) {
      scheduleInactivity()
      return
    }
    activationSession.value = false
    state.value = 'dormant'
    void window.asistenteDesktop?.hideAssistant()
  }, inactivitySeconds.value * 1000)
}

function activateSession(showWindow = true): void {
  activationSession.value = true
  if (state.value === 'dormant') state.value = 'idle'
  if (showWindow) void window.asistenteDesktop?.showAssistant()
  scheduleInactivity()
}

function sendRecognizedText(text: string): void {
  const clean = text.trim()
  if (!clean) return
  activateSession()
  messages.value.push({ id: crypto.randomUUID(), role: 'user', text: clean })
  try {
    socket.sendText(clean)
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: String(error) })
  }
}

async function processActivationAudio(blob: Blob): Promise<void> {
  if (blob.size < 500) return
  activationBusy = true
  const previousState = state.value
  if (activationSession.value) state.value = 'transcribing'
  try {
    const context = activationSession.value ? 'active' : 'dormant'
    const text = await transcribeAudio(blob, context)
    if (!text.trim()) return
    const wakeCommand = commandAfterWakePhrase(text)
    if (!activationSession.value) {
      if (wakeCommand === null) return
      activateSession()
      if (wakeCommand) sendRecognizedText(`${wakePhrase.value} ${wakeCommand}`)
      return
    }
    if (wakeCommand === null) sendRecognizedText(text)
    else if (wakeCommand) sendRecognizedText(`${wakePhrase.value} ${wakeCommand}`)
  } catch {
    if (activationSession.value) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: 'No pude transcribir el audio de activación.' })
    }
  } finally {
    activationBusy = false
    if (!['processing', 'speaking'].includes(state.value)) {
      state.value = activationSession.value ? 'idle' : 'dormant'
    } else if (previousState === 'dormant' && !activationSession.value) {
      state.value = 'dormant'
    }
  }
}

function cancelActivationUtterance(): void {
  if (!activationRecorder) return
  discardActivationAudio = true
  const activeRecorder = activationRecorder
  activationRecorder = undefined
  activeRecorder.stop()
}

function monitorActivation(): void {
  if (!activationAnalyser || !activationEnabled.value) return
  const values = new Uint8Array(activationAnalyser.fftSize)
  activationAnalyser.getByteTimeDomainData(values)
  const rms = Math.sqrt(values.reduce((sum, value) => {
    const sample = (value - 128) / 128
    return sum + sample * sample
  }, 0) / values.length)
  const now = Date.now()
  const available = !speechPending && now >= microphoneResumeAt && !activationBusy && !recording.value && ['idle', 'dormant'].includes(state.value)
  if (available && rms >= 0.025 && !activationRecorder && activationStream) {
    activationChunks = []
    activationRecorder = new MediaRecorder(activationStream)
    discardActivationAudio = false
    activationStartedAt = now
    activationSilenceAt = 0
    activationRecorder.ondataavailable = (event) => {
      if (event.data.size) activationChunks.push(event.data)
    }
    const mimeType = activationRecorder.mimeType || 'audio/webm'
    activationRecorder.onstop = () => {
      if (discardActivationAudio) {
        discardActivationAudio = false
        activationChunks = []
        return
      }
      const blob = new Blob(activationChunks, { type: mimeType })
      void processActivationAudio(blob)
    }
    activationRecorder.start()
  }
  if (activationRecorder) {
    if (rms >= 0.018) activationSilenceAt = 0
    else if (!activationSilenceAt) activationSilenceAt = now
    const enoughSilence = activationSilenceAt > 0 && now - activationSilenceAt >= 850
    if ((enoughSilence && now - activationStartedAt >= 350) || now - activationStartedAt >= 9000) {
      const activeRecorder = activationRecorder
      activationRecorder = undefined
      activeRecorder.stop()
    }
  }
}

async function startActivationListener(): Promise<void> {
  if (!activationEnabled.value || activationStream) return
  try {
    activationStream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true }
    })
    activationContext = new AudioContext()
    await activationContext.resume()
    activationAnalyser = activationContext.createAnalyser()
    activationAnalyser.fftSize = 512
    activationContext.createMediaStreamSource(activationStream).connect(activationAnalyser)
    activationFrame = window.setInterval(monitorActivation, 80)
    activateSession(false)
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Activación por voz: ${String(error)}` })
  }
}

function stopActivationListener(): void {
  window.clearInterval(activationFrame)
  cancelActivationUtterance()
  activationStream?.getTracks().forEach((track) => track.stop())
  activationStream = undefined
  void activationContext?.close()
  activationContext = undefined
  activationAnalyser = undefined
  window.clearTimeout(inactivityTimer)
}

async function storeActivationSettings(): Promise<void> {
  savingActivation.value = true
  try {
    const saved: ActivationSettings = await saveActivationSettings({
      enabled: activationEnabled.value,
      inactivity_seconds: inactivitySeconds.value,
      show_on_wake: true,
      hide_on_timeout: true
    })
    wakePhrase.value = saved.wake_phrase
    wakePhrases.value = saved.wake_phrases
    inactivitySeconds.value = saved.inactivity_seconds
    if (saved.enabled) await startActivationListener()
    else {
      stopActivationListener()
      activationSession.value = true
      state.value = 'idle'
    }
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Activación: ${String(error)}` })
  } finally { savingActivation.value = false }
}

async function refreshAccessEntries(): Promise<void> {
  try {
    accessEntries.value = await getAccessEntries()
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Accesos: ${String(error)}` })
  }
}

async function storeAccessEntry(): Promise<void> {
  if (!accessName.value.trim() || !accessTarget.value.trim()) return
  accessBusy.value = true
  try {
    const entry = await addAccessEntry({
      name: accessName.value.trim(),
      kind: accessKind.value,
      target: accessTarget.value.trim(),
      aliases: accessAliases.value.split(',').map((alias) => alias.trim()).filter(Boolean),
      spoken_name: accessSpokenName.value.trim() || accessName.value.trim()
    })
    accessEntries.value = [...accessEntries.value, entry].sort((a, b) => a.name.localeCompare(b.name))
    accessName.value = ''
    accessTarget.value = ''
    accessAliases.value = ''
    accessSpokenName.value = ''
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Acceso ${entry.name} añadido.` })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Accesos: ${String(error)}` })
  } finally {
    accessBusy.value = false
  }
}

async function storeAccessSpokenName(entry: AccessEntry): Promise<void> {
  const spokenName = entry.spoken_name.trim()
  if (!spokenName) return
  accessBusy.value = true
  try {
    const saved = await saveAccessSpokenName(entry.id, spokenName)
    accessEntries.value = accessEntries.value.map((item) => item.id === saved.id ? saved : item)
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Pronunciación de ${saved.name} guardada.` })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Accesos: ${String(error)}` })
  } finally {
    accessBusy.value = false
  }
}

async function removeAccessEntry(entry: AccessEntry): Promise<void> {
  accessBusy.value = true
  try {
    await deleteAccessEntry(entry.id)
    accessEntries.value = accessEntries.value.filter((item) => item.id !== entry.id)
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Accesos: ${String(error)}` })
  } finally {
    accessBusy.value = false
  }
}

async function launchAccessEntry(entry: AccessEntry): Promise<void> {
  try {
    const result = await openAccessEntry(entry.id)
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: result.message })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Accesos: ${String(error)}` })
  }
}

async function emptyVoiceCache(): Promise<void> {
  try {
    cacheStats.value = await clearVoiceCache()
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: 'Caché de voz eliminada.' })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Caché: ${String(error)}` })
  }
}

async function storeVoicePreferences(): Promise<void> {
  savingPreferences.value = true
  try {
    await saveVoicePreferences({
      engine: ttsEngine.value,
      edge_voice: edgeVoice.value,
      elevenlabs_voice_id: elevenVoiceId.value.trim(),
      fish_reference_id: fishReferenceId.value.trim(),
      custom_endpoint: customEndpoint.value.trim(),
      custom_voice: customVoice.value.trim(),
      custom_model: customModel.value.trim(),
      rvc_enabled: useRvc.value,
      voice_output: voiceOutput.value
    })
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: 'Configuración de voz guardada.' })
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Configuración: ${String(error)}` })
  } finally {
    savingPreferences.value = false
  }
}

async function speak(text: string, fragments?: string[]): Promise<void> {
  if (!voiceOutput.value) return
  const spokenText = text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[*_#`>~-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!/[\p{L}\p{N}]{2}/u.test(spokenText)) return
  speechPending = true
  cancelActivationUtterance()
  try {
    state.value = 'speaking'
    const voice = ttsEngine.value === 'edge'
      ? edgeVoice.value
      : ttsEngine.value === 'elevenlabs'
        ? elevenVoiceId.value
        : ttsEngine.value === 'fish'
          ? fishReferenceId.value
          : ttsEngine.value === 'custom'
            ? customVoice.value
            : undefined
    const result = await synthesizeSpeech(
      spokenText,
      useRvc.value,
      ttsEngine.value,
      voice,
      ttsEngine.value === 'elevenlabs'
        ? 'eleven_flash_v2_5'
        : ttsEngine.value === 'fish'
          ? 's2-pro'
          : customModel.value || undefined,
      ttsEngine.value === 'custom' ? customEndpoint.value : undefined,
      fragments
    )
    if (result.fallbackFrom) {
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'system',
        text: `${result.fallbackFrom} no estuvo disponible; se utilizó ${result.provider}.`
      })
    }
    try {
      cacheStats.value = await getVoiceCacheStats()
    } catch {
      if (result.cacheHit) cacheStats.value.hits += 1
    }
    const url = URL.createObjectURL(result.blob)
    currentAudio = new Audio(url)
    await currentAudio.play()
    await new Promise<void>((resolve) => {
      if (!currentAudio) return resolve()
      currentAudio.onended = () => resolve()
      currentAudio.onerror = () => resolve()
    })
    URL.revokeObjectURL(url)
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Voz: ${String(error)}` })
  } finally {
    speechPending = false
    microphoneResumeAt = Date.now() + 900
    state.value = 'idle'
    scheduleInactivity()
  }
}

function handleMessage(message: ServerMessage): void {
  if (message.type === 'assistant_state') {
    const nextState = String(message.payload.state) as AssistantState
    if (['processing', 'speaking'].includes(nextState)) cancelActivationUtterance()
    if (!speechPending) state.value = nextState
  } else if (message.type === 'assistant_text') {
    if (activationEnabled.value) activateSession(false)
    const usage = (message.payload.usage ?? {}) as Record<string, unknown>
    messages.value.push({
      id: message.request_id ?? crypto.randomUUID(),
      role: 'assistant',
      text: String(message.payload.text ?? ''),
      usage: {
        input: Number(usage.input_tokens ?? 0),
        output: Number(usage.output_tokens ?? 0),
        thinking: Number(usage.thinking_tokens ?? 0),
        total: Number(usage.total_tokens ?? 0),
        session: Number(usage.session_tokens ?? 0)
      }
    })
    const fragments = Array.isArray(message.payload.speech_fragments)
      ? message.payload.speech_fragments.map(String)
      : undefined
    const speech = speak(String(message.payload.text ?? ''), fragments)
    const clientAction = String(message.payload.client_action ?? '')
    if (clientAction === 'quit_assistant') {
      void speech.finally(() => window.asistenteDesktop?.quitAssistant())
    } else if (clientAction === 'shutdown_pc') {
      void speech.finally(() => window.asistenteDesktop?.shutdownPc())
    } else if (clientAction === 'hide_assistant') {
      void speech.finally(() => {
        activationSession.value = false
        state.value = activationEnabled.value ? 'dormant' : 'idle'
        window.clearTimeout(inactivityTimer)
        return window.asistenteDesktop?.hideAssistant()
      })
    }
  } else if (message.type === 'conversation_cleared') {
    messages.value = [{ id: crypto.randomUUID(), role: 'system', text: 'Conversación reiniciada.' }]
  } else if (message.type === 'error') {
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'system',
      text: `Error: ${String(message.payload.message ?? 'desconocido')}`
    })
  }
}

const socket = new AssistantSocket(handleMessage, (connected) => {
  state.value = connected
    ? activationEnabled.value && !activationSession.value ? 'dormant' : 'idle'
    : 'disconnected'
})

function send(): void {
  const text = input.value.trim()
  if (!text || !canSend.value) return
  input.value = ''
  sendRecognizedText(text)
}

async function toggleRecording(): Promise<void> {
  if (recording.value) {
    recorder?.stop()
    recording.value = false
    return
  }
  if (!['idle', 'dormant'].includes(state.value)) return
  activateSession()
  cancelActivationUtterance()
  try {
    recordingStream = await navigator.mediaDevices.getUserMedia({ audio: true })
    chunks = []
    recorder = new MediaRecorder(recordingStream)
    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunks.push(event.data)
    }
    recorder.onstop = async () => {
      recordingStream?.getTracks().forEach((track) => track.stop())
      state.value = 'transcribing'
      try {
        const blob = new Blob(chunks, { type: recorder?.mimeType || 'audio/webm' })
        const text = await transcribeAudio(blob)
        input.value = text
        state.value = 'idle'
        send()
      } catch (error) {
        messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Micrófono: ${String(error)}` })
        state.value = 'idle'
      }
    }
    recorder.start()
    recording.value = true
    state.value = 'listening'
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Micrófono: ${String(error)}` })
    state.value = 'idle'
  }
}

onMounted(async () => {
  removeOpenSettingsListener = window.asistenteDesktop?.onOpenSettings(() => {
    settingsOpen.value = true
    window.clearTimeout(inactivityTimer)
  })
  socket.connect()
  try {
    const profile = await getAssistantProfile()
    assistantName.value = profile.name
    assistantNameDraft.value = profile.name
    wakePhrase.value = profile.wake_phrase
    document.title = profile.name
    messages.value[0].text = `Hola, soy ${profile.name}. El motor local está iniciando.`
  } catch {
    assistantNameDraft.value = assistantName.value
  }
  try {
    llmConfig.value = await getLLMConfig()
    const history = await getConversationHistory()
    if (history.length) messages.value = history.map(m => ({id: crypto.randomUUID(), role: m.role, text: m.content}))
    const health = await getHealth()
    configured.value = Boolean(health.provider_configured)
  } catch {
    configured.value = false
  }
  try {
    const activation = await getActivationSettings()
    activationEnabled.value = activation.enabled
    inactivitySeconds.value = activation.inactivity_seconds
    wakePhrase.value = activation.wake_phrase
    wakePhrases.value = activation.wake_phrases
    if (activation.enabled) await startActivationListener()
    else activationSession.value = true
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Activación: ${String(error)}` })
  }
  try {
    edgeVoices.value = await getEdgeVoices()
  } catch {
    edgeVoices.value = [
      { name: 'es-MX-DaliaNeural', locale: 'es-MX', gender: 'Female', display_name: 'Dalia' },
      { name: 'es-ES-ElviraNeural', locale: 'es-ES', gender: 'Female', display_name: 'Elvira' }
    ]
  }
  try {
    const voiceConfiguration = await getVoiceConfiguration()
    credentials.value = voiceConfiguration.credentials
    cacheStats.value = voiceConfiguration.cache
    const preferences = voiceConfiguration.preferences
    ttsEngine.value = preferences.engine
    edgeVoice.value = preferences.edge_voice
    elevenVoiceId.value = preferences.elevenlabs_voice_id
    fishReferenceId.value = preferences.fish_reference_id
    customEndpoint.value = preferences.custom_endpoint
    customVoice.value = preferences.custom_voice
    customModel.value = preferences.custom_model
    useRvc.value = preferences.rvc_enabled
    voiceOutput.value = preferences.voice_output
  } catch {
    credentials.value = {}
  }
  await refreshAccessEntries()
  await refreshBrowserConfiguration()
  try {
    const saved = await getFileAccessPreferences()
    fileAccessPreferences.value = saved
    fileAccessExtensionsDraft.value = saved.extensions.join(', ')
    indexedFiles.value = await getFileIndex()
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Lectura de archivos: ${String(error)}` })
  }
  await refreshMemory()
  await refreshSchedule()
  schedulePollTimer = window.setInterval(() => { void pollScheduledEvents() }, 10_000)
})
onBeforeUnmount(() => {
  removeOpenSettingsListener?.()
  socket.close()
  recorder?.stop()
  recordingStream?.getTracks().forEach((track) => track.stop())
  currentAudio?.pause()
  window.clearInterval(schedulePollTimer)
  stopActivationListener()
})
</script>

<template>
  <main class="shell">
    <section class="avatar-stage">
      <Avatar3D :state="state" :assistant-name="assistantName" />
    </section>

    <section class="conversation main-conversation" aria-label="Conversación actual">
      <article v-for="message in messages" :key="message.id" :class="message.role">
        <span>{{ message.text }}</span>
        <small v-if="message.usage && message.usage.total > 0">
          {{ message.usage.total }} tokens · {{ message.usage.input }} entrada ·
          {{ message.usage.output }} salida<span v-if="message.usage.thinking > 0">
            · {{ message.usage.thinking }} razonamiento</span> · sesión {{ message.usage.session }}
        </small>
      </article>
    </section>

    <section v-if="settingsOpen" class="settings-panel">
      <section class="credential-module">
        <strong>Modelo de conversación</strong>
        <select v-model="llmConfig.provider"><option value="gemini">Gemini</option><option value="ollama">Ollama local</option></select>
        <input v-if="llmConfig.provider === 'gemini'" v-model="llmConfig.gemini_model" placeholder="Modelo Gemini" />
        <input v-else v-model="llmConfig.ollama_model" placeholder="Modelo Ollama" />
        <button type="button" :disabled="savingLLM" @click="updateLLM">{{ savingLLM ? 'Aplicando…' : 'Aplicar modelo' }}</button>
        <button type="button" :disabled="syncingApps" @click="detectApps">{{ syncingApps ? 'Buscando…' : 'Detectar aplicaciones instaladas' }}</button>
        <small>{{ modelStatus }}</small>
        <small>Archivos: puedes buscar, crear TXT, CSV, Word, Excel, PowerPoint y PDF; copiar, mover y renombrar. Las modificaciones requieren confirmación.</small>
      </section>
      <div class="settings-panel-header">
        <div><strong>Configuración</strong><small>Personaliza el funcionamiento de {{ assistantName }}</small></div>
        <div class="settings-panel-actions">
          <button type="button" title="Nueva conversación" aria-label="Nueva conversación" @click="socket.clearConversation">↻</button>
          <button type="button" title="Cerrar configuración" aria-label="Cerrar configuración" @click="settingsOpen = false">×</button>
        </div>
      </div>
      <div class="assistant-name-setting">
        <div>
          <strong>Nombre del asistente</strong>
          <small>Frase de activación: “{{ wakePhrase }}”</small>
        </div>
        <div>
          <input v-model="assistantNameDraft" maxlength="40" placeholder="Nombre" />
          <button
            type="button"
            :disabled="savingAssistantName || !assistantNameDraft.trim()"
            @click="storeAssistantName"
          >{{ savingAssistantName ? 'Guardando…' : 'Aplicar' }}</button>
        </div>
      </div>
      <div class="activation-settings">
        <div>
          <strong>Activación por voz</strong>
          <small>Frases dinámicas con el nombre actual</small>
        </div>
        <label><input v-model="activationEnabled" type="checkbox" /> Escuchar en segundo plano</label>
        <label>
          Ocultar después de
          <input v-model.number="inactivitySeconds" type="number" min="30" max="1800" step="30" />
          segundos
        </label>
        <button type="button" :disabled="savingActivation" @click="storeActivationSettings">
          {{ savingActivation ? 'Guardando…' : 'Guardar activación' }}
        </button>
        <small>Frases actuales: {{ wakePhrases.join(' · ') }}</small>
      </div>
      <div class="settings-title">
        <div><strong>Claves API</strong><small>Se guardan de forma segura en el Administrador de credenciales de Windows</small></div>
      </div>
      <section class="credential-module">
        <div class="credential-module-heading">
          <strong>Claves API del agente</strong>
          <small>Necesarias para conversar, usar la búsqueda web y la memoria semántica.</small>
        </div>
        <div v-for="provider in agentCredentialProviders" :key="provider.id" class="api-provider">
          <div class="provider-name">
            <strong>{{ provider.name }}</strong>
            <small>{{ provider.detail }}</small>
          </div>
          <span class="credential-state" :class="{ configured: credentials[provider.id] }">
            {{ credentials[provider.id] ? 'Configurada' : 'Sin clave' }}
          </span>
          <input
            v-model="providerKeys[provider.id]"
            type="password"
            :placeholder="credentials[provider.id] ? 'Escribe otra clave para reemplazarla' : 'API key'"
            autocomplete="new-password"
          />
          <button
            type="button"
            :disabled="savingCredential !== null || providerKeys[provider.id].trim().length < 8"
            @click="storeProviderKey(provider.id)"
          >{{ savingCredential === provider.id ? '…' : 'Guardar' }}</button>
          <button
            type="button"
            class="delete-key"
            :disabled="savingCredential !== null || !credentials[provider.id]"
            title="Eliminar clave"
            @click="removeProviderKey(provider.id)"
          >Eliminar</button>
        </div>
      </section>
      <section class="credential-module">
        <div class="credential-module-heading">
          <strong>Claves API de voz</strong>
          <small>Solo necesitas configurar el proveedor de voz que elijas.</small>
        </div>
        <div v-for="provider in voiceCredentialProviders" :key="provider.id" class="api-provider">
          <div class="provider-name">
            <strong>{{ provider.name }}</strong>
            <small>{{ provider.detail }}</small>
          </div>
          <span class="credential-state" :class="{ configured: credentials[provider.id] }">
            {{ credentials[provider.id] ? 'Configurada' : 'Sin clave' }}
          </span>
          <input
            v-model="providerKeys[provider.id]"
            type="password"
            :placeholder="credentials[provider.id] ? 'Escribe otra clave para reemplazarla' : 'API key'"
            autocomplete="new-password"
          />
          <button
            type="button"
            :disabled="savingCredential !== null || providerKeys[provider.id].trim().length < 8"
            @click="storeProviderKey(provider.id)"
          >{{ savingCredential === provider.id ? '…' : 'Guardar' }}</button>
          <button
            type="button"
            class="delete-key"
            :disabled="savingCredential !== null || !credentials[provider.id]"
            title="Eliminar clave"
            @click="removeProviderKey(provider.id)"
          >Eliminar</button>
        </div>
      </section>

      <div class="access-settings file-access-settings">
        <div class="settings-title access-heading">
          <div><strong>Lectura de archivos</strong><small>Asistente Modular solo leerá archivos dentro de estas carpetas y con los tipos indicados.</small></div>
        </div>
        <div class="target-picker">
          <input v-model="fileAccessFolderDraft" placeholder="Carpeta autorizada para lectura" />
          <button type="button" @click="chooseFileAccessFolder">Examinar</button>
        </div>
        <button class="add-file-folder" type="button" :disabled="!fileAccessFolderDraft.trim()" @click="addFileAccessFolder">Añadir carpeta</button>
        <div class="file-folder-list">
          <div v-for="folder in fileAccessPreferences.folders" :key="folder" class="file-folder-entry">
            <span :title="folder">{{ folder }}</span>
            <button type="button" class="delete-key" :disabled="savingFileAccess" @click="removeFileAccessFolder(folder)">Quitar</button>
          </div>
          <small v-if="fileAccessPreferences.folders.length === 0">No hay carpetas autorizadas: Asistente Modular no puede leer ningún archivo todavía.</small>
        </div>
        <label class="file-extensions">
          Tipos permitidos
          <input v-model="fileAccessExtensionsDraft" maxlength="300" placeholder="txt, md, csv, json, docx" />
          <small>Escribe extensiones separadas por comas, sin punto. Disponibles: txt, md, csv, json y docx.</small>
        </label>
        <button type="button" :disabled="savingFileAccess" @click="storeFileAccessPreferences">
          {{ savingFileAccess ? 'Guardando…' : 'Guardar permisos de lectura' }}
        </button>
        <div class="file-index-heading">
          <div><strong>Índice local</strong><small>{{ indexedFiles.length }} archivos autorizados por nombre.</small></div>
          <button type="button" :disabled="refreshingFileIndex || savingFileAccess" @click="updateFileIndex">{{ refreshingFileIndex ? 'Actualizando…' : 'Actualizar archivos' }}</button>
        </div>
        <div v-if="indexedFiles.length" class="indexed-file-list">
          <span v-for="file in indexedFiles.slice(0, 8)" :key="file.path" :title="file.path">{{ file.name }}</span>
          <small v-if="indexedFiles.length > 8">y {{ indexedFiles.length - 8 }} más</small>
        </div>
        <small class="file-reading-help">Luego puedes decir “Resume el informe de robótica” sin escribir la ruta. Actualiza el índice si agregas, renombras o eliminas archivos.</small>
      </div>

      <div class="access-settings">
        <div class="settings-title access-heading">
          <div><strong>Accesos permitidos</strong><small>Aplicaciones, archivos y carpetas que el asistente puede abrir</small></div>
        </div>
        <div class="access-form">
          <input v-model="accessName" maxlength="80" placeholder="Nombre, por ejemplo: Steam" />
          <select v-model="accessKind">
            <option value="application">Aplicación</option>
            <option value="file">Archivo</option>
            <option value="folder">Carpeta</option>
          </select>
          <div class="target-picker">
            <input v-model="accessTarget" :placeholder="accessTargetPlaceholder" />
            <button type="button" @click="chooseAccessTarget">Examinar</button>
          </div>
          <input class="access-wide" v-model="accessAliases" placeholder="Alias separados por comas: steam, juegos" />
          <input class="access-wide" v-model="accessSpokenName" placeholder="Nombre pronunciado (opcional)" />
          <button
            type="button"
            :disabled="accessBusy || !accessName.trim() || !accessTarget.trim()"
            @click="storeAccessEntry"
          >Añadir acceso</button>
        </div>
        <div class="access-list">
          <div v-for="entry in regularAccessEntries" :key="entry.id" class="access-entry">
            <div>
              <strong>{{ entry.name }}</strong>
              <small>{{ entry.kind }} · {{ entry.aliases.join(', ') || 'sin alias' }}</small>
              <span :title="entry.target">{{ entry.target }}</span>
              <div class="spoken-name-editor">
                <input v-model="entry.spoken_name" maxlength="120" aria-label="Nombre pronunciado" />
                <button type="button" :disabled="accessBusy || !entry.spoken_name.trim()" @click="storeAccessSpokenName(entry)">Voz</button>
              </div>
            </div>
            <button type="button" title="Probar acceso" @click="launchAccessEntry(entry)">Abrir</button>
            <button type="button" class="delete-key" :disabled="accessBusy" @click="removeAccessEntry(entry)">Eliminar</button>
          </div>
          <small v-if="regularAccessEntries.length === 0">Aún no hay accesos configurados.</small>
        </div>
      </div>

      <div class="access-settings">
        <div class="settings-title access-heading">
          <div><strong>Launchers de juegos</strong><small>Al decir “cierra”, Asistente Modular cierra la ventana sin matar el proceso</small></div>
        </div>
        <div class="access-form">
          <input v-model="launcherName" maxlength="80" placeholder="Nombre, por ejemplo: Steam" />
          <input v-model="launcherAliases" placeholder="Alias: steam, vapor" />
          <div class="target-picker">
            <input v-model="launcherTarget" placeholder="Ruta del launcher .exe o .lnk" />
            <button type="button" @click="chooseApplicationTarget('launcher')">Examinar</button>
          </div>
          <button type="button" :disabled="accessBusy || !launcherName.trim() || !launcherTarget.trim()" @click="storeLauncher">Añadir launcher</button>
        </div>
        <div class="access-list">
          <div v-for="entry in launcherEntries" :key="entry.id" class="access-entry">
            <div>
              <strong>{{ entry.name }}</strong>
              <small>cierre de ventana · {{ entry.aliases.join(', ') || 'sin alias' }}</small>
              <span :title="entry.target">{{ entry.target }}</span>
            </div>
            <button type="button" title="Probar launcher" @click="launchAccessEntry(entry)">Abrir</button>
            <button type="button" class="delete-key" :disabled="accessBusy" @click="removeAccessEntry(entry)">Eliminar</button>
          </div>
          <small v-if="launcherEntries.length === 0">Aún no hay launchers configurados.</small>
        </div>
      </div>

      <div class="access-settings">
        <div class="settings-title access-heading">
          <div><strong>Navegador de Asistente Modular</strong><small>Solo uno; sin configuración usa el predeterminado de Windows</small></div>
          <span class="credential-state" :class="{ configured: browserConfigured }">{{ browserConfigured ? 'Configurado' : 'Predeterminado' }}</span>
        </div>
        <div class="access-form">
          <input v-model="browserName" maxlength="80" placeholder="Nombre: Firefox" />
          <input v-model="browserWord" maxlength="80" placeholder="Palabra: firefox" />
          <div class="target-picker">
            <input v-model="browserTarget" placeholder="Ruta del navegador .exe" />
            <button type="button" @click="chooseApplicationTarget('browser')">Examinar</button>
          </div>
          <input class="access-wide" v-model="browserAliases" placeholder="Alias: fire fox, navegador" />
          <div class="settings-buttons">
            <button type="button" :disabled="webBusy || !browserName.trim() || !browserWord.trim() || !browserTarget.trim()" @click="storeBrowser">Guardar navegador</button>
            <button type="button" class="delete-key" :disabled="webBusy || !browserConfigured" @click="useSystemBrowser">Usar Windows</button>
          </div>
        </div>

        <div class="settings-title access-heading subsection-heading">
          <div><strong>Accesos a páginas</strong><small>Nombre, enlace y palabras que Asistente Modular reconocerá</small></div>
        </div>
        <div class="access-form">
          <input v-model="websiteName" maxlength="80" placeholder="Nombre: YouTube" />
          <input v-model="websiteAliases" placeholder="Alias: you tube, videos" />
          <input class="access-wide" v-model="websiteUrl" maxlength="2000" placeholder="https://www.youtube.com" />
          <button type="button" :disabled="webBusy || !websiteName.trim() || !websiteUrl.trim()" @click="storeWebsite">Añadir página</button>
        </div>
        <div class="access-list">
          <div v-for="site in websites" :key="site.id" class="access-entry website-entry">
            <div>
              <strong>{{ site.name }}</strong>
              <small>{{ site.aliases.join(', ') || 'sin alias' }}</small>
              <span :title="site.url">{{ site.url }}</span>
            </div>
            <button type="button" class="delete-key" :disabled="webBusy" @click="removeWebsite(site)">Eliminar</button>
          </div>
          <small v-if="websites.length === 0">Aún no hay páginas configuradas.</small>
        </div>
      </div>

      <div v-if="!configured" class="notice">
        Gemini aún no tiene una clave configurada. Puedes probar la conexión y añadirla después.
      </div>

      <div class="access-settings">
        <div class="settings-title access-heading"><div><strong>Memoria de {{ assistantName }}</strong><small>También puedes decir “recuerda que…”</small></div></div>
        <div class="access-form">
          <input class="access-wide" v-model="memoryDraft" maxlength="1000" placeholder="Ejemplo: mi color favorito es el azul" @keyup.enter="storeMemory" />
          <button type="button" :disabled="memoryBusy || !memoryDraft.trim()" @click="storeMemory">Recordar</button>
        </div>
        <div class="access-list">
          <div v-for="memory in memories" :key="memory.id" class="access-entry memory-entry"><div><strong>{{ memory.content }}</strong><small>{{ new Date(memory.created_at).toLocaleString() }}</small></div><button type="button" class="delete-key" :disabled="memoryBusy" @click="removeMemory(memory)">Olvidar</button></div>
          <small v-if="memories.length === 0">Aún no hay recuerdos guardados.</small>
        </div>
      </div>

      <div class="access-settings">
        <div class="settings-title access-heading"><div><strong>Recordatorios</strong><small>Se ejecutan localmente sin Gemini.</small></div></div>
        <div class="access-form">
          <input v-model="reminderTitle" maxlength="300" placeholder="Qué recordar o hacer" />
          <input v-model="reminderAt" type="datetime-local" />
          <select v-model="reminderAction"><option value="notify">Avisar</option><option value="open_access">Abrir acceso</option></select>
          <select v-if="reminderAction === 'open_access'" v-model="reminderAccessId"><option value="">Selecciona un acceso</option><option v-for="entry in accessEntries" :key="entry.id" :value="entry.id">{{ entry.name }}</option></select>
          <button type="button" :disabled="scheduleBusy || !reminderTitle.trim() || !reminderAt || (reminderAction === 'open_access' && !reminderAccessId)" @click="storeReminder">Crear recordatorio</button>
        </div>
        <div class="access-list">
          <div v-for="reminder in reminders.filter((item) => item.status === 'pending')" :key="reminder.id" class="access-entry"><div><strong>{{ reminder.title }}</strong><small>{{ new Date(reminder.due_at).toLocaleString() }} · {{ reminder.action_type === 'open_access' ? 'abre un acceso' : 'aviso' }}</small></div><button type="button" class="delete-key" :disabled="scheduleBusy" @click="removeReminder(reminder)">Eliminar</button></div>
          <small v-if="!reminders.some((item) => item.status === 'pending')">No hay recordatorios pendientes.</small>
        </div>
      </div>

      <div class="access-settings">
        <div class="settings-title access-heading"><div><strong>Rutinas</strong><small>Abren los accesos elegidos en los días y hora indicados.</small></div></div>
        <div class="access-form">
          <input v-model="routineName" maxlength="100" placeholder="Nombre: Inicio de trabajo" />
          <input v-model="routineTime" type="time" />
          <select v-model="routineAccessIds" multiple size="4" class="access-wide" aria-label="Accesos de rutina"><option v-for="entry in accessEntries" :key="entry.id" :value="entry.id">{{ entry.name }}</option></select>
          <div class="routine-days access-wide"><button v-for="(name, day) in ['L','M','X','J','V','S','D']" :key="name" type="button" :class="{ selected: routineDays.includes(day) }" @click="toggleRoutineDay(day)">{{ name }}</button></div>
          <button type="button" :disabled="scheduleBusy || !routineName.trim() || !routineAccessIds.length || !routineDays.length" @click="storeRoutine">Crear rutina</button>
        </div>
        <div class="access-list">
          <div v-for="routine in routines" :key="routine.id" class="access-entry"><div><strong>{{ routine.name }}</strong><small>{{ routine.time_of_day }} · días {{ routine.days.map((day) => ['L','M','X','J','V','S','D'][day]).join(', ') }}</small></div><button type="button" class="delete-key" :disabled="scheduleBusy" @click="removeRoutine(routine)">Eliminar</button></div>
          <small v-if="routines.length === 0">Aún no hay rutinas configuradas.</small>
        </div>
      </div>

      <div class="settings-title voice-heading">
        <div><strong>Voz</strong><small>Motor, modelo y caché de las respuestas habladas</small></div>
      </div>
      <div class="voice-options">
      <label><input v-model="voiceOutput" type="checkbox" /> Respuesta hablada</label>
      <label><input v-model="useRvc" type="checkbox" /> Voz Miku (RVC)</label>
      <select v-model="ttsEngine" aria-label="Motor de voz" @change="voiceMenuOpen = false">
        <option value="edge">Edge TTS</option>
        <option value="elevenlabs">ElevenLabs</option>
        <option value="fish">Fish Audio</option>
        <option value="custom">API personalizada</option>
        <option value="kokoro">Kokoro local</option>
      </select>
      <div v-if="ttsEngine === 'edge'" class="voice-picker">
        <button type="button" class="voice-picker-button" @click="voiceMenuOpen = !voiceMenuOpen">
          <span>{{ selectedVoiceLabel }}</span><b>⌄</b>
        </button>
        <div v-if="voiceMenuOpen" class="voice-menu">
          <input v-model="voiceSearch" type="search" placeholder="Buscar voz o país…" />
          <div class="voice-list">
            <button
              v-for="voice in filteredEdgeVoices"
              :key="voice.name"
              type="button"
              :class="{ selected: voice.name === edgeVoice }"
              @click="selectEdgeVoice(voice)"
            >
              <span>{{ voice.name.replace('Neural', '').split('-').at(-1) }}</span>
              <small>{{ voice.locale }} · {{ voice.gender === 'Female' ? 'Femenina' : 'Masculina' }}</small>
            </button>
          </div>
        </div>
      </div>
      <div v-if="ttsEngine === 'elevenlabs'" class="provider-settings">
        <input v-model="elevenVoiceId" placeholder="Voice ID de ElevenLabs" />
      </div>
      <div v-if="ttsEngine === 'fish'" class="provider-settings">
        <input v-model="fishReferenceId" placeholder="Reference ID de Fish Audio" />
      </div>
      <div v-if="ttsEngine === 'custom'" class="provider-settings custom-provider">
        <input v-model="customEndpoint" placeholder="URL HTTPS del endpoint" />
        <input v-model="customVoice" placeholder="Voz" />
        <input v-model="customModel" placeholder="Modelo" />
      </div>
      <div class="cache-status">
        <span>Caché: {{ cacheLabel }}</span>
        <div>
          <button type="button" :disabled="savingPreferences" @click="storeVoicePreferences">
            {{ savingPreferences ? 'Guardando…' : 'Guardar ajustes' }}
          </button>
          <button type="button" @click="emptyVoiceCache">Vaciar caché</button>
        </div>
      </div>
      </div>

      <div class="settings-title history-heading">
        <div><strong>Actividad reciente</strong><small>Mensajes y consumo de la sesión actual</small></div>
      </div>
      <section class="conversation settings-conversation">
        <article v-for="message in messages" :key="message.id" :class="message.role">
          <span>{{ message.text }}</span>
          <small v-if="message.usage && message.usage.total > 0">
            {{ message.usage.total }} tokens · {{ message.usage.input }} entrada ·
            {{ message.usage.output }} salida<span v-if="message.usage.thinking > 0">
              · {{ message.usage.thinking }} razonamiento</span> · sesión {{ message.usage.session }}
          </small>
        </article>
      </section>
    </section>

    <form @submit.prevent="send">
      <button
        class="microphone"
        :class="{ recording }"
        type="button"
        :disabled="state !== 'idle' && !recording"
        :aria-label="recording ? 'Detener grabación' : 'Hablar'"
        @click="toggleRecording"
      >{{ recording ? '■' : '●' }}</button>
      <input v-model="input" autocomplete="off" :placeholder="`Escribe algo para ${assistantName}…`" />
      <button class="send" :disabled="!canSend" aria-label="Enviar">➜</button>
    </form>
  </main>
</template>

<style>
:root { color-scheme: dark; font-family: Inter, Segoe UI, sans-serif; background: transparent; color: #eef2ff; }
* { box-sizing: border-box; }
html, body, #app { background: transparent; }
body { margin: 0; min-width: 320px; min-height: 100vh; overflow: hidden; }
button, input { font: inherit; }
.shell { position: relative; height: 100vh; display: flex; flex-direction: column; gap: 6px; padding: 6px; overflow: hidden; background: transparent; }
.avatar-stage { position: relative; min-height: 0; flex: 1; overflow: hidden; -webkit-app-region: drag; }
.settings-panel { position: absolute; z-index: 20; inset: 12px; overflow-y: auto; padding: 15px; border: 1px solid #ffffff24; border-radius: 20px; background: #11172af7; box-shadow: 0 18px 55px #000a; backdrop-filter: blur(18px); }
.settings-panel-header { position: sticky; z-index: 8; top: -15px; display: flex; align-items: flex-start; justify-content: space-between; margin: -15px -15px 12px; padding: 15px; border-bottom: 1px solid #ffffff17; background: #11172af2; backdrop-filter: blur(18px); }
.settings-panel-header > div:first-child { display: flex; flex-direction: column; gap: 3px; }
.settings-panel-header small { color: #7f89aa; font-size: .68rem; }
.settings-panel-header button { width: 32px; height: 32px; border: 0; border-radius: 9px; color: #cbd5e1; background: #ffffff0d; font-size: 1.2rem; cursor: pointer; }
.settings-panel-actions { display: flex; gap: 6px; }
.assistant-name-setting { display: flex; flex-direction: column; gap: 8px; padding-bottom: 12px; }
.assistant-name-setting > div:first-child { display: flex; flex-direction: column; gap: 3px; }
.assistant-name-setting small { color: #7f89aa; font-size: .68rem; }
.assistant-name-setting > div:last-child { display: grid; grid-template-columns: 1fr auto; gap: 7px; }
.assistant-name-setting input { padding: 7px 9px; border: 1px solid #ffffff17; border-radius: 8px; color: #dbe2ff; background: #090e1c; }
.assistant-name-setting button { padding: 6px 10px; border: 0; border-radius: 8px; color: white; background: #6d63df; cursor: pointer; }
.assistant-name-setting button:disabled { opacity: .35; cursor: default; }
.activation-settings { display: flex; flex-direction: column; gap: 8px; padding: 12px 0; border-top: 1px solid #ffffff1f; }
.activation-settings > div { display: flex; flex-direction: column; gap: 3px; }
.activation-settings small { color: #7f89aa; font-size: .68rem; }
.activation-settings label { display: flex; align-items: center; gap: 7px; color: #cbd5e1; font-size: .76rem; }
.activation-settings input[type='number'] { width: 82px; padding: 6px 8px; border: 1px solid #ffffff17; border-radius: 8px; background: #090e1c; }
.activation-settings button { padding: 7px 10px; border: 0; border-radius: 8px; color: white; background: #6d63df; cursor: pointer; }
.settings-title { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 10px; }
.settings-title > div { display: flex; flex-direction: column; gap: 3px; }
.settings-title small, .provider-name small { color: #7f89aa; font-size: .68rem; }
.settings-title button { border: 0; color: #aab3d5; background: transparent; font-size: 1.25rem; cursor: pointer; }
.credential-module { display: flex; flex-direction: column; gap: 2px; padding: 12px 0; border-top: 1px solid #ffffff1f; }
.credential-module-heading { display: flex; flex-direction: column; gap: 3px; padding-bottom: 4px; }
.credential-module-heading strong { color: #dbe2ff; font-size: .82rem; }
.credential-module-heading small { color: #7f89aa; font-size: .68rem; line-height: 1.35; }
.api-provider { display: grid; grid-template-columns: minmax(110px, .8fr) auto; gap: 7px 10px; padding: 10px 0; border-top: 1px solid #ffffff0d; }
.provider-name { display: flex; flex-direction: column; gap: 2px; font-size: .8rem; }
.credential-state { align-self: center; color: #fbbf24; font-size: .68rem; }
.credential-state.configured { color: #52e0a1; }
.api-provider input { grid-column: 1 / -1; padding: 7px 9px; border: 1px solid #ffffff17; border-radius: 8px; color: #dbe2ff; background: #090e1c; }
.api-provider button { padding: 6px 9px; border: 0; border-radius: 8px; color: white; background: #6d63df; cursor: pointer; }
.api-provider button.delete-key { color: #fda4af; background: #ffffff0d; }
.api-provider button:disabled { opacity: .35; cursor: default; }
.access-settings { margin-top: 14px; padding-top: 12px; border-top: 1px solid #ffffff1f; }
.access-heading { margin-bottom: 8px; }
.file-access-settings { display: flex; flex-direction: column; gap: 8px; }
.add-file-folder { align-self: flex-start; padding: 6px 9px; border: 0; border-radius: 8px; color: white; background: #6d63df; cursor: pointer; }
.add-file-folder:disabled { opacity: .35; cursor: default; }
.file-folder-list { display: flex; flex-direction: column; gap: 6px; }
.file-folder-list > small, .file-reading-help, .file-extensions small { color: #7f89aa; font-size: .68rem; line-height: 1.4; }
.file-folder-entry { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center; padding: 7px 9px; border: 1px solid #ffffff12; border-radius: 8px; background: #090e1c; }
.file-folder-entry span { overflow: hidden; color: #cbd5e1; font-size: .72rem; text-overflow: ellipsis; white-space: nowrap; }
.file-folder-entry button { padding: 4px 7px; border: 0; border-radius: 7px; color: #fda4af; background: #ffffff0d; cursor: pointer; font-size: .68rem; }
.file-extensions { display: flex; flex-direction: column; gap: 4px; color: #cbd5e1; font-size: .76rem; }
.file-extensions input { padding: 7px 9px; border: 1px solid #ffffff17; border-radius: 8px; color: #dbe2ff; background: #090e1c; }
.file-access-settings > button:last-of-type { padding: 7px 10px; border: 0; border-radius: 8px; color: white; background: #6d63df; cursor: pointer; }
.file-access-settings > button:last-of-type:disabled { opacity: .35; cursor: default; }
.file-index-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding-top: 3px; }
.file-index-heading > div { display: flex; flex-direction: column; gap: 2px; }
.file-index-heading strong { color: #dbe2ff; font-size: .76rem; }
.file-index-heading small { color: #7f89aa; font-size: .67rem; }
.file-index-heading button { padding: 5px 8px; border: 0; border-radius: 7px; color: #cbd5e1; background: #ffffff0d; cursor: pointer; font-size: .68rem; }
.file-index-heading button:disabled { opacity: .35; cursor: default; }
.indexed-file-list { display: flex; flex-wrap: wrap; gap: 5px; }
.indexed-file-list span { max-width: 100%; overflow: hidden; padding: 4px 7px; border-radius: 999px; color: #b9c3e6; background: #ffffff0d; font-size: .66rem; text-overflow: ellipsis; white-space: nowrap; }
.indexed-file-list small { align-self: center; color: #7f89aa; font-size: .66rem; }
.access-form { display: grid; grid-template-columns: 1fr auto; gap: 7px; }
.access-form input, .access-form select { padding: 7px 9px; border: 1px solid #ffffff17; border-radius: 8px; color: #dbe2ff; background: #090e1c; }
.target-picker { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr auto; gap: 7px; }
.target-picker input { overflow: hidden; text-overflow: ellipsis; }
.access-form > .access-wide { grid-column: 1 / -1; }
.access-form button, .access-entry button { padding: 6px 9px; border: 0; border-radius: 8px; color: white; background: #6d63df; cursor: pointer; }
.access-form > button { grid-column: 1 / -1; }
.settings-buttons { grid-column: 1 / -1; display: grid; grid-template-columns: 1fr 1fr; gap: 7px; }
.subsection-heading { margin-top: 16px; padding-top: 12px; border-top: 1px solid #ffffff0d; }
.website-entry { grid-template-columns: 1fr auto; }
.access-form button:disabled, .access-entry button:disabled { opacity: .35; cursor: default; }
.access-list { display: flex; flex-direction: column; gap: 6px; margin-top: 10px; }
.access-list > small { color: #7f89aa; }
.access-entry { display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 6px; padding: 8px; border-radius: 9px; background: #090e1c; }
.access-entry > div { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.access-entry strong { font-size: .76rem; }
.access-entry small { color: #8791b4; font-size: .65rem; }
.access-entry span { overflow: hidden; color: #687290; font-size: .61rem; text-overflow: ellipsis; white-space: nowrap; }
.access-entry .spoken-name-editor { display: grid; grid-template-columns: 1fr auto; gap: 5px; margin-top: 4px; }
.spoken-name-editor input { padding: 5px 7px; border: 1px solid #ffffff17; border-radius: 7px; color: #dbe2ff; background: #11172a; font-size: .68rem; }
.spoken-name-editor button { padding: 4px 7px; font-size: .67rem; }
.access-entry button.delete-key { color: #fda4af; background: #ffffff0d; }
.memory-entry { grid-template-columns: 1fr auto; }
.routine-days { display: flex; gap: 5px; }
.routine-days button { flex: 1; padding: 6px 0; color: #aab3d5; background: #ffffff0d; }
.routine-days button.selected { color: white; background: #6d63df; }
.notice { padding: 11px 13px; border: 1px solid #fbbf2440; border-radius: 12px; background: #fbbf2410; color: #fde68a; font-size: .82rem; }
.conversation { min-height: 0; flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 10px; padding: 4px 2px; }
.main-conversation { flex: 0 1 190px; max-height: 190px; padding: 10px; border: 1px solid #ffffff1a; border-radius: 15px; background: #0b1024d9; box-shadow: 0 10px 30px #0005; -webkit-app-region: no-drag; }
.settings-conversation { max-height: 260px; padding: 8px; border: 1px solid #ffffff0d; border-radius: 12px; background: #090e1c80; }
.voice-heading, .history-heading { margin-top: 16px; padding-top: 14px; border-top: 1px solid #ffffff1f; }
article { max-width: 86%; padding: 11px 13px; border-radius: 15px; line-height: 1.42; font-size: .93rem; }
article span { display: block; }
article small { display: block; margin-top: 8px; padding-top: 7px; border-top: 1px solid #ffffff12; color: #aab3d5; font-size: .69rem; line-height: 1.3; }
.conversation article small span { display: inline; }
article.assistant { align-self: flex-start; background: #171e35; border-bottom-left-radius: 5px; }
article.user { align-self: flex-end; background: #5c55c7; border-bottom-right-radius: 5px; }
article.system { align-self: center; color: #aab3d5; font-size: .8rem; background: transparent; }
.voice-options { position: relative; display: flex; flex-wrap: wrap; align-items: center; gap: 9px 16px; color: #aab3d5; font-size: .76rem; z-index: 5; }
.voice-options label { display: flex; align-items: center; gap: 5px; }
.voice-options input { accent-color: #7c70ee; }
.voice-options select { max-width: 150px; padding: 5px 7px; border: 1px solid #ffffff17; border-radius: 8px; color: #dbe2ff; background: #11172a; }
.voice-picker { position: relative; min-width: 150px; }
.voice-picker-button { display: flex; align-items: center; justify-content: space-between; width: 100%; padding: 6px 9px; border: 1px solid #ffffff17; border-radius: 8px; color: #dbe2ff; background: #11172a; cursor: pointer; }
.voice-picker-button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.voice-menu { position: absolute; top: calc(100% + 6px); right: 0; width: 255px; padding: 8px; border: 1px solid #ffffff1f; border-radius: 12px; background: #11172a; box-shadow: 0 14px 40px #0008; }
.voice-menu > input { width: 100%; padding: 8px 9px; border: 1px solid #ffffff17; border-radius: 8px; background: #090e1c; }
.voice-list { max-height: 190px; overflow-y: auto; margin-top: 7px; }
.voice-list button { display: flex; justify-content: space-between; align-items: center; width: 100%; padding: 8px; border: 0; border-radius: 7px; color: #dbe2ff; background: transparent; cursor: pointer; text-align: left; }
.voice-list button:hover, .voice-list button.selected { background: #6d63df33; }
.voice-list button small { color: #8791b4; font-size: .67rem; }
.provider-settings, .cache-status { display: flex; align-items: center; gap: 7px; width: 100%; }
.provider-settings input { flex: 1; min-width: 100px; padding: 6px 8px; border: 1px solid #ffffff17; border-radius: 8px; color: #dbe2ff; background: #11172a; }
.custom-provider { flex-wrap: wrap; }
.cache-status button { padding: 6px 9px; border: 0; border-radius: 8px; color: white; background: #6d63df; cursor: pointer; }
.cache-status { justify-content: space-between; color: #7f89aa; font-size: .68rem; }
.cache-status > div { display: flex; gap: 6px; }
.cache-status button { padding: 4px 7px; background: #ffffff0d; color: #aab3d5; }
form, .settings-panel { -webkit-app-region: no-drag; }
form { display: grid; grid-template-columns: auto 1fr auto; gap: 9px; padding: 8px; border: 1px solid #ffffff24; background: #11172ae8; border-radius: 16px; box-shadow: 0 10px 28px #0006; backdrop-filter: blur(14px); }
input { min-width: 0; border: 0; outline: 0; color: inherit; background: transparent; padding: 8px; }
form button { width: 39px; height: 39px; border: 0; border-radius: 12px; color: white; cursor: pointer; }
form .send { background: #6d63df; }
form .microphone { color: #fda4af; background: #ffffff0d; font-size: .72rem; }
form .microphone.recording { color: white; background: #e04f70; animation: pulse 1s infinite; }
form button:disabled { opacity: .35; cursor: default; }
@keyframes pulse { 50% { opacity: .55; transform: scale(.96); } }
</style>
