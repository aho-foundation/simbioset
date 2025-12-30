import { Component } from 'solid-js'
import styles from '~/styles/interview.module.css'
import { CopyIcon, EditIcon, FactCheckIcon } from './MessageIcons'

interface MessageActionsProps {
  content: string
  onCopy: () => void
  onFactCheck: () => void
  onEdit: () => void
  isFactCheckLoading?: boolean
}

export const MessageActions: Component<MessageActionsProps> = (props) => {
  return (
    <div class={styles.messageActions}>
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
        onClick={props.onEdit}
        title="Редактировать сообщение (создаст новую ноду)"
      >
        <EditIcon />
      </button>
    </div>
  )
}
