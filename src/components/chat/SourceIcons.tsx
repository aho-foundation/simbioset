import type { Component } from 'solid-js'

// Иконка для базы знаний
export const KnowledgeBaseIcon: Component = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  </svg>
)

// Иконка для научной литературы
export const ScientificLiteratureIcon: Component = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    <line x1="8" y1="7" x2="16" y2="7" />
    <line x1="8" y1="11" x2="16" y2="11" />
    <line x1="8" y1="15" x2="12" y2="15" />
  </svg>
)

// Иконка для веб-поиска
export const WebSearchIcon: Component = () => (
  <svg
    width="14"
    height="14"
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
)

// Иконка для публикаций
export const PublicationIcon: Component = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <path d="M14 2v6h6" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
    <polyline points="10 9 9 9 8 9" />
  </svg>
)

// Иконка по умолчанию
export const DefaultSourceIcon: Component = () => (
  <svg
    width="14"
    height="14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
)

// Маппинг эмоджи на иконки для декодирования
const emojiToIconMap: Record<string, Component> = {
  '📚': ScientificLiteratureIcon, // научная литература
  '🌐': WebSearchIcon, // веб-поиск
  '🧠': KnowledgeBaseIcon, // база знаний
  '🤖': PublicationIcon, // нейронная сеть / публикация
  '📖': PublicationIcon, // публикация
  '🔬': ScientificLiteratureIcon // исследование
}

// Функция для получения иконки по типу источника (эмоджи или текст)
export const getSourceIcon = (sourceType: string): Component => {
  // Сначала проверяем на эмоджи
  if (emojiToIconMap[sourceType]) {
    return emojiToIconMap[sourceType]
  }

  // Затем проверяем текстовые типы
  const typeLower = sourceType.toLowerCase()

  if (typeLower.includes('база знаний') || typeLower.includes('knowledge base')) {
    return KnowledgeBaseIcon
  }
  if (
    typeLower.includes('научная') ||
    typeLower.includes('литература') ||
    typeLower.includes('scientific') ||
    typeLower.includes('literature')
  ) {
    return ScientificLiteratureIcon
  }
  if (
    typeLower.includes('веб') ||
    typeLower.includes('поиск') ||
    typeLower.includes('web') ||
    typeLower.includes('search')
  ) {
    return WebSearchIcon
  }
  if (
    typeLower.includes('публикация') ||
    typeLower.includes('исследование') ||
    typeLower.includes('publication') ||
    typeLower.includes('research')
  ) {
    return PublicationIcon
  }

  return DefaultSourceIcon
}
