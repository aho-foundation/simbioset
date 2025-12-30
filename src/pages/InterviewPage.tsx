import { createEffect, createResource, createSignal, For, onCleanup, onMount, Show } from 'solid-js'
import { isServer } from 'solid-js/web'
import { ConversationActions } from '~/components/chat/ConversationActions'
import { DetectorsToolbar } from '~/components/chat/DetectorsToolbar'
import MarkdownRenderer from '~/components/chat/MarkdownRenderer'
import { MessageActions } from '~/components/chat/MessageActions'
import { MessageEditor } from '~/components/chat/MessageEditor'
import { RelatedKnowledge } from '~/components/chat/RelatedKnowledge'
import { useKnowledgeBase } from '~/contexts/KnowledgeBaseContext'
import { useSession } from '~/contexts/SessionContext'
import styles from '~/styles/interview.module.css'
import type { Message, MessageSource } from '~/types/chat'
import type { ConceptNode, TreeResponse } from '~/types/kb'

// Тип для сообщений истории чата
interface ChatHistoryMessage {
  id?: string | number
  parentId?: string | null
  childrenIds?: string[]
  content?: string
  message?: string
  role?: 'user' | 'assistant' | 'system'
  type?: string
  category?: string
  timestamp?: number
  sources?: MessageSource[]
  sessionId?: string
}

const DEFAULT_STARTERS = [
  'Что такое симбиоз и симбиосеть?',
  'Давай вместе исследовать экосистему!',
  'Как можно улучшать качества биосферы?'
]

const STORAGE_KEY = 'conversation-starters'

// Load starters from localStorage
const loadStartersFromStorage = (): string[] => {
  if (isServer) return DEFAULT_STARTERS
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : DEFAULT_STARTERS
  } catch {
    return DEFAULT_STARTERS
  }
}

// Save starters to localStorage
const saveStartersToStorage = (starters: string[]): void => {
  if (isServer) return
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(starters))
  } catch {
    // Ignore storage errors
  }
}

// Get 3 random starters from array
const getRandomStarters = (allStarters: string[]): string[] => {
  if (allStarters.length <= 3) return allStarters
  const shuffled = [...allStarters].sort(() => Math.random() - 0.5)
  return shuffled.slice(0, 3)
}

// Load new starters from API and add to storage
const loadNewStarters = async (): Promise<string[]> => {
  try {
    const res = await fetch('/api/chat/starters')
    if (res.ok) {
      const data = await res.json()
      if (Array.isArray(data) && data.length > 0) {
        const current = loadStartersFromStorage()
        // Добавляем только новые, исключая дубликаты
        const updated = [...new Set([...current, ...data])]
        // Ограничиваем до 50 стартеров
        const limited = updated.slice(0, 50)
        saveStartersToStorage(limited)
        // Возвращаем только новые добавленные стартеры
        return data.filter((s: string) => !current.includes(s))
      }
    }
  } catch (error) {
    console.error('Failed to load new starters:', error)
  }
  return []
}

