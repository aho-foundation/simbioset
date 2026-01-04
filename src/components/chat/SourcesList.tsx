import { For, Show } from 'solid-js'
import styles from '~/styles/interview.module.css'
import type { MessageSource } from '~/types/chat'
import { getSourceIcon } from './SourceIcons'

interface SourcesListProps {
  sources: MessageSource[]
}

export const SourcesList = (props: SourcesListProps) => {
  const validSources = () => {
    return props.sources.filter((s) => {
      // Фильтруем источники с валидными данными
      if (!s.title || !s.type) return false

      // Исключаем неизвестные типы
      const invalidTypes = ['неизвестный тип', 'unknown type', 'unknown']
      if (invalidTypes.some((invalid) => s.type.toLowerCase().includes(invalid))) return false

      // Исключаем слишком короткие или слишком длинные названия
      if (s.title.length < 3 || s.title.length > 200) return false

      // Исключаем технические строки
      const technicalPatterns = ['===', '---', 'http://', 'https://']
      if (technicalPatterns.some((pattern) => s.title.includes(pattern))) return false

      return true
    })
  }

  return (
    <Show when={validSources().length > 0}>
      <div class={styles.sourcesInline}>
        <For each={validSources()}>
          {(source) => {
            const Icon = getSourceIcon(source.type)

            // Если есть URL, делаем кликабельную ссылку
            if (source.url) {
              return (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  class={styles.sourceInlineItem}
                  title={`${source.title} (${source.type}) - кликните для перехода`}
                  style="cursor: pointer; text-decoration: none;"
                >
                  <span class={styles.sourceIcon}>
                    <Icon />
                  </span>
                  <span class={styles.sourceInlineTitle}>{source.title}</span>
                </a>
              )
            }

            // Иначе обычный бейдж
            return (
              <span class={styles.sourceInlineItem} title={`${source.title} (${source.type})`}>
                <span class={styles.sourceIcon}>
                  <Icon />
                </span>
                <span class={styles.sourceInlineTitle}>{source.title}</span>
              </span>
            )
          }}
        </For>
      </div>
    </Show>
  )
}
