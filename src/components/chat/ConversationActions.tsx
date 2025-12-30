import { Component } from 'solid-js'
import styles from '~/styles/interview.module.css'
import { CopyIcon, ShareIcon } from './MessageIcons'

interface ConversationActionsProps {
  onCopy: () => void
  onShare: () => void
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
    </div>
  )
}
