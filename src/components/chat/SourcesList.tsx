import { For, Show } from 'solid-js'
import styles from '~/styles/interview.module.css'
import type { MessageSource } from '~/types/chat'
import {
  BsBook, BsGlobe, BsFileText, BsQuestionCircle,
  BsCode, BsPlayBtn, BsNewspaper, BsMortarboard,
  BsBuilding, BsPeople, BsRobot, BsDatabase
} from 'solid-icons/bs'

// Маппинг типов источников на иконки
const sourceTypeToIconMap: Record<string, any> = {
  // Википедия
  'википедия': BsDatabase,
  'wikipedia': BsDatabase,

  // Научная литература и исследования
  'научная литература': BsBook,
  'scientific literature': BsBook,
  'медицинские исследования': BsBook,
  'научные публикации': BsFileText,
  'препринты': BsFileText,
  'исследование': BsBook,
  'research': BsBook,

  // Веб и поиск
  'веб-поиск': BsGlobe,
  'web search': BsGlobe,
  'веб-ресурс': BsGlobe,

  // База знаний и экспертные знания
  'база знаний': BsDatabase,
  'knowledge base': BsDatabase,
  'экспертные знания': BsDatabase,
  'expert knowledge': BsDatabase,

  // Нейронная сеть
  'нейронная сеть': BsRobot,
  'neural network': BsRobot,

  // Публикации
  'публикация': BsFileText,
  'publication': BsFileText,

  // Код и разработка
  'код': BsCode,
  'code': BsCode,
  'код и разработка': BsCode,

  // Видео
  'видео': BsPlayBtn,
  'video': BsPlayBtn,

  // Новости
  'новости': BsNewspaper,
  'news': BsNewspaper,

  // Образование
  'образование': BsMortarboard,
  'education': BsMortarboard,

  // Официальные данные
  'официальные данные': BsBuilding,

  // Некоммерческие организации
  'некоммерческая организация': BsPeople,
}

// Функция для получения иконки по типу источника
const getSourceIcon = (sourceType: string): any => {
  const typeLower = sourceType.toLowerCase()

  // Проверяем точное совпадение
  if (sourceTypeToIconMap[typeLower]) {
    return sourceTypeToIconMap[typeLower]
  }

  // Проверяем частичное совпадение
  for (const [key, icon] of Object.entries(sourceTypeToIconMap)) {
    if (typeLower.includes(key)) {
      return icon
    }
  }

  // Для эмодзи (наследие старой системы)
  const emojiToIconMap: Record<string, any> = {
    '📚': BsDatabase,
    '🌐': BsGlobe,
    '🧠': BsDatabase,
    '🤖': BsFileText,
    '📖': BsFileText,
    '🔬': BsBook
  }

  if (emojiToIconMap[sourceType]) {
    return emojiToIconMap[sourceType]
  }

  return BsQuestionCircle
}

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
                  title={`${source.title} (${source.type})`}
                  style="cursor: pointer; text-decoration: none; display: inline-flex;"
                >
                  <span class={styles.sourceIcon}>
                    <Icon size={14} />
                  </span>
                  <span class={styles.sourceInlineTitle}>{source.title}</span>
                </a>
              )
            }

            // Иначе обычный бейдж
            return (
              <span class={styles.sourceInlineItem} title={`${source.title} (${source.type})`}>
                <span class={styles.sourceIcon}>
                  <Icon size={14} />
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
