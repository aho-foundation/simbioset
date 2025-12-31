import { createResource } from 'solid-js'
import { type Paragraph, ParagraphSchema, type SearchResponse, SearchResponseSchema } from './schemas'

// Простой клиент Weaviate для frontend
export class WeaviateClient {
  private baseUrl: string

  constructor(baseUrl = '/api') {
    this.baseUrl = baseUrl
  }

  // Поиск параграфов с фильтрацией и продвинутыми возможностями
  async searchParagraphs(params: {
    query: string
    document_id?: string
    limit?: number
    tags?: string[]
    exclude_tags?: string[]
    location?: string
    ecosystem_id?: string
    use_hybrid?: boolean
    hybrid_alpha?: number
    use_reranking?: boolean
    timestamp_from?: number
    timestamp_to?: number
  }): Promise<SearchResponse> {
    const searchParams = new URLSearchParams({
      q: params.query,
      ...(params.document_id && { document_id: params.document_id }),
      ...(params.limit && { limit: params.limit.toString() }),
      ...(params.tags && params.tags.length > 0 && { tags: params.tags.join(',') }),
      ...(params.exclude_tags &&
        params.exclude_tags.length > 0 && { exclude_tags: params.exclude_tags.join(',') }),
      ...(params.location && { location: params.location }),
      ...(params.ecosystem_id && { ecosystem_id: params.ecosystem_id }),
      ...(params.use_hybrid !== undefined && { use_hybrid: params.use_hybrid.toString() }),
      ...(params.hybrid_alpha !== undefined && { hybrid_alpha: params.hybrid_alpha.toString() }),
      ...(params.use_reranking !== undefined && { use_reranking: params.use_reranking.toString() }),
      ...(params.timestamp_from !== undefined && { timestamp_from: params.timestamp_from.toString() }),
      ...(params.timestamp_to !== undefined && { timestamp_to: params.timestamp_to.toString() })
    })

    const response = await fetch(`${this.baseUrl}/storage/search?${searchParams}`)
    if (!response.ok) {
      throw new Error(`Search failed: ${response.statusText}`)
    }

    const data = await response.json()
    return SearchResponseSchema.parse(data)
  }

  // Получение параграфа по ID
  async getParagraph(documentId: string, paragraphId: string): Promise<Paragraph> {
    const response = await fetch(
      `${this.baseUrl}/storage/documents/${documentId}/paragraphs/${paragraphId}`
    )
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
export function createParagraphSearch(
  query: () => string,
  options:
    | {
        document_id?: string
        limit?: number
        tags?: string[]
        exclude_tags?: string[]
        location?: string
        ecosystem_id?: string
        use_hybrid?: boolean
        hybrid_alpha?: number
        use_reranking?: boolean
        timestamp_from?: number
        timestamp_to?: number
      }
    | (() => {
        document_id?: string
        limit?: number
        tags?: string[]
        exclude_tags?: string[]
        location?: string
        ecosystem_id?: string
        use_hybrid?: boolean
        hybrid_alpha?: number
        use_reranking?: boolean
        timestamp_from?: number
        timestamp_to?: number
      }) = {}
) {
  // Поддерживаем как объект, так и функцию для реактивности
  const getOptions = typeof options === 'function' ? options : () => options

  return createResource(
    () => {
      const q = query()
      if (!q?.trim()) return null

      const opts = getOptions()
      return {
        query: q,
        ...opts
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
