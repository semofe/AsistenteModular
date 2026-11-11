<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Avatar3D from './components/avatar/Avatar3D.vue'
import type { ChatItem } from './types/chat'
import { useMemory } from './composables/useMemory'
import { useSchedule } from './composables/useSchedule'
import ConversationList from './components/chat/ConversationList.vue'
import MemoryPanel from './components/memory/MemoryPanel.vue'
import SchedulePanel from './components/schedule/SchedulePanel.vue'

import {
  getLLMConfig,
  saveLLMConfig,
  syncDiscoveredApps,
  getConversationHistory,
  type LLMConfig,
  addAccessEntry,
  addWebsiteShortcut,
  clearBrowserConfiguration,
  clearVoiceCache,
  deleteAccessEntry,
  deleteVoiceCredential,
  getAssistantProfile,
  getConversationPreferences,
  getFileAccessPreferences,
  getFileIndex,
  getActivationSettings,
  getBrowserConfiguration,
  getAccessEntries,
  getHealth,
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
} from './services/backend'


const llmConfig = ref<LLMConfig>({provider: 'gemini', gemini_model: 'gemini-3.6-flash', ollama_model: 'llama3.2:1b', llama_cpp_model: 'Qwen3-8B-64k-Josiefied-Uncensored-NEO-Max-D_AU-Q4_K_M-imat'})
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
const microphoneStorageKey = 'asistente.microphone'
const selectedMicrophone = ref(localStorage.getItem(microphoneStorageKey) ?? '')
const microphones = ref<MediaDeviceInfo[]>([])
const detectingMicrophones = ref(false)
const microphoneError = ref('')
const selectedMicrophoneMissing = computed(() => Boolean(selectedMicrophone.value)
  && !microphones.value.some(device => device.deviceId === selectedMicrophone.value))
type CredentialProvider = 'gemini' | 'elevenlabs' | 'fish' | 'custom'
const settingsOpen = ref(false)
const settingsSections = [
  { id: 'general', label: 'General' },
  { id: 'model', label: 'Modelo y claves' },
  { id: 'voice', label: 'Voz' },
  { id: 'apps', label: 'Aplicaciones' },
  { id: 'files', label: 'Archivos' },
  { id: 'web', label: 'Navegador y web' },
  { id: 'memory', label: 'Memoria y rutinas' },
  { id: 'activity', label: 'Actividad' }
] as const
type SettingsSection = typeof settingsSections[number]['id']
const activeSettingsSection = ref<SettingsSection>('general')
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
let recorder: MediaRecorder | undefined
let recordingStream: MediaStream | undefined
let chunks: Blob[] = []
let currentAudio: HTMLAudioElement | undefined
let speechPending = false
let speechQueue = Promise.resolve()
let speechAbortController: AbortController | undefined
let speechVersion = 0
const activeRequestId = ref<string | null>(null)
let microphoneResumeAt = 0
let activationStream: MediaStream | undefined
let activationListenerVersion = 0
let activationContext: AudioContext | undefined
let activationAnalyser: AnalyserNode | undefined
let activationFrame = 0
let activationRecorder: MediaRecorder | undefined
let activationChunks: Blob[] = []
let activationStartedAt = 0
let activationSilenceAt = 0
let activationBusy = false
let lastActivationError = ''
let discardActivationAudio = false
let inactivityTimer: number | undefined
let schedulePollTimer: number | undefined
let removeOpenSettingsListener: (() => void) | undefined
const messages = ref<ChatItem[]>([
  { id: 'welcome', role: 'assistant', text: 'Hola. El motor local está iniciando.' }
])

const { memories, memoryDraft, memoryBusy, refreshMemory, storeMemory, removeMemory } = useMemory(messages)

const { reminders, reminderTitle, reminderAt, reminderAction, reminderAccessId, routines, routineName, routineTime, routineAccessIds, routineDays, scheduleBusy, refreshSchedule, pollScheduledEvents, storeReminder, removeReminder, toggleRoutineDay, storeRoutine, removeRoutine } = useSchedule(messages, speak)

