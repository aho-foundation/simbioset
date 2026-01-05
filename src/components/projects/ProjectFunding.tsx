import { Component, createSignal } from 'solid-js'
import type { Backer, CrowdfundedProject, FundingTier } from '~/types/projects'
import styles from './ProjectFunding.module.css'

interface ProjectFundingProps {
  project: CrowdfundedProject
  onBack: (amount: Backer) => Promise<void>
  onRefresh: () => void
}

interface BackingModalProps {
  project: CrowdfundedProject
  isOpen: boolean
  onClose: () => void
  onConfirm: (tierId: string, amount: number, isPublic: boolean) => Promise<void>
}

const BackingModal: Component<BackingModalProps> = (props) => {
  const [selectedTier, setSelectedTier] = createSignal<string | null>(null)
  const [customAmount, setCustomAmount] = createSignal<number>(0)
  const [isPublic, setIsPublic] = createSignal(true)
  const [isSubmitting, setIsSubmitting] = createSignal(false)

  const selectedTierData = () => {
    if (!selectedTier()) return null
    return props.project.funding_tiers.find((tier) => tier.id === selectedTier())
  }

  const totalAmount = () => {
    if (selectedTier() === 'custom') {
      return customAmount()
    }
    const tier = selectedTierData()
    return tier ? tier.amount : 0
  }

  const handleSubmit = async () => {
    if (!totalAmount() || totalAmount() < 1) return

    setIsSubmitting(true)
    try {
      const tierId = selectedTier() === 'custom' ? undefined : selectedTier()
      await props.onConfirm(tierId || '', totalAmount(), isPublic())
      props.onClose()
    } catch (error) {
      console.error('Failed to back project:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('ru-RU', {
      style: 'currency',
      currency: 'RUB',
      maximumFractionDigits: 0
    }).format(amount)
  }

  if (!props.isOpen) return null

  return (
    <div class={styles.modalOverlay} onClick={props.onClose}>
      <div class={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div class={styles.modalHeader}>
          <h3>Поддержать проект</h3>
          <button class={styles.closeButton} onClick={props.onClose}>
            ×
          </button>
        </div>

        <div class={styles.modalBody}>
          <div class={styles.projectSummary}>
            <h4>{props.project.title}</h4>
            <p>{props.project.description}</p>
          </div>

          <div class={styles.tiersSection}>
            <h4>Выберите уровень поддержки</h4>
            <div class={styles.tiersList}>
              <For each={props.project.funding_tiers}>
                {(tier) => {
                  const isSelected = selectedTier() === tier.id
                  const isFull =
                    tier.limit &&
                    props.project.backers.filter((b) => b.tier_id === tier.id).length >= tier.limit

                  return (
                    <div
                      class={`${styles.tierCard} ${isSelected ? styles.selected : ''} ${isFull ? styles.full : ''}`}
                      onClick={() => !isFull && setSelectedTier(tier.id)}
                    >
                      <div class={styles.tierHeader}>
                        <h5>{tier.title}</h5>
                        <span class={styles.tierAmount}>{formatCurrency(tier.amount)}</span>
                      </div>
                      <p class={styles.tierDescription}>{tier.description}</p>
                      <Show when={tier.rewards.length > 0}>
                        <div class={styles.tierRewards}>
                          <h6>Вознаграждения:</h6>
                          <ul>
                            <For each={tier.rewards}>{(reward) => <li>{reward}</li>}</For>
                          </ul>
                        </div>
                      </Show>
                      <Show when={tier.limit}>
                        <div class={styles.tierLimit}>
                          Осталось:{' '}
                          {tier.limit! - props.project.backers.filter((b) => b.tier_id === tier.id).length}{' '}
                          из {tier.limit}
                        </div>
                      </Show>
                      <Show when={isFull}>
                        <div class={styles.tierFull}>Уровень заполнен</div>
                      </Show>
                    </div>
                  )
                }}
              </For>

              <div
                class={`${styles.tierCard} ${selectedTier() === 'custom' ? styles.selected : ''}`}
                onClick={() => setSelectedTier('custom')}
              >
                <div class={styles.tierHeader}>
                  <h5>Произвольная сумма</h5>
                </div>
                <p class={styles.tierDescription}>Поддержите проект любой суммой</p>
                <Show when={selectedTier() === 'custom'}>
                  <input
                    type="number"
                    class={styles.customAmountInput}
                    placeholder="Введите сумму"
                    value={customAmount()}
                    onInput={(e) => setCustomAmount(Number.parseInt(e.currentTarget.value, 10) || 0)}
                    min="1"
                  />
                </Show>
              </div>
            </div>
          </div>

          <div class={styles.backingOptions}>
            <label class={styles.checkboxLabel}>
              <input
                type="checkbox"
                checked={isPublic()}
                onChange={(e) => setIsPublic(e.currentTarget.checked)}
              />
              Показывать мою поддержку публично
            </label>
          </div>

          <div class={styles.backingSummary}>
            <div class={styles.summaryRow}>
              <span>Итого к оплате:</span>
              <span class={styles.totalAmount}>
                {totalAmount() > 0 ? formatCurrency(totalAmount()) : 'Выберите уровень'}
              </span>
            </div>
          </div>
        </div>

        <div class={styles.modalFooter}>
          <button class={styles.cancelButton} onClick={props.onClose}>
            Отмена
          </button>
          <button
            class={styles.confirmButton}
            onClick={handleSubmit}
            disabled={!totalAmount() || totalAmount() < 1 || isSubmitting()}
          >
            <Show when={isSubmitting()} fallback="Поддержать проект">
              Обрабатывается...
            </Show>
          </button>
        </div>
      </div>
    </div>
  )
}

export const ProjectFunding: Component<ProjectFundingProps> = (props) => {
  const [showBackingModal, setShowBackingModal] = createSignal(false)
  const [_selectedTier, _setSelectedTier] = createSignal<FundingTier | null>(null)

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

  const handleBacking = async (tierId: string, amount: number, isPublic: boolean) => {
    // Создаем объект backer
    const backer: Backer = {
      user_id: 'anonymous', // В реальном приложении брать из авторизации
      name: 'Анонимный спонсор', // В реальном приложении брать из профиля
      amount: amount,
      backing_date: new Date().toISOString(),
      tier_id: tierId || undefined,
      public: isPublic
    }

    await props.onBack(backer)
    props.onRefresh()
  }

  const recentBackers = () => {
    return props.project.backers
      .filter((backer) => backer.public)
      .sort((a, b) => new Date(b.backing_date).getTime() - new Date(a.backing_date).getTime())
      .slice(0, 5)
  }

  return (
    <div class={styles.fundingContainer}>
      <div class={styles.fundingHeader}>
        <h2>Краудфандинг</h2>
        <button
          class={styles.supportProjectButton}
          onClick={() => setShowBackingModal(true)}
          disabled={props.project.status !== 'active'}
        >
          Поддержать проект
        </button>
      </div>

      <div class={styles.fundingOverview}>
        <div class={styles.fundingProgress}>
          <div class={styles.progressStats}>
            <div class={styles.progressAmount}>
              <span class={styles.currentAmount}>{formatCurrency(props.project.current_funding)}</span>
              <span class={styles.goalAmount}>из {formatCurrency(props.project.funding_goal)}</span>
            </div>
            <div class={styles.progressPercentage}>{progressPercentage().toFixed(0)}%</div>
          </div>

          <div class={styles.progressBar}>
            <div class={styles.progressFill} style={{ width: `${progressPercentage()}%` }} />
          </div>

          <div class={styles.fundingMeta}>
            <span class={styles.backersCount}>{props.project.backers.length} спонсоров</span>
            <span class={styles.timeLeft}>
              {daysLeft() === 0 ? 'Завершено' : `${daysLeft()} дней осталось`}
            </span>
          </div>
        </div>
      </div>

      <Show when={props.project.funding_tiers.length > 0}>
        <div class={styles.fundingTiers}>
          <h3>Уровни поддержки</h3>
          <div class={styles.tiersGrid}>
            <For each={props.project.funding_tiers}>
              {(tier) => {
                const backersCount = props.project.backers.filter((b) => b.tier_id === tier.id).length
                const isFull = tier.limit && backersCount >= tier.limit

                return (
                  <div class={`${styles.tierPreview} ${isFull ? styles.tierFull : ''}`}>
                    <div class={styles.tierPreviewHeader}>
                      <h4>{tier.title}</h4>
                      <span class={styles.tierPreviewAmount}>{formatCurrency(tier.amount)}</span>
                    </div>
                    <p class={styles.tierPreviewDescription}>{tier.description}</p>
                    <Show when={tier.rewards.length > 0}>
                      <div class={styles.tierPreviewRewards}>
                        <For each={tier.rewards.slice(0, 2)}>
                          {(reward) => <span class={styles.rewardTag}>{reward}</span>}
                        </For>
                        <Show when={tier.rewards.length > 2}>
                          <span class={styles.rewardTag}>+{tier.rewards.length - 2}</span>
                        </Show>
                      </div>
                    </Show>
                    <Show when={tier.limit}>
                      <div class={styles.tierBackers}>
                        {backersCount} из {tier.limit}
                      </div>
                    </Show>
                  </div>
                )
              }}
            </For>
          </div>
        </div>
      </Show>

      <Show when={recentBackers().length > 0}>
        <div class={styles.recentBackers}>
          <h3>Недавние спонсоры</h3>
          <div class={styles.backersList}>
            <For each={recentBackers()}>
              {(backer) => (
                <div class={styles.backerItem}>
                  <span class={styles.backerName}>{backer.name}</span>
                  <span class={styles.backerAmount}>{formatCurrency(backer.amount)}</span>
                  <span class={styles.backerDate}>
                    {new Date(backer.backing_date).toLocaleDateString('ru-RU')}
                  </span>
                </div>
              )}
            </For>
          </div>
        </div>
      </Show>

      <BackingModal
        project={props.project}
        isOpen={showBackingModal()}
        onClose={() => setShowBackingModal(false)}
        onConfirm={handleBacking}
      />
    </div>
  )
}
