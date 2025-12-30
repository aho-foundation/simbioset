import { A } from '@solidjs/router'
import { Component, createSignal, Show } from 'solid-js'
import { useI18n } from '~/i18n'
import styles from '~/styles/Header.module.css'

// Иконки для разделов - простые и понятные
// Sources - чат-бабл (интервью, диалог)
const SourcesIcon = () => (
  <div class={styles.iconWrapper}>
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
      <line x1="9" y1="6" x2="15" y2="6" />
      <line x1="9" y1="10" x2="13" y2="10" />
    </svg>
  </div>
)

// Knowledge - дерево знаний с реалистичной структурой
const KnowledgeIcon = () => (
  <div class={styles.iconWrapper}>
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      {/* Ствол */}
      <path d="M12 22V14" />
      <path d="M11 14h2" />
      {/* Основные ветки от ствола */}
      <path d="M12 14L9 10" />
      <path d="M12 14L15 10" />
      <path d="M12 14L7 8" />
      <path d="M12 14L17 8" />
      <path d="M12 14L5 5" />
      <path d="M12 14L19 5" />
      {/* Вторичные ветки слева */}
      <path d="M9 10L7 7" />
      <path d="M9 10L6 9" />
      <path d="M7 8L5 6" />
      <path d="M7 8L4 7" />
      <path d="M5 5L3 3" />
      <path d="M5 5L2 4" />
      {/* Вторичные ветки справа */}
      <path d="M15 10L17 7" />
      <path d="M15 10L18 9" />
      <path d="M17 8L19 6" />
      <path d="M17 8L20 7" />
      <path d="M19 5L21 3" />
      <path d="M19 5L22 4" />
      {/* Узлы знаний */}
      <circle cx="6" cy="7" r="0.8" fill="currentColor" />
      <circle cx="8" cy="9" r="0.8" fill="currentColor" />
      <circle cx="16" cy="9" r="0.8" fill="currentColor" />
      <circle cx="18" cy="7" r="0.8" fill="currentColor" />
      <circle cx="4" cy="5" r="0.8" fill="currentColor" />
      <circle cx="20" cy="5" r="0.8" fill="currentColor" />
    </svg>
  </div>
)

// Funds - кошелек/деньги
const FundsIcon = () => (
  <div class={styles.iconWrapper}>
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
      <line x1="12" y1="11" x2="12" y2="17" />
      <line x1="8" y1="11" x2="8" y2="17" />
      <line x1="16" y1="11" x2="16" y2="17" />
    </svg>
  </div>
)

// Логотип для сайдбара - простой глобус
const LogoIcon = () => (
  <svg
    width="40"
    height="40"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M2 12h20" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
)

const Header: Component = () => {
  const [isExpanded, setIsExpanded] = createSignal(false)
  const { t } = useI18n()

  return (
    <aside
      class={styles.sidebar}
      classList={{ [styles.expanded]: isExpanded() }}
      onDblClick={() => setIsExpanded(!isExpanded())}
    >
      <div class={styles.logo}>
        <A href="/" class={styles.logoLink} title="Главная">
          <LogoIcon />
        </A>
        {isExpanded() && (
          <div class={styles.logoText}>
            <div class={styles.logoTitle}>{t('Симбиосеть')}</div>
            <div class={styles.tagline}>{t('Планетарный стетоскоп')}</div>
          </div>
        )}
      </div>

      <nav class={styles.nav}>
        <ul class={styles.navList}>
          <li class={styles.navItem}>
            <A href="/sources" class={styles.navLink} activeClass={styles.active} title="Источники">
              <SourcesIcon />
              <Show when={isExpanded()}>
                <span class={styles.navText}>{t('Источники')}</span>
              </Show>
            </A>
          </li>
          <li class={styles.navItem}>
            <A href="/knowledge" class={styles.navLink} activeClass={styles.active} title="Знания">
              <KnowledgeIcon />
              <Show when={isExpanded()}>
                <span class={styles.navText}>{t('Знания')}</span>
              </Show>
            </A>
          </li>
          <li class={styles.navItem}>
            <A href="/funds" class={styles.navLink} activeClass={styles.active} title="Финансирование">
              <FundsIcon />
              <Show when={isExpanded()}>
                <span class={styles.navText}>{t('Финансирование')}</span>
              </Show>
            </A>
          </li>
          <li class={styles.navItem}>
            <A
              href="/classification"
              class={styles.navLink}
              activeClass={styles.active}
              title="Классификация"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path d="M7 7h10M7 12h10M7 17h10M3 3v18h18V3z" />
              </svg>
              <Show when={isExpanded()}>
                <span class={styles.navText}>{t('Классификация')}</span>
              </Show>
            </A>
          </li>
        </ul>
      </nav>
    </aside>
  )
}

export default Header