const canSend = computed(() => ['idle', 'dormant'].includes(state.value) && input.value.trim().length > 0)
const canStop = computed(() => state.value === 'processing' || state.value === 'speaking' || speechPending)
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
    activeRequestId.value = socket.sendText(clean)
  } catch (error) {
    messages.value.push({ id: crypto.randomUUID(), role: 'system', text: String(error) })
  }
}

async function processActivationAudio(blob: Blob): Promise<void> {
  if (blob.size < 500) return
  activationBusy = true
  if (activationSession.value) state.value = 'transcribing'
  try {
    const context = activationSession.value ? 'active' : 'dormant'
    const text = await transcribeAudio(blob, context)
    lastActivationError = ''
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
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    if (detail !== lastActivationError) {
      lastActivationError = detail
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Transcripción de voz: ${detail}` })
    }
  } finally {
    activationBusy = false
    if (state.value === 'transcribing') {
      state.value = activationSession.value ? 'idle' : 'dormant'
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

async function openMicrophone(audio: MediaTrackConstraints = {}): Promise<MediaStream> {
  const deviceId = selectedMicrophone.value
  if (deviceId) {
    try {
      return await navigator.mediaDevices.getUserMedia({ audio: { ...audio, deviceId: { exact: deviceId } } })
    } catch (error) {
      if (!(error instanceof DOMException) || !['NotFoundError', 'OverconstrainedError', 'NotReadableError'].includes(error.name)) throw error
    }
  }
  return navigator.mediaDevices.getUserMedia({ audio })
}

async function refreshMicrophones(): Promise<void> {
  const devices = await navigator.mediaDevices?.enumerateDevices() ?? []
  microphones.value = devices.filter(device =>
    device.kind === 'audioinput' && device.deviceId && !['default', 'communications'].includes(device.deviceId)
  )
}

async function detectMicrophones(): Promise<void> {
  detectingMicrophones.value = true
  microphoneError.value = ''
  let stream: MediaStream | undefined
  try {
    if (!activationStream) stream = await openMicrophone()
    await refreshMicrophones()
  } catch {
    microphoneError.value = 'No pude detectar los micrófonos. Revisa el permiso de micrófono en Windows.'
  } finally {
    stream?.getTracks().forEach(track => track.stop())
    detectingMicrophones.value = false
  }
}

async function restartActivationMicrophone(): Promise<void> {
  stopActivationListener()
  await startActivationListener(false)
}

async function changeMicrophone(event: Event): Promise<void> {
  selectedMicrophone.value = (event.target as HTMLSelectElement).value
  localStorage.setItem(microphoneStorageKey, selectedMicrophone.value)
  microphoneError.value = ''
  if (activationEnabled.value) await restartActivationMicrophone()
}

async function handleMicrophoneDeviceChange(): Promise<void> {
  const wasMissing = selectedMicrophoneMissing.value
  try {
    await refreshMicrophones()
  } catch {
    return
  }
  if (activationEnabled.value && wasMissing !== selectedMicrophoneMissing.value) {
    await restartActivationMicrophone()
  }
}

async function startActivationListener(initializeSession = true): Promise<void> {
  if (!activationEnabled.value || activationStream) return
  const version = ++activationListenerVersion
  let stream: MediaStream | undefined
  let context: AudioContext | undefined
  try {
    stream = await openMicrophone({ echoCancellation: true, noiseSuppression: true, autoGainControl: true })
    if (version !== activationListenerVersion) return
    context = new AudioContext()
    await context.resume()
    if (version !== activationListenerVersion) return
    const analyser = context.createAnalyser()
    analyser.fftSize = 512
    context.createMediaStreamSource(stream).connect(analyser)
    activationStream = stream
    activationContext = context
    activationAnalyser = analyser
    activationFrame = window.setInterval(monitorActivation, 80)
    stream.getAudioTracks()[0]?.addEventListener('ended', () => {
      if (activationStream === stream) void restartActivationMicrophone()
    }, { once: true })
    if (initializeSession) activateSession(false)
    else scheduleInactivity()
    void refreshMicrophones().catch(() => {})
  } catch (error) {
    if (version === activationListenerVersion) {
      messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Activación por voz: ${String(error)}` })
    }
  } finally {
    if (stream !== activationStream) {
      stream?.getTracks().forEach(track => track.stop())
      void context?.close()
    }
  }
}

