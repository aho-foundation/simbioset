export type Chat = {
  id: string
  title: string
  timestamp: Date | string
  content: string
}

export interface MessageSource {
  title: string
  type: string
}

export type Message = {
  id: number | string
  role: 'user' | 'assistant' | 'system'
  content: string
  sources?: MessageSource[]
}