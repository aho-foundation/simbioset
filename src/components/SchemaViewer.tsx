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
              {/* Информация о типе хранилища */}
              <div class={styles.storageInfo}>
                <div class={styles.infoRow}>
                  <span class={styles.infoLabel}>Тип хранилища:</span>
                  <span class={styles.infoValue}>
                    {schemaInfo().storage_type === 'weaviate' ? '🗄️ Weaviate' : '💾 FAISS'}
                  </span>
                </div>

                <Show when={schemaInfo().collection_name}>
                  <div class={styles.infoRow}>
                    <span class={styles.infoLabel}>Коллекция:</span>
                    <span class={styles.infoValue}>{schemaInfo().collection_name}</span>
                  </div>
                </Show>

                <Show when={schemaInfo().autoschema_enabled !== undefined}>
                  <div class={styles.infoRow}>
                    <span class={styles.infoLabel}>AutoSchema:</span>
                    <span
                      class={`${styles.infoValue} ${
                        schemaInfo().autoschema_enabled ? styles.enabled : styles.disabled
                      }`}
                    >
                      {schemaInfo().autoschema_enabled ? '✅ Включен' : '❌ Выключен'}
                    </span>
                  </div>
                </Show>

                <Show when={schemaInfo().total_properties !== undefined}>
                  <div class={styles.infoRow}>
                    <span class={styles.infoLabel}>Всего свойств:</span>
                    <span class={styles.infoValue}>{schemaInfo().total_properties}</span>
                  </div>
                </Show>
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
