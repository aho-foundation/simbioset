import { Component, createMemo, createResource, For, JSX, Show } from 'solid-js'
import { getTags } from '../lib/api/tags'
import styles from './SchemaViewer.module.css'
import Card from './ui/Card'

// Иконки для замены эмоджи
const DatabaseIcon = () => (
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
    <ellipse cx="12" cy="5" rx="9" ry="3" />
    <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" />
    <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" />
  </svg>
)

const ServerIcon = () => (
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
    <rect x="2" y="2" width="20" height="8" rx="2" ry="2" />
    <rect x="2" y="14" width="20" height="8" rx="2" ry="2" />
    <line x1="6" y1="6" x2="6.01" y2="6" />
    <line x1="6" y1="18" x2="6.01" y2="18" />
  </svg>
)

const BotIcon = () => (
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
    <path d="M12 8V4H8" />
    <rect x="4" y="8" width="16" height="12" rx="2" />
    <path d="M2 14h2" />
    <path d="M20 14h2" />
    <path d="M15 13v2" />
    <path d="M9 13v2" />
  </svg>
)

const SettingsIcon = () => (
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
    <circle cx="12" cy="12" r="3" />
    <path d="M12 1v6m0 6v6m11-7h-6m-6 0H1m16.24-3.76l-4.24 4.24m-6-6L3.76 7.76" />
  </svg>
)

const StarIcon = () => (
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
    <polygon points="12,2 15.09,8.26 22,9.27 17,14.14 18.18,21.02 12,17.77 5.82,21.02 7,14.14 2,9.27 8.91,8.26" />
  </svg>
)

const TextIcon = () => (
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
    <polyline points="4,7 4,4 20,4 20,7" />
    <line x1="9" y1="20" x2="15" y2="20" />
    <line x1="12" y1="4" x2="12" y2="20" />
  </svg>
)

const NumberIcon = () => (
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
    <line x1="8" y1="5" x2="16" y2="5" />
    <line x1="8" y1="11" x2="16" y2="11" />
    <line x1="8" y1="17" x2="16" y2="17" />
    <line x1="4" y1="7" x2="8" y2="5" />
    <line x1="4" y1="13" x2="8" y2="11" />
    <line x1="4" y1="19" x2="8" y2="17" />
    <line x1="20" y1="7" x2="16" y2="5" />
    <line x1="20" y1="13" x2="16" y2="11" />
    <line x1="20" y1="19" x2="16" y2="17" />
  </svg>
)

const CalendarIcon = () => (
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
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
)

const CheckIcon = () => (
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
    <polyline points="20,6 9,17 4,12" />
  </svg>
)

interface SchemaProperty {
  name: string
  data_type: string
  description?: string
}

interface SchemaInfo {
  storage_type: string
  collection_name?: string
  autoschema_enabled?: boolean
  properties?: SchemaProperty[]
  total_properties?: number
  error?: string
  message?: string
}

