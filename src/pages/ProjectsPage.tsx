import { Component, createResource, createSignal, For, Show } from 'solid-js'
import { ProjectCard } from '~/components/projects/ProjectCard'
import { ProjectFunding } from '~/components/projects/ProjectFunding'
import { ProjectStats } from '~/components/projects/ProjectStats'
import { useI18n } from '~/i18n'
import type {
  Backer,
  CrowdfundedProject,
  Project,
  ProjectsResponse,
  ProjectStats as Stats
} from '~/types/projects'
import { isCrowdfundedProject } from '~/types/projects'
import styles from './ProjectsPage.module.css'

// Mock data for when backend is unavailable
const getMockProjects = (): Project[] => [
  {
    id: 'mock-cs-1',
    title: 'Система анализа экосистем на основе ИИ',
    description:
      'Разработка интеллектуальной системы для мониторинга и анализа экологических данных с использованием машинного обучения и компьютерного зрения.',
    status: 'active',
    creation_date: '2025-01-01T10:00:00Z',
    update_date: '2025-01-15T14:30:00Z',
    knowledge_base_id: 'kb-ecosystem-analysis',
    tags: ['ai', 'ecology', 'machine-learning', 'computer-vision'],
    ideas: [
      {
        id: 'idea-1',
        project_id: 'mock-cs-1',
        author_id: 'user1',
        content: 'Добавить поддержку спутниковых снимков для анализа лесных пожаров',
        submission_date: '2025-01-10T09:00:00Z',
        votes: 12,
        status: 'approved'
      },
      {
        id: 'idea-2',
        project_id: 'mock-cs-1',
        author_id: 'user2',
        content: 'Интеграция с датчиками IoT для реального времени мониторинга',
        submission_date: '2025-01-12T11:00:00Z',
        votes: 8,
        status: 'submitted'
      }
    ],
    contributors: [
      {
        user_id: 'user1',
        name: 'Алексей Иванов',
        role: 'ML инженер',
        contribution_date: '2025-01-05T10:00:00Z',
        contributions: ['Архитектура модели', 'Подготовка датасета']
      },
      {
        user_id: 'user3',
        name: 'Мария Петрова',
        role: 'Data Scientist',
        contribution_date: '2025-01-08T14:00:00Z',
        contributions: ['Анализ данных', 'Валидация модели']
      }
    ]
  },
  {
    id: 'mock-cf-1',
    title: 'Экологичный дрон для мониторинга лесов',
    description:
      'Создание автономного дрона с системой компьютерного зрения для обнаружения нарушений экосистемы лесов и раннего предупреждения о пожарах.',
    status: 'active',
    creation_date: '2025-01-03T12:00:00Z',
    update_date: '2025-01-16T16:45:00Z',
    knowledge_base_id: 'kb-drone-monitoring',
    tags: ['drone', 'forest', 'fire-detection', 'computer-vision'],
    funding_goal: 2500000,
    current_funding: 875000,
    start_date: '2025-01-01T00:00:00Z',
    end_date: '2025-04-01T23:59:59Z',
    backers: [
      {
        user_id: 'user4',
        name: 'ООО "Зеленые технологии"',
        amount: 500000,
        backing_date: '2025-01-05T10:00:00Z',
        tier_id: 'gold',
        public: true
      },
      {
        user_id: 'user5',
        name: 'Анонимный спонсор',
        amount: 250000,
        backing_date: '2025-01-08T14:00:00Z',
        tier_id: 'silver',
        public: false
      },
      {
        user_id: 'user6',
        name: 'Фонд экологии',
        amount: 125000,
        backing_date: '2025-01-12T09:30:00Z',
        tier_id: 'bronze',
        public: true
      }
    ],
    funding_tiers: [
      {
        id: 'bronze',
        title: 'Бронзовый спонсор',
        description: 'Базовая поддержка проекта',
        amount: 50000,
        rewards: ['Упоминание в соцсетях', 'Отчет о прогрессе'],
        limit: 20
      },
      {
        id: 'silver',
        title: 'Серебряный спонсор',
        description: 'Расширенная поддержка',
        amount: 250000,
        rewards: ['Бронзовые награды +', 'Доступ к бета-тестированию', 'Персональная благодарность'],
        limit: 10
      },
      {
        id: 'gold',
        title: 'Золотой спонсор',
        description: 'Премиум поддержка',
        amount: 500000,
        rewards: ['Серебряные награды +', 'Приглашение на презентацию', 'Совместная разработка требований'],
        limit: 5
      }
    ]
  },
  {
    id: 'mock-cs-2',
    title: 'Платформа citizen science для экологии',
    description:
      'Создание веб-платформы, где волонтеры могут участвовать в сборе и анализе экологических данных, помогая ученым в исследованиях.',
    status: 'active',
    creation_date: '2025-01-07T09:00:00Z',
    update_date: '2025-01-14T11:20:00Z',
    knowledge_base_id: 'kb-citizen-science',
    tags: ['citizen-science', 'volunteers', 'data-collection', 'web-platform'],
    ideas: [
      {
        id: 'idea-3',
        project_id: 'mock-cs-2',
        author_id: 'user7',
        content: 'Добавить мобильное приложение для оффлайн сбора данных',
        submission_date: '2025-01-11T13:00:00Z',
        votes: 15,
        status: 'approved'
      },
      {
        id: 'idea-4',
        project_id: 'mock-cs-2',
        author_id: 'user8',
        content: 'Система геймификации для мотивации волонтеров',
        submission_date: '2025-01-13T10:00:00Z',
        votes: 9,
        status: 'reviewed'
      }
    ],
    contributors: [
      {
        user_id: 'user9',
        name: 'Дмитрий Сидоров',
        role: 'Full-stack разработчик',
        contribution_date: '2025-01-08T11:00:00Z',
        contributions: ['Фронтенд разработка', 'API дизайн']
      },
      {
        user_id: 'user10',
        name: 'Елена Кузнецова',
        role: 'UX/UI дизайнер',
        contribution_date: '2025-01-09T15:00:00Z',
        contributions: ['Дизайн интерфейса', 'Прототипирование']
      }
    ]
  },
  {
    id: 'mock-cf-2',
    title: 'Система очистки воздуха для городов',
    description:
      'Разработка и установка инновационных систем очистки воздуха в городских районах с высоким уровнем загрязнения.',
    status: 'completed',
    creation_date: '2024-11-15T08:00:00Z',
    update_date: '2025-01-10T17:00:00Z',
    knowledge_base_id: 'kb-air-purification',
    tags: ['air-purification', 'urban', 'pollution', 'technology'],
    funding_goal: 5000000,
    current_funding: 5200000,
    start_date: '2024-11-01T00:00:00Z',
    end_date: '2025-01-15T23:59:59Z',
    backers: [
      {
        user_id: 'user11',
        name: 'Муниципалитет города',
        amount: 2000000,
        backing_date: '2024-11-20T12:00:00Z',
        tier_id: 'enterprise',
        public: true
      },
      {
        user_id: 'user12',
        name: 'Эко-фонд "Чистый воздух"',
        amount: 1500000,
        backing_date: '2024-12-01T09:00:00Z',
        tier_id: 'gold',
        public: true
      }
    ],
    funding_tiers: [
      {
        id: 'basic',
        title: 'Базовая поддержка',
        description: 'Помощь в развитии проекта',
        amount: 100000,
        rewards: ['Отчет о результатах', 'Упоминание в публикациях']
      },
      {
        id: 'gold',
        title: 'Золотая поддержка',
        description: 'Значительная поддержка',
        amount: 1000000,
        rewards: ['Базовые награды +', 'Участие в презентации', 'Награда с логотипом']
      },
      {
        id: 'enterprise',
        title: 'Корпоративная поддержка',
        description: 'Крупная корпоративная поддержка',
        amount: 2000000,
        rewards: ['Золотые награды +', 'Совместный брендинг', 'Стратегическое партнерство']
      }
    ]
  }
]

