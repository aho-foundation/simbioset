import { Component, createResource, createSignal, For, Show } from 'solid-js'
import { useSession } from '~/contexts/SessionContext'
import styles from './ArtifactsPanel.module.css'

interface ArtifactsPanelProps {
  onClose: () => void
  onCreateProject: () => void
}

export const ArtifactsPanel: Component<ArtifactsPanelProps> = (props) => {
  const { sessionId } = useSession()
  const artifacts = useArtifacts()
  const [showCreateDialog, setShowCreateDialog] = createSignal(false)
  const [projectTitle, setProjectTitle] = createSignal('')
  const [projectDescription, setProjectDescription] = createSignal('')
  const [isCreating, setIsCreating] = createSignal(false)

  // Загружаем артефакты из API (если нужно синхронизировать)
  const [_apiArtifacts] = createResource(sessionId, async (sid) => {
    if (!sid) return []
    try {
      const response = await fetch(`/api/artifacts?session_id=${sid}`)
      if (response.ok) {
        const data = await response.json()
        return data
      }
    } catch (error) {
      console.error('Failed to load artifacts from API:', error)
    }
    return []
  })

  const handleRemoveArtifact = async (artifactId: string) => {
    try {
      const response = await fetch(`/api/artifacts/${artifactId}?session_id=${sessionId()}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        artifacts.removeArtifact(artifactId)
      }
    } catch (error) {
      console.error('Failed to remove artifact:', error)
    }
  }

  const handleAcceptSuggestion = async (artifactId: string) => {
    try {
      const response = await fetch(`/api/artifacts/suggestions/${artifactId}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId() })
      })
      if (response.ok) {
        artifacts.refetch() // Обновляем список артефактов
      }
    } catch (error) {
      console.error('Failed to accept suggestion:', error)
    }
  }

  const handleRejectSuggestion = async (artifactId: string) => {
    try {
      const response = await fetch(`/api/artifacts/suggestions/${artifactId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId() })
      })
      if (response.ok) {
        artifacts.refetch() // Обновляем список артефактов
      }
    } catch (error) {
      console.error('Failed to reject suggestion:', error)
    }
  }

  const handleCreateProject = async () => {
    if (!projectTitle().trim() || !projectDescription().trim()) return

    setIsCreating(true)
    try {
      const artifactsList = artifacts.artifacts()
      if (artifactsList.length === 0) {
        alert('Нет артефактов для создания проекта')
        return
      }

      const response = await fetch('/api/projects/from-artifacts', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          session_id: sessionId(),
          title: projectTitle(),
          description: projectDescription(),
          artifacts: artifactsList.map((a) => ({
            id: a.id,
            content: a.content,
            selected_text: a.selectedText,
            type: a.type,
            timestamp: a.timestamp.toISOString()
          })),
          knowledge_base_id: `chat-session-${sessionId()}`,
          tags: ['chat-artifacts', 'generated']
        })
      })

      if (response.ok) {
        const project = await response.json()
        alert(`Проект "${project.title}" создан успешно!`)
        setShowCreateDialog(false)
        setProjectTitle('')
        setProjectDescription('')
        // Очищаем артефакты после создания проекта
        artifacts.clearArtifacts()
        props.onCreateProject()
      } else {
        const error = await response.json()
        alert(`Ошибка создания проекта: ${error.detail?.message || 'Неизвестная ошибка'}`)
      }
    } catch (error) {
      console.error('Failed to create project:', error)
      alert('Ошибка создания проекта')
    } finally {
      setIsCreating(false)
    }
  }

  const currentArtifacts = () => artifacts.artifacts()

  return (
    <div class={styles.overlay} onClick={props.onClose}>
      <div class={styles.panel} onClick={(e) => e.stopPropagation()}>
        <div class={styles.header}>
          <h3>Артефакты беседы ({currentArtifacts().length})</h3>
          <button class={styles.closeButton} onClick={props.onClose}>
            ×
          </button>
        </div>

        <div class={styles.content}>
          <Show
            when={currentArtifacts().length > 0}
            fallback={
              <div class={styles.empty}>
                <p>Нет отмеченных артефактов</p>
                <p class={styles.hint}>
                  Выделите текст в сообщениях и нажмите на иконку звезды для маркировки артефакта
                </p>
              </div>
            }
          >
            <div class={styles.artifactsList}>
              <For each={currentArtifacts()}>
                {(artifact) => (
                  <div class={styles.artifact}>
                    <div class={styles.artifactHeader}>
                      <span class={styles.artifactType}>
                        {artifact.suggested && '⭐ '}
                        {artifact.type}
                        {artifact.suggested && (
                          <small style="color: #2563eb; margin-left: 4px;">
                            ({Math.round(artifact.confidence * 100)}%)
                          </small>
                        )}
                      </span>
                      {artifact.suggested ? (
                        <div style="display: flex; gap: 4px;">
                          <button
                            class={styles.confirmButton}
                            onClick={() => handleAcceptSuggestion(artifact.id)}
                            title="Принять предложение"
                            style="font-size: 12px; padding: 2px 6px;"
                          >
                            ✓
                          </button>
                          <button
                            class={styles.removeButton}
                            onClick={() => handleRejectSuggestion(artifact.id)}
                            title="Отклонить предложение"
                            style="font-size: 12px; padding: 2px 6px;"
                          >
                            ×
                          </button>
                        </div>
                      ) : (
                      <button
                        class={styles.removeButton}
                        onClick={() => handleRemoveArtifact(artifact.id)}
                        title="Удалить артефакт"
                      >
                        ×
                      </button>
                      )}
                    </div>
                    <div class={styles.artifactContent}>
                      <p>{artifact.content}</p>
                    </div>
                    <div class={styles.artifactMeta}>
                      <small>
                        {artifact.timestamp.toLocaleString('ru-RU')}
                        {artifact.suggested && ' • Предложено автоматически'}
                      </small>
                    </div>
                  </div>
                )}
              </For>
            </div>

            <div class={styles.actions}>
              <button
                class={styles.createButton}
                onClick={() => setShowCreateDialog(true)}
                disabled={currentArtifacts().length === 0}
              >
                Создать проект
              </button>
              <button
                class={styles.clearButton}
                onClick={() => artifacts.clearArtifacts()}
                disabled={currentArtifacts().length === 0}
              >
                Очистить все
              </button>
            </div>
          </Show>
        </div>

        {/* Диалог создания проекта */}
        <Show when={showCreateDialog()}>
          <div class={styles.dialogOverlay} onClick={() => setShowCreateDialog(false)}>
            <div class={styles.dialog} onClick={(e) => e.stopPropagation()}>
              <h4>Создать проект из артефактов</h4>

              <div class={styles.formGroup}>
                <label for="project-title">Название проекта</label>
                <input
                  id="project-title"
                  type="text"
                  value={projectTitle()}
                  onInput={(e) => setProjectTitle(e.target.value)}
                  placeholder="Введите название проекта"
                  required
                />
              </div>

              <div class={styles.formGroup}>
                <label for="project-description">Описание проекта</label>
                <textarea
                  id="project-description"
                  value={projectDescription()}
                  onInput={(e) => setProjectDescription(e.target.value)}
                  placeholder="Опишите проект"
                  rows="4"
                  required
                />
              </div>

              <div class={styles.dialogActions}>
                <button class={styles.cancelButton} onClick={() => setShowCreateDialog(false)}>
                  Отмена
                </button>
                <button
                  class={styles.confirmButton}
                  onClick={handleCreateProject}
                  disabled={isCreating() || !projectTitle().trim() || !projectDescription().trim()}
                >
                  {isCreating() ? 'Создание...' : 'Создать проект'}
                </button>
              </div>
            </div>
          </div>
        </Show>
      </div>
    </div>
  )
}
