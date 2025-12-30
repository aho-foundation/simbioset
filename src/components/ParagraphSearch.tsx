import { Component, createSignal, For, Show } from 'solid-js'
import { createParagraphSearch } from '~/lib/weaviate'
import styles from './ParagraphSearch.module.css'
import Card from './ui/Card'

const ParagraphSearch: Component<{
  documentId?: string
  limit?: number
}> = (props) => {
  const [query, setQuery] = createSignal('')
  const [searchData] = createParagraphSearch(query, {
    document_id: props.documentId,
    limit: props.limit || 10
  })

  const handleSearch = (e: Event) => {
    e.preventDefault()
    // Trigger search by updating signal
    setQuery(query())
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
          Искать
        </button>
      </form>

      <Show when={searchData.loading}>
        <div class={styles.loading}>Поиск...</div>
      </Show>

      <Show when={searchData.error}>
        <div class={styles.error}>Ошибка поиска: {searchData.error.message}</div>
      </Show>

      <Show when={searchData() && searchData()!.results.length > 0}>
        <div class={styles.results}>
          <h4>Найдено: {searchData()!.total} результатов</h4>
          <For each={searchData()!.results}>
            {(result) => (
              <div class={styles.resultItem}>
                <div class={styles.resultContent}>{result.paragraph.content}</div>
                <div class={styles.resultMeta}>
                  <span class={styles.score}>Схожесть: {(result.score * 100).toFixed(1)}%</span>
                  <Show when={result.paragraph.tags?.length}>
                    <span class={styles.tags}>{result.paragraph.tags!.join(', ')}</span>
                  </Show>
                  <Show when={result.paragraph.author}>
                    <span class={styles.author}>{result.paragraph.author}</span>
                  </Show>
                </div>
              </div>
            )}
          </For>
        </div>
      </Show>

      <Show when={searchData() && searchData()!.results.length === 0 && !searchData.loading}>
        <div class={styles.noResults}>Ничего не найдено</div>
      </Show>
    </Card>
  )
}

export default ParagraphSearch
