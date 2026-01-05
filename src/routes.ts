import type { RouteDefinition } from '@solidjs/router'
import { lazy } from 'solid-js'
import NotFound from './errors/404'
import Home from './pages/HomePage'
import InterviewPage from './pages/InterviewPage'
import ProjectsPage from './pages/ProjectsPage'

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
    path: '/projects',
    component: ProjectsPage
  },
  {
    path: '/knowledge',
    component: lazy(() => import('./pages/KnowledgeTreePage'))
  },
  {
    path: '/schema',
    component: lazy(() => import('./pages/ClassificationPage'))
  },
  {
    path: '**',
    component: NotFound
  }
]
