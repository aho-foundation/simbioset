import { A } from '@solidjs/router'
import { Component, createSignal, Show } from 'solid-js'
import { useI18n } from '~/i18n'
import styles from '~/styles/Header.module.css'

// Иконки для разделов - простые и понятные
// Sources - чат-бабл (интервью, диалог)
const SourcesIcon = () => (
  <svg
    class={styles.icon}
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
)

// Knowledge - дерево знаний с реалистичной структурой
const KnowledgeIcon = () => (
  <svg
    class={styles.icon}
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
)

// Projects
const ProjectsIcon = () => (
  <svg
    class={styles.icon}
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
  >
    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
    <line x1="9" y1="9" x2="15" y2="9" />
    <line x1="9" y1="12" x2="15" y2="12" />
    <line x1="9" y1="15" x2="13" y2="15" />
  </svg>
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
            <A href="/projects" class={styles.navLink} activeClass={styles.active} title="Проекты">
              <ProjectsIcon />
              <Show when={isExpanded()}>
                <span class={styles.navText}>{t('Проекты')}</span>
              </Show>
            </A>
          </li>
        </ul>
      </nav>
    </aside>
  )
}

export default Header