const InterviewPage = () => {
  const [messages, setMessages] = createSignal<Message[]>([])
  const [inputValue, setInputValue] = createSignal('')
  const [isLoading, setIsLoading] = createSignal(false)
  const [detectorLoading, setDetectorLoading] = createSignal(false)
  const [detectorErrors, setDetectorErrors] = createSignal<Record<string, boolean>>({})
  const [summaryLoading, setSummaryLoading] = createSignal(false)
  const [isLoadingMoreStarters, setIsLoadingMoreStarters] = createSignal(false)
  const [inputHeight, setInputHeight] = createSignal(48)
  const [isResizing, setIsResizing] = createSignal(false)
  const [isPanelOpen, setIsPanelOpen] = createSignal(false)
  const [treeRefreshKey, setTreeRefreshKey] = createSignal(0)
  const [editingMessageId, setEditingMessageId] = createSignal<number | null>(null)
  const [editingContent, setEditingContent] = createSignal('')
  const { sessionId, setSessionId } = useSession()
  const kb = useKnowledgeBase()

  // Проверка, достаточно ли контента для отображения аналитической панели (минимум 2 сообщения)
  const canShowAnalyticsPanel = () => {
    const tree = conversationTree()
    return tree && tree.stats && tree.stats.totalNodes >= 2
  }

  let inputAreaRef: HTMLDivElement | undefined
  let textareaRef: HTMLTextAreaElement | undefined
  let startY = 0
  let startHeight = 0

  // Initialize starters from localStorage
  const [starters, setStarters] = createSignal<string[]>(getRandomStarters(loadStartersFromStorage()))

  // Функция для перебора стартеров
  const loadMoreStarters = async () => {
    if (isLoadingMoreStarters()) return

    setIsLoadingMoreStarters(true)
    try {
      let allStarters = loadStartersFromStorage()
      const currentStarters = starters()

      // Если стартеров меньше 50, запрашиваем новые из API
      if (allStarters.length < 50) {
        try {
          const newStarters = await loadNewStarters()
          if (newStarters.length > 0) {
            // Обновляем список всех стартеров после загрузки
            allStarters = loadStartersFromStorage()
          }
        } catch (error) {
          console.error('Failed to load new starters:', error)
        }
      }

      if (allStarters.length <= 3) {
        // Если стартеров мало, просто перемешиваем их
        const newStarters = getRandomStarters(allStarters)
        // Убеждаемся, что список действительно изменился
        if (JSON.stringify(newStarters) !== JSON.stringify(currentStarters)) {
          setStarters(newStarters)
        } else {
          // Если получились те же самые, перемешиваем еще раз
          setStarters([...allStarters].sort(() => Math.random() - 0.5))
        }
        return
      }

      // Получаем новые случайные стартеры, исключая текущие
      const availableStarters = allStarters.filter((s) => !currentStarters.includes(s))

      if (availableStarters.length >= 3) {
        // Если есть достаточно новых стартеров, берем их
        const shuffled = [...availableStarters].sort(() => Math.random() - 0.5)
        setStarters(shuffled.slice(0, 3))
      } else if (availableStarters.length > 0) {
        // Если новых стартеров меньше 3, дополняем текущими
        const shuffled = [...availableStarters].sort(() => Math.random() - 0.5)
        const needed = 3 - shuffled.length
        const fromCurrent = [...currentStarters].sort(() => Math.random() - 0.5).slice(0, needed)
        const newStarters = [...shuffled, ...fromCurrent].sort(() => Math.random() - 0.5)
        setStarters(newStarters)
      } else {
        // Если все стартеры уже показаны, перемешиваем все заново
        // Убеждаемся, что получился другой набор
        let newStarters = getRandomStarters(allStarters)
        let attempts = 0
        while (JSON.stringify(newStarters) === JSON.stringify(currentStarters) && attempts < 10) {
          newStarters = getRandomStarters(allStarters)
          attempts++
        }
        setStarters(newStarters)
      }
    } finally {
      setIsLoadingMoreStarters(false)
    }
  }

  // Load new starters asynchronously on mount (only if less than 50)
  onMount(async () => {
    const currentStarters = loadStartersFromStorage()
    // Не запрашиваем новые, если уже есть 50 или больше стартеров
    if (currentStarters.length >= 50) return

    // Запрашиваем новые только если стартеров меньше 3 (для начальной загрузки)
    if (currentStarters.length < 3) {
      const newStarters = await loadNewStarters()
      if (newStarters.length > 0) {
        // Update starters with new random selection from expanded pool
        setStarters(getRandomStarters(loadStartersFromStorage()))
      }
    }
  })

  // Загружаем историю один раз через createResource и используем для сообщений и дерева
  const [chatHistory, { refetch: refetchHistory }] = createResource(
    () => sessionId(),
    async (sid) => {
      if (!sid) return null

      try {
        const historyRes = await fetch(`/api/chat/session/${sid}/history`, {
          cache: 'no-store',
          headers: { 'Cache-Control': 'no-cache' }
        })
        if (historyRes.ok) {
          const history = await historyRes.json()
          console.log('Loaded chat history:', history.length, 'messages')
          return history
        }
      } catch (error) {
        console.error('Failed to load chat history:', error)
      }
      return null
    }
  )

  // Обновляем сообщения из истории только при первой загрузке
  createEffect(() => {
    const history = chatHistory()
    if (!history || !Array.isArray(history) || messages().length > 0) return

    const transformedMessages = history
      .filter((msg: ChatHistoryMessage) => msg.role === 'user' || msg.role === 'assistant')
      .map((msg: ChatHistoryMessage) => ({
        id: typeof msg.id === 'number' ? msg.id : Number(msg.id) || Date.now(),
        role: (msg.role as 'user' | 'assistant') ?? 'user',
        content: msg.content || msg.message || ''
      }))

    if (transformedMessages.length > 0) {
      setMessages(transformedMessages)
    }
  })

  // conversationTree автоматически обновится при изменении chatHistory()
  // благодаря реактивности SolidJS - не нужно дополнительных эффектов

  const canRunDetectors = () => {
    const all = messages()
    const hasUser = all.some((m) => m.role === 'user')
    const hasAssistant = all.some((m) => m.role === 'assistant')
    // Разрешаем детекторы только после первого ответа бота и при наличии хотя бы одного пользовательского сообщения
    return hasUser && hasAssistant
  }

  const getCurrentTextForDetectors = () => {
    const current = inputValue().trim()
    if (current) return current
    const allMessages = messages()
    const lastUser = [...allMessages].reverse().find((m) => m.role === 'user')
    return lastUser?.content || ''
  }

  const appendDetectorResult = (title: string, payload: unknown) => {
    const summary =
      typeof payload === 'string' ? payload : `\`\`\`json\n${JSON.stringify(payload, null, 2)}\n\`\`\``
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now() + Math.random(),
        role: 'assistant',
        content: `🔍 ${title}\n\n${summary}`
      } as const
    ])
  }

  const generateSummary = async () => {
    if (!canShowAnalyticsPanel() || summaryLoading()) return

    setSummaryLoading(true)
    try {
      const conversationText = messages()
        .map((m) => `${m.role}: ${m.content}`)
        .join('\n\n')

      const res = await fetch('/api/summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: conversationText })
      })

      if (!res.ok) {
        appendDetectorResult('Саммари', `Ошибка: ${res.status} ${res.statusText}`)
        return
      }

      const data = await res.json()
      appendDetectorResult('Саммари диалога', data)
    } catch (e) {
      appendDetectorResult('Саммари', `Ошибка запроса: ${(e as Error).message}`)
    } finally {
      setSummaryLoading(false)
    }
  }

  const runDetector = async (kind: 'organisms' | 'ecosystems' | 'environment' | 'all') => {
    if (!canRunDetectors() || detectorLoading()) return
    const text = getCurrentTextForDetectors()
    if (!text) return
    setDetectorLoading(true)
    try {
      let endpoint = '/api/detect/organisms'
      if (kind === 'ecosystems') endpoint = '/api/detect/ecosystems'
      if (kind === 'environment') endpoint = '/api/detect/environment'
      if (kind === 'all') endpoint = '/api/detect/smart'

      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      })

      if (!res.ok) {
        // Показываем ошибку на кнопке вместо сообщения в чате
        setDetectorErrors(prev => ({ ...prev, [kind]: true }))
        // Автоматически сбрасываем ошибку через 2 секунды
        setTimeout(() => {
          setDetectorErrors(prev => ({ ...prev, [kind]: false }))
        }, 2000)
        return
      }

      const data = await res.json()
      const titleMap: Record<typeof kind, string> = {
        organisms: 'Организмы',
        ecosystems: 'Экосистемы',
        environment: 'Метрики среды',
        all: 'Анализ'
      }
      appendDetectorResult(titleMap[kind], data)
    } catch (e) {
      // Показываем ошибку на кнопке вместо сообщения в чате
      setDetectorErrors(prev => ({ ...prev, [kind]: true }))
      // Автоматически сбрасываем ошибку через 2 секунды
      setTimeout(() => {
        setDetectorErrors(prev => ({ ...prev, [kind]: false }))
      }, 2000)
    } finally {
      setDetectorLoading(false)
    }
  }

  const sendMessage = async () => {
    const text = inputValue().trim()
    if (!text || isLoading()) return

    // Add user message
    const userMessage: Message = { id: Date.now(), role: 'user', content: text }
    // Используем функциональное обновление для надежности
    setMessages((prev) => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    try {
      const res = await fetch('/api/chat/message', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          sessionId: sessionId(),
          author: 'user'
        })
      })
      const data = await res.json()

      // Update session ID if new one was created
      // НЕ обновляем sessionId если он уже установлен, чтобы не вызвать перезагрузку истории
      if (data.sessionId && !sessionId()) {
        setSessionId(data.sessionId)
      }

      // Add AI message
      const aiMessage: Message = {
        id: data.response?.messageId || Date.now() + 1,
        role: 'assistant',
        content: data.response?.message || '🤷',
        sources: data.response?.sources || []
      }
      // Обновляем сообщения, добавляя новое AI сообщение
      setMessages((prev) => [...prev, aiMessage])

      // Обновляем историю - createEffect автоматически обновит дерево при изменении истории
      void refetchHistory()
      // Обновляем дерево, увеличивая ключ обновления
      setTreeRefreshKey((prev) => prev + 1)
    } catch {
      const errorMessage: Message = {
        id: Date.now() + 1,
        role: 'assistant',
        content: '⚠️'
      }
      setMessages([...messages(), errorMessage])
    }

    setIsLoading(false)
  }

  // Обработка ресайза за верхний край
  const handleResizeStart = (e: MouseEvent) => {
    if (isServer || !textareaRef || !inputAreaRef) return
    e.preventDefault()
    e.stopPropagation()
    setIsResizing(true)
    startY = e.clientY
    startHeight = textareaRef.offsetHeight
    document.addEventListener('mousemove', handleResizeMove)
    document.addEventListener('mouseup', handleResizeEnd)
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'ns-resize'
  }

  const handleResizeMove = (e: MouseEvent) => {
    if (!isResizing() || !textareaRef || !inputAreaRef) return
    e.preventDefault()
    const deltaY = startY - e.clientY // Инвертируем, так как тянем вверх
    const newHeight = Math.max(48, Math.min(400, startHeight + deltaY))
    setInputHeight(newHeight)
    textareaRef.style.height = `${newHeight}px`
    textareaRef.style.minHeight = `${newHeight}px`
  }

  const handleResizeEnd = () => {
    setIsResizing(false)
    document.removeEventListener('mousemove', handleResizeMove)
    document.removeEventListener('mouseup', handleResizeEnd)
    document.body.style.userSelect = ''
    document.body.style.cursor = ''
  }

  onCleanup(() => {
    document.removeEventListener('mousemove', handleResizeMove)
    document.removeEventListener('mouseup', handleResizeEnd)
  })

  // Загрузка дерева диалога для текущей сессии
  // Используем уже загруженную историю из chatHistory, чтобы избежать дублирования запросов
  const [conversationTree] = createResource(
    () => {
      const sid = sessionId()
      if (!sid) return null
      // Ждем, пока история загрузится (chatHistory() вернет undefined пока загружается)
      const history = chatHistory()
      return [sid, treeRefreshKey(), history] as const
    },
    async ([sid, _refreshKey, history]): Promise<TreeResponse | null> => {
      if (!sid) return null

      // Используем уже загруженную историю, если она есть
      if (history && Array.isArray(history) && history.length > 0) {
        // Преобразуем историю в формат TreeResponse
        const nodes: ConceptNode[] = history.map(
          (msg: ChatHistoryMessage): ConceptNode => ({
            id: String(msg.id || Date.now()),
            parentId: msg.parentId || null,
            childrenIds: msg.childrenIds || [],
            content: msg.content || msg.message || '',
            role: msg.role || 'user',
            type: (msg.type as ConceptNode['type']) || 'message',
            category: (msg.category as ConceptNode['category']) || 'neutral',
            timestamp: msg.timestamp || Date.now(),
            sources: [], // MessageSource[] is incompatible with ConceptNode sources format
            sessionId: msg.sessionId || sid,
            position: { x: 0, y: 0, z: 0 }
          })
        )

        // Находим корневой узел (системный или первый без родителя)
        const rootNode =
          nodes.find((n) => !n.parentId && n.role === 'system') ||
          nodes.find((n) => !n.parentId) ||
          nodes[0]

        console.log('Tree built with', nodes.length, 'nodes, root:', rootNode?.id)

        const treeResponse: TreeResponse = {
          root: rootNode || {
            id: sid,
            parentId: null,
            childrenIds: [],
            content: '',
            role: 'system',
            type: 'message',
            category: 'neutral',
            timestamp: Date.now(),
            sources: [],
            sessionId: sid,
            position: { x: 0, y: 0, z: 0 }
          },
          total: 0,
          nodes,
          stats: {
            totalNodes: nodes.length,
            maxDepth: 1,
            rootNodes: 1
          }
        }
        return treeResponse
      }

      // Если история пустая или null, пробуем загрузить через KB API
      if (history === null || (Array.isArray(history) && history.length === 0)) {
        try {
          const tree = await kb.getTree({ rootId: sid, depth: 10, limit: 1000 })
          if (tree?.nodes?.length > 0) {
            return tree
          }
        } catch (error) {
          console.error('Failed to load conversation tree from KB:', error)
        }
      }

      // Если ничего не загрузилось, возвращаем пустое дерево
      const emptyTree: TreeResponse = {
        root: {
          id: sid,
          parentId: null,
          childrenIds: [],
          content: '',
          role: 'system',
          type: 'message',
          category: 'neutral',
          timestamp: Date.now(),
          sources: [],
          sessionId: sid,
          position: { x: 0, y: 0, z: 0 }
        },
        nodes: [],
        stats: {
          totalNodes: 0,
          maxDepth: 0,
          rootNodes: 0
        },
        total: 0
      }
      return emptyTree
    }
  )

  // Функция для копирования текста с форматированием
  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      // Можно добавить уведомление об успешном копировании
    } catch (err) {
      console.error('Failed to copy:', err)
      // Fallback для старых браузеров
      const textArea = document.createElement('textarea')
      textArea.value = text
      textArea.style.position = 'fixed'
      textArea.style.opacity = '0'
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
    }
  }

  // Функция для копирования всего диалога
  const copyFullConversation = () => {
    const conversationText = messages()
      .map((msg) => {
        const roleLabel = msg.role === 'user' ? 'Пользователь' : 'Ассистент'
        return `${roleLabel}:\n${msg.content}\n`
      })
      .join('\n---\n\n')
    void copyToClipboard(conversationText)
  }

  // Функция для начала редактирования
  const startEditing = (messageId: number, currentContent: string) => {
    setEditingMessageId(messageId)
    setEditingContent(currentContent)
  }

  // Функция для отмены редактирования
  const cancelEditing = () => {
    setEditingMessageId(null)
    setEditingContent('')
  }

  // Функция для сохранения отредактированного сообщения как новой ноды
  const saveEditedMessage = async (originalMessageId: number) => {
    const editedText = editingContent().trim()
    if (!editedText) {
      cancelEditing()
      return
    }

    const message = messages().find((m) => m.id === originalMessageId)
    if (!message) {
      cancelEditing()
      return
    }

    try {
      const currentSessionId = sessionId()
      if (!currentSessionId) {
        console.error('No session ID available')
        cancelEditing()
        return
      }

      // Создаем новую ноду с отредактированным содержимым
      // Создаем как новую независимую ноду (не привязанную к оригиналу)
      // Используем sessionId как parentId, если он есть, чтобы привязать к текущей сессии
      const parentId = currentSessionId || null
      await kb.createNode({
        parentId,
        content: editedText,
        role: message.role as 'user' | 'assistant' | 'system'
      })

      // Добавляем отредактированное сообщение в чат
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + Math.random(),
          role: message.role,
          content: editedText
        } as const
      ])

      cancelEditing()
    } catch (error) {
      console.error('Failed to save edited message:', error)
      alert('Не удалось сохранить отредактированное сообщение. Попробуйте еще раз.')
    }
  }

  // Функция для запуска фактчекера
  const runFactCheck = async (text: string) => {
    if (detectorLoading()) return
    setDetectorLoading(true)
    try {
      const res = await fetch('/api/detect/factcheck', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      })

      if (!res.ok) {
        appendDetectorResult('Фактчекер', `Ошибка: ${res.status} ${res.statusText}`)
        return
      }

      const data = await res.json()
      const statusMap: Record<string, string> = {
        true: '✅ Верно',
        false: '❌ Ложно',
        partial: '⚠️ Частично верно',
        unverifiable: '❓ Нельзя проверить',
        unknown: '❓ Неизвестно'
      }
      const status = statusMap[data.status] || data.status
      const confidence = data.details?.confidence
        ? ` (уверенность: ${(data.details.confidence * 100).toFixed(0)}%)`
        : ''
      appendDetectorResult(
        'Фактчекер',
        `${status}${confidence}\n\nДетали: ${JSON.stringify(data.details, null, 2)}`
      )
    } catch (e) {
      appendDetectorResult('Фактчекер', `Ошибка запроса: ${(e as Error).message}`)
    } finally {
      setDetectorLoading(false)
    }
  }

  return (
    <div class={styles.interviewContainer}>
      <div class={styles.chatMain}>
        <div class={styles.chatMessages}>
          <For each={messages()}>
            {(message) => (
              <div
                class={`${styles.conceptBubble} ${message.role === 'user' ? styles.userConcept : styles.aiConcept}`}
              >
                <Show
                  when={editingMessageId() === message.id}
                  fallback={
                    <>
                      <div class={styles.conceptContent}>
                        <MarkdownRenderer content={message.content} />
                      </div>
                      <MessageActions
                        content={message.content}
                        onCopy={() => copyToClipboard(message.content)}
                        onFactCheck={() => void runFactCheck(message.content)}
                        onEdit={() => startEditing(message.id as number, message.content)}
                        isFactCheckLoading={detectorLoading()}
                      />
                      {/* Отображение источников для AI сообщений */}
                      <Show
                        when={message.role === 'assistant' && message.sources && message.sources.length > 0}
                      >
                        <div class={styles.sourcesSection}>
                          <h5 class={styles.sourcesTitle}>Источники:</h5>
                          <ul class={styles.sourcesList}>
                            <For each={message.sources}>
                              {(source: MessageSource) => (
                                <li class={styles.sourceItem}>
                                  <span class={styles.sourceTitle}>{source.title}</span>
                                  <Show when={source.type}>
                                    <span class={styles.sourceType}>({source.type})</span>
                                  </Show>
                                </li>
                              )}
                            </For>
                          </ul>
                        </div>
                      </Show>
                    </>
                  }
                >
                  <MessageEditor
                    content={editingContent()}
                    onContentChange={setEditingContent}
                    onSave={() => void saveEditedMessage(message.id as number)}
                    onCancel={cancelEditing}
                  />
                </Show>
              </div>
            )}
          </For>

          <Show when={isLoading()}>
            <div class={`${styles.conceptBubble} ${styles.aiConcept} ${styles.loading}`}>
              <div class={styles.typingIndicator}>
                <div class={styles.dot} />
                <div class={styles.dot} />
                <div class={styles.dot} />
              </div>
            </div>
          </Show>

          {/* Show buttons only for new sessions (no messages yet) */}
          <Show when={messages().length === 0}>
            <div class={styles.quickButtons}>
              <div class={styles.quickButtonsTitle}>Начните разговор:</div>
              <div class={styles.quickButtonsGrid}>
                <For each={starters()}>
                  {(starter, index) => (
                    <button
                      class={styles.quickButton}
                      onClick={() => {
                        setInputValue(starter)
                        void sendMessage()
                      }}
                    >
                      <span class={styles.quickButtonIcon}>
                        {index() === 0 ? '🤝' : index() === 1 ? '🌱' : '💡'}
                      </span>
                      <span class={styles.quickButtonText}>{starter}</span>
                    </button>
                  )}
                </For>
                <button
                  class={styles.moreButton}
                  onClick={() => {
                    void loadMoreStarters()
                  }}
                  disabled={isLoadingMoreStarters()}
                  title="Показать другие варианты"
                >
                  <Show
                    when={isLoadingMoreStarters()}
                    fallback={<span class={styles.moreButtonIcon}>↻</span>}
                  >
                    <div class={styles.typingIndicator}>
                      <div class={styles.dot} />
                      <div class={styles.dot} />
                      <div class={styles.dot} />
                    </div>
                  </Show>
                  <span class={styles.moreButtonText}>Ещё</span>
                </button>
              </div>
            </div>
          </Show>

          {/* Кнопки копирования и шеринга для всего диалога */}
          <Show when={messages().length > 0}>
            <ConversationActions
              onCopy={copyFullConversation}
              onShare={() => {
                const currentSessionId = sessionId()
                if (currentSessionId) {
                  const shareUrl = `${window.location.origin}/chat/${currentSessionId}`
                  if (navigator.share) {
                    void navigator.share({
                      title: 'Диалог',
                      text: 'Посмотрите этот диалог',
                      url: shareUrl
                    })
                  } else {
                    // Копируем ссылку в буфер обмена
                    void navigator.clipboard.writeText(shareUrl).then(() => {
                      alert('Ссылка скопирована в буфер обмена!')
                    })
                  }
                } else {
                  alert('Невозможно создать ссылку: нет активной сессии')
                }
              }}
            />
          </Show>
        </div>

        <div class={styles.chatInputArea} ref={inputAreaRef}>
          <div class={styles.resizeHandle} onMouseDown={handleResizeStart} />
          <textarea
            ref={textareaRef}
            placeholder="Введите ваше сообщение..."
            value={inputValue()}
            onInput={(e) => {
              setInputValue(e.currentTarget.value)
              // Автоматическое изменение высоты при вводе
              if (textareaRef) {
                textareaRef.style.height = 'auto'
                const newHeight = Math.min(400, Math.max(48, textareaRef.scrollHeight))
                textareaRef.style.height = `${newHeight}px`
                setInputHeight(newHeight)
              }
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void sendMessage()
              }
            }}
            disabled={isLoading()}
            class={styles.chatInput}
            style={{ height: `${inputHeight()}px` }}
            rows={2}
          />
          <div class={styles.actionsGroup}>
            <button
              onClick={() => setIsPanelOpen(!isPanelOpen())}
              disabled={!canShowAnalyticsPanel()}
              class={styles.menuBtn}
              title={
                !canShowAnalyticsPanel()
                  ? 'Нужно хотя бы 2 сообщения для аналитики'
                  : isPanelOpen()
                    ? 'Закрыть аналитическую панель'
                    : 'Открыть аналитическую панель'
              }
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>
            <button
              onClick={sendMessage}
              disabled={isLoading() || !inputValue().trim()}
              class={styles.sendBtn}
              title="Отправить"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </button>
          </div>
        </div>

        {/* Правая панель со связанными знаниями */}
        <div class={`${styles.conversationTree} ${isPanelOpen() ? styles.panelOpen : ''}`}>
          <div class={styles.treeHeader}>
            <DetectorsToolbar onRunDetector={runDetector} detectorLoading={detectorLoading()} detectorErrors={detectorErrors()} />
            <button
              onClick={generateSummary}
              disabled={!canShowAnalyticsPanel() || summaryLoading()}
              class={styles.summaryBtn}
              title={summaryLoading() ? 'Генерация саммари...' : 'Создать саммари диалога'}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14,2 14,8 20,8" />
                <line x1="16" y1="13" x2="8" y2="13" />
                <line x1="16" y1="17" x2="8" y2="17" />
                <polyline points="10,9 9,9 8,9" />
              </svg>
              {summaryLoading() && <span class={styles.loadingSpinner}></span>}
            </button>
            <button
              onClick={() => setIsPanelOpen(false)}
              class={styles.closePanelBtn}
              title="Закрыть панель"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
          <div class={styles.treeContent}>
            <RelatedKnowledge
              messages={messages()}
              onRunDetector={runDetector}
              detectorLoading={detectorLoading()}
              canRunDetectors={canRunDetectors()}
            />
            <Show when={conversationTree() && conversationTree()!.stats?.totalNodes}>
              <div class={styles.treeStats}>
                <div class={styles.treeStatItem}>
                  <span class={styles.treeStatLabel}>Узлов:</span>
                  <span class={styles.treeStatValue}>{conversationTree()!.stats?.totalNodes}</span>
                </div>
                <div class={styles.treeStatItem}>
                  <span class={styles.treeStatLabel}>Глубина:</span>
                  <span class={styles.treeStatValue}>{conversationTree()!.stats?.maxDepth}</span>
                </div>
              </div>
            </Show>
          </div>
        </div>
      </div>
    </div>
  )
}

export default InterviewPage
