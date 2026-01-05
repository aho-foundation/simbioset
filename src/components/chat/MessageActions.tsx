import { Component, Show } from 'solid-js'
import styles from '~/styles/interview.module.css'
import type { MessageSource } from '~/types/chat'
import {
  ArtifactIcon,
  BookSearchIcon,
  CopyIcon,
  EditIcon,
  FactCheckIcon,
  WebSearchIcon
} from './MessageIcons'
import { SourcesList } from './SourcesList'

interface MessageActionsProps {
  content: string
  selectedText?: string
  onCopy: () => void
  onFactCheck: () => void
  onWebSearch?: () => void
  onBookSearch?: () => void
  onEdit: () => void
  onMarkArtifact?: () => void
  isFactCheckLoading?: boolean
  sources?: MessageSource[]
}

export const MessageActions: Component<MessageActionsProps> = (props) => {
  // Предотвращаем исчезновение тулбара при hover на источниках
  const handleSourcesHover = (e: MouseEvent) => {
    e.stopPropagation()
    const messageActions = (e.currentTarget as Element)?.closest(`.${styles.messageActions}`)
    if (messageActions) {
      ;(messageActions as HTMLElement).style.opacity = '1'
      ;(messageActions as HTMLElement).style.visibility = 'visible'
    }
  }

  return (
    <div class={styles.messageActions}>
      <div class={styles.messageActionsLeft}>
        <Show when={props.sources && props.sources.length > 0}>
          <div
            onMouseEnter={handleSourcesHover}
            onMouseMove={handleSourcesHover}
            onMouseLeave={(_e) => {
              // Не делаем ничего, пусть родительский hover управляет
            }}
          >
            <SourcesList sources={props.sources!} />
          </div>
        </Show>
      </div>
      <div class={styles.messageActionsRight}>
        <button
          class={styles.copyMessageButton}
          onClick={props.onCopy}
          title="Скопировать содержимое с форматированием"
        >
          <CopyIcon />
        </button>
        <button
          class={styles.copyMessageButton}
          onClick={props.onFactCheck}
          title="Проверить достоверность сообщения"
          disabled={props.isFactCheckLoading}
        >
          <FactCheckIcon />
        </button>
        <Show when={props.onWebSearch}>
          <button
            class={styles.copyMessageButton}
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              props.onWebSearch?.()
            }}
            title="Поиск в интернете по этому сообщению"
            disabled={props.isFactCheckLoading}
          >
            <WebSearchIcon />
          </button>
        </Show>
        <Show when={props.onBookSearch}>
          <button
            class={styles.copyMessageButton}
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              props.onBookSearch?.()
            }}
            title="Поиск книг по этому сообщению"
            disabled={props.isFactCheckLoading}
          >
            <BookSearchIcon />
          </button>
        </Show>
        <Show when={props.onMarkArtifact && props.selectedText}>
          <button
            class={styles.copyMessageButton}
            onClick={(e) => {
              e.preventDefault()
              e.stopPropagation()
              props.onMarkArtifact?.()
            }}
            title="Отметить как артефакт"
          >
            <ArtifactIcon />
          </button>
        </Show>
        <button
          class={styles.copyMessageButton}
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            props.onEdit()
          }}
          title="Редактировать сообщение (создаст новую ноду)"
        >
          <EditIcon />
        </button>
      </div>
    </div>
  )
}
