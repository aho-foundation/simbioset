import { createContext, JSX, useContext } from 'solid-js'
import type {
  ConceptNode,
  NodeWithContext,
  SearchResponse,
  Source,
  StatsResponse,
  TreeResponse
} from '../types/kb'

// API Types
export interface GetNodeOptions {
  includeParent?: boolean
  includeChildren?: boolean
  includeSiblings?: boolean
  maxDepth?: number
}

export interface GetTreeOptions {
  rootId?: string
  depth?: number
  limit?: number
  offset?: number
  category?: string
  type?: string
}

export interface SearchNodesOptions {
  category?: string
  type?: string
  limit?: number
  offset?: number
}

export interface CreateNodeData {
  parentId?: string | null
  content: string
  role?: 'user' | 'assistant' | 'system'
}

export interface UpdateNodeData {
  content?: string
  sources?: Array<{
    source: Source
    type: 'confirm' | 'doubt'
    tool?: string
    sentiment?: 'positive' | 'negative' | 'neutral'
    userConfirmed?: boolean
    reliabilityScore?: number
  }>
  expanded?: boolean
  selected?: boolean
}

export interface AddSourceData {
  url: string
  title?: string
}

export interface ContinueConversationData {
  nodeId: string
  message: string
  sessionId?: string
}

// Source interface is now defined in src/types/kb.d.ts
// This duplicate definition has been removed to avoid conflicts

export interface DeleteResult {
  success: boolean
}

export interface SetExpandedResult {
  success: boolean
  nodeId: string
  expanded: boolean
}

export interface SetSelectedResult {
  success: boolean
  nodeId: string
  selected: boolean
}

export type ToggleResult = SetExpandedResult

export interface ClearSelectionResult {
  success: boolean
  clearedCount: number
}

export type AddSourceResponse = Source
export type ContinueConversationResponse = ConceptNode

const API_BASE = '/api/kb'

// API Functions
export async function getNode(nodeId: string, options?: GetNodeOptions): Promise<NodeWithContext> {
  const params = new URLSearchParams()
  if (options?.includeParent !== undefined) params.set('include_parent', options.includeParent.toString())
  if (options?.includeChildren !== undefined)
    params.set('include_children', options.includeChildren.toString())
  if (options?.includeSiblings !== undefined)
    params.set('include_siblings', options.includeSiblings.toString())
  if (options?.maxDepth !== undefined) params.set('max_depth', options.maxDepth.toString())

  const response = await fetch(`${API_BASE}/nodes/${nodeId}?${params}`)
  if (!response.ok) throw new Error(`Failed to get node: ${response.statusText}`)
  return response.json()
}

export async function getTree(options?: GetTreeOptions): Promise<TreeResponse> {
  const params = new URLSearchParams()
  if (options?.rootId) params.set('root_id', options.rootId)
  if (options?.depth !== undefined) params.set('depth', options.depth.toString())
  if (options?.limit !== undefined) params.set('limit', options.limit.toString())
  if (options?.offset !== undefined) params.set('offset', options.offset.toString())
  if (options?.category) params.set('category', options.category)
  if (options?.type) params.set('type', options.type)

  const response = await fetch(`${API_BASE}/tree?${params}`)
  if (!response.ok) throw new Error(`Failed to get tree: ${response.statusText}`)
  return response.json()
}

export async function searchNodes(query: string, options?: SearchNodesOptions): Promise<SearchResponse> {
  const params = new URLSearchParams()
  params.set('q', query)
  if (options?.category) params.set('category', options.category)
  if (options?.type) params.set('type', options.type)
  if (options?.limit !== undefined) params.set('limit', options.limit.toString())
  if (options?.offset !== undefined) params.set('offset', options.offset.toString())

  const response = await fetch(`${API_BASE}/search?${params}`)
  if (!response.ok) throw new Error(`Failed to search nodes: ${response.statusText}`)
  return response.json()
}

export async function createNode(data: CreateNodeData): Promise<ConceptNode> {
  const response = await fetch(`${API_BASE}/nodes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      parentId: data.parentId,
      content: data.content,
      role: data.role || 'user'
    })
  })
  if (!response.ok) throw new Error(`Failed to create node: ${response.statusText}`)
  return response.json()
}

export async function updateNode(nodeId: string, updates: UpdateNodeData): Promise<NodeWithContext> {
  const response = await fetch(`${API_BASE}/nodes/${nodeId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(updates)
  })
  if (!response.ok) throw new Error(`Failed to update node: ${response.statusText}`)
  return response.json()
}

export async function deleteNode(nodeId: string, cascade = true) {
  const params = new URLSearchParams()
  params.set('cascade', cascade.toString())

  const response = await fetch(`${API_BASE}/nodes/${nodeId}?${params}`, {
    method: 'DELETE'
  })
  if (!response.ok) throw new Error(`Failed to delete node: ${response.statusText}`)
  return response.json()
}

export async function getStats(): Promise<StatsResponse> {
  const response = await fetch(`${API_BASE}/stats`)
  if (!response.ok) throw new Error(`Failed to get stats: ${response.statusText}`)
  return response.json()
}

export async function getRootNode(): Promise<ConceptNode> {
  const response = await fetch(`${API_BASE}/root`)
  if (!response.ok) throw new Error(`Failed to get root node: ${response.statusText}`)
  return response.json()
}

export async function setNodeExpanded(nodeId: string, expanded = true) {
  const response = await fetch(`${API_BASE}/nodes/${nodeId}/expand`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expanded })
  })
  if (!response.ok) throw new Error(`Failed to set node expanded: ${response.statusText}`)
  return response.json()
}

