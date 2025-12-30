import { createSignal, For, onMount } from 'solid-js'
import { Chat } from '~/types/chat'
import { useKnowledgeBase } from '../../contexts/KnowledgeBaseContext'
import type { ConceptNode } from '../../types/kb'
import styles from './ChatSidebar.module.css'

// Иконка дерева знаний
const KnowledgeIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M12 22V14" />
    <path d="M10 14h4" />
    <path d="M8 10L12 14L16 10" />
    <path d="M6 6L12 12L18 6" />
    <circle cx="8" cy="8" r="1" fill="currentColor" />
    <circle cx="16" cy="8" r="1" fill="currentColor" />
    <circle cx="10" cy="11" r="1" fill="currentColor" />
    <circle cx="14" cy="11" r="1" fill="currentColor" />
  </svg>
)

// Иконка финансирования
const FundsIcon = () => (
  <svg
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M11 11h2a2 2 0 1 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 16" />
    <path d="M7 21h1.414a1 1 0 0 0 .707-.293l7.586-7.586a1 1 0 0 0 .293-.707V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v7l-4 4v0a2 2 0 0 0 2 2h2z" />
    <path d="M22 11c-1 0-2-4-3.5-4.5S15 8 15 9.5c0 .8.5 1.5 1.5 1.5s2.5 0 3.5-1c1 0 2 0 2 0" />
  </svg>
)

// Интерфейс для сессии с дополнительной информацией
interface ChatSession extends ConceptNode {
  nodeCount: number
  lastUpdated: number
}

type ChatSidebarProps = {
  onChatSelect: (node: ConceptNode) => void
  currentPath: ConceptNode[]
  recentChats: Chat[]
}

export const ChatSidebar = (props: ChatSidebarProps) => {
  const kb = useKnowledgeBase()
  const [sessions, setSessions] = createSignal<ChatSession[]>([])
  const [currentPage, setCurrentPage] = createSignal(0)
  const [totalPages, setTotalPages] = createSignal(0)
  const itemsPerPage = 50

  // Функция для получения всех узлов в сессии
  const getNodesInSession = (sessionId: string, allNodes: ConceptNode[]): ConceptNode[] => {
    const result: ConceptNode[] = []
    const stack = [sessionId]

    while (stack.length > 0) {
      const currentId = stack.pop()!
      const node = allNodes.find((n) => n.id === currentId)
      if (node) {
        result.push(node)
        stack.push(...node.childrenIds)
      }
    }

    return result
  }

  // Загрузка сессий с сортировкой
  const loadSessions = async () => {
    try {
      // Получаем все сессии (корневые узлы)
      const allSessions = await kb.getChatSessions()

      // Получаем все узлы для подсчета
      const allNodesResponse = await fetch('/api/kb/tree?limit=10000')
      const allNodesData = await allNodesResponse.json()
      const allNodes = allNodesData.nodes as ConceptNode[]

      // Подготавливаем сессии с информацией о количестве узлов и времени последнего обновления
      const sessionsWithInfo: ChatSession[] = allSessions.map((session) => {
        const nodesInSession = getNodesInSession(session.id, allNodes)
        const nodeCount = nodesInSession.length

        // Находим последнее обновленное сообщение в сессии
        const lastUpdated =
          nodesInSession.length > 0
            ? Math.max(...nodesInSession.map((n) => n.timestamp || 0))
            : session.timestamp || 0

        return {
          ...session,
          nodeCount,
          lastUpdated
        }
      })

      // Сортируем: сначала по количеству узлов (по убыванию), затем по свежести (по убыванию)
      const sortedSessions = sessionsWithInfo.sort((a, b) => {
        if (b.nodeCount !== a.nodeCount) {
          return b.nodeCount - a.nodeCount // Сначала по количеству узлов
        }
        return b.lastUpdated - a.lastUpdated // Потом по свежести
      })

      // Вычисляем общее количество страниц
      const total = Math.ceil(sortedSessions.length / itemsPerPage)
      setTotalPages(total)

      // Показываем только текущую страницу
      const startIndex = currentPage() * itemsPerPage
      const endIndex = startIndex + itemsPerPage
      const paginatedSessions = sortedSessions.slice(startIndex, endIndex)

      setSessions(paginatedSessions)
    } catch (error) {
      console.error('Error loading sessions:', error)
    }
  }

  onMount(loadSessions)

  // Обновление при смене страницы
  const handlePageChange = (newPage: number) => {
    if (newPage >= 0 && newPage < totalPages()) {
      setCurrentPage(newPage)
    }
  }

  const handleChatSelect = async (session: ChatSession) => {
    try {
      const fullSession = await kb.getChatSession(session.id)
      props.onChatSelect(fullSession)
    } catch {
      // Возвращаем базовую информацию о сессии
      const basicSession: ConceptNode = {
        id: session.id,
        parentId: null,
        childrenIds: [],
        content: session.content,
        sources: [],
        timestamp: session.timestamp,
        type: session.type,
        category: session.category,
        position: session.position,
        sessionId: session.sessionId,
        conceptNodeId: session.conceptNodeId,
        role: session.role,
        expanded: session.expanded,
        selected: session.selected
      }
      props.onChatSelect(basicSession)
    }
  }

  return (
    <div class={styles.sidebar}>
      {/* Навигационные иконки */}
      <div class={styles.navIcons}>
        <a href="/knowledge" class={styles.navIcon} title="Древо знаний">
          <KnowledgeIcon />
        </a>
        <a href="/funds" class={styles.navIcon} title="Фандинг">
          <FundsIcon />
        </a>
      </div>
      <div class={styles.chatsList}>
        <For each={sessions()}>
          {(session) => (
            <div
              class={`${styles.chatItem} ${props.currentPath.some((node) => node.id === session.id) ? styles.active : ''}`}
              onClick={() => handleChatSelect(session)}
            >
              <div class={styles.chatPreview}>
                {session.content.length > 50 ? `${session.content.substring(0, 50)}...` : session.content}
              </div>
              <div class={styles.chatInfo}>
                <span class={styles.nodeCount}>{session.nodeCount} узлов</span>
                <div class={styles.chatTimestamp}>
                  {new Date(session.lastUpdated).toLocaleString('ru-RU', {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                  })}
                </div>
              </div>
            </div>
          )}
        </For>
      </div>

      {/* Пагинация */}
      {totalPages() > 1 && (
        <div class={styles.pagination}>
          <button
            class={styles.pageButton}
            disabled={currentPage() === 0}
            onClick={() => handlePageChange(currentPage() - 1)}
          >
            {'<'}
          </button>
          <span class={styles.pageInfo}>
            {currentPage() + 1} из {totalPages()}
          </span>
          <button
            class={styles.pageButton}
            disabled={currentPage() === totalPages() - 1}
            onClick={() => handlePageChange(currentPage() + 1)}
          >
            {'>'}
          </button>
        </div>
      )}
    </div>
  )
}

export default ChatSidebar
