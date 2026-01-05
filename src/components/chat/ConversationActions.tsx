import { Component, Show } from 'solid-js'
import styles from '~/styles/interview.module.css'
import badgeStyles from './ConversationActions.module.css'
import {
  BookSearchIcon,
  CopyIcon,
  FactCheckIcon,
  LocationIcon,
  ShareIcon,
  WebSearchIcon
} from './MessageIcons'

// SVG иконка уровня уверенности фактчекера
const ConfidenceIcon = (props: { confidence: number }) => {
  const percentage = Math.round(props.confidence * 100)
  const strokeDasharray = `${percentage} 100`

  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      {/* Фон круга */}
      <circle cx="12" cy="12" r="10" stroke="#e5e7eb" fill="none" />
      {/* Заполнение круга в зависимости от уверенности */}
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="#10b981"
        fill="none"
        stroke-dasharray={strokeDasharray}
        stroke-dashoffset="0"
        transform="rotate(-90 12 12)"
        stroke-linecap="round"
      />
      {/* Текст с процентом */}
      <text x="12" y="16" text-anchor="middle" font-size="6" font-weight="bold" fill="#10b981">
        {percentage}
      </text>
    </svg>
  )
}

interface ConversationActionsProps {
  onCopy: () => void
  onShare: () => void
  onSendLocation?: () => void
  onWebSearch?: () => void
  onBookSearch?: () => void
  onFactCheck?: () => void
  currentLocation?: string | null
  factCheckResult?: { status: 'true' | 'false' | null; confidence?: number } | null
  hasWebSearchError?: boolean
  hasLocationError?: boolean
  hasBookSearchError?: boolean
}

export const ConversationActions: Component<ConversationActionsProps> = (props) => {
  return (
    <div class={styles.copyAllButtonContainer}>
      <button class={styles.copyButton} onClick={props.onCopy} title="Копировать">
        <CopyIcon />
      </button>
      <button class={styles.copyButton} onClick={props.onShare} title="Поделиться">
        <ShareIcon />
      </button>
      <Show when={props.onSendLocation}>
        <button class={styles.copyButton} onClick={props.onSendLocation} title="Отправить локацию">
          <div class={badgeStyles.badgeContainer}>
            <LocationIcon />
            <Show when={props.hasLocationError}>
              <div class={badgeStyles.locationErrorBadge} />
            </Show>
          </div>
        </button>
      </Show>
      <Show when={props.onWebSearch}>
        <button class={styles.copyButton} onClick={props.onWebSearch} title="Поиск в интернете">
          <div class={badgeStyles.badgeContainer}>
            <WebSearchIcon />
            <Show when={props.hasWebSearchError}>
              <div class={badgeStyles.webSearchErrorBadge} />
            </Show>
          </div>
        </button>
      </Show>
      <Show when={props.onBookSearch}>
        <button class={styles.copyButton} onClick={props.onBookSearch} title="Поиск книг">
          <div class={badgeStyles.badgeContainer}>
            <BookSearchIcon />
            <Show when={props.hasBookSearchError}>
              <div class={badgeStyles.bookSearchErrorBadge} />
            </Show>
          </div>
        </button>
      </Show>
      <Show when={props.onFactCheck}>
        <button class={styles.copyButton} onClick={props.onFactCheck} title="Фактчек">
          <div class={badgeStyles.badgeContainer}>
            <FactCheckIcon />
            <Show when={props.factCheckResult?.status}>
              {props.factCheckResult?.status === 'true' && props.factCheckResult?.confidence ? (
                <div class={badgeStyles.confidenceBadge}>
                  <ConfidenceIcon confidence={props.factCheckResult.confidence} />
                </div>
              ) : (
                <div
                  class={`${badgeStyles.factCheckBadge} ${
                    props.factCheckResult?.status === 'true'
                      ? badgeStyles.factCheckBadgeTrue
                      : props.factCheckResult?.status === 'false'
                        ? badgeStyles.factCheckBadgeFalse
                        : badgeStyles.factCheckBadgeUnknown
                  }`}
                >
                  {props.factCheckResult?.status === 'true'
                    ? '✓'
                    : props.factCheckResult?.status === 'false'
                      ? '✗'
                      : '?'}
                </div>
              )}
            </Show>
          </div>
        </button>
      </Show>
    </div>
  )
}
