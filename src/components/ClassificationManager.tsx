import { Component, createResource, createSignal, For, Show } from 'solid-js'
import {
  AnalyzeTagsResult,
  analyzeTags,
  createTag,
  getTags,
  type Tag,
  type TagCreate,
  updateTag
} from '~/lib/api/tags'
import styles from './ClassificationManager.module.css'
import Card from './ui/Card'

const ClassificationManager: Component = () => {
  const [showCreateForm, setShowCreateForm] = createSignal(false)
  const [newTagName, setNewTagName] = createSignal('')
  const [newTagDescription, setNewTagDescription] = createSignal('')
  const [newTagCategory, setNewTagCategory] = createSignal('')
  const [analyzing, setAnalyzing] = createSignal(false)
  const [analysisResult, setAnalysisResult] = createSignal<AnalyzeTagsResult | null>(null)

  // Загружаем теги
  const [tags, { refetch }] = createResource(() => getTags(false))

  // Группируем теги по категориям
  const tagsByCategory = () => {
    const allTags = tags()
    if (!allTags) return {}

    const grouped: Record<string, Tag[]> = {}
    for (const tag of allTags) {
      const category = tag.category || 'Без категории'
      if (!grouped[category]) {
        grouped[category] = []
      }
      grouped[category].push(tag)
    }
    return grouped
  }

  // Статистика
  const stats = () => {
    const allTags = tags()
    if (!allTags) return { total: 0, active: 0, totalUsage: 0 }

    return {
      total: allTags.length,
      active: allTags.filter((t) => t.is_active).length,
      totalUsage: allTags.reduce((sum, t) => sum + (t.usage_count || 0), 0)
    }
  }

  // Создание тега
  const handleCreateTag = async (e: Event) => {
    e.preventDefault()
    try {
      const tagData: TagCreate = {
        name: newTagName().trim(),
        description: newTagDescription().trim() || undefined,
        category: newTagCategory().trim() || undefined
      }

      await createTag(tagData)
      setNewTagName('')
      setNewTagDescription('')
      setNewTagCategory('')
      setShowCreateForm(false)
      refetch()
    } catch (error) {
      console.error('Failed to create tag:', error)
      alert('Ошибка при создании тега')
    }
  }

  // Переключение активности тега
  const toggleTagActive = async (tag: Tag) => {
    try {
      await updateTag(tag.name, { is_active: !tag.is_active })
      refetch()
    } catch (error) {
      console.error('Failed to update tag:', error)
      alert('Ошибка при обновлении тега')
    }
  }

  // Анализ тегов через LLM
  const handleAnalyzeTags = async () => {
    setAnalyzing(true)
    setAnalysisResult(null)
    try {
      const result = await analyzeTags(100)
      setAnalysisResult(result)
      refetch()
    } catch (error) {
      console.error('Failed to analyze tags:', error)
      alert('Ошибка при анализе тегов')
    } finally {
      setAnalyzing(false)
    }
  }

  // Маппинг категорий на понятные названия
  const categoryName = (category: string) => {
    const map: Record<string, string> = {
      ecosystem: 'Экосистема',
      solution: 'Решения',
      general: 'Общее'
    }
    return map[category] || category
  }

  // Маппинг тегов на понятные названия
  const tagDisplayName = (tag: Tag) => {
    const map: Record<string, string> = {
      ecosystem_risk: '⚠️ Риск',
      ecosystem_vulnerability: '🔴 Уязвимость',
      suggested_ecosystem_solution: '✅ Решение',
      ecosystem_solution: '✅ Решение',
      neutral: '⚪ Нейтральный'
    }
    return map[tag.name] || tag.name
  }

  return (
    <div class={styles.classificationManager}>
      <Card title="Управление классификацией">
        {/* Статистика */}
        <div class={styles.stats}>
          <div class={styles.statItem}>
            <div class={styles.statValue}>{stats().total}</div>
            <div class={styles.statLabel}>Всего тегов</div>
          </div>
          <div class={styles.statItem}>
            <div class={styles.statValue}>{stats().active}</div>
            <div class={styles.statLabel}>Активных</div>
          </div>
          <div class={styles.statItem}>
            <div class={styles.statValue}>{stats().totalUsage}</div>
            <div class={styles.statLabel}>Использований</div>
          </div>
        </div>

        {/* Действия */}
        <div class={styles.actions}>
          <button
            type="button"
            onClick={() => setShowCreateForm(!showCreateForm())}
            class={styles.actionButton}
          >
            {showCreateForm() ? '✕ Отмена' : '+ Создать тег'}
          </button>
          <button
            type="button"
            onClick={handleAnalyzeTags}
            disabled={analyzing()}
            class={`${styles.actionButton} ${styles.analyzeButton}`}
          >
            {analyzing() ? '⏳ Анализ...' : '🤖 Анализ через LLM'}
          </button>
        </div>

        {/* Форма создания тега */}
        <Show when={showCreateForm()}>
          <form onSubmit={handleCreateTag} class={styles.createForm}>
            <div class={styles.formGroup}>
              <label class={styles.label}>Название тега:</label>
              <input
                type="text"
                value={newTagName()}
                onInput={(e) => setNewTagName(e.currentTarget.value)}
                placeholder="ecosystem_risk"
                required
                class={styles.input}
              />
            </div>
            <div class={styles.formGroup}>
              <label class={styles.label}>Описание:</label>
              <textarea
                value={newTagDescription()}
                onInput={(e) => setNewTagDescription(e.currentTarget.value)}
                placeholder="Описание тега..."
                class={styles.textarea}
              />
            </div>
            <div class={styles.formGroup}>
              <label class={styles.label}>Категория:</label>
              <input
                type="text"
                value={newTagCategory()}
                onInput={(e) => setNewTagCategory(e.currentTarget.value)}
                placeholder="ecosystem, solution, general..."
                class={styles.input}
              />
            </div>
            <button type="submit" class={styles.submitButton}>
              Создать
            </button>
          </form>
        </Show>

        {/* Результаты анализа */}
        <Show when={analysisResult()}>
          <div class={styles.analysisResult}>
            <h4>Результаты анализа:</h4>
            <Show when={analysisResult()!.new_tags.length > 0}>
              <div class={styles.resultSection}>
                <strong>Новые теги ({analysisResult()!.new_tags.length}):</strong>
                <ul>
                  <For each={analysisResult()!.new_tags}>
                    {(tag) => (
                      <li>
                        <strong>{tagDisplayName(tag as Tag)}</strong> - {tag.description || 'без описания'}
                      </li>
                    )}
                  </For>
                </ul>
              </div>
            </Show>
            <Show when={analysisResult()!.updated_tags.length > 0}>
              <div class={styles.resultSection}>
                <strong>Обновленные теги ({analysisResult()!.updated_tags.length}):</strong>
                <ul>
                  <For each={analysisResult()!.updated_tags}>{(tagName) => <li>{tagName}</li>}</For>
                </ul>
              </div>
            </Show>
            <Show when={analysisResult()!.deactivated_tags.length > 0}>
              <div class={styles.resultSection}>
                <strong>Деактивированные теги ({analysisResult()!.deactivated_tags.length}):</strong>
                <ul>
                  <For each={analysisResult()!.deactivated_tags}>{(tagName) => <li>{tagName}</li>}</For>
                </ul>
              </div>
            </Show>
          </div>
        </Show>

        {/* Список тегов по категориям */}
        <Show when={tags()}>
          <div class={styles.tagsList}>
            <For each={Object.entries(tagsByCategory())}>
              {([category, categoryTags]) => (
                <div class={styles.categorySection}>
                  <h3 class={styles.categoryTitle}>{categoryName(category)}</h3>
                  <div class={styles.tagsGrid}>
                    <For each={categoryTags}>
                      {(tag) => (
                        <div class={`${styles.tagCard} ${!tag.is_active ? styles.inactive : ''}`}>
                          <div class={styles.tagHeader}>
                            <span class={styles.tagName}>{tagDisplayName(tag)}</span>
                            <button
                              type="button"
                              onClick={() => toggleTagActive(tag)}
                              class={`${styles.toggleButton} ${tag.is_active ? styles.active : ''}`}
                              title={tag.is_active ? 'Деактивировать' : 'Активировать'}
                            >
                              {tag.is_active ? '✓' : '✕'}
                            </button>
                          </div>
                          <Show when={tag.description}>
                            <div class={styles.tagDescription}>{tag.description}</div>
                          </Show>
                          <div class={styles.tagMeta}>
                            <span class={styles.usageCount}>Использований: {tag.usage_count || 0}</span>
                            <Show when={tag.examples && tag.examples.length > 0}>
                              <span class={styles.examplesCount}>Примеров: {tag.examples!.length}</span>
                            </Show>
                          </div>
                        </div>
                      )}
                    </For>
                  </div>
                </div>
              )}
            </For>
          </div>
        </Show>

        <Show when={tags.loading}>
          <div class={styles.loading}>Загрузка тегов...</div>
        </Show>

        <Show when={tags.error}>
          <div class={styles.error}>Ошибка загрузки тегов: {tags.error.message}</div>
        </Show>
      </Card>
    </div>
  )
}

export default ClassificationManager
