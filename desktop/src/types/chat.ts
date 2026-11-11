export interface ChatItem {
  id: string
  role: 'user' | 'assistant' | 'system'
  text: string
  usage?: {
    input: number
    output: number
    thinking: number
    total: number
    session: number
    responseMs: number
  }
}
