import { Component } from 'solid-js'
import styles from '~/styles/interview.module.css'
import { CopyIcon, EditIcon, FactCheckIcon } from './MessageIcons'
import { SourcesList } from './SourcesList'
import type { MessageSource } from '~/types/chat'

interface MessageActionsProps {
  content: string
  onCopy: () => void
  onFactCheck: () => void
  onEdit: () => void
  isFactCheckLoading?: boolean
  sources?: MessageSource[]
}

export const MessageActions: Component<MessageActionsProps> = (props) => {
  return (
    <div class={styles.messageActions}>
      <div class={styles.messageActionsLeft}>
        <Show when={props.sources && props.sources.length > 0}>
          <SourcesList sources={props.sources!} />
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
