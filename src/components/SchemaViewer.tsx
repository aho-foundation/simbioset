import { Component, createResource, For, Show } from 'solid-js'
import styles from './SchemaViewer.module.css'
import Card from './ui/Card'

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
