import { z } from 'zod'

// Минимальные схемы для поиска параграфов
export const ParagraphSchema = z.object({
  id: z.string(),
  content: z.string(),
  document_id: z.string(),
  node_id: z.string().optional(),
  document_type: z.string(),
  tags: z.array(z.string()),
  author: z.string().optional(),
  author_id: z.number().optional(),
  location: z.string().optional(),
  ecosystem_id: z.string().optional(),
  embedding: z.array(z.number()).optional()
})

export const SearchResultSchema = z.object({
  paragraph: ParagraphSchema,
  score: z.number()
})

export const SearchResponseSchema = z.object({
  results: z.array(SearchResultSchema),
  total: z.number()
})

export type Paragraph = z.infer<typeof ParagraphSchema>
export type SearchResult = z.infer<typeof SearchResultSchema>
export type SearchResponse = z.infer<typeof SearchResponseSchema>
