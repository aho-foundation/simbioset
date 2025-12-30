import { type Component, createSignal, onCleanup, onMount, Show } from 'solid-js'
import { isServer } from 'solid-js/web'
import ConversationsNav from '~/components/ConversationsNav'
import styles from '~/styles/knowledge-tree.module.css'
import type { ConceptNode } from '~/types/kb'

interface TreeUpdate {
  root?: ConceptNode | null
  nodes?: ConceptNode[]
  stats?: {
    totalNodes: number
    maxDepth: number
    rootNodes: number
  } | null
  error?: string
}

const KnowledgeTreePage: Component = () => {
  const [treeData, setTreeData] = createSignal<ConceptNode[]>([])
  const [loading, setLoading] = createSignal(true)
  const [error, setError] = createSignal<string | null>(null)
  const [_selectedNode, setSelectedNode] = createSignal<ConceptNode | null>(null)

  let eventSource: EventSource | null = null

  // Подключение к SSE потоку для автоматического обновления
  onMount(() => {
    if (isServer) return

    const connectSSE = () => {
      try {
        const url = new URL('/api/kb/tree/stream', window.location.origin)
        url.searchParams.set('depth', '3')
        url.searchParams.set('limit', '100')

        eventSource = new EventSource(url.toString())

        eventSource.onopen = () => {
          console.log('SSE connection opened')
          setError(null)
        }

        eventSource.onmessage = (event) => {
          try {
            const update: TreeUpdate = JSON.parse(event.data)

            // Проверяем наличие ошибки
            if (update.error) {
              console.error('SSE error:', update.error)
              setError(update.error)
              setLoading(false)
              return
            }

            // Обновляем дерево при получении новых данных
            // nodes может быть пустым массивом - это нормально
            if (update.nodes !== undefined) {
              setTreeData(update.nodes)
              setLoading(false)
              setError(null)
            }
          } catch (err) {
            console.error('Failed to parse SSE message:', err)
            setError('Ошибка при обработке данных')
            setLoading(false)
          }
        }

        eventSource.onerror = (err) => {
          console.error('SSE connection error:', err)
          setError('Ошибка подключения к серверу')
          eventSource?.close()

          // Переподключение через 5 секунд
          setTimeout(() => {
            if (eventSource?.readyState === EventSource.CLOSED) {
              connectSSE()
            }
          }, 5000)
        }
      } catch (err) {
        console.error('Failed to create SSE connection:', err)
        setError('Не удалось подключиться к серверу')
      }
    }

    connectSSE()
  })

  onCleanup(() => {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  })

  // Обработчик выбора ноды
  const handleNodeSelect = (node: ConceptNode) => {
    console.log('Node selected:', node.id)
    setSelectedNode(node)
  }

  return (
    <div class={styles.knowledgeTreePage}>
      <div class={styles.header}>
        <div class={styles.featureIcon}>🌳</div>
        <h1 class={styles.title}>Интерактивное дерево знаний</h1>
        <p class={styles.subtitle}>Исследуйте структурированные знания симбиосети</p>
      </div>

      <div class={styles.content}>
        <Show when={loading()}>
          <div class={styles.loading}>
            <div class={styles.spinner} />
            <p>Загрузка дерева знаний...</p>
          </div>
        </Show>

        <Show when={!loading() && error()}>
          <div class={styles.error}>
            <p class={styles.errorMessage}>Ошибка загрузки дерева знаний: {error()}</p>
            <p class={styles.errorMessage}>Попытка переподключения...</p>
          </div>
        </Show>

        <Show when={!loading() && !error()}>
          <Show when={treeData() && treeData()!.length > 0}>
            <div class={styles.threeDContainer}>
              <ConversationsNav nodes={treeData()!} onNodeSelect={handleNodeSelect} />
            </div>
          </Show>
          <Show when={treeData() && treeData()!.length === 0}>
            <div class={styles.empty}>
              <p>Дерево знаний пусто</p>
            </div>
          </Show>
        </Show>
      </div>
    </div>
  )
}

export default KnowledgeTreePage
