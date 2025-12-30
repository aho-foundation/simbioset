import { createContext, createSignal, JSX, onMount, useContext } from 'solid-js'
import { isServer } from 'solid-js/web'

interface SessionContextValue {
  sessionId: () => string | undefined
  loadSession: () => Promise<void>
  refreshSession: () => Promise<void>
  setSessionId: (s: string) => Promise<void>
}

const SessionContext = createContext<SessionContextValue>()

export const SessionProvider = (props: { children: JSX.Element }) => {
  const [sessionId, setSessionId] = createSignal<string>()

  const loadSession = async () => {
    if (!isServer) {
      try {
        // Get current session ID from server (from httpOnly cookie)
        const res = await fetch('/api/chat/session/current', {
          credentials: 'include'
        })
        if (res.ok) {
          const data = await res.json()
          setSessionId(data.sessionId)
        }
      } catch (error) {
        console.error('Failed to load session:', error)
      }
    }
  }

  const refreshSession = async () => {
    await loadSession()
  }

  const value: SessionContextValue = {
    sessionId,
    loadSession,
    refreshSession,
    setSessionId
  }

  // Load session on mount
  onMount(() => {
    void loadSession()
  })

  return <SessionContext.Provider value={value}>{props.children}</SessionContext.Provider>
}

export const useSession = () => {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error('useSession must be used within SessionProvider')
  }
  return context
}
