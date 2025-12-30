import { Component, createSignal, For, Show } from 'solid-js'
import { createParagraphSearch } from '~/lib/weaviate'
import styles from './ParagraphSearch.module.css'
import Card from './ui/Card'

// Типы контента для фильтрации
type ContentType = 'all' | 'risks' | 'vulnerabilities' | 'solutions'
type TimeFilter = 'all' | 'today' | 'week' | 'month'
type SortBy = 'relevance' | 'time'

const ParagraphSearch: Component<{
  documentId?: string
  limit?: number
}> = (props) => {
  const [query, setQuery] = createSignal('')
  const [contentType, setContentType] = createSignal<ContentType>('all')
  const [timeFilter, setTimeFilter] = createSignal<TimeFilter>('all')
  const [sortBy, setSortBy] = createSignal<SortBy>('relevance')
  const [location, setLocation] = createSignal('')
  const [showFilters, setShowFilters] = createSignal(false)

  // Маппинг типов контента на теги
  const contentTypeToTags = (type: ContentType): string[] | undefined => {
    switch (type) {
      case 'risks':
        return ['ecosystem_risk']
      case 'vulnerabilities':
        return ['ecosystem_vulnerability']
      case 'solutions':
        return ['suggested_ecosystem_solution', 'ecosystem_solution']
      default:
        return undefined
    }
  }

  // Вычисляем timestamp для фильтра по времени
  const getTimeRange = (filter: TimeFilter): { from?: number; to?: number } => {
    const now = Math.floor(Date.now() / 1000)
    switch (filter) {
      case 'today': {
        const todayStart = new Date()
        todayStart.setHours(0, 0, 0, 0)
        return { from: Math.floor(todayStart.getTime() / 1000), to: now }
      }
      case 'week': {
        const weekAgo = now - 7 * 24 * 60 * 60
        return { from: weekAgo, to: now }
      }
      case 'month': {
        const monthAgo = now - 30 * 24 * 60 * 60
        return { from: monthAgo, to: now }
      }
      default:
        return {}
    }
  }

  // Создаем реактивный источник для параметров поиска
  // Zero-config: все технические параметры оптимальны по умолчанию
  const searchParams = () => {
    const timeRange = getTimeRange(timeFilter())
    return {
      document_id: props.documentId,
      limit: props.limit || 10,
      tags: contentTypeToTags(contentType()),
      location: location().trim() || undefined,
      timestamp_from: timeRange.from,
      timestamp_to: timeRange.to,
      // Технические параметры - оптимальные по умолчанию, не показываем пользователю
      use_hybrid: true, // Всегда включен для лучшей точности
      hybrid_alpha: 0.5, // Оптимальный баланс
      use_reranking: false // Выключен для скорости (можно включить для критических запросов)
    }
  }

  const [searchData] = createParagraphSearch(query, searchParams)

  const handleSearch = (e: Event) => {
    e.preventDefault()
    // Trigger search by updating signal
    setQuery(query())
  }

  // Сортировка результатов
  const sortedResults = () => {
    const data = searchData()
    if (!data || !data.results) return []

    const results = [...data.results]

    if (sortBy() === 'time') {
      // Сортируем по времени (если есть timestamp в параграфе)
      return results.sort((a, b) => {
        const getTime = (timestamp: string | Date | undefined): number => {
          if (!timestamp) return 0
          if (timestamp instanceof Date) return timestamp.getTime()
          if (typeof timestamp === 'string') {
            const date = new Date(timestamp)
            return Number.isNaN(date.getTime()) ? 0 : date.getTime()
          }
          return 0
        }
        const timeA = getTime(a.paragraph.timestamp)
        const timeB = getTime(b.paragraph.timestamp)
        return timeB - timeA // Новые сначала
      })
    }

    // По умолчанию - по релевантности (уже отсортировано)
    return results
  }

  return (
    <Card title="Поиск параграфов" class={styles.paragraphSearch}>
      <form onSubmit={handleSearch} class={styles.searchForm}>
        <input
          type="text"
          value={query()}
          onInput={(e) => setQuery(e.currentTarget.value)}
          placeholder="Введите запрос для поиска..."
          class={styles.searchInput}
        />
        <button type="submit" disabled={!query().trim()} class={styles.searchButton}>
          <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          Искать
        </button>
      </form>

      <Show when={searchData.loading}>
        <div class={styles.loading}>Поиск...</div>
      </Show>

      <Show when={searchData.error}>
        <div class={styles.error}>Ошибка поиска: {searchData.error.message}</div>
      </Show>

      {/* Фильтры для пользователей */}
      <div class={styles.filtersSection}>
        <button type="button" onClick={() => setShowFilters(!showFilters())} class={styles.filtersToggle}>
          {showFilters() ? '▼' : '▶'} Фильтры
        </button>

        <Show when={showFilters()}>
          <div class={styles.filters}>
            {/* Тип контента */}
            <div class={styles.filterGroup}>
              <label class={styles.filterLabel}>Тип контента:</label>
              <div class={styles.buttonGroup}>
                <button
                  type="button"
                  onClick={() => setContentType('all')}
                  class={`${styles.filterButton} ${contentType() === 'all' ? styles.active : ''}`}
                >
                  Все
                </button>
                <button
                  type="button"
                  onClick={() => setContentType('risks')}
                  class={`${styles.filterButton} ${contentType() === 'risks' ? styles.active : ''}`}
                >
                  ⚠️ Риски
                </button>
                <button
                  type="button"
                  onClick={() => setContentType('vulnerabilities')}
                  class={`${styles.filterButton} ${contentType() === 'vulnerabilities' ? styles.active : ''}`}
                >
                  🔴 Уязвимости
                </button>
                <button
                  type="button"
                  onClick={() => setContentType('solutions')}
                  class={`${styles.filterButton} ${contentType() === 'solutions' ? styles.active : ''}`}
                >
                  ✅ Решения
                </button>
              </div>
            </div>

            {/* Время */}
            <div class={styles.filterGroup}>
              <label class={styles.filterLabel}>Период:</label>
              <div class={styles.buttonGroup}>
                <button
                  type="button"
                  onClick={() => setTimeFilter('all')}
                  class={`${styles.filterButton} ${timeFilter() === 'all' ? styles.active : ''}`}
                >
                  Все время
                </button>
                <button
                  type="button"
                  onClick={() => setTimeFilter('today')}
                  class={`${styles.filterButton} ${timeFilter() === 'today' ? styles.active : ''}`}
                >
                  Сегодня
                </button>
                <button
                  type="button"
                  onClick={() => setTimeFilter('week')}
                  class={`${styles.filterButton} ${timeFilter() === 'week' ? styles.active : ''}`}
                >
                  Неделя
                </button>
                <button
                  type="button"
                  onClick={() => setTimeFilter('month')}
                  class={`${styles.filterButton} ${timeFilter() === 'month' ? styles.active : ''}`}
                >
                  Месяц
                </button>
              </div>
            </div>

            {/* Локация */}
            <div class={styles.filterGroup}>
              <label class={styles.filterLabel}>Локация:</label>
              <input
                type="text"
                value={location()}
                onInput={(e) => setLocation(e.currentTarget.value)}
                placeholder="Москва, тайга, Сибирь..."
                class={styles.locationInput}
              />
            </div>

            {/* Сортировка */}
            <div class={styles.filterGroup}>
              <label class={styles.filterLabel}>Сортировка:</label>
              <div class={styles.buttonGroup}>
                <button
                  type="button"
                  onClick={() => setSortBy('relevance')}
                  class={`${styles.filterButton} ${sortBy() === 'relevance' ? styles.active : ''}`}
                >
                  По релевантности
                </button>
                <button
                  type="button"
                  onClick={() => setSortBy('time')}
                  class={`${styles.filterButton} ${sortBy() === 'time' ? styles.active : ''}`}
                >
                  По времени
                </button>
              </div>
            </div>
          </div>
        </Show>
      </div>

      <Show when={searchData() && sortedResults().length > 0}>
        <div class={styles.results}>
          <div class={styles.resultsHeader}>
            <h4>Найдено: {searchData()!.total} результатов</h4>
            <Show when={contentType() !== 'all' || timeFilter() !== 'all' || location().trim()}>
              <div class={styles.activeFilters}>
                <Show when={contentType() !== 'all'}>
                  <span class={styles.activeFilter}>
                    {contentType() === 'risks' && '⚠️ Риски'}
                    {contentType() === 'vulnerabilities' && '🔴 Уязвимости'}
                    {contentType() === 'solutions' && '✅ Решения'}
                  </span>
                </Show>
                <Show when={timeFilter() !== 'all'}>
                  <span class={styles.activeFilter}>
                    {timeFilter() === 'today' && 'Сегодня'}
                    {timeFilter() === 'week' && 'Неделя'}
                    {timeFilter() === 'month' && 'Месяц'}
                  </span>
                </Show>
                <Show when={location().trim()}>
                  <span class={styles.activeFilter}>📍 {location().trim()}</span>
                </Show>
              </div>
            </Show>
          </div>
          <For each={sortedResults()}>
            {(result) => (
              <div class={styles.resultItem}>
                <div class={styles.resultContent}>{result.paragraph.content}</div>
                <div class={styles.resultMeta}>
                  <Show when={result.score > 0}>
                    <span class={styles.score}>Релевантность: {(result.score * 100).toFixed(0)}%</span>
                  </Show>
                  <Show when={result.paragraph.tags?.length}>
                    <div class={styles.resultTags}>
                      <For each={result.paragraph.tags}>
                        {(tag) => (
                          <span
                            class={`${styles.resultTag} ${
                              tag === 'ecosystem_risk'
                                ? styles.tagRisk
                                : tag === 'ecosystem_vulnerability'
                                  ? styles.tagVulnerability
                                  : tag.includes('solution')
                                    ? styles.tagSolution
                                    : ''
                            }`}
                          >
                            {tag === 'ecosystem_risk' && '⚠️ Риск'}
                            {tag === 'ecosystem_vulnerability' && '🔴 Уязвимость'}
                            {(tag === 'suggested_ecosystem_solution' || tag === 'ecosystem_solution') &&
                              '✅ Решение'}
                            {![
                              'ecosystem_risk',
                              'ecosystem_vulnerability',
                              'suggested_ecosystem_solution',
                              'ecosystem_solution'
                            ].includes(tag) && tag}
                          </span>
                        )}
                      </For>
                    </div>
                  </Show>
                  <div class={styles.resultFooter}>
                    <Show when={result.paragraph.author}>
                      <span class={styles.author}>👤 {result.paragraph.author}</span>
                    </Show>
                    <Show when={result.paragraph.location}>
                      <span class={styles.location}>📍 {result.paragraph.location}</span>
                    </Show>
                    <Show when={result.paragraph.timestamp}>
                      <span class={styles.timestamp}>
                        🕒 {(() => {
                          const ts = result.paragraph.timestamp!
                          const date = ts instanceof Date ? ts : new Date(ts)
                          return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString('ru-RU')
                        })()}
                      </span>
                    </Show>
                  </div>
                </div>
              </div>
            )}
          </For>
        </div>
      </Show>

      <Show when={searchData() && sortedResults().length === 0 && !searchData.loading}>
        <div class={styles.noResults}>Ничего не найдено</div>
      </Show>
    </Card>
  )
}

export default ParagraphSearch
