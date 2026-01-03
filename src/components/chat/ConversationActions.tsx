import { Component } from 'solid-js'
import styles from '~/styles/interview.module.css'
import { BookSearchIcon, CopyIcon, LocationIcon, ShareIcon, WebSearchIcon } from './MessageIcons'

interface ConversationActionsProps {
  onCopy: () => void
  onShare: () => void
  onSendLocation?: () => void
  onWebSearch?: () => void
  onBookSearch?: () => void
  currentLocation?: string | null
}

export const ConversationActions: Component<ConversationActionsProps> = (props) => {
  return (
    <div class={styles.copyAllButtonContainer}>
      <button
        class={styles.copyButton}
        onClick={props.onCopy}
        title="Скопировать весь диалог с форматированием"
      >
        <CopyIcon />
      </button>
      <button
        class={styles.copyButton}
        onClick={props.onShare}
        title="Расшарить публичную ссылку на диалог"
      >
        <ShareIcon />
      </button>
      <Show when={props.onSendLocation}>
        <button
          class={styles.copyButton}
          onClick={props.onSendLocation}
          title={`Отправить локацию для локализации экосистемы${props.currentLocation ? ` (текущая: ${props.currentLocation})` : ''}`}
        >
          <LocationIcon />
        </button>
      </Show>
      <Show when={props.onWebSearch}>
        <button
          class={styles.copyButton}
          onClick={props.onWebSearch}
          title="Поиск в интернете по теме диалога"
        >
          <WebSearchIcon />
        </button>
      </Show>
      <Show when={props.onBookSearch}>
        <button class={styles.copyButton} onClick={props.onBookSearch} title="Поиск книг по теме диалога">
          <BookSearchIcon />
        </button>
      </Show>
    </div>
  )
}