const SchemaViewer: Component = () => {
  const [schema, { refetch }] = createResource<SchemaInfo>(async () => {
    const response = await fetch('/api/storage/schema')
    if (!response.ok) {
      throw new Error(`Failed to fetch schema: ${response.statusText}`)
    }
    return response.json()
  })

  const [tags] = createResource(async () => {
    try {
      return await getTags(true) // Только активные теги
    } catch (error) {
      console.warn('Failed to load tags for cloud:', error)
      return []
    }
  })

  // Группируем свойства по типам
  const propertiesByType = () => {
    const props = schema()?.properties
    if (!props) return {}

    const grouped: Record<string, SchemaProperty[]> = {}
    for (const prop of props) {
      const type = prop.data_type || 'unknown'
      if (!grouped[type]) {
        grouped[type] = []
      }
      grouped[type].push(prop)
    }
    return grouped
  }

  // Понятные названия типов с иконками
  const typeDisplayName = (type: string) => {
    const map: Record<string, { icon: () => JSX.Element; label: string }> = {
      'DataType.TEXT': { icon: TextIcon, label: 'Текст' },
      'DataType.INT': { icon: NumberIcon, label: 'Число' },
      'DataType.NUMBER': { icon: NumberIcon, label: 'Число' },
      'DataType.DATE': { icon: CalendarIcon, label: 'Дата' },
      'DataType.BOOL': { icon: CheckIcon, label: 'Булево' },
      'DataType.TEXT_ARRAY': { icon: TextIcon, label: 'Массив текста' },
      'DataType.INT_ARRAY': { icon: NumberIcon, label: 'Массив чисел' }
    }
    return map[type] || { icon: TextIcon, label: type }
  }

  // Подготовка данных для облака тегов
  const tagCloudData = createMemo(() => {
    const allTags = tags()
    if (!allTags || allTags.length === 0) return []

    // Сортируем по usage_count и берем топ 20
    const topTags = allTags.sort((a, b) => b.usage_count - a.usage_count).slice(0, 20)

    if (topTags.length === 0) return []

    // Находим min/max для нормализации размеров
    const maxCount = topTags[0].usage_count
    const minCount = topTags[topTags.length - 1].usage_count

    return topTags.map((tag) => {
      // Рассчитываем размер шрифта (от 0.8em до 2.5em)
      const fontSize =
        minCount === maxCount
          ? 1.5 // Если все теги имеют одинаковый count
          : 0.8 + ((tag.usage_count - minCount) / (maxCount - minCount)) * 1.7

      return {
        ...tag,
        fontSize: Math.max(0.8, Math.min(2.5, fontSize))
      }
    })
  })

  return (
    <div class={styles.schemaViewer}>
      <Card title="Схема данных">
        <Show when={schema.loading}>
          <div class={styles.loading}>Загрузка схемы...</div>
        </Show>

        <Show when={schema.error}>
          <div class={styles.error}>Ошибка загрузки схемы: {schema.error.message}</div>
        </Show>

        <Show when={schema()}>
          {(schemaInfo) => (
            <>
              {/* Инфографика структуры данных */}
              <div class={styles.infographics}>
                <div class={styles.dataFlow}>
                  {/* Центральный узел - хранилище */}
                  <div class={styles.storageNode}>
                    <div class={styles.storageIcon}>
                      {schemaInfo().storage_type === 'weaviate' ? <DatabaseIcon /> : <ServerIcon />}
                    </div>
                    <div class={styles.storageTitle}>
                      {schemaInfo().storage_type === 'weaviate' ? 'Weaviate' : 'FAISS'}
                    </div>
                    <Show when={schemaInfo().collection_name}>
                      <div class={styles.collectionBadge}>{schemaInfo().collection_name}</div>
                    </Show>
                  </div>

                  {/* Статистика */}
                  <div class={styles.statsContainer}>
                    <div class={styles.statCard}>
                      <div class={styles.statNumber}>{schemaInfo().total_properties || 0}</div>
                      <div class={styles.statLabel}>свойств</div>
                    </div>

                    <div class={styles.statCard}>
                      <div class={styles.statNumber}>{Object.keys(propertiesByType()).length}</div>
                      <div class={styles.statLabel}>типов</div>
                    </div>

                    <Show when={schemaInfo().autoschema_enabled !== undefined}>
                      <div
                        class={`${styles.statCard} ${schemaInfo().autoschema_enabled ? styles.autoschemaActive : styles.autoschemaInactive}`}
                      >
                        <div class={styles.statIcon}>
                          {schemaInfo().autoschema_enabled ? <BotIcon /> : <SettingsIcon />}
                        </div>
                        <div class={styles.statLabel}>
                          {schemaInfo().autoschema_enabled ? 'AutoSchema' : 'Ручная схема'}
                        </div>
                      </div>
                    </Show>
                  </div>

                  {/* Визуализация типов данных */}
                  <Show when={schemaInfo().properties}>
                    <div class={styles.dataTypesVisualization}>
                      <h4 class={styles.vizTitle}>Распределение типов данных</h4>
                      <div class={styles.typeBars}>
                        <For each={Object.entries(propertiesByType())}>
                          {([type, props]) => {
                            const percentage = (props.length / (schemaInfo().total_properties || 1)) * 100
                            const typeInfo = typeDisplayName(type)
                            const IconComponent = typeInfo.icon
                            return (
                              <div class={styles.typeBar}>
                                <div class={styles.typeInfo}>
                                  <span class={styles.typeIcon}>
                                    <IconComponent />
                                  </span>
                                  <span class={styles.typeName}>{typeInfo.label}</span>
                                  <span class={styles.typeCount}>{props.length}</span>
                                </div>
                                <div class={styles.progressBar}>
                                  <div class={styles.progressFill} style={{ width: `${percentage}%` }} />
                                </div>
                              </div>
                            )
                          }}
                        </For>
                      </div>
                    </div>
                  </Show>
                </div>
              </div>

              {/* Облако тегов */}
              <Show when={tagCloudData().length > 0}>
                <div class={styles.tagCloud}>
                  <h3 class={styles.sectionTitle}>
                    <StarIcon /> Популярные теги
                  </h3>
                  <div class={styles.tagCloudContainer}>
                    <For each={tagCloudData()}>
                      {(tag) => (
                        <span
                          class={styles.tagCloudItem}
                          style={{
                            'font-size': `${tag.fontSize}em`,
                            'font-weight': tag.fontSize > 1.5 ? '700' : tag.fontSize > 1.2 ? '600' : '400'
                          }}
                          title={`${tag.name}: использовано ${tag.usage_count} раз`}
                        >
                          {tag.name}
                        </span>
                      )}
                    </For>
                  </div>
                  <div class={styles.tagCloudStats}>
                    Показано топ {tagCloudData().length} из {tags()?.length || 0} активных тегов
                  </div>
                </div>
              </Show>

              {/* Сообщение для FAISS */}
              <Show when={schemaInfo().storage_type === 'faiss'}>
                <div class={styles.message}>
                  <p>{schemaInfo().message}</p>
                  <p class={styles.hint}>
                    FAISS - это in-memory векторный индекс, схема данных определяется в коде приложения.
                  </p>
                </div>
              </Show>

              {/* Свойства для Weaviate */}
              <Show when={schemaInfo().storage_type === 'weaviate' && schemaInfo().properties}>
                <div class={styles.propertiesSection}>
                  <h3 class={styles.sectionTitle}>Свойства коллекции</h3>

                  <Show when={schemaInfo().autoschema_enabled}>
                    <div class={styles.autoschemaNote}>
                      <strong>
                        <BotIcon /> AutoSchema активен:
                      </strong>{' '}
                      Схема создается и обновляется автоматически при добавлении данных. Новые свойства
                      добавляются автоматически.
                    </div>
                  </Show>

                  <For each={Object.entries(propertiesByType())}>
                    {([type, props]) => {
                      const typeInfo = typeDisplayName(type)
                      const IconComponent = typeInfo.icon
                      return (
                        <div class={styles.typeGroup}>
                          <h4 class={styles.typeTitle}>
                            <IconComponent /> {typeInfo.label}
                          </h4>
                          <div class={styles.propertiesList}>
                            <For each={props}>
                              {(prop) => (
                                <div class={styles.propertyCard}>
                                  <div class={styles.propertyHeader}>
                                    <span class={styles.propertyName}>{prop.name}</span>
                                    <span class={styles.propertyType}>
                                      <IconComponent /> {typeInfo.label}
                                    </span>
                                  </div>
                                  <Show when={prop.description}>
                                    <div class={styles.propertyDescription}>{prop.description}</div>
                                  </Show>
                                </div>
                              )}
                            </For>
                          </div>
                        </div>
                      )
                    }}
                  </For>
                </div>
              </Show>

              {/* Ошибка */}
              <Show when={schemaInfo().error}>
                <div class={styles.error}>
                  <strong>Ошибка получения схемы:</strong> {schemaInfo().error}
                </div>
              </Show>

              {/* Кнопка обновления */}
              <div class={styles.actions}>
                <button type="button" onClick={refetch} class={styles.refreshButton}>
                  🔄 Обновить схему
                </button>
              </div>
            </>
          )}
        </Show>
      </Card>
    </div>
  )
}

export default SchemaViewer