export async function toggleNodeExpanded(nodeId: string): Promise<ToggleResult> {
  const response = await fetch(`${API_BASE}/nodes/${nodeId}/toggle-expand`, {
    method: 'POST'
  })
  if (!response.ok) throw new Error(`Failed to toggle node expanded: ${response.statusText}`)
  return response.json()
}

export async function setNodeSelected(nodeId: string, selected = true): Promise<SetSelectedResult> {
  const response = await fetch(`${API_BASE}/nodes/${nodeId}/select`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ selected })
  })
  if (!response.ok) throw new Error(`Failed to set node selected: ${response.statusText}`)
  return response.json()
}

export async function toggleNodeSelected(nodeId: string): Promise<ToggleResult> {
  const response = await fetch(`${API_BASE}/nodes/${nodeId}/toggle-select`, {
    method: 'POST'
  })
  if (!response.ok) throw new Error(`Failed to toggle node selected: ${response.statusText}`)
  return response.json()
}

export async function getSelectedNodes(): Promise<ConceptNode[]> {
  const response = await fetch(`${API_BASE}/nodes/selected`)
  if (!response.ok) throw new Error(`Failed to get selected nodes: ${response.statusText}`)
  return response.json()
}

export async function clearSelection(): Promise<ClearSelectionResult> {
  const response = await fetch(`${API_BASE}/nodes/clear-selection`, {
    method: 'POST'
  })
  if (!response.ok) throw new Error(`Failed to clear selection: ${response.statusText}`)
  return response.json()
}

export async function getChatSessions(): Promise<ConceptNode[]> {
  const response = await fetch(`${API_BASE}/sessions`)
  if (!response.ok) throw new Error(`Failed to get chat sessions: ${response.statusText}`)
  return response.json()
}

export async function getChatSession(sessionId: string): Promise<ConceptNode> {
  const response = await fetch(`${API_BASE}/sessions/${sessionId}`)
  if (!response.ok) throw new Error(`Failed to get chat session: ${response.statusText}`)
  return response.json()
}

export async function addSourceToNode(nodeId: string, source: AddSourceData): Promise<AddSourceResponse> {
  const response = await fetch(`${API_BASE}/nodes/${nodeId}/sources`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(source)
  })
  if (!response.ok) throw new Error(`Failed to add source to node: ${response.statusText}`)
  return response.json()
}

export async function continueConversationFromNode(
  data: ContinueConversationData
): Promise<ContinueConversationResponse> {
  const response = await fetch(`${API_BASE}/continue-from-node`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      node_id: data.nodeId,
      message: data.message,
      session_id: data.sessionId
    })
  })
  if (!response.ok) throw new Error(`Failed to continue conversation: ${response.statusText}`)
  return response.json()
}

// Alias for backward compatibility
export const getNodeWithContext = getNode

export interface KnowledgeBaseContextValue {
  // Node operations
  getNode: (nodeId: string, options?: GetNodeOptions) => Promise<NodeWithContext>
  getTree: (options?: GetTreeOptions) => Promise<TreeResponse>
  searchNodes: (query: string, options?: SearchNodesOptions) => Promise<SearchResponse>
  createNode: (data: CreateNodeData) => Promise<ConceptNode>
  updateNode: (nodeId: string, updates: UpdateNodeData) => Promise<NodeWithContext>
  deleteNode: (nodeId: string, cascade?: boolean) => Promise<DeleteResult>

  // Selection operations
  setNodeSelected: (nodeId: string, selected?: boolean) => Promise<SetSelectedResult>
  toggleNodeSelected: (nodeId: string) => Promise<ToggleResult>
  getSelectedNodes: () => Promise<ConceptNode[]>
  clearSelection: () => Promise<ClearSelectionResult>

  // Expansion operations
  setNodeExpanded: (nodeId: string, expanded?: boolean) => Promise<SetExpandedResult>
  toggleNodeExpanded: (nodeId: string) => Promise<ToggleResult>

  // Sessions
  getChatSessions: () => Promise<ConceptNode[]>
  getChatSession: (sessionId: string) => Promise<ConceptNode>

  // Sources
  addSourceToNode: (nodeId: string, source: AddSourceData) => Promise<AddSourceResponse>

  // Conversation
  continueConversationFromNode: (data: ContinueConversationData) => Promise<ContinueConversationResponse>

  // Stats
  getStats: () => Promise<StatsResponse>
  getRootNode: () => Promise<ConceptNode>
}

const KnowledgeBaseContext = createContext<KnowledgeBaseContextValue>()

export const KnowledgeBaseProvider = (props: { children: JSX.Element }) => {
  const value: KnowledgeBaseContextValue = {
    getNode,
    getTree,
    searchNodes,
    createNode,
    updateNode,
    deleteNode,
    getStats,
    getRootNode,
    setNodeSelected,
    toggleNodeSelected,
    getSelectedNodes,
    clearSelection,
    setNodeExpanded,
    toggleNodeExpanded,
    getChatSessions,
    getChatSession,
    addSourceToNode,
    continueConversationFromNode
  }

  return <KnowledgeBaseContext.Provider value={value}>{props.children}</KnowledgeBaseContext.Provider>
}

export const useKnowledgeBase = () => {
  const context = useContext(KnowledgeBaseContext)
  if (!context) {
    throw new Error('useKnowledgeBase must be used within KnowledgeBaseProvider')
  }
  return context
}
