/**
 * API клиент для работы с тегами и классификацией
 */

export interface Tag {
  id: string
  name: string
  description?: string
  category?: string
  usage_count: number
  is_active: boolean
  examples?: string[]
  created_at?: string
  updated_at?: string
}

export interface TagCreate {
  name: string
  description?: string
  category?: string
  examples?: string[]
}

export interface TagUpdate {
  description?: string
  category?: string
  is_active?: boolean
}

export interface AnalyzeTagsResult {
  analyzed: number
  new_tags: Tag[]
  updated_tags: string[]
  deactivated_tags: string[]
}

/**
 * Получить все теги
 */
export async function getTags(activeOnly = true): Promise<Tag[]> {
  const response = await fetch(`/api/classify/tags?active_only=${activeOnly}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch tags: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Получить тег по имени
 */
export async function getTag(tagName: string): Promise<Tag> {
  const response = await fetch(`/api/classify/tags/${encodeURIComponent(tagName)}`)
  if (!response.ok) {
    throw new Error(`Failed to fetch tag: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Создать новый тег
 */
export async function createTag(tag: TagCreate): Promise<Tag> {
  const response = await fetch('/api/classify/tags', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(tag)
  })
  if (!response.ok) {
    throw new Error(`Failed to create tag: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Обновить тег
 */
export async function updateTag(tagName: string, updates: TagUpdate): Promise<Tag> {
  const response = await fetch(`/api/classify/tags/${encodeURIComponent(tagName)}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(updates)
  })
  if (!response.ok) {
    throw new Error(`Failed to update tag: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Анализировать параграфы и обновить теги
 */
export async function analyzeTags(sampleSize = 100): Promise<AnalyzeTagsResult> {
  const response = await fetch(`/api/classify/tags/analyze?sample_size=${sampleSize}`, {
    method: 'POST'
  })
  if (!response.ok) {
    throw new Error(`Failed to analyze tags: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Предложить теги для параграфа
 */
export async function suggestTags(paragraphContent: string): Promise<string[]> {
  const response = await fetch(
    `/api/classify/tags/suggest?paragraph_content=${encodeURIComponent(paragraphContent)}`,
    {
      method: 'POST'
    }
  )
  if (!response.ok) {
    throw new Error(`Failed to suggest tags: ${response.statusText}`)
  }
  return response.json()
}
