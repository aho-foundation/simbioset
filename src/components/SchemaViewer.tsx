import { Component, createResource, For, Show, createMemo } from 'solid-js'
import styles from './SchemaViewer.module.css'
import Card from './ui/Card'
import { getTags } from '../lib/api/tags'

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

  // Понятные названия типов
  const typeDisplayName = (type: string) => {
    const map: Record<string, string> = {
      'DataType.TEXT': '📝 Текст',
      'DataType.INT': '🔢 Число',
      'DataType.NUMBER': '🔢 Число',
      'DataType.DATE': '📅 Дата',
      'DataType.BOOL': '✓ Булево',
      'DataType.TEXT_ARRAY': '📝 Массив текста',
      'DataType.INT_ARRAY': '🔢 Массив чисел'
    }
    return map[type] || type
  }

  // Подготовка данных для облака тегов
  const tagCloudData = createMemo(() => {
    const allTags = tags()
    if (!allTags || allTags.length === 0) return []

    // Сортируем по usage_count и берем топ 20
    const topTags = allTags
      .sort((a, b) => b.usage_count - a.usage_count)
      .slice(0, 20)

    if (topTags.length === 0) return []

    // Находим min/max для нормализации размеров
    const maxCount = topTags[0].usage_count
    const minCount = topTags[topTags.length - 1].usage_count

    return topTags.map(tag => {
      // Рассчитываем размер шрифта (от 0.8em до 2.5em)
      const fontSize = minCount === maxCount
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
                      {schemaInfo().storage_type === 'weaviate' ? '🗄️' : '💾'}
                    </div>
                    <div class={styles.storageTitle}>
                      {schemaInfo().storage_type === 'weaviate' ? 'Weaviate' : 'FAISS'}
                    </div>
                    <Show when={schemaInfo().collection_name}>
                      <div class={styles.collectionBadge}>
                        {schemaInfo().collection_name}
                      </div>
                    </Show>
                  </div>

                  {/* Статистика */}
                  <div class={styles.statsContainer}>
                    <div class={styles.statCard}>
                      <div class={styles.statNumber}>
                        {schemaInfo().total_properties || 0}
                      </div>
                      <div class={styles.statLabel}>свойств</div>
                    </div>

                    <div class={styles.statCard}>
                      <div class={styles.statNumber}>
                        {Object.keys(propertiesByType()).length}
                      </div>
                      <div class={styles.statLabel}>типов</div>
                    </div>

                    <Show when={schemaInfo().autoschema_enabled !== undefined}>
                      <div class={`${styles.statCard} ${schemaInfo().autoschema_enabled ? styles.autoschemaActive : styles.autoschemaInactive}`}>
                        <div class={styles.statIcon}>
                          {schemaInfo().autoschema_enabled ? '🤖' : '⚙️'}
                        </div>
                        <div class={styles.statLabel}>
                          {schemaInfo().autoschema_enabled ? 'AutoSchema' : 'Ручная схема'}
                        </div>
                      </div>
                    </Show>
                  </div>

                  {/* Визуализация типов данных */}
                  <Show when={schemaInfo().properties && schemaInfo().properties.length > 0}>
                    <div class={styles.dataTypesVisualization}>
                      <h4 class={styles.vizTitle}>Распределение типов данных</h4>
                      <div class={styles.typeBars}>
                        <For each={Object.entries(propertiesByType())}>
                          {([type, props]) => {
                            const percentage = (props.length / (schemaInfo().total_properties || 1)) * 100
                            return (
                              <div class={styles.typeBar}>
                                <div class={styles.typeInfo}>
                                  <span class={styles.typeIcon}>
                                    {typeDisplayName(type).split(' ')[0]}
                                  </span>
                                  <span class={styles.typeName}>
                                    {typeDisplayName(type).split(' ').slice(1).join(' ')}
                                  </span>
                                  <span class={styles.typeCount}>
                                    {props.length}
                                  </span>
                                </div>
                                <div class={styles.progressBar}>
                                  <div
                                    class={styles.progressFill}
                                    style={{ width: `${percentage}%` }}
                                  ></div>
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
                  <h3 class={styles.sectionTitle}>🌟 Популярные теги</h3>
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
                      <strong>🤖 AutoSchema активен:</strong> Схема создается и обновляется автоматически
                      при добавлении данных. Новые свойства добавляются автоматически.
                    </div>
                  </Show>

                  <For each={Object.entries(propertiesByType())}>
                    {([type, props]) => (
                      <div class={styles.typeGroup}>
                        <h4 class={styles.typeTitle}>{typeDisplayName(type)}</h4>
                        <div class={styles.propertiesList}>
                          <For each={props}>
                            {(prop) => (
                              <div class={styles.propertyCard}>
                                <div class={styles.propertyHeader}>
                                  <span class={styles.propertyName}>{prop.name}</span>
                                  <span class={styles.propertyType}>{typeDisplayName(type)}</span>
                                </div>
                                <Show when={prop.description}>
                                  <div class={styles.propertyDescription}>{prop.description}</div>
                                </Show>
                              </div>
                            )}
                          </For>
                        </div>
                      </div>
                    )}
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