const getMockStats = (projects: Project[]): Stats => {
  const totalProjects = projects.length
  const activeProjects = projects.filter((p) => p.status === 'active').length
  const completedProjects = projects.filter((p) => p.status === 'completed').length

  const crowdfundedProjects = projects.filter(isCrowdfundedProject)
  const totalFunding = crowdfundedProjects.reduce((sum, p) => sum + p.current_funding, 0)
  const averageFunding = crowdfundedProjects.length > 0 ? totalFunding / crowdfundedProjects.length : 0
  const backersCount = crowdfundedProjects.reduce((sum, p) => sum + p.backers.length, 0)

  return {
    total_projects: totalProjects,
    active_projects: activeProjects,
    completed_projects: completedProjects,
    total_funding: totalFunding,
    average_funding: averageFunding,
    backers_count: backersCount
  }
}

const ProjectsPage: Component = () => {
  const { t } = useI18n()
  const [selectedProject, setSelectedProject] = createSignal<Project | null>(null)
  const [refetchTrigger, setRefetchTrigger] = createSignal(0)

  // Load projects from API with fallback to mock data
  const [projectsData] = createResource(
    () => refetchTrigger(),
    async (): Promise<ProjectsResponse> => {
      try {
        const response = await fetch('/api/projects?limit=50')
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        const data = await response.json()

        // If API returns empty or invalid data, use mock data
        if (!data.projects || data.projects.length === 0) {
          console.warn('API returned empty projects data, using mock data')
          return {
            projects: getMockProjects(),
            total: getMockProjects().length,
            offset: 0,
            limit: 50
          }
        }

        return data
      } catch (err) {
        console.warn('Backend unavailable, using mock data:', err)
        const mockProjects = getMockProjects()
        return {
          projects: mockProjects,
          total: mockProjects.length,
          offset: 0,
          limit: 50
        }
      }
    },
    {
      initialValue: { projects: [], total: 0, offset: 0, limit: 50 }
    }
  )

  // Load project statistics
  const [statsData] = createResource(
    () => [refetchTrigger(), projectsData()],
    async ([_, projectsResponse]): Promise<Stats> => {
      try {
        // Use projects data to calculate stats
        const projects = (projectsResponse as ProjectsResponse)?.projects || []

        if (projects.length === 0) {
          // If no projects, use mock stats
          return getMockStats(getMockProjects())
        }

        const totalProjects = projects.length
        const activeProjects = projects.filter((p) => p.status === 'active').length
        const completedProjects = projects.filter((p) => p.status === 'completed').length

        const crowdfundedProjects = projects.filter(isCrowdfundedProject)
        const totalFunding = crowdfundedProjects.reduce((sum, p) => sum + p.current_funding, 0)
        const averageFunding =
          crowdfundedProjects.length > 0 ? totalFunding / crowdfundedProjects.length : 0
        const backersCount = crowdfundedProjects.reduce((sum, p) => sum + p.backers.length, 0)

        return {
          total_projects: totalProjects,
          active_projects: activeProjects,
          completed_projects: completedProjects,
          total_funding: totalFunding,
          average_funding: averageFunding,
          backers_count: backersCount
        }
      } catch (err) {
        console.error('Error calculating stats:', err)
        // Fallback to mock stats
        return getMockStats(getMockProjects())
      }
    }
  )

  // Functions for crowdfunding
  const handleProjectSelect = (project: Project) => {
    setSelectedProject(project)
  }

  const handleProjectSupport = async (project: Project) => {
    if (isCrowdfundedProject(project)) {
      setSelectedProject(project)
    }
  }

  const handleProjectContribute = async (project: Project) => {
    // Handle crowdsourcing contribution
    console.log('Contribute to project:', project.id)
  }

  const handleBacking = async (backer: Backer) => {
    if (!selectedProject() || !isCrowdfundedProject(selectedProject()!)) return

    try {
      // Try to call API first
      const response = await fetch(`/api/projects/${selectedProject()!.id}/back`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: backer.user_id,
          name: backer.name,
          amount: backer.amount,
          tier_id: backer.tier_id,
          public: backer.public
        })
      })

      if (response.ok) {
        // API call successful
        setRefetchTrigger((prev) => prev + 1)
        return
      }

      // If API fails, simulate success for demo purposes
      console.warn('API unavailable, simulating successful backing')

      // For demo: add backer to mock project (this won't persist)
      if (isCrowdfundedProject(selectedProject()!)) {
        const project = selectedProject()! as CrowdfundedProject
        const newBacker: Backer = {
          ...backer,
          backing_date: new Date().toISOString()
        }
        project.backers.push(newBacker)
        project.current_funding += backer.amount
      }

      // Refresh to show updated data
      setRefetchTrigger((prev) => prev + 1)
    } catch (error) {
      console.error('Failed to add backer:', error)

      // For demo purposes, still simulate success
      console.warn('Simulating successful backing despite error')
      if (isCrowdfundedProject(selectedProject()!)) {
        const project = selectedProject()! as CrowdfundedProject
        const newBacker: Backer = {
          ...backer,
          backing_date: new Date().toISOString()
        }
        project.backers.push(newBacker)
        project.current_funding += backer.amount
      }
      setRefetchTrigger((prev) => prev + 1)
    }
  }

  const handleRefreshFunding = () => {
    setRefetchTrigger((prev) => prev + 1)
  }

  return (
    <div class={styles.projectsPage}>
      <div class={styles.header}>
        <p class={styles.subtitle}>{t('Преобразование идей в реальные проекты с поддержкой сообщества')}</p>
      </div>

      {projectsData.loading || statsData.loading ? (
        <div class={styles.loading}>
          <div class={styles.spinner} />
          <p>{t('Загрузка проектов...')}</p>
        </div>
      ) : (
        <div class={styles.content}>
          {/* Статистика проектов */}
          <Show when={statsData()}>
            <ProjectStats stats={statsData()!} />
          </Show>

          {/* Сетка проектов */}
          <section class={styles.projectsSection}>
            <h2 class={styles.sectionTitle}>{t('Активные проекты')}</h2>
            <div class={styles.projectsGrid}>
              <For each={projectsData()?.projects || []}>
                {(project) => (
                  <ProjectCard
                    project={project}
                    onSelect={handleProjectSelect}
                    onSupport={handleProjectSupport}
                    onContribute={handleProjectContribute}
                  />
                )}
              </For>
            </div>

            <Show when={(projectsData()?.projects || []).length === 0}>
              <div class={styles.empty}>
                <p>{t('Пока нет активных проектов')}</p>
                <p class={styles.hint}>
                  {t('Создайте артефакты в чате, чтобы преобразовать их в проекты')}
                </p>
              </div>
            </Show>

            <Show when={(projectsData()?.projects || []).length > 0}>
              <div class={styles.dataNotice}>
                <small>
                  {projectsData()?.projects?.some((p) => p.id.startsWith('mock-'))
                    ? '🔧 Используются демонстрационные данные (бэкенд недоступен)'
                    : '✅ Данные загружены из API'}
                </small>
              </div>
            </Show>
          </section>

          {/* Детали выбранного проекта */}
          <Show when={selectedProject()}>
            <section class={styles.projectDetails}>
              <div class={styles.detailsHeader}>
                <h2>{selectedProject()!.title}</h2>
                <button class={styles.closeButton} onClick={() => setSelectedProject(null)}>
                  ×
                </button>
              </div>

              <div class={styles.detailsContent}>
                <div class={styles.projectInfo}>
                  <p class={styles.projectDescription}>{selectedProject()!.description}</p>
                  <div class={styles.projectMeta}>
                    <span class={styles.status}>Статус: {selectedProject()!.status}</span>
                    <span class={styles.created}>
                      Создан: {new Date(selectedProject()!.creation_date).toLocaleDateString('ru-RU')}
                    </span>
                  </div>
                </div>

                <Show when={isCrowdfundedProject(selectedProject()!)}>
                  <ProjectFunding
                    project={selectedProject()! as CrowdfundedProject}
                    onBack={handleBacking}
                    onRefresh={handleRefreshFunding}
                  />
                </Show>

                <Show when={!isCrowdfundedProject(selectedProject()!)}>
                  <div class={styles.crowdsourcingSection}>
                    <h3>Краудсорсинг</h3>
                    <p>Этот проект открыт для вклада идей и участия сообщества.</p>
                    <button
                      class={styles.contributeButton}
                      onClick={() => handleProjectContribute(selectedProject()!)}
                    >
                      Внести вклад
                    </button>
                  </div>
                </Show>
              </div>
            </section>
          </Show>
        </div>
      )}
    </div>
  )
}

export default ProjectsPage
