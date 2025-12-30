import { For, Show } from 'solid-js'
import styles from '~/styles/interview.module.css'
import type { MessageSource } from '~/types/chat'
import { getSourceIcon } from './SourceIcons'

interface SourcesListProps {
  sources: MessageSource[]
}

export const SourcesList = (props: SourcesListProps) => {
  const validSources = () =>
    props.sources.filter((s) => s.title && s.type && !s.type.toLowerCase().includes('неизвестный'))

  return (
    <Show when={validSources().length > 0}>
      <div class={styles.sourcesInline}>
        <For each={validSources()}>
          {(source) => {
            const Icon = getSourceIcon(source.type)
            return (
              <span class={styles.sourceInlineItem} title={source.title}>
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
