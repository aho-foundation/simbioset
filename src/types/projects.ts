// TypeScript типы для проектов из артефактов

export type ProjectStatus = 'draft' | 'active' | 'completed' | 'archived' | 'failed'

export interface Contributor {
  user_id: string
  name: string
  role: string
  contribution_date: string
  contributions: string[]
}

export interface Backer {
  user_id: string
  name: string
  amount: number
  backing_date: string
  tier_id?: string
  public: boolean
}

export interface FundingTier {
  id: string
  title: string
  description: string
  amount: number
  rewards: string[]
  limit?: number
}

export interface Idea {
  id: string
  project_id: string
  author_id: string
  content: string
  submission_date: string
  votes: number
  status: 'submitted' | 'reviewed' | 'approved' | 'rejected' | 'implemented'
}

export interface BaseProject {
  id: string
  title: string
  description: string
  status: ProjectStatus
  creation_date: string
  update_date: string
  knowledge_base_id: string
  tags: string[]
}

export interface CrowdsourcedProject extends BaseProject {
  ideas: Idea[]
  contributors: Contributor[]
}

export interface CrowdfundedProject extends BaseProject {
  funding_goal: number
  current_funding: number
  start_date: string
  end_date: string
  backers: Backer[]
  funding_tiers: FundingTier[]
}

export type Project = CrowdsourcedProject | CrowdfundedProject

// Утилиты для определения типа проекта
export function isCrowdsourcedProject(project: Project): project is CrowdsourcedProject {
  return 'ideas' in project
}

export function isCrowdfundedProject(project: Project): project is CrowdfundedProject {
  return 'funding_goal' in project
}

// API response types
export interface ProjectsResponse {
  projects: Project[]
  total: number
  offset: number
  limit: number
}

export interface ProjectStats {
  total_projects: number
  active_projects: number
  completed_projects: number
  total_funding: number
  average_funding: number
  backers_count: number
}
