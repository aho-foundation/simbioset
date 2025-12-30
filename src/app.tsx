import { JSX, Suspense } from 'solid-js'
import MainLayout from './components/layout/MainLayout'
import { KnowledgeBaseProvider } from './contexts/KnowledgeBaseContext'
import { SessionProvider } from './contexts/SessionContext'
import { I18nProvider } from './i18n'

import '~/styles/globals.css'

const App = (props: { children: JSX.Element }) => {
  return (
    <I18nProvider>
      <SessionProvider>
        <KnowledgeBaseProvider>
          <MainLayout>
            <Suspense>{props.children}</Suspense>
          </MainLayout>
        </KnowledgeBaseProvider>
      </SessionProvider>
    </I18nProvider>
  )
}

export default App
