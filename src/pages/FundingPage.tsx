import { A } from '@solidjs/router'
import { Component, createResource, createSignal } from 'solid-js'
import { useI18n } from '~/i18n'
import styles from '~/styles/funding.module.css'

// Типы данных для проектов и инициатив
type EcoInitiative = {
  id: string
  name: string
  description: string
  status: 'active' | 'completed' | 'planned'
  impactScore: number
  investment: number
  roi: number
  category: 'renewable_energy' | 'waste_management' | 'urban_greening' | 'water_conservation'
}

type Recommendation = {
  id: string
  title: string
  description: string
  potentialImpact: number
  estimatedCost: number
  category: string
}

const ProjectsPage: Component = () => {
  const { t } = useI18n()
  const [selectedInitiative, setSelectedInitiative] = createSignal<EcoInitiative | null>(null)
  const [refetchTrigger, setRefetchTrigger] = createSignal(0)

  // Load funding data using createResource for proper reactivity
  const [fundingData] = createResource(
    () => refetchTrigger(), // Trigger refetch on change
    async () => {
      try {
        // In real app, this would be API call
        // For demo, simulate loading with mock data
        await new Promise((resolve) => setTimeout(resolve, 800))

        const mockInitiatives: EcoInitiative[] = [
          {
            id: 'init-1',
            name: t('Солнечная ферма "Зеленый луч"'),
            description: t('Установка солнечных панелей на 500 кВт в промышленной зоне'),
            status: 'active',
            impactScore: 85,
            investment: 12000000,
            roi: 18.5,
            category: 'renewable_energy'
          },
          {
            id: 'init-2',
            name: t('Система переработки отходов "ЭкоЦикл"'),
            description: t('Внедрение инновационной системы сортировки и переработки отходов'),
            status: 'completed',
            impactScore: 92,
            investment: 8500000,
            roi: 22.3,
            category: 'waste_management'
          },
          {
            id: 'init-3',
            name: t('Парк "Зеленое будущее"'),
            description: t('Создание экологического парка с системами очистки воздуха'),
            status: 'planned',
            impactScore: 78,
            investment: 4200000,
            roi: 15.7,
            category: 'urban_greening'
          }
        ]

        const mockRecommendations: Recommendation[] = [
          {
            id: 'rec-1',
            title: t('Оптимизация энергопотребления в офисах'),
            description: t(
              'Внедрение систем умного освещения и климат-контроля для снижения энергозатрат на 30%'
            ),
            potentialImpact: 45,
            estimatedCost: 1500000,
            category: 'energy_efficiency'
          },
          {
            id: 'rec-2',
            title: t('Программа "Зеленый транспорт"'),
            description: t(
              'Стимулирование использования электротранспорта и велосипедов среди сотрудников'
            ),
            potentialImpact: 62,
            estimatedCost: 800000,
            category: 'transport'
          },
          {
            id: 'rec-3',
            title: t('Система мониторинга качества воздуха'),
            description: t(
              'Установка датчиков и аналитической платформы для контроля качества воздуха в реальном времени'
            ),
            potentialImpact: 75,
            estimatedCost: 2100000,
            category: 'air_quality'
          }
        ]

        return { initiatives: mockInitiatives, recommendations: mockRecommendations }
      } catch (err) {
        console.error('Error loading funding data:', err)
        throw new Error(t('Не удалось загрузить данные'))
      }
    },
    {
      initialValue: { initiatives: [], recommendations: [] }
    }
  )

  // Вспомогательные функции для анализа эффективности
  const calculateEfficiencyScore = (initiative: EcoInitiative): number => {
    // Простая формула расчета эффективности
    return Math.min(100, initiative.impactScore * 0.4 + initiative.roi * 0.6)
  }

  const getEfficiencyAnalysis = (initiative: EcoInitiative): string => {
    const score = calculateEfficiencyScore(initiative)

    if (score >= 80) {
      return t(
        'Высокоэффективный проект с отличным балансом экологического воздействия и финансовой отдачи. Рекомендуется к расширению.'
      )
    } else if (score >= 60) {
      return t(
        'Хороший проект с потенциалом для улучшения. Рассмотрите возможность оптимизации затрат или увеличения экологического эффекта.'
      )
    } else if (score >= 40) {
      return t(
        'Проект требует внимания. Низкая рентабельность или ограниченное экологическое воздействие. Рекомендуется пересмотреть стратегию.'
      )
    } else {
      return t(
        'Низкоэффективный проект. Требуется серьезный анализ и возможная приостановка или реструктуризация.'
      )
    }
  }

  // Вычисление общей эффективности
  const getTotalImpact = () => {
    const initiatives = fundingData()?.initiatives || []
    return initiatives.reduce((sum: number, init: EcoInitiative) => sum + init.impactScore, 0)
  }

  const getTotalInvestment = () => {
    const initiatives = fundingData()?.initiatives || []
    return initiatives.reduce((sum: number, init: EcoInitiative) => sum + init.investment, 0)
  }

  const getAverageROI = () => {
    const initiatives = fundingData()?.initiatives || []
    const activeInitiatives = initiatives.filter((init: EcoInitiative) => init.status === 'active')
    if (activeInitiatives.length === 0) return 0
    return (
      activeInitiatives.reduce((sum: number, init: EcoInitiative) => sum + init.roi, 0) /
      activeInitiatives.length
    )
  }

  // Форматирование чисел
  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0
    }).format(value)
  }

  return (
    <div class={styles.fundingPage}>
      <div class={styles.header}>
        <h1 class={styles.title}>{t('Самоорганизация экологических инициатив')}</h1>
        <p class={styles.subtitle}>{t('Помощь и мониторинг проектов с оценкой эффективности')}</p>
      </div>

      {fundingData.loading ? (
        <div class={styles.loading}>
          <div class={styles.spinner} />
          <p>{t('Загрузка данных...')}</p>
        </div>
      ) : fundingData.error ? (
        <div class={styles.error}>
          <p class={styles.errorMessage}>{fundingData.error.message}</p>
          <button
            class={styles.retryButton}
            onClick={() => {
              // Refetch data
              setRefetchTrigger((prev) => prev + 1)
            }}
          >
            {t('Повторить попытку')}
          </button>
        </div>
      ) : (
        <div class={styles.content}>
          {/* Общая статистика */}
          <section class={styles.statsSection}>
            <h2 class={styles.sectionTitle}>{t('Общая эффективность')}</h2>
            <div class={styles.statsGrid}>
              <div class={styles.statCard}>
                <div class={styles.statValue}>{getTotalImpact()}</div>
                <div class={styles.statLabel}>{t('Суммарный экологический эффект')}</div>
              </div>
              <div class={styles.statCard}>
                <div class={styles.statValue}>{formatCurrency(getTotalInvestment())}</div>
                <div class={styles.statLabel}>{t('Общий объем инвестиций')}</div>
              </div>
              <div class={styles.statCard}>
                <div class={styles.statValue}>{getAverageROI().toFixed(1)}%</div>
                <div class={styles.statLabel}>{t('Средняя рентабельность')}</div>
              </div>
              <div class={styles.statCard}>
                <div class={styles.statValue}>
                  {
                    (fundingData()?.initiatives || []).filter(
                      (init: EcoInitiative) => init.status === 'active'
                    ).length
                  }
                </div>
                <div class={styles.statLabel}>{t('Активные инициативы')}</div>
              </div>
            </div>
          </section>

          {/* Мониторинг инициатив */}
          <section class={styles.initiativesSection}>
            <h2 class={styles.sectionTitle}>{t('Мониторинг экологических инициатив')}</h2>
            <div class={styles.initiativesGrid}>
              {(fundingData()?.initiatives || []).map((initiative: EcoInitiative) => (
                <div
                  class={`${styles.initiativeCard} ${selectedInitiative()?.id === initiative.id ? styles.selected : ''}`}
                  onClick={() => setSelectedInitiative(initiative)}
                >
                  <div class={styles.initiativeHeader}>
                    <h3 class={styles.initiativeName}>{initiative.name}</h3>
                    <span class={`${styles.statusBadge} ${styles[`status_${initiative.status}`]}`}>
                      {t(
                        initiative.status === 'active'
                          ? 'Активно'
                          : initiative.status === 'completed'
                            ? 'Завершено'
                            : 'Планируется'
                      )}
                    </span>
                  </div>
                  <p class={styles.initiativeDescription}>{initiative.description}</p>
                  <div class={styles.initiativeMetrics}>
                    <div class={styles.metric}>
                      <span class={styles.metricLabel}>{t('Эффект')}</span>
                      <span class={styles.metricValue}>{initiative.impactScore}</span>
                    </div>
                    <div class={styles.metric}>
                      <span class={styles.metricLabel}>{t('ROI')}</span>
                      <span class={styles.metricValue}>{initiative.roi}%</span>
                    </div>
                    <div class={styles.metric}>
                      <span class={styles.metricLabel}>{t('Инвестиции')}</span>
                      <span class={styles.metricValue}>{formatCurrency(initiative.investment)}</span>
                    </div>
                  </div>
                  <div class={styles.categoryTag}>
                    {t(
                      initiative.category === 'renewable_energy'
                        ? 'Возобновляемая энергия'
                        : initiative.category === 'waste_management'
                          ? 'Управление отходами'
                          : initiative.category === 'urban_greening'
                            ? 'Озеленение'
                            : 'Сохранение воды'
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Рекомендации */}
          <section class={styles.recommendationsSection}>
            <h2 class={styles.sectionTitle}>{t('Рекомендации по улучшению')}</h2>
            <div class={styles.recommendationsGrid}>
              {(fundingData()?.recommendations || []).map((recommendation: Recommendation) => (
                <div class={styles.recommendationCard}>
                  <h3 class={styles.recommendationTitle}>{recommendation.title}</h3>
                  <p class={styles.recommendationDescription}>{recommendation.description}</p>
                  <div class={styles.recommendationMetrics}>
                    <div class={styles.recommendationMetric}>
                      <span class={styles.recommendationLabel}>{t('Потенциальный эффект')}</span>
                      <span class={styles.recommendationValue}>{recommendation.potentialImpact}</span>
                    </div>
                    <div class={styles.recommendationMetric}>
                      <span class={styles.recommendationLabel}>{t('Оценка стоимости')}</span>
                      <span class={styles.recommendationValue}>
                        {formatCurrency(recommendation.estimatedCost)}
                      </span>
                    </div>
                  </div>
                  <A href="/knowledge" class={styles.learnMoreButton}>
                    {t('Подробнее')}
                  </A>
                </div>
              ))}
            </div>
          </section>

          {/* Оценка эффективности */}
          {selectedInitiative() && (
            <section class={styles.efficiencySection}>
              <h2 class={styles.sectionTitle}>{t('Оценка эффективности проекта')}</h2>
              <div class={styles.efficiencyContent}>
                <div class={styles.efficiencyHeader}>
                  <h3 class={styles.selectedInitiativeName}>{selectedInitiative()!.name}</h3>
                  <div class={styles.efficiencyScore}>
                    {t('Эффективность:')} {calculateEfficiencyScore(selectedInitiative()!)}%
                  </div>
                </div>

                <div class={styles.efficiencyDetails}>
                  <div class={styles.efficiencyChart}>
                    <div class={styles.chartLabel}>{t('Финансовые показатели')}</div>
                    <div class={styles.chartBars}>
                      <div class={styles.chartBar}>
                        <div class={styles.barLabel}>{t('Инвестиции')}</div>
                        <div
                          class={styles.barValue}
                          style={{
                            width: `${Math.min((selectedInitiative()!.investment / 20000000) * 100, 100)}%`
                          }}
                        >
                          {formatCurrency(selectedInitiative()!.investment)}
                        </div>
                      </div>
                      <div class={styles.chartBar}>
                        <div class={styles.barLabel}>{t('ROI')}</div>
                        <div
                          class={styles.barValue}
                          style={{ width: `${Math.min(selectedInitiative()!.roi, 100)}%` }}
                        >
                          {selectedInitiative()!.roi}%
                        </div>
                      </div>
                      <div class={styles.chartBar}>
                        <div class={styles.barLabel}>{t('Экологический эффект')}</div>
                        <div
                          class={styles.barValue}
                          style={{ width: `${Math.min(selectedInitiative()!.impactScore, 100)}%` }}
                        >
                          {selectedInitiative()!.impactScore}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class={styles.efficiencyAnalysis}>
                    <h4>{t('Анализ эффективности')}</h4>
                    <p>{getEfficiencyAnalysis(selectedInitiative()!)}</p>
                  </div>
                </div>
              </div>
            </section>
          )}
        </div>
      )}
    </div>
  )
}

export default ProjectsPage
