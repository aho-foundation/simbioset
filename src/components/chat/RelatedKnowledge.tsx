import { createResource, For, Show } from 'solid-js'
import { useKnowledgeBase } from '~/contexts/KnowledgeBaseContext'
import { useSession } from '~/contexts/SessionContext'
import type { Message } from '~/types/chat'
import type { ConceptNode, Source } from '~/types/kb'
import styles from './RelatedKnowledge.module.css'

interface RelatedKnowledgeProps {
  messages: Message[]
  onRunDetector?: (kind: 'organisms' | 'ecosystems' | 'environment' | 'all') => void
  detectorLoading?: boolean
  canRunDetectors?: boolean
}

export const RelatedKnowledge = (props: RelatedKnowledgeProps) => {
  const kb = useKnowledgeBase()
  const { sessionId } = useSession()

  // Поиск связанных узлов из базы знаний
  const [relatedNodes] = createResource(
    () => props.messages,
    async (msgs) => {
      if (!msgs || msgs.length === 0) return []
      try {
        // Берем содержимое всех сообщений для поиска
        const searchText = msgs.map((m) => m.content).join(' ')
        const results = await kb.searchNodes(searchText, { limit: 10 })
        return results.results?.map((r) => r.node) || []
      } catch (error) {
        console.error('Failed to load related nodes:', error)
        return []
      }
    }
  )

  // Поиск похожих диалогов
  const [similarDialogs] = createResource(
    () => ({ sessionId: sessionId(), messages: props.messages }),
    async ({ sessionId: sid, messages: msgs }) => {
      if (!sid || !msgs || msgs.length === 0) return []
      try {
        // Получаем все сессии
        const sessions = await kb.getChatSessions()
        // Фильтруем текущую сессию
        const otherSessions = sessions.filter((s) => s.id !== sid)

        // Ищем похожие по содержимому
        const searchText = msgs.map((m) => m.content).join(' ')
        const similar: Array<{ session: ConceptNode; similarity: number }> = []

        for (const session of otherSessions.slice(0, 20)) {
          // Простое сравнение по ключевым словам (можно улучшить)
          const sessionText = session.content || ''
          const commonWords = searchText
            .toLowerCase()
            .split(/\s+/)
            .filter((word) => word.length > 3 && sessionText.toLowerCase().includes(word))
          if (commonWords.length > 0) {
            similar.push({
              session,
              similarity: commonWords.length / Math.max(searchText.split(/\s+/).length, 1)
            })
          }
        }

        return similar
          .sort((a, b) => b.similarity - a.similarity)
          .slice(0, 5)
          .map((item) => item.session)
      } catch (error) {
        console.error('Failed to load similar dialogs:', error)
        return []
      }
    }
  )

  // Получение источников из сообщений
  const [sources] = createResource(
    () => relatedNodes(),
    async (nodes) => {
      if (!nodes || nodes.length === 0) return []
      try {
        const allSources: Array<{ id: string; title: string; url?: string; nodeId: string }> = []

        // Ищем источники в связанных узлах
        for (const node of nodes) {
          try {
            const nodeWithContext = await kb.getNode(node.id)
            if (nodeWithContext.node.sources && nodeWithContext.node.sources.length > 0) {
              for (const sourceRef of nodeWithContext.node.sources) {
                if (sourceRef && typeof sourceRef === 'object' && 'source' in sourceRef) {
                  const source = (sourceRef as { source: Source }).source
                  allSources.push({
                    id: source.id,
                    title: source.title || 'Источник',
                    url: source.url,
                    nodeId: node.id
                  })
                }
              }
            }
          } catch (e) {
            // Пропускаем узлы без источников
            console.debug('Node without sources or error loading node:', node.id, e)
          }
        }

        // Убираем дубликаты
        const uniqueSources = Array.from(new Map(allSources.map((s) => [s.id, s])).values())

        return uniqueSources
      } catch (error) {
        console.error('Failed to load sources:', error)
        return []
      }
    }
  )

  return (
    <div class={styles.relatedKnowledge}>
      {/* Связанные узлы из базы знаний */}
      <div class={styles.section}>
        <h4 class={styles.sectionTitle}>Связанные узлы</h4>
        <Show
          when={!relatedNodes.loading && relatedNodes() && relatedNodes()!.length > 0}
          fallback={
            <div class={styles.emptyState}>
              {relatedNodes.loading ? 'Загрузка...' : 'Связанные узлы не найдены'}
            </div>
          }
        >
          <div class={styles.nodesList}>
            <For each={relatedNodes()}>
              {(node) => (
                <div
                  class={styles.nodeItem}
                  onClick={() => {
                    // Можно добавить навигацию к узлу
                    console.log('Navigate to node:', node.id)
                  }}
                >
                  <div class={styles.nodeContent}>
                    {node.content && node.content.length > 100
                      ? `${node.content.substring(0, 100)}...`
                      : node.content || 'Узел без содержимого'}
                  </div>
                  <div class={styles.nodeMeta}>
                    {node.type && <span class={styles.nodeType}>{node.type}</span>}
                    {node.category && <span class={styles.nodeCategory}>{node.category}</span>}
                  </div>
                </div>
              )}
            </For>
          </div>
        </Show>
      </div>

      {/* Похожие диалоги */}
      <div class={styles.section}>
        <h4 class={styles.sectionTitle}>Похожие диалоги</h4>
        <Show
          when={!similarDialogs.loading && similarDialogs() && similarDialogs()!.length > 0}
          fallback={
            <div class={styles.emptyState}>
              {similarDialogs.loading ? 'Загрузка...' : 'Похожие диалоги не найдены'}
            </div>
          }
        >
          <div class={styles.dialogsList}>
            <For each={similarDialogs()}>
              {(session) => (
                <div
                  class={styles.dialogItem}
                  onClick={() => {
                    // Переключение на другой диалог
                    console.log('Switch to session:', session.id)
                  }}
                >
                  <div class={styles.dialogContent}>
                    {session.content && session.content.length > 80
                      ? `${session.content.substring(0, 80)}...`
                      : session.content || 'Диалог без названия'}
                  </div>
                  <div class={styles.dialogMeta}>
                    {session.childrenIds && session.childrenIds.length > 0 && (
                      <span class={styles.dialogCount}>{session.childrenIds.length} сообщений</span>
                    )}
                  </div>
                </div>
              )}
            </For>
          </div>
        </Show>
      </div>

      {/* Источники */}
      <div class={styles.section}>
        <h4 class={styles.sectionTitle}>Источники</h4>
        <Show
          when={!sources.loading && sources() && sources()!.length > 0}
          fallback={
            <div class={styles.emptyState}>{sources.loading ? 'Загрузка...' : 'Источники не найдены'}</div>
          }
        >
          <div class={styles.sourcesList}>
            <For each={sources()}>
              {(source) => (
                <div class={styles.sourceItem}>
                  {source.url ? (
                    <a
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      class={styles.sourceLink}
                    >
                      {source.title}
                    </a>
                  ) : (
                    <span class={styles.sourceTitle}>{source.title}</span>
                  )}
                </div>
              )}
            </For>
          </div>
        </Show>
      </div>
    </div>
  )
}
