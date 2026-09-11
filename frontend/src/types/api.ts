// Mirrors backend Pydantic schemas exactly. Keep in sync with:
// backend/app/schemas/{auth,user,course,doubt,quiz}.py

export interface UserRead {
  id: number
  email: string
  full_name: string
  is_active: boolean
  onboarding_completed: boolean
  learning_goal: string | null
  experience_level: string | null
  preferred_pace: string | null
  topics_of_interest: string[] | null
}

export interface Token {
  access_token: string
  token_type: string
}

export interface OnboardingUpdate {
  learning_goal?: string | null
  experience_level?: string | null
  preferred_pace?: string | null
  topics_of_interest?: string[] | null
  onboarding_completed?: boolean | null
}

export type ModuleStatus = 'pending' | 'generating' | 'completed' | 'failed'

export interface ModuleSummary {
  id: number
  order_index: number
  title: string
  summary: string | null
  status: ModuleStatus
}

export interface ModuleDetail extends ModuleSummary {
  content: string | null
}

export interface CourseRead {
  id: number
  title: string
  description: string | null
  status: string
  current_difficulty: string
  created_at: string
  modules: ModuleSummary[]
}

export interface CourseDetail extends CourseRead {
  modules: ModuleDetail[]
}

export interface CourseCreate {
  topic?: string | null
  num_modules?: number
}

export interface DoubtCreate {
  module_id: number
  question: string
}

export interface QuizQuestionPublic {
  question: string
  options: string[]
}

export interface QuizRead {
  id: number
  module_id: number
  difficulty: string
  created_at: string
  questions: QuizQuestionPublic[]
}

export interface QuizAttemptCreate {
  answers: number[]
}

export interface QuizQuestionResult {
  question: string
  options: string[]
  correct_index: number
  explanation: string
  selected_index: number | null
  is_correct: boolean
}

export interface QuizAttemptRead {
  id: number
  quiz_id: number
  score: number
  difficulty_at_attempt: string
  new_difficulty: string
  results: QuizQuestionResult[]
}

export interface ModuleScoreStat {
  module_id: number
  module_title: string
  attempts_count: number
  average_score: number
}

export interface ScoreTrendPoint {
  attempt_id: number
  module_id: number
  score: number
  created_at: string
}

export interface AnalyticsSummary {
  modules_completed: number
  modules_total: number
  average_score_by_module: ModuleScoreStat[]
  score_trend: ScoreTrendPoint[]
}
