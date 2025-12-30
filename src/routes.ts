import type { RouteDefinition } from '@solidjs/router'
import { lazy } from 'solid-js'
import NotFound from './errors/404'
import FundingPage from './pages/FundingPage'
import Home from './pages/HomePage'
import InterviewPage from './pages/InterviewPage'

export const routes: RouteDefinition[] = [
  {
    path: '/',
    component: Home
  },
  {
    path: '/sources',
    component: InterviewPage
  },
  {
    path: '/funds',
    component: FundingPage
  },
  {
    path: '/knowledge',
    component: lazy(() => import('./pages/KnowledgeTreePage'))
  },
  {
    path: '/classification',
    component: lazy(() => import('./pages/ClassificationPage'))
  },
  {
    path: '**',
    component: NotFound
  }
]
