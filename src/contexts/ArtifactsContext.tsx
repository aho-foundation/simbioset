import { createContext, createEffect, createSignal, JSX, useContext } from 'solid-js'

export interface Artifact {
  id: string
  messageId: string | number
  content: string
  selectedText: string
  timestamp: Date
  type?: 'idea' | 'requirement' | 'note' | 'insight'
  suggested?: boolean
}

interface SerializedArtifact {
  id: string
  messageId: string | number
  content: string
  selectedText: string
  timestamp: string
  type?: 'idea' | 'requirement' | 'note' | 'insight'
}

interface ArtifactsContextValue {
  artifacts: () => Artifact[]
  addArtifact: (
    messageId: string | number,
    selectedText: string,
    content?: string,
    type?: Artifact['type']
  ) => void
  removeArtifact: (artifactId: string) => void
  clearArtifacts: () => void
  getArtifactsByMessage: (messageId: string | number) => Artifact[]
}

const ArtifactsContext = createContext<ArtifactsContextValue>()

export const useArtifacts = () => {
  const context = useContext(ArtifactsContext)
  if (!context) {
    throw new Error('useArtifacts must be used within an ArtifactsProvider')
  }
  return context
}

interface ArtifactsProviderProps {
  children: JSX.Element
}

export const ArtifactsProvider = (props: ArtifactsProviderProps) => {
  const [artifacts, setArtifacts] = createSignal<Artifact[]>([])

  // Загружаем артефакты из localStorage при инициализации
  createEffect(() => {
    try {
      const saved = localStorage.getItem('chat_artifacts')
      if (saved) {
        const parsed = JSON.parse(saved)
        // Преобразуем timestamp обратно в Date
        const artifactsWithDates = parsed.map((artifact: SerializedArtifact) => ({
          ...artifact,
          timestamp: new Date(artifact.timestamp)
        }))
        setArtifacts(artifactsWithDates)
      }
    } catch (error) {
      console.error('Failed to load artifacts from localStorage:', error)
    }
  })

  // Сохраняем артефакты в localStorage при изменении
  createEffect(() => {
    try {
      localStorage.setItem('chat_artifacts', JSON.stringify(artifacts()))
    } catch (error) {
      console.error('Failed to save artifacts to localStorage:', error)
    }
  })

  const addArtifact = (
    messageId: string | number,
    selectedText: string,
    content?: string,
    type: Artifact['type'] = 'note'
  ) => {
    const newArtifact: Artifact = {
      id: `artifact_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      messageId,
      content: content || selectedText,
      selectedText,
      timestamp: new Date(),
      type
    }

    setArtifacts((prev) => [...prev, newArtifact])
  }

  const removeArtifact = (artifactId: string) => {
    setArtifacts((prev) => prev.filter((artifact) => artifact.id !== artifactId))
  }

  const clearArtifacts = () => {
    setArtifacts([])
  }

  const getArtifactsByMessage = (messageId: string | number) => {
    return artifacts().filter((artifact) => artifact.messageId === messageId)
  }

  const value: ArtifactsContextValue = {
    artifacts,
    addArtifact,
    removeArtifact,
    clearArtifacts,
    getArtifactsByMessage
  }

  return <ArtifactsContext.Provider value={value}>{props.children}</ArtifactsContext.Provider>
}