function stopActivationListener(): void {
  activationListenerVersion++
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

async function playResponseAudio(blob: Blob): Promise<void> {
  const url = URL.createObjectURL(blob)
  const audio = new Audio(url)
  currentAudio = audio
  const events = new AbortController()
  let watchdog: number | undefined
  try {
    await new Promise<void>((resolve, reject) => {
      const resetWatchdog = (milliseconds: number) => {
        window.clearTimeout(watchdog)
        watchdog = window.setTimeout(() => reject(new Error('La reproducción de voz se quedó detenida.')), milliseconds)
      }
      const options = { once: true, signal: events.signal }
      audio.addEventListener('ended', () => resolve(), options)
      audio.addEventListener('pause', () => resolve(), options)
      audio.addEventListener('error', () => reject(new Error('No pude reproducir la respuesta de voz.')), options)
      audio.addEventListener('playing', () => {
        resetWatchdog(Number.isFinite(audio.duration) ? Math.max(15000, (audio.duration + 5) * 1000) : 60000)
      }, options)
      resetWatchdog(15000)
      void audio.play().catch(reject)
    })
  } finally {
    events.abort()
    window.clearTimeout(watchdog)
    audio.pause()
    currentAudio = undefined
    URL.revokeObjectURL(url)
  }
}

function speak(text: string, fragments?: string[]): Promise<void> {
  const version = speechVersion
  const response = speechQueue.then(() => version === speechVersion ? speakResponse(text, fragments, version) : undefined)
  speechQueue = response.catch(() => {})
  return response
}

function stopCurrentResponse(): void {
  if (activeRequestId.value) socket.cancelResponse(activeRequestId.value)
  activeRequestId.value = null
  speechVersion++
  speechAbortController?.abort()
  speechAbortController = undefined
  currentAudio?.pause()
  speechQueue = Promise.resolve()
  speechPending = false
  if (state.value === 'processing' || state.value === 'speaking') state.value = activationEnabled.value && !activationSession.value ? 'dormant' : 'idle'
  scheduleInactivity()
}

async function speakResponse(text: string, fragments: string[] | undefined, version: number): Promise<void> {
  if (!voiceOutput.value) return
  const spokenText = text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/[*_#`>~-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
  if (!/[\p{L}\p{N}]{2}/u.test(spokenText)) return
  speechPending = true
  const controller = new AbortController()
  speechAbortController = controller
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
      fragments,
      controller.signal
    )
    if (version !== speechVersion) return
    if (result.fallbackFrom) {
      messages.value.push({
        id: crypto.randomUUID(),
        role: 'system',
        text: `${result.fallbackFrom} no estuvo disponible; se utilizó ${result.provider}.`
      })
    }
    void getVoiceCacheStats().then(stats => {
      cacheStats.value = stats
    }).catch(() => {
      if (result.cacheHit) cacheStats.value.hits += 1
    })
    await playResponseAudio(result.blob)
  } catch (error) {
    if (!(error instanceof DOMException && error.name === 'AbortError')) messages.value.push({ id: crypto.randomUUID(), role: 'system', text: `Voz: ${String(error)}` })
  } finally {
    if (speechAbortController === controller) speechAbortController = undefined
    if (version === speechVersion) speechPending = false
    microphoneResumeAt = Date.now() + 900
    if (state.value === 'speaking') {
      state.value = activationEnabled.value && !activationSession.value ? 'dormant' : 'idle'
    }
    scheduleInactivity()
  }
}

