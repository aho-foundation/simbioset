import { createResource, createSignal } from 'solid-js'
import { ParagraphSchema, SearchResponseSchema, type Paragraph, type SearchResponse } from './schemas'

// Простой клиент Weaviate для frontend
export class WeaviateClient {
  private baseUrl: string

  constructor(baseUrl = '/api') {
    this.baseUrl = baseUrl
  }

  // Поиск параграфов с фильтрацией
  async searchParagraphs(params: {
    query: string
    document_id?: string
    limit?: number
    tags?: string[]
    location?: string
    ecosystem_id?: string
  }): Promise<SearchResponse> {
    const searchParams = new URLSearchParams({
      q: params.query,
      ...(params.document_id && { document_id: params.document_id }),
      ...(params.limit && { limit: params.limit.toString() }),
      ...(params.tags && { tags: params.tags.join(',') }),
      ...(params.location && { location: params.location }),
      ...(params.ecosystem_id && { ecosystem_id: params.ecosystem_id }),
    })

    const response = await fetch(`${this.baseUrl}/search?${searchParams}`)
    if (!response.ok) {
      throw new Error(`Search failed: ${response.statusText}`)
    }

    const data = await response.json()
    return SearchResponseSchema.parse(data)
  }

  // Получение параграфа по ID
  async getParagraph(documentId: string, paragraphId: string): Promise<Paragraph> {
    const response = await fetch(`${this.baseUrl}/documents/${documentId}/paragraphs/${paragraphId}`)
    if (!response.ok) {
      throw new Error(`Get paragraph failed: ${response.statusText}`)
    }

    const data = await response.json()
    return ParagraphSchema.parse(data)
  }
}

// Глобальный экземпляр клиента
export const weaviateClient = new WeaviateClient()

// SolidJS хуки для работы с Weaviate
export function createParagraphSearch(query: () => string, options: {
  document_id?: string
  limit?: number
  tags?: string[]
  location?: string
  ecosystem_id?: string
} = {}) {
  return createResource(
    () => {
      const q = query()
      if (!q?.trim()) return null

      return {
        query: q,
        ...options
      }
    },
    async (params) => {
      return await weaviateClient.searchParagraphs(params)
    }
  )
}

export function createParagraphLoader(documentId: string, paragraphId: string) {
  return createResource(
    () => ({ documentId, paragraphId }),
    async ({ documentId, paragraphId }) => {
      return await weaviateClient.getParagraph(documentId, paragraphId)
    }
  )
}