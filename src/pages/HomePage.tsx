import { A } from '@solidjs/router'
import { Component } from 'solid-js'
import ParagraphSearch from '~/components/ParagraphSearch'
import { useI18n } from '~/i18n'

import styles from '~/styles/home.module.css'

const Home: Component = () => {
  const { t } = useI18n()

  return (
    <div class={styles.container}>
      {/* Hero Section */}
      <section class={styles.hero}>
        <div class={styles.heroContent}>
          <h1 class={styles.heroTitle}>{t('Симбиосеть')}</h1>
          <p class={styles.heroTagline}>{t('Планетарный стетоскоп')}</p>
          <p class={styles.heroSubtitle}>{t('Улучшаем качества биосферы с помощью Big Data и AI')}</p>
          <div class={styles.ctaButtons}>
            <A href="/sources" class={styles.ctaButtonSecondary}>
              {t('Источники')}
            </A>
          </div>
        </div>
        <div class={styles.heroVisual}>
          {/* Placeholder for AI/Big Data visualization */}
          <div class={styles.dataVisualization}>
            <svg viewBox="0 0 400 300" class={styles.visualizationSvg}>
              <defs>
                <linearGradient id="dataGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" style="stop-color:#3b82f6;stop-opacity:1" />
                  <stop offset="100%" style="stop-color:#1e40af;stop-opacity:1" />
                </linearGradient>
              </defs>
              <path
                d="M50,250 Q100,200 150,220 T250,180 T350,200"
                stroke="url(#dataGradient)"
                stroke-width="3"
                fill="none"
              />
              <circle cx="150" cy="220" r="4" fill="#3b82f6" />
              <circle cx="250" cy="180" r="4" fill="#3b82f6" />
              <circle cx="350" cy="200" r="4" fill="#3b82f6" />
              <text x="200" y="280" text-anchor="middle" fill="#64748b" font-size="14">
                {t('Анализ данных в реальном времени')}
              </text>
            </svg>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section class={styles.features}>
        <div class={styles.featuresGrid}>
          <div class={styles.featureCard}>
            <div class={styles.featureIcon}>🌍</div>
            <h3 class={styles.featureTitle}>{t('Агрегация открытых данных')}</h3>
            <p class={styles.featureDescription}>
              {t('Отслеживание качества воздуха, воды и почвы с помощью IoT сенсоров и спутниковых данных')}
            </p>
          </div>
          <div class={styles.featureCard}>
            <div class={styles.featureIcon}>📊</div>
            <h3 class={styles.featureTitle}>{t('Визуализация данных')}</h3>
            <p class={styles.featureDescription}>{t('Алгоритмическиая кластеризация и выборка')}</p>
          </div>
          <div class={`${styles.featureCard} ${styles.knowledgeTreeCard}`}>
            <div class={styles.featureIcon}>🌳</div>
            <h3 class={styles.featureTitle}>{t('Дерево знаний')}</h3>
            <p class={styles.featureDescription}>
              {t(
                'Исследуйте интерактивное 3D представление концептуальных узлов и их взаимосвязей в базе знаний'
              )}
            </p>
            <A href="/knowledge" class={styles.featureLink}>
              {t('Знания')} →
            </A>
          </div>
          <div class={styles.featureCard}>
            <div class={styles.featureIcon}>🔬</div>
            <h3 class={styles.featureTitle}>{t('Анализ изображений')}</h3>
            <p class={styles.featureDescription}>
              {t(
                'Обработка изображений с микроскопа, обычных фотографий и спутниковых снимков NASA с автоматическим обнаружением организмов и экосистем'
              )}
            </p>
          </div>
          <div class={styles.featureCard}>
            <div class={styles.featureIcon}>🏷️</div>
            <h3 class={styles.featureTitle}>{t('Умная классификация')}</h3>
            <p class={styles.featureDescription}>
              {t(
                'Автоматическая классификация контента через LLM с множественными тегами для поиска симбиотических связей'
              )}
            </p>
          </div>
          <div class={styles.featureCard}>
            <div class={styles.featureIcon}>🔍</div>
            <h3 class={styles.featureTitle}>{t('Обнаружение организмов и экосистем')}</h3>
            <p class={styles.featureDescription}>
              {t(
                'Автоматическое обнаружение организмов, классификация по биологической роли и выявление экосистем с холистической моделью'
              )}
            </p>
          </div>
          <div class={styles.featureCard}>
            <div class={styles.featureIcon}>🔗</div>
            <h3 class={styles.featureTitle}>{t('Векторный поиск')}</h3>
            <p class={styles.featureDescription}>
              {t('Семантический поиск по базе знаний с фильтрацией по тегам, факт-чекингом и локализацией')}
            </p>
          </div>
          <div class={styles.featureCard}>
            <div class={styles.featureIcon}>🌐</div>
            <h3 class={styles.featureTitle}>{t('Холистическая модель')}</h3>
            <p class={styles.featureDescription}>
              {t(
                'Организм = маленькая экосистема, экосистема = большой организм. Поддержка вложенных структур и симбиотических связей'
              )}
            </p>
          </div>
        </div>
      </section>

      {/* Big Data Section */}
      <section class={styles.bigDataSection}>
        <p class={styles.sectionDescription}>
          {t(
            'Мы обрабатываем данные из спутников, датчиков, волонтёров и других открытых источников для создания комплексных аналитических моделей.'
          )}
        </p>
        <div class={styles.dataSources}>
          <div class={styles.dataSource}>
            <div class={styles.sourceIcon}>🛰️</div>
            <div class={styles.sourceInfo}>
              <div class={styles.sourceName}>{t('Спутниковые данные')}</div>
              <div class={styles.sourceValue}>12 TB/день</div>
            </div>
          </div>
          <div class={styles.dataSource}>
            <div class={styles.sourceIcon}>📡</div>
            <div class={styles.sourceInfo}>
              <div class={styles.sourceName}>{t('IoT Датчики')}</div>
              <div class={styles.sourceValue}>5M устройств</div>
            </div>
          </div>
          <div class={styles.dataSource}>
            <div class={styles.sourceIcon}>🌐</div>
            <div class={styles.sourceInfo}>
              <div class={styles.sourceName}>{t('Социальные данные')}</div>
              <div class={styles.sourceValue}>100K источников</div>
            </div>
          </div>
        </div>
      </section>

      {/* Call to Action */}
      <section class={styles.finalCta}>
        <h2 class={styles.ctaTitle}>{t('Готовы улучшить вашу экосистему?')}</h2>
        <p class={styles.ctaSubtitle}>
          {t(
            'Присоединяйтесь к нашей миссии по созданию современных и эффективных человековключающих экосистем'
          )}
        </p>
        <div class={styles.ctaButtons}>
          <A href="/sources" class={styles.ctaButtonLarge} activeClass={styles.active}>
            {t('Источники')}
          </A>
          <A href="/knowledge" class={styles.ctaButtonLarge} activeClass={styles.active}>
            {t('Знания')}
          </A>
          <A href="/funds" class={styles.ctaButtonLarge} activeClass={styles.active}>
            {t('Финансирование')}
          </A>
        </div>
      </section>
    </div>
  )
}

export default Home