function handleMessage(message: ServerMessage): void {
  if (message.type === 'assistant_state') {
    if (message.request_id && activeRequestId.value && message.request_id !== activeRequestId.value) return
    const nextState = String(message.payload.state) as AssistantState
    if (['processing', 'speaking'].includes(nextState)) cancelActivationUtterance()
    if (!speechPending) state.value = nextState
  } else if (message.type === 'assistant_text') {
    if (message.request_id !== activeRequestId.value) return
    activeRequestId.value = null
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
        session: Number(usage.session_tokens ?? 0),
        responseMs: Number(usage.response_time_ms ?? 0)
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
  } else if (message.type === 'response_cancelled') {
    activeRequestId.value = null
    if (!speechPending) state.value = activationEnabled.value && !activationSession.value ? 'dormant' : 'idle'
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
    recordingStream = await openMicrophone()
    void refreshMicrophones().catch(() => {})
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
  navigator.mediaDevices?.addEventListener('devicechange', handleMicrophoneDeviceChange)
  void refreshMicrophones().catch(() => {})
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
  navigator.mediaDevices?.removeEventListener('devicechange', handleMicrophoneDeviceChange)
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

    <ConversationList class="main-conversation" aria-label="Conversación actual" :messages="messages" />

    <section v-if="settingsOpen" class="settings-panel" aria-labelledby="settings-heading">
      <div class="settings-panel-header">
        <div><h1 id="settings-heading">Configuración</h1><small>Personaliza el funcionamiento de {{ assistantName }}</small></div>
        <div class="settings-panel-actions">
          <button type="button" title="Nueva conversación" aria-label="Nueva conversación" @click="socket.clearConversation">↻</button>
          <button type="button" title="Cerrar configuración" aria-label="Cerrar configuración" @click="settingsOpen = false">×</button>
        </div>
      </div>
      <div class="settings-layout">
        <nav class="settings-nav" aria-label="Secciones de configuración">
          <button
            v-for="section in settingsSections"
            :key="section.id"
            type="button"
            :aria-pressed="activeSettingsSection === section.id"
            @click="activeSettingsSection = section.id"
          >{{ section.label }}</button>
        </nav>
        <div :key="activeSettingsSection" class="settings-content">
          <div v-if="activeSettingsSection === 'general'" class="settings-section">
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
          </div>
          <div v-else-if="activeSettingsSection === 'model'" class="settings-section">
            <section class="credential-module">
              <div class="credential-module-heading">
                <strong>Modelo de conversación</strong>
                <small>Elige el proveedor y el modelo que usa el asistente para responder.</small>
              </div>
              <select v-model="llmConfig.provider" aria-label="Proveedor de conversación"><option value="gemini">Gemini</option><option value="ollama">Ollama local</option><option value="llama_cpp">llama.cpp local</option></select>
              <input v-if="llmConfig.provider === 'gemini'" v-model="llmConfig.gemini_model" aria-label="Modelo Gemini" placeholder="Modelo Gemini" />
              <input v-else-if="llmConfig.provider === 'ollama'" v-model="llmConfig.ollama_model" aria-label="Modelo Ollama" placeholder="Modelo Ollama" />
              <input v-else v-model="llmConfig.llama_cpp_model" aria-label="Modelo llama.cpp" placeholder="Modelo llama.cpp" />
              <button type="button" :disabled="savingLLM" @click="updateLLM">{{ savingLLM ? 'Aplicando…' : 'Aplicar modelo' }}</button>
              <small v-if="llmConfig.provider === 'llama_cpp'">Inicia llama-server en http://127.0.0.1:8080 antes de conversar.</small>
              <small>{{ modelStatus }}</small>
            </section>
            <div v-if="llmConfig.provider === 'gemini' && !configured" class="notice">
              Gemini aún no tiene una clave configurada. Puedes probar la conexión y añadirla después.
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
          </div>
          <div v-else-if="activeSettingsSection === 'voice'" class="settings-section">
            <section class="credential-module microphone-settings">
              <div class="credential-module-heading">
                <strong>Micrófono</strong>
                <small>Se usa al grabar y al escuchar en segundo plano.</small>
              </div>
              <label for="microphone-select">Dispositivo de entrada</label>
              <select id="microphone-select" :value="selectedMicrophone" :disabled="recording || detectingMicrophones" @change="changeMicrophone">
                <option value="">Predeterminado de Windows</option>
                <option v-if="selectedMicrophoneMissing" :value="selectedMicrophone">Micrófono guardado (no disponible)</option>
                <option v-for="(device, index) in microphones" :key="device.deviceId" :value="device.deviceId">
                  {{ device.label || `Micrófono ${index + 1}` }}
                </option>
              </select>
              <small v-if="selectedMicrophoneMissing">Se usará el predeterminado mientras el micrófono guardado no esté disponible.</small>
              <button type="button" :disabled="recording || detectingMicrophones" @click="detectMicrophones">
                {{ detectingMicrophones ? 'Detectando…' : 'Detectar micrófonos' }}
              </button>
              <small v-if="microphoneError" role="status">{{ microphoneError }}</small>
            </section>
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
          </div>
          <div v-else-if="activeSettingsSection === 'apps'" class="settings-section">
            <div class="access-settings">
              <div class="settings-title access-heading">
                <div><strong>Accesos permitidos</strong><small>Aplicaciones, archivos y carpetas que el asistente puede abrir</small></div>
              </div>
              <button class="detect-apps" type="button" :disabled="syncingApps" @click="detectApps">{{ syncingApps ? 'Buscando…' : 'Detectar aplicaciones instaladas' }}</button>
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
          </div>
          <div v-else-if="activeSettingsSection === 'files'" class="settings-section">
            <div class="access-settings file-access-settings">
              <div class="settings-title access-heading">
                <div><strong>Lectura de archivos</strong><small>Autoriza las carpetas donde el asistente puede buscar archivos por nombre. Las extensiones de abajo se aplican a la lectura del contenido.</small></div>
              </div>
              <small class="file-reading-help">Puedes buscar, crear TXT, CSV, Word, Excel, PowerPoint y PDF; copiar, mover y renombrar. Las modificaciones requieren confirmación.</small>
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
                {{ savingFileAccess ? 'Guardando…' : 'Guardar permisos de archivos' }}
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
          </div>
          <div v-else-if="activeSettingsSection === 'web'" class="settings-section">
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
                <div><strong>Accesos a páginas</strong><small>Atajos opcionales para abrir una dirección concreta con «Entra a…».</small></div>
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
          </div>
          <div v-else-if="activeSettingsSection === 'memory'" class="settings-section">
            <MemoryPanel :assistant-name="assistantName" :memories="memories" :memory-busy="memoryBusy" v-model:memoryDraft="memoryDraft" @storeMemory="storeMemory" @removeMemory="removeMemory" />

            <SchedulePanel :access-entries="accessEntries" :reminders="reminders" :routines="routines" :schedule-busy="scheduleBusy" v-model:reminderTitle="reminderTitle" v-model:reminderAt="reminderAt" v-model:reminderAction="reminderAction" v-model:reminderAccessId="reminderAccessId" v-model:routineName="routineName" v-model:routineTime="routineTime" v-model:routineAccessIds="routineAccessIds" v-model:routineDays="routineDays" @storeReminder="storeReminder" @removeReminder="removeReminder" @toggleRoutineDay="toggleRoutineDay" @storeRoutine="storeRoutine" @removeRoutine="removeRoutine" />
          </div>
          <div v-else-if="activeSettingsSection === 'activity'" class="settings-section">
            <div class="settings-title history-heading">
              <div><strong>Actividad reciente</strong><small>Mensajes y consumo de la sesión actual</small></div>
            </div>
            <ConversationList class="settings-conversation" :messages="messages" />
          </div>
        </div>
      </div>
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
      <button v-if="canStop" class="stop" type="button" aria-label="Detener respuesta" title="Detener respuesta y voz" @click="stopCurrentResponse">■</button>
      <input v-model="input" autocomplete="off" :placeholder="`Escribe algo para ${assistantName}…`" />
      <button class="send" :disabled="!canSend" aria-label="Enviar">➜</button>
    </form>
  </main>
</template>

<style src="./styles/app.css"></style>
