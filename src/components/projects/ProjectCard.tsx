import { Component, Show } from 'solid-js'
import type { CrowdfundedProject, CrowdsourcedProject, Project } from '~/types/projects'
import { isCrowdfundedProject } from '~/types/projects'
import styles from './ProjectCard.module.css'

interface ProjectCardProps {
  project: Project
  onSelect?: (project: Project) => void
  onSupport?: (project: Project) => void
  onContribute?: (project: Project) => void
}

const StatusBadge: Component<{ status: string }> = (props) => {
  const getStatusText = (status: string) => {
    switch (status) {
      case 'draft':
        return 'Черновик'
      case 'active':
        return 'Активен'
      case 'completed':
        return 'Завершен'
      case 'archived':
        return 'Архивирован'
      case 'failed':
        return 'Неудача'
      default:
        return status
    }
  }

  const getStatusClass = (status: string) => {
    switch (status) {
      case 'active':
        return styles.statusActive
      case 'completed':
        return styles.statusCompleted
      case 'failed':
        return styles.statusFailed
      default:
        return styles.statusDefault
    }
  }

  return (
    <span class={`${styles.statusBadge} ${getStatusClass(props.status)}`}>
      {getStatusText(props.status)}
    </span>
  )
}

const CrowdfundedProjectInfo: Component<{ project: CrowdfundedProject }> = (props) => {
  const progressPercentage = () => {
    return Math.min((props.project.current_funding / props.project.funding_goal) * 100, 100)
  }

  const daysLeft = () => {
    const end = new Date(props.project.end_date)
    const now = new Date()
    const diff = Math.ceil((end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24))
    return Math.max(0, diff)
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0
    }).format(amount)
  }

  return (
    <div class={styles.crowdfundInfo}>
      <div class={styles.fundingProgress}>
        <div class={styles.fundingBar}>
          <div class={styles.fundingBarFill} style={{ width: `${progressPercentage()}%` }} />
        </div>
        <div class={styles.fundingStats}>
          <span class={styles.fundingCurrent}>{formatCurrency(props.project.current_funding)}</span>
          <span class={styles.fundingGoal}>из {formatCurrency(props.project.funding_goal)}</span>
        </div>
      </div>
      <div class={styles.fundingMeta}>
        <span class={styles.backersCount}>{props.project.backers.length} спонсоров</span>
        <span class={styles.daysLeft}>{daysLeft()} дней осталось</span>
      </div>
    </div>
  )
}

const CrowdsourcedProjectInfo: Component<{ project: CrowdsourcedProject }> = (props) => {
  return (
    <div class={styles.crowdsourcedInfo}>
      <div class={styles.ideasCount}>{props.project.ideas.length} идей</div>
      <div class={styles.contributorsCount}>{props.project.contributors.length} участников</div>
    </div>
  )
}

export const ProjectCard: Component<ProjectCardProps> = (props) => {
  const handleCardClick = () => {
    props.onSelect?.(props.project)
  }

  const handleSupportClick = (e: Event) => {
    e.stopPropagation()
    props.onSupport?.(props.project)
  }

  const handleContributeClick = (e: Event) => {
    e.stopPropagation()
    props.onContribute?.(props.project)
  }

  return (
    <div class={styles.projectCard} onClick={handleCardClick}>
      <div class={styles.projectHeader}>
        <h3 class={styles.projectTitle}>{props.project.title}</h3>
        <StatusBadge status={props.project.status} />
      </div>

      <p class={styles.projectDescription}>
        {props.project.description.length > 150
          ? `${props.project.description.substring(0, 150)}...`
          : props.project.description}
      </p>

      <Show when={isCrowdfundedProject(props.project)}>
        <CrowdfundedProjectInfo project={props.project} />
      </Show>

      <Show when={!isCrowdfundedProject(props.project)}>
        <CrowdsourcedProjectInfo project={props.project as CrowdsourcedProject} />
      </Show>

      <div class={styles.projectTags}>
        {props.project.tags.slice(0, 3).map((tag) => (
          <span class={styles.tag}>#{tag}</span>
        ))}
        <Show when={props.project.tags.length > 3}>
          <span class={styles.tag}>+{props.project.tags.length - 3}</span>
        </Show>
      </div>

      <div class={styles.projectActions}>
        <Show when={isCrowdfundedProject(props.project)}>
          <button
            class={styles.supportButton}
            onClick={handleSupportClick}
            disabled={props.project.status !== 'active'}
          >
            Поддержать
          </button>
        </Show>

        <Show when={!isCrowdfundedProject(props.project)}>
          <button
            class={styles.contributeButton}
            onClick={handleContributeClick}
            disabled={props.project.status !== 'active'}
          >
            Внести вклад
          </button>
        </Show>
      </div>

      <div class={styles.projectMeta}>
        <small class={styles.creationDate}>
          Создан: {new Date(props.project.creation_date).toLocaleDateString('ru-RU')}
        </small>
      </div>
    </div>
  )
}
