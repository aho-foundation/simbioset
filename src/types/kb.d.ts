/**
 * Статистика по Knowledge Base
 */
export interface Source {
  id: string
  url: string
  title?: string
  timestamp: number
}

export interface ConceptNode {
  id: string
  parentId: string | null
  childrenIds: string[]
  content: string
  sources: Array<{
    source: Source;
    type: 'confirm' | 'doubt';
    tool?: string;
    sentiment?: 'positive' | 'negative' | 'neutral';
    userConfirmed?: boolean;
    reliabilityScore?: number;
  }>
  timestamp: number
  embedding?: number[]
  expanded?: boolean
  selected?: boolean
  role?: 'user' | 'assistant' | 'system'
  sessionId?: string
  type:
    | 'question'
    | 'answer'
    | 'fact'
    | 'opinion'
    | 'solution'
    | 'message'
    | 'concept_reference'
    | 'user_observation'
  category: 'threat' | 'protection' | 'conservation' | 'neutral' | 'metrics'
  position: {
    x: number
    y: number
    z: number
  }
  conceptNodeId?: string
  children?: ConceptNode[]
}

export interface StatsResponse {
  total_nodes: number
  max_depth: number
  categories: Record<string, number>
  types: Record<string, number>
}

export interface NodeWithContext {
  node: ConceptNode
  parent?: ConceptNode
  children: ConceptNode[]
  siblings: ConceptNode[]
}

export interface TreeResponse {
  root?: ConceptNode
  nodes: ConceptNode[]
  total: number
  root_id?: string
  stats?: {
    totalNodes: number
    maxDepth: number
    rootNodes: number
  }
}

export interface SearchResponse {
  results: Array<{
    node: ConceptNode
    relevance: number
  }>
  total: number
}

