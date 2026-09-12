/*
 * Product view-models. The application maps API / course data into these; the
 * components take a view-model + callbacks and never fetch. Runtime Zod
 * contracts live in @vmsh/contracts once the API is wired.
 */

export interface CourseView {
  id: string
  code: string
  name: string
  subjectCode: string
  /** Semantic course accent; never carries status or verdict meaning. */
  accentIndex: 0 | 1 | 2 | 3 | 4
}

export interface GroupView {
  id: string
  courseId: string
  /** `groups.short_code` — «н», «п», «х», `dp2`, `i9a` и будущие значения. */
  code: string
  /** Полное название: школьник видит слово в контексте курса, не один код. */
  name: string
  /** 1–4 — категориальный цвет по `sort_order`; 0 — нейтральный/системный. */
  colorIndex: 0 | 1 | 2 | 3 | 4
}

export interface CourseEnrollmentView {
  course: CourseView
  activeGroupId: string
  allowedGroups: GroupView[]
  attendanceMode: 'online' | 'in-person'
}

export interface CourseLessonView {
  id: string
  courseId: string
  lessonNumber: number
  title?: string
}

export interface GroupLessonView {
  id: string
  courseLessonId: string
  groupId: string
  lessonNumber: number
}

/**
 * Transitional name for legacy adapters only. New product components use
 * GroupView and always carry the course context explicitly.
 */
export type LevelView = GroupView

export type VerdictTone =
  'none' | 'negative' | 'partial-low' | 'partial-mid' | 'partial-high' | 'positive'

export interface VerdictView {
  /** Стабильный id из registry курса. */
  value: string
  symbol: string
  label: string
  /** Вес для статистики (`VERDICT_TO_NUM`), не показывается ученику числом. */
  weight: number
  tone: VerdictTone
  /** Автор оценки — живой преподаватель или ИИ; визуально различаются. */
  provenance?: 'human' | 'ai'
}

/** `WRITTEN_BEFORE_ORALLY` школьнику всегда показывается как oral. */
export type TaskType = 'test' | 'written' | 'oral'

export type TaskStatusTone = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

export interface TaskStatusView {
  kind:
    | 'not-started'
    | 'opened'
    | 'draft'
    | 'queued'
    | 'sent'
    | 'checking'
    | 'accepted'
    | 'needs-work'
    | 'rejected'
  label: string
  tone: TaskStatusTone
}

export interface TaskListItemView {
  id: string
  /** Отображаемый номер, напр. «21н.6». */
  number: string
  title: string
  type: TaskType
  status: TaskStatusView
  /** Итоговый вердикт, если проверка завершена. */
  verdict?: VerdictView
  hasNewFeedback?: boolean
}
