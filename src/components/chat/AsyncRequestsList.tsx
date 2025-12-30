import { createEffect, createSignal, For, onCleanup, onMount, Show } from 'solid-js'
import { isServer } from 'solid-js/web'
import styles from './AsyncRequestsList.module.css'

export interface AsyncRequest {
  id: string
  type: 'message' | 'detector' | 'factcheck' | 'search' | 'other'
  status: 'pending' | 'processing' | 'completed' | 'error'
  title: string
  description?: string
  createdAt: number
  completedAt?: number
  error?: string
  result?: unknown
}

interface AsyncRequestsListProps {
  requests?: AsyncRequest[]
  onClose?: () => void
}

/**
 * Компонент для отображения списка асинхронных запросов
 * с отслеживанием статуса через SSE
 */
export const AsyncRequestsList = (props: AsyncRequestsListProps) => {
  const [requests, setRequests] = createSignal<AsyncRequest[]>(props.requests || [])
  const [isConnected, setIsConnected] = createSignal(false)

  let eventSource: EventSource | null = null

  // Подключение к SSE потоку для отслеживания статуса запросов
  onMount(() => {
    if (isServer) return

    const connectSSE = () => {
      try {
        const url = new URL('/api/requests/stream', window.location.origin)
        eventSource = new EventSource(url.toString())

        eventSource.onopen = () => {
          console.log('SSE connection for async requests opened')
          setIsConnected(true)
        }

        eventSource.onmessage = (event) => {
          try {
            const update = JSON.parse(event.data)

            if (update.error) {
              console.error('SSE error:', update.error)
              return
            }

            // Обновляем статус запроса
            if (update.request_id && update.status) {
              setRequests((prev) =>
                prev.map((req) =>
                  req.id === update.request_id
                    ? {
                        ...req,
                        status: update.status,
                        completedAt: update.completed_at
                          ? new Date(update.completed_at).getTime()
                          : undefined,
                        error: update.error,
                        result: update.result
                      }
                    : req
                )
              )
            }

            // Добавляем новый запрос
            if (update.request_id && update.type && !requests().some((r) => r.id === update.request_id)) {
              setRequests((prev) => [
                ...prev,
                {
                  id: update.request_id,
                  type: update.type || 'other',
                  status: 'pending',
                  title: update.title || 'Новый запрос',
                  description: update.description,
                  createdAt: update.created_at ? new Date(update.created_at).getTime() : Date.now()
                }
              ])
            }
          } catch (err) {
            console.error('Failed to parse SSE message:', err)
          }
        }

        eventSource.onerror = (err) => {
          console.error('SSE connection error:', err)
          setIsConnected(false)
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
        setIsConnected(false)
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

  // Синхронизация с внешними пропсами
  createEffect(() => {
    if (props.requests) {
      setRequests(props.requests)
    }
  })

  const getStatusIcon = (status: AsyncRequest['status']) => {
    switch (status) {
      case 'pending':
        return '⏳'
      case 'processing':
        return '🔄'
      case 'completed':
        return '✅'
      case 'error':
        return '❌'
      default:
        return '⏳'
    }
  }

  const getTypeIcon = (type: AsyncRequest['type']) => {
    switch (type) {
      case 'message':
        return '💬'
      case 'detector':
        return '🔍'
      case 'factcheck':
        return '✓'
      case 'search':
        return '🔎'
      default:
        return '📋'
    }
  }

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = Date.now()
    const diff = now - timestamp

    if (diff < 1000) return 'только что'
    if (diff < 60000) return `${Math.floor(diff / 1000)}с назад`
    if (diff < 3600000) return `${Math.floor(diff / 60000)}м назад`
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  const removeRequest = (id: string) => {
    setRequests((prev) => prev.filter((r) => r.id !== id))
  }

  const clearCompleted = () => {
    setRequests((prev) => prev.filter((r) => r.status !== 'completed' && r.status !== 'error'))
  }

  return (
    <div class={styles.container}>
      <div class={styles.header}>
        <div class={styles.headerTitle}>
          <h3 class={styles.title}>Асинхронные запросы</h3>
          <Show when={isConnected()}>
            <span class={styles.statusIndicator} title="Подключено к SSE">
              🟢
            </span>
          </Show>
        </div>
        <div class={styles.headerActions}>
          <button class={styles.clearButton} onClick={clearCompleted} title="Очистить завершенные">
            Очистить
          </button>
          <Show when={props.onClose}>
            <button class={styles.closeButton} onClick={props.onClose} title="Закрыть панель">
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
          </Show>
        </div>
      </div>

      <div class={styles.list}>
        <Show
          when={requests().length > 0}
          fallback={
            <div class={styles.empty}>
              <p>Нет активных запросов</p>
            </div>
          }
        >
          <For each={requests()}>
            {(request) => (
              <div
                class={`${styles.requestItem} ${styles[request.status]}`}
                title={request.description || request.title}
              >
                <div class={styles.requestHeader}>
                  <div class={styles.requestIcon}>
                    <span class={styles.typeIcon}>{getTypeIcon(request.type)}</span>
                    <span class={styles.statusIcon}>{getStatusIcon(request.status)}</span>
                  </div>
                  <div class={styles.requestInfo}>
                    <div class={styles.requestTitle}>{request.title}</div>
                    <div class={styles.requestMeta}>
                      <span class={styles.requestTime}>{formatTime(request.createdAt)}</span>
                      <Show when={request.type}>
                        <span class={styles.requestType}>{request.type}</span>
                      </Show>
                    </div>
                  </div>
                  <button
                    class={styles.removeButton}
                    onClick={() => removeRequest(request.id)}
                    title="Удалить"
                  >
                    ×
                  </button>
                </div>

                <Show when={request.status === 'processing'}>
                  <div class={styles.progressBar}>
                    <div class={styles.progressFill} />
                  </div>
                </Show>

                <Show when={request.error}>
                  <div class={styles.errorMessage}>{request.error}</div>
                </Show>

                <Show when={request.status === 'completed' && request.result}>
                  <div class={styles.resultPreview}>
                    {typeof request.result === 'string'
                      ? request.result.substring(0, 100)
                      : JSON.stringify(request.result).substring(0, 100)}
                    ...
                  </div>
                </Show>
              </div>
            )}
          </For>
        </Show>
      </div>
    </div>
  )
}
