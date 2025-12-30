import { createSignal, For, Show } from 'solid-js'
import { useKnowledgeBase } from '~/contexts/KnowledgeBaseContext'
import { useSession } from '~/contexts/SessionContext'
import type { ConceptNode, TreeResponse } from '~/types/kb'
import styles from './ConversationGraph.module.css'

interface ConversationGraphProps {
  tree: TreeResponse | null
  onNodeSelect?: (nodeId: string) => void
  onBranchCreate?: (parentId: string) => Promise<void> | void
  onRunDetector?: (kind: 'organisms' | 'ecosystems' | 'environment' | 'all', nodeId: string) => void
  onEditNode?: (nodeId: string) => void
  onFactCheck?: (nodeId: string) => void
  onSearch?: (nodeId: string) => void
}

/**
 * Компонент для отображения беседы в виде вертикального плоского графа
 * с возможностью создания развилок
 */
export const ConversationGraph = (props: ConversationGraphProps) => {
  const kb = useKnowledgeBase()
  const { sessionId } = useSession()
  const [selectedNodeId, setSelectedNodeId] = createSignal<string | null>(null)
  const [branchInputVisible, setBranchInputVisible] = createSignal<string | null>(null)
  const [branchInputValue, setBranchInputValue] = createSignal('')
  const [isCreatingBranch, setIsCreatingBranch] = createSignal(false)
  const [hoveredNodeId, setHoveredNodeId] = createSignal<string | null>(null)

  // Построение плоского списка узлов в порядке обхода дерева
  const buildFlatList = (nodes: ConceptNode[]): ConceptNode[] => {
    if (nodes.length === 0) return []

    // Фильтруем только сообщения (исключаем системные узлы)
    const messageNodes = nodes.filter(
      (n) => n.type === 'message' && (n.role === 'user' || n.role === 'assistant')
    )

    if (messageNodes.length === 0) {
      // Если нет сообщений, но есть узлы, показываем все
      return nodes.sort((a, b) => a.timestamp - b.timestamp)
    }

    // Находим корневой узел (системный узел сессии или первый узел без родителя)
    const rootId = props.tree?.root_id
    let root = rootId ? messageNodes.find((n) => n.id === rootId) : null

    // Если не нашли по rootId, ищем первый узел без родителя или системный
    if (!root) {
      root =
        nodes.find((n) => !n.parentId && n.role === 'system') ||
        nodes.find((n) => !n.parentId) ||
        messageNodes[0]
    }

    // Если корня нет, просто сортируем по времени
    if (!root) {
      return messageNodes.sort((a, b) => a.timestamp - b.timestamp)
    }

    const result: ConceptNode[] = []
    const nodeMap = new Map<string, ConceptNode>()
    const childrenMap = new Map<string, ConceptNode[]>()

    // Создаем карты для быстрого доступа (используем все узлы для связей)
    nodes.forEach((node) => {
      nodeMap.set(node.id, node)
      if (node.parentId) {
        if (!childrenMap.has(node.parentId)) {
          childrenMap.set(node.parentId, [])
        }
        childrenMap.get(node.parentId)!.push(node)
      }
    })

    // Рекурсивная функция для обхода дерева
    const traverse = (nodeId: string, depth: number) => {
      const node = nodeMap.get(nodeId)
      if (!node) return

      // Добавляем только сообщения в результат
      if (node.type === 'message' && (node.role === 'user' || node.role === 'assistant')) {
        result.push(node)
      }

      const children = childrenMap.get(nodeId) || []
      // Сортируем детей по timestamp для хронологического порядка
      children.sort((a, b) => a.timestamp - b.timestamp)

      children.forEach((child) => {
        traverse(child.id, depth + 1)
      })
    }

    // Начинаем обход от корня, но пропускаем системные узлы в выводе
    if (root.role === 'system') {
      // Если корень системный, начинаем с его детей
      const rootChildren = childrenMap.get(root.id) || []
      rootChildren.sort((a, b) => a.timestamp - b.timestamp)
      rootChildren.forEach((child) => {
        traverse(child.id, 0)
      })
    } else {
      traverse(root.id, 0)
    }

    // Если результат пустой, но есть сообщения, просто сортируем их по времени
    if (result.length === 0 && messageNodes.length > 0) {
      return messageNodes.sort((a, b) => a.timestamp - b.timestamp)
    }

    return result
  }

  const flatNodes = () => {
    if (!props.tree || !props.tree.nodes.length) return []
    return buildFlatList(props.tree.nodes)
  }

  // Получение детей узла
  const getNodeChildren = (nodeId: string): ConceptNode[] => {
    return flatNodes().filter((n) => n.parentId === nodeId)
  }

  // Получение родителя узла
  const getNodeParent = (nodeId: string): ConceptNode | null => {
    const node = flatNodes().find((n) => n.id === nodeId)
    if (!node || !node.parentId) return null
    return flatNodes().find((n) => n.id === node.parentId) || null
  }

  // Получение всех братьев узла (узлы с тем же родителем)
  const getNodeSiblings = (nodeId: string): ConceptNode[] => {
    const node = flatNodes().find((n) => n.id === nodeId)
    if (!node || !node.parentId) return []
    return flatNodes().filter((n) => n.parentId === node.parentId && n.id !== nodeId)
  }

  // Создание развилки (нового ответа от существующего узла)
  const handleCreateBranch = async (parentId: string) => {
    const text = branchInputValue().trim()
    if (!text || isCreatingBranch()) return

    setIsCreatingBranch(true)
    try {
      const currentSessionId = sessionId()
      if (!currentSessionId) {
        console.error('No session ID available')
        return
      }

      // Создаем новый узел в базе знаний с указанным parentId
      // Это создаст развилку от существующего узла
      const newNode = await kb.createNode({
        parentId,
        content: text,
        role: 'user'
      })

      // Используем continueConversationFromNode для генерации ответа от нового узла
      // Это создаст ответный узел от newNode.id
      await kb.continueConversationFromNode({
        nodeId: newNode.id,
        message: text,
        sessionId: currentSessionId
      })

      setBranchInputValue('')
      setBranchInputVisible(null)

      // Вызываем callback для обновления дерева
      await props.onBranchCreate?.(parentId)
    } catch (error) {
      console.error('Failed to create branch:', error)
      alert('Не удалось создать развилку. Попробуйте еще раз.')
    } finally {
      setIsCreatingBranch(false)
    }
  }

  // Обработка клика по узлу
  const handleNodeClick = (nodeId: string) => {
    setSelectedNodeId(nodeId)
    props.onNodeSelect?.(nodeId)
  }

  return (
    <div class={styles.graphContainer}>
      <div class={styles.graphList}>
        <For each={flatNodes()}>
          {(node, _idx) => {
            const children = () => getNodeChildren(node.id)
            const siblings = () => getNodeSiblings(node.id)
            const parent = () => getNodeParent(node.id)
            const hasBranches = () => children().length > 1
            const isSelected = () => selectedNodeId() === node.id
            const showInput = () => branchInputVisible() === node.id

            const isHovered = () => hoveredNodeId() === node.id

            return (
              <div
                class={`${styles.graphNode} ${isSelected() ? styles.selected : ''} ${
                  hasBranches() ? styles.hasBranches : ''
                }`}
                onClick={() => handleNodeClick(node.id)}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
              >
                {/* Линия связи с родителем */}
                <Show when={parent()}>
                  <div class={styles.connectionLine} />
                </Show>

                {/* Индикатор развилки */}
                <Show when={hasBranches()}>
                  <div class={styles.branchIndicator}>
                    <span class={styles.branchCount}>{children().length}</span>
                  </div>
                </Show>

                {/* Содержимое узла */}
                <div class={styles.nodeContent}>
                  <div class={styles.nodeHeader}>
                    <span class={styles.nodeRole}>{node.role === 'user' ? '👤' : '🤖'}</span>
                    <span class={styles.nodeText}>{node.content}</span>
                  </div>

                  {/* Показываем братьев (альтернативные ветки) */}
                  <Show when={siblings().length > 0}>
                    <div class={styles.siblingsIndicator}>
                      <span class={styles.siblingsLabel}>
                        {siblings().length} альтернатив{siblings().length === 1 ? 'а' : 'ы'}
                      </span>
                    </div>
                  </Show>

                  {/* Действия при наведении (не показываем для системных узлов) */}
                  <Show when={isHovered() && node.role !== 'system'}>
                    <div class={styles.nodeActions} onClick={(e) => e.stopPropagation()}>
                      <a
                        class={styles.actionLink}
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          props.onFactCheck?.(node.id)
                        }}
                      >
                        Фактчекер
                      </a>
                      <a
                        class={styles.actionLink}
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          props.onEditNode?.(node.id)
                        }}
                      >
                        Редактирование
                      </a>
                      <a
                        class={styles.actionLink}
                        href="#"
                        onClick={(e) => {
                          e.preventDefault()
                          e.stopPropagation()
                          props.onSearch?.(node.id)
                        }}
                      >
                        Поиск
                      </a>
                    </div>
                  </Show>

                  {/* Поле ввода для новой развилки */}
                  <Show when={showInput()}>
                    <div class={styles.branchInputContainer} onClick={(e) => e.stopPropagation()}>
                      <textarea
                        class={styles.branchInput}
                        placeholder="Введите альтернативный ответ..."
                        value={branchInputValue()}
                        onInput={(e) => setBranchInputValue(e.currentTarget.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !e.shiftKey) {
                            e.preventDefault()
                            void handleCreateBranch(node.id)
                          }
                          if (e.key === 'Escape') {
                            setBranchInputVisible(null)
                            setBranchInputValue('')
                          }
                        }}
                        disabled={isCreatingBranch()}
                        rows={2}
                      />
                      <div class={styles.branchInputActions}>
                        <button
                          class={styles.branchInputButton}
                          onClick={() => {
                            void handleCreateBranch(node.id)
                          }}
                          disabled={isCreatingBranch() || !branchInputValue().trim()}
                        >
                          {isCreatingBranch() ? 'Создание...' : 'Создать'}
                        </button>
                        <button
                          class={styles.branchInputCancel}
                          onClick={() => {
                            setBranchInputVisible(null)
                            setBranchInputValue('')
                          }}
                        >
                          Отмена
                        </button>
                      </div>
                    </div>
                  </Show>
                </div>
              </div>
            )
          }}
        </For>
      </div>

      <Show when={flatNodes().length === 0}>
        <div class={styles.emptyState}>
          <p>Граф беседы появится после отправки сообщения</p>
          <p class={styles.emptyStateHint}>Отправьте сообщение, чтобы увидеть структуру диалога</p>
        </div>
      </Show>
    </div>
  )
}
