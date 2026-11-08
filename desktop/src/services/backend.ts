export type AssistantState =
  | 'disconnected'
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'processing'
  | 'speaking'
  | 'dormant'

export interface ServerMessage {
  version: 1
  type: 'assistant_state' | 'assistant_text' | 'conversation_cleared' | 'pong' | 'error'
  request_id?: string | null
  timestamp?: string
  payload: Record<string, unknown>
}

const HTTP_URL = 'http://127.0.0.1:8765'
const WS_URL = 'ws://127.0.0.1:8765/ws'

export async function getHealth(): Promise<Record<string, unknown>> {
  const response = await fetch(`${HTTP_URL}/api/health`)
  if (!response.ok) throw new Error(`Backend no disponible (${response.status})`)
  return response.json()
}

export interface AssistantProfile {
  name: string
  language: string
  wake_phrase: string
}


export interface ConversationPreferences {
  web_search_enabled: boolean
}

export async function getConversationPreferences(): Promise<ConversationPreferences> {
  const response = await fetch(`${HTTP_URL}/api/conversation/preferences`)
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function saveConversationPreferences(
  preferences: ConversationPreferences
): Promise<ConversationPreferences> {
  const response = await fetch(`${HTTP_URL}/api/conversation/preferences`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preferences)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export interface FileAccessPreferences {
  folders: string[]
  extensions: string[]
}

export interface IndexedFile {
  name: string
  path: string
  extension: string
}

export async function getFileAccessPreferences(): Promise<FileAccessPreferences> {
  const response = await fetch(`${HTTP_URL}/api/files/preferences`)
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function saveFileAccessPreferences(
  preferences: FileAccessPreferences
): Promise<FileAccessPreferences> {
  const response = await fetch(`${HTTP_URL}/api/files/preferences`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(preferences)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function getFileIndex(): Promise<IndexedFile[]> {
  const response = await fetch(`${HTTP_URL}/api/files/index`)
  if (!response.ok) throw await apiError(response)
  return ((await response.json()) as { files: IndexedFile[] }).files
}

export async function refreshFileIndex(): Promise<IndexedFile[]> {
  const response = await fetch(`${HTTP_URL}/api/files/index/refresh`, { method: 'POST' })
  if (!response.ok) throw await apiError(response)
  return ((await response.json()) as { files: IndexedFile[] }).files
}
export async function getAssistantProfile(): Promise<AssistantProfile> {
  const response = await fetch(`${HTTP_URL}/api/assistant/profile`)
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function saveAssistantProfile(name: string): Promise<AssistantProfile> {
  const response = await fetch(`${HTTP_URL}/api/assistant/profile`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name })
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export interface ActivationSettings {
  enabled: boolean
  wake_phrase: string
  wake_phrases: string[]
  wake_phrase_template: string
  inactivity_seconds: number
  show_on_wake: boolean
  hide_on_timeout: boolean
}

export async function getActivationSettings(): Promise<ActivationSettings> {
  const response = await fetch(`${HTTP_URL}/api/activation`)
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function saveActivationSettings(settings: {
  enabled: boolean
  inactivity_seconds: number
  show_on_wake: boolean
  hide_on_timeout: boolean
}): Promise<ActivationSettings> {
  const response = await fetch(`${HTTP_URL}/api/activation`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(settings)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export type AccessKind = 'application' | 'file' | 'folder'

export interface AccessEntry {
  id: string
  name: string
  kind: AccessKind
  target: string
  aliases: string[]
  arguments: string[]
  working_directory?: string | null
  enabled: boolean
  spoken_name: string
  close_policy: 'process' | 'window'
}

export async function getAccessEntries(): Promise<AccessEntry[]> {
  const response = await fetch(`${HTTP_URL}/api/access`)
  if (!response.ok) throw await apiError(response)
  const body = (await response.json()) as { entries: AccessEntry[] }
  return body.entries
}

export async function addAccessEntry(entry: {
  name: string
  kind: AccessKind
  target: string
  aliases: string[]
  spoken_name?: string
  close_policy?: 'process' | 'window'
}): Promise<AccessEntry> {
  const response = await fetch(`${HTTP_URL}/api/access`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export interface BrowserConfig {
  name: string
  activation_word: string
  executable: string
  aliases: string[]
}

export interface WebsiteShortcut {
  id: string
  name: string
  url: string
  aliases: string[]
  enabled: boolean
}

export async function getBrowserConfiguration(): Promise<{
  browser: BrowserConfig | null
  websites: WebsiteShortcut[]
}> {
  const response = await fetch(`${HTTP_URL}/api/browser`)
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function saveBrowserConfiguration(config: BrowserConfig): Promise<BrowserConfig> {
  const response = await fetch(`${HTTP_URL}/api/browser`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(config)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function clearBrowserConfiguration(): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/browser`, { method: 'DELETE' })
  if (!response.ok) throw await apiError(response)
}

export async function addWebsiteShortcut(site: {
  name: string
  url: string
  aliases: string[]
}): Promise<WebsiteShortcut> {
  const response = await fetch(`${HTTP_URL}/api/websites`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(site)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function deleteWebsiteShortcut(websiteId: string): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/websites/${encodeURIComponent(websiteId)}`, {
    method: 'DELETE'
  })
  if (!response.ok) throw await apiError(response)
}

export async function saveAccessSpokenName(
  entryId: string,
  spokenName: string
): Promise<AccessEntry> {
  const response = await fetch(`${HTTP_URL}/api/access/${encodeURIComponent(entryId)}/spoken-name`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ spoken_name: spokenName })
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function deleteAccessEntry(entryId: string): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/access/${encodeURIComponent(entryId)}`, {
    method: 'DELETE'
  })
  if (!response.ok) throw await apiError(response)
}

export async function openAccessEntry(entryId: string): Promise<{ message: string }> {
  const response = await fetch(`${HTTP_URL}/api/access/${encodeURIComponent(entryId)}/open`, {
    method: 'POST'
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export interface MemoryEntry {
  id: string
  content: string
  category: string
  created_at: string
  updated_at: string
}

export async function getMemories(): Promise<MemoryEntry[]> {
  const response = await fetch(`${HTTP_URL}/api/memories`)
  if (!response.ok) throw await apiError(response)
  return ((await response.json()) as { memories: MemoryEntry[] }).memories
}

export async function addMemory(content: string, category = 'general'): Promise<MemoryEntry> {
  const response = await fetch(`${HTTP_URL}/api/memories`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ content, category })
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function deleteMemory(memoryId: string): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/memories/${encodeURIComponent(memoryId)}`, { method: 'DELETE' })
  if (!response.ok) throw await apiError(response)
}

export interface Reminder {
  id: string
  title: string
  due_at: string
  action_type: 'notify' | 'open_access'
  access_id: string | null
  status: 'pending' | 'completed' | 'cancelled' | 'failed'
  created_at: string
  completed_at: string | null
}

export interface Routine {
  id: string
  name: string
  time_of_day: string
  days: number[]
  access_ids: string[]
  enabled: boolean
  last_run_date: string | null
}

export async function getReminders(): Promise<Reminder[]> {
  const response = await fetch(`${HTTP_URL}/api/reminders`)
  if (!response.ok) throw await apiError(response)
  return ((await response.json()) as { reminders: Reminder[] }).reminders
}

export async function addReminder(value: Omit<Reminder, 'id' | 'status' | 'created_at' | 'completed_at'>): Promise<Reminder> {
  const response = await fetch(`${HTTP_URL}/api/reminders`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function deleteReminder(reminderId: string): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/reminders/${encodeURIComponent(reminderId)}`, { method: 'DELETE' })
  if (!response.ok) throw await apiError(response)
}

export async function getRoutines(): Promise<Routine[]> {
  const response = await fetch(`${HTTP_URL}/api/routines`)
  if (!response.ok) throw await apiError(response)
  return ((await response.json()) as { routines: Routine[] }).routines
}

export async function addRoutine(value: Omit<Routine, 'id' | 'enabled' | 'last_run_date'>): Promise<Routine> {
  const response = await fetch(`${HTTP_URL}/api/routines`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function deleteRoutine(routineId: string): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/routines/${encodeURIComponent(routineId)}`, { method: 'DELETE' })
  if (!response.ok) throw await apiError(response)
}

export async function getScheduledEvents(): Promise<string[]> {
  const response = await fetch(`${HTTP_URL}/api/schedule/events`)
  if (!response.ok) throw await apiError(response)
  return ((await response.json()) as { events: string[] }).events
}

async function apiError(response: Response): Promise<Error> {
  try {
    const body = (await response.json()) as { detail?: string }
    return new Error(body.detail ?? `Error HTTP ${response.status}`)
  } catch {
    return new Error(`Error HTTP ${response.status}`)
  }
}

export type TranscriptionContext = 'manual' | 'active' | 'dormant'

export async function transcribeAudio(
  blob: Blob,
  context: TranscriptionContext = 'manual'
): Promise<string> {
  const response = await fetch(`${HTTP_URL}/api/voice/transcribe?context=${context}`, {
    method: 'POST',
    signal: AbortSignal.timeout(45000),
    headers: { 'Content-Type': blob.type || 'audio/webm' },
    body: blob
  })
  if (!response.ok) throw await apiError(response)
  const body = (await response.json()) as { text: string }
  return body.text
}

export interface EdgeVoice {
  name: string
  locale: string
  gender: string
  display_name: string
}

export type VoiceEngine = 'edge' | 'elevenlabs' | 'fish' | 'custom' | 'kokoro'

export interface VoicePreferences {
  engine: VoiceEngine
  edge_voice: string
  elevenlabs_voice_id: string
  fish_reference_id: string
  custom_endpoint: string
  custom_voice: string
  custom_model: string
  rvc_enabled: boolean
  voice_output: boolean
}

export interface VoiceConfiguration {
  credentials: Record<string, boolean>
  cache: { files: number; bytes: number; hits: number }
  preferences: VoicePreferences
}

export async function getVoiceConfiguration(): Promise<VoiceConfiguration> {
  const response = await fetch(`${HTTP_URL}/api/voice/config`)
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function saveVoiceCredential(provider: string, apiKey: string): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/voice/credentials/${provider}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey })
  })
  if (!response.ok) throw await apiError(response)
}

export async function deleteVoiceCredential(provider: string): Promise<{ configured: boolean }> {
  const response = await fetch(`${HTTP_URL}/api/voice/credentials/${provider}`, {
    method: 'DELETE'
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function saveVoicePreferences(preferences: VoicePreferences): Promise<VoicePreferences> {
  const response = await fetch(`${HTTP_URL}/api/voice/preferences`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(preferences)
  })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function clearVoiceCache(): Promise<{ files: number; bytes: number; hits: number }> {
  const response = await fetch(`${HTTP_URL}/api/voice/cache`, { method: 'DELETE' })
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function getVoiceCacheStats(): Promise<{ files: number; bytes: number; hits: number }> {
  const response = await fetch(`${HTTP_URL}/api/voice/cache`)
  if (!response.ok) throw await apiError(response)
  return response.json()
}

export async function getEdgeVoices(): Promise<EdgeVoice[]> {
  const response = await fetch(`${HTTP_URL}/api/voice/edge-voices`)
  if (!response.ok) throw await apiError(response)
  const body = (await response.json()) as { voices: EdgeVoice[] }
  return body.voices
}

export async function synthesizeSpeech(
  text: string,
  useRvc: boolean,
  engine: VoiceEngine,
  voice?: string,
  model?: string,
  endpoint?: string,
  fragments?: string[]
): Promise<{ blob: Blob; provider: string; cacheHit: boolean; fallbackFrom?: string }> {
  const response = await fetch(`${HTTP_URL}/api/voice/synthesize`, {
    method: 'POST',
    signal: AbortSignal.timeout(60000),
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, fragments, use_rvc: useRvc, engine, voice, model, endpoint })
  })
  if (!response.ok) throw await apiError(response)
  const fallbackFrom = response.headers.get('X-Asistente-Modular-Fallback-From') || undefined
  return {
    blob: await response.blob(),
    provider: response.headers.get('X-Asistente-Modular-TTS-Provider') || engine,
    cacheHit: response.headers.get('X-Asistente-Modular-Cache') === 'hit',
    fallbackFrom
  }
}

function once(target: EventTarget, event: string): Promise<void> {
  return new Promise((resolve, reject) => {
    target.addEventListener(event, () => resolve(), { once: true })
    target.addEventListener('error', () => reject(new Error(`Error de audio: ${event}`)), {
      once: true
    })
  })
}

export async function playEdgeStream(text: string, voice: string, audio: HTMLAudioElement): Promise<void> {
  const response = await fetch(`${HTTP_URL}/api/voice/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, engine: 'edge', voice, use_rvc: false })
  })
  if (!response.ok) throw await apiError(response)
  if (!response.body || !MediaSource.isTypeSupported('audio/mpeg')) {
    const fallback = await response.blob()
    const fallbackUrl = URL.createObjectURL(fallback)
    audio.src = fallbackUrl
    await audio.play()
    await once(audio, 'ended')
    URL.revokeObjectURL(fallbackUrl)
    return
  }

  const mediaSource = new MediaSource()
  const mediaUrl = URL.createObjectURL(mediaSource)
  audio.src = mediaUrl
  await once(mediaSource, 'sourceopen')
  const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg')
  const reader = response.body.getReader()
  let started = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      if (!value?.byteLength) continue
      sourceBuffer.appendBuffer(value)
      await once(sourceBuffer, 'updateend')
      if (!started) {
        await audio.play()
        started = true
      }
    }
    if (sourceBuffer.updating) await once(sourceBuffer, 'updateend')
    mediaSource.endOfStream()
    if (started) await once(audio, 'ended')
  } finally {
    URL.revokeObjectURL(mediaUrl)
  }
}

export class AssistantSocket {
  private socket?: WebSocket
  private reconnectTimer?: number
  private manuallyClosed = false

  constructor(
    private readonly onMessage: (message: ServerMessage) => void,
    private readonly onConnection: (connected: boolean) => void
  ) {}

  connect(): void {
    this.manuallyClosed = false
    this.socket = new WebSocket(WS_URL)
    this.socket.onopen = () => this.onConnection(true)
    this.socket.onmessage = (event) => {
      this.onMessage(JSON.parse(String(event.data)) as ServerMessage)
    }
    this.socket.onerror = () => this.socket?.close()
    this.socket.onclose = () => {
      this.onConnection(false)
      if (!this.manuallyClosed) {
        this.reconnectTimer = window.setTimeout(() => this.connect(), 1500)
      }
    }
  }

  sendText(text: string): string {
    const requestId = crypto.randomUUID()
    this.send({ version: 1, type: 'user_text', request_id: requestId, payload: { text } })
    return requestId
  }

  clearConversation(): void {
    this.send({
      version: 1,
      type: 'clear_conversation',
      request_id: crypto.randomUUID(),
      payload: {}
    })
  }

  close(): void {
    this.manuallyClosed = true
    window.clearTimeout(this.reconnectTimer)
    this.socket?.close()
  }

  private send(message: object): void {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      throw new Error('El asistente todavía no está conectado.')
    }
    this.socket.send(JSON.stringify(message))
  }
}


export interface LLMConfig {
  provider: 'gemini' | 'ollama'
  gemini_model: string
  ollama_model: string
}
export async function getLLMConfig(): Promise<LLMConfig> {
  const response = await fetch(`${HTTP_URL}/api/llm/config`)
  if (!response.ok) throw new Error('No pude cargar el modelo.')
  return response.json()
}
export async function saveLLMConfig(config: LLMConfig): Promise<LLMConfig> {
  const response = await fetch(`${HTTP_URL}/api/llm/config`, {method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(config)})
  if (!response.ok) throw new Error('No pude guardar el modelo.')
  return response.json()
}
export async function syncDiscoveredApps(): Promise<number> {
  const response = await fetch(`${HTTP_URL}/api/access/sync`, {method: 'POST'})
  if (!response.ok) throw new Error('No pude detectar aplicaciones.')
  return (await response.json()).added
}
export async function getConversationHistory(): Promise<Array<{role: 'user' | 'assistant'; content: string}>> {
  const response = await fetch(`${HTTP_URL}/api/conversation/history`)
  if (!response.ok) throw new Error('No pude recuperar la conversación.')
  return (await response.json()).messages
}
