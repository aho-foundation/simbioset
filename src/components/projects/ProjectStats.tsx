import { Component, For, JSX, Show } from 'solid-js'
import type { ProjectStats as Stats } from '~/types/projects'
import styles from './ProjectStats.module.css'

// SVG иконки для статистики
const ProjectsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M3 7v10a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2Z" />
    <path d="M8 5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2H8V5Z" />
  </svg>
)

const ActiveProjectsIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    <path d="M12 2v7" />
  </svg>
)

const CompletedIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <circle cx="12" cy="12" r="10" />
    <path d="m9 12 2 2 4-4" />
  </svg>
)

const FundingIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <line x1="12" y1="1" x2="12" y2="23" />
    <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
  </svg>
)

const AverageIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M3 3v18h18" />
    <path d="m19 9-5 5-4-4-3 3" />
  </svg>
)

const BackersIcon = () => (
  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </svg>
)

interface ProjectStatsProps {
  stats: Stats
}

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  icon?: JSX.Element
  trend?: 'up' | 'down' | 'neutral'
}

const StatCard: Component<StatCardProps> = (props) => {
  const formatValue = (value: string | number) => {
    if (typeof value === 'number') {
      if (value >= 1000000) {
        return `${(value / 1000000).toFixed(1)}M`
      } else if (value >= 1000) {
        return `${(value / 1000).toFixed(1)}K`
      }
      return value.toLocaleString('ru-RU')
    }
    return value
  }

  return (
    <div class={styles.statCard}>
      <div class={styles.statIcon}>{props.icon}</div>
      <div class={styles.statContent}>
        <div class={styles.statValue}>{formatValue(props.value)}</div>
        <div class={styles.statTitle}>{props.title}</div>
        <Show when={props.subtitle}>
          <div class={styles.statSubtitle}>{props.subtitle}</div>
        </Show>
      </div>
      <Show when={props.trend}>
        <div class={`${styles.trendIndicator} ${styles[`trend${props.trend}`]}`}>
          {props.trend === 'up' ? '↗' : props.trend === 'down' ? '↘' : '→'}
        </div>
      </Show>
    </div>
  )
}

export const ProjectStats: Component<ProjectStatsProps> = (props) => {
  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0
    }).format(amount)
  }

  const stats = [
    {
      title: 'Всего проектов',
      value: props.stats.total_projects,
      icon: <ProjectsIcon />,
      subtitle: 'Активных инициатив'
    },
    {
      title: 'Активные проекты',
      value: props.stats.active_projects,
      icon: <ActiveProjectsIcon />,
      subtitle: `${Math.round((props.stats.active_projects / props.stats.total_projects) * 100)}% от общего числа`
    },
    {
      title: 'Завершенные',
      value: props.stats.completed_projects,
      icon: <CompletedIcon />,
      subtitle: 'Успешных проектов'
    },
    {
      title: 'Общее финансирование',
      value: formatCurrency(props.stats.total_funding),
      icon: <FundingIcon />,
      subtitle: 'Собрано средств'
    },
    {
      title: 'Среднее финансирование',
      value: formatCurrency(props.stats.average_funding),
      icon: <AverageIcon />,
      subtitle: 'На проект'
    },
    {
      title: 'Спонсоры',
      value: props.stats.backers_count,
      icon: <BackersIcon />,
      subtitle: 'Уникальных участников'
    }
  ]

  return (
    <div class={styles.statsContainer}>
      <div class={styles.statsGrid}>
        <For each={stats}>{(stat) => <StatCard {...stat} />}</For>
      </div>

      <div class={styles.statsSummary}>
        <div class={styles.summaryCard}>
          <h3>Экологический эффект</h3>
          <div class={styles.impactScore}>
            <span class={styles.impactValue}>
              {Math.round((props.stats.completed_projects / Math.max(props.stats.total_projects, 1)) * 100)}
              %
            </span>
            <span class={styles.impactLabel}>успешность проектов</span>
          </div>
          <p class={styles.impactDescription}>
            Из {props.stats.total_projects} запущенных проектов успешно завершен{' '}
            {props.stats.completed_projects}, что демонстрирует высокую эффективность нашей модели
            самоорганизации.
          </p>
        </div>

        <div class={styles.summaryCard}>
          <h3>Сообщество</h3>
          <div class={styles.communityStats}>
            <div class={styles.communityMetric}>
              <span class={styles.metricValue}>{props.stats.backers_count}</span>
              <span class={styles.metricLabel}>активных участников</span>
            </div>
            <div class={styles.communityMetric}>
              <span class={styles.metricValue}>{formatCurrency(props.stats.total_funding)}</span>
              <span class={styles.metricLabel}>инвестировано в экологию</span>
            </div>
          </div>
          <p class={styles.communityDescription}>
            Наше сообщество объединяет людей, готовых вкладывать время и средства в создание устойчивого
            будущего планеты.
          </p>
        </div>
      </div>
    </div>
  )
}
