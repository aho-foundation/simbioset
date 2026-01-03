import styles from './DetectorsToolbar.module.css'

interface DetectorsToolbarProps {
  onRunDetector?: (kind: 'organisms' | 'ecosystems' | 'environment' | 'all') => Promise<void>
  detectorLoading: boolean
  detectorErrors?: Record<string, boolean>
}

export const DetectorsToolbar = (props: DetectorsToolbarProps) => {
  const getButtonClass = (kind: string) => {
    let classes = styles.detectorBtn
    if (props.detectorErrors?.[kind]) {
      classes += ` ${styles.error}`
    }
    return classes
  }

  return (
    <div class={styles.detectorButtons}>
      <button
        onClick={() => props.onRunDetector?.('ecosystems')}
        disabled={props.detectorLoading}
        class={getButtonClass('ecosystems')}
        title="Найти экосистемы в тексте"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
          <path d="M12 17.5c-.28 0-.5-.22-.5-.5s.22-.5.5-.5.5.22.5.5-.22.5-.5.5z" />
        </svg>
      </button>
      <button
        onClick={() => props.onRunDetector?.('environment')}
        disabled={props.detectorLoading}
        class={getButtonClass('environment')}
        title="Анализ условий среды"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M3 3v18h18" />
          <path d="M18.7 8l-5.1 5.2-2.8-2.7L7 14.3" />
        </svg>
      </button>
      <button
        onClick={() => props.onRunDetector?.('all')}
        disabled={props.detectorLoading}
        class={getButtonClass('all')}
        title="Комплексный анализ"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
      </button>
    </div>
  )
}
