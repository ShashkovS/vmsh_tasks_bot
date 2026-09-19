/*
 * Deterministic prototype/read-model helpers for the accepted multi-course
 * decisions. They deliberately do not persist data or model backend tables;
 * they make Storybook fixtures and future API contracts testable today.
 */

export interface EnrollmentProjection {
  courseId: string
  activeGroupId: string
  allowedGroupIds: string[]
}

export function createEnrollmentProjection(input: EnrollmentProjection): EnrollmentProjection {
  const allowedGroupIds = [...new Set(input.allowedGroupIds)]
  if (!allowedGroupIds.includes(input.activeGroupId)) {
    throw new Error('active group must be included in course access')
  }
  return { ...input, allowedGroupIds }
}

export interface ScheduleWindowSnapshot {
  conditionAt: string
  hintAt: string | null
  closesAt: string
  solutionAt: string
  sourceVersion: number
}

export function materializeScheduleSnapshot(
  courseTemplate: ScheduleWindowSnapshot,
  groupOverride?: Partial<Omit<ScheduleWindowSnapshot, 'sourceVersion'>>,
): ScheduleWindowSnapshot {
  return { ...courseTemplate, ...groupOverride }
}

export interface TelegramBindingProjection {
  id: string
  owner: 'course' | 'group'
  purpose: 'news-source' | 'materials-target'
}

export function resolveTelegramBindings(
  courseBindings: TelegramBindingProjection[],
  groupBindings: TelegramBindingProjection[],
): TelegramBindingProjection[] {
  const news = [...courseBindings, ...groupBindings].filter(
    (binding) => binding.purpose === 'news-source',
  )
  const groupTargets = groupBindings.filter((binding) => binding.purpose === 'materials-target')
  const targets =
    groupTargets.length > 0
      ? groupTargets
      : courseBindings.filter((binding) => binding.purpose === 'materials-target')
  return [...news, ...targets]
}

export interface ConcreteSubmissionProjection {
  id: string
  problemId: string
  createdAt: string
  verdict?: string
}

export interface SynonymProjection {
  submissionIds: string[]
  chronology: ConcreteSubmissionProjection[]
  verdictTargetProblemId: string | null
}

export function projectSynonymSubmissions(
  submissions: ConcreteSubmissionProjection[],
): SynonymProjection {
  const chronology = [...submissions].sort((left, right) =>
    left.createdAt.localeCompare(right.createdAt),
  )
  return {
    submissionIds: chronology.map(({ id }) => id),
    chronology,
    verdictTargetProblemId: chronology.at(-1)?.problemId ?? null,
  }
}

export function splitSynonymStatuses(
  problemIds: string[],
  submissions: ConcreteSubmissionProjection[],
): Record<string, string> {
  return Object.fromEntries(
    problemIds.map((problemId) => {
      const latest = submissions
        .filter((submission) => submission.problemId === problemId)
        .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
        .at(-1)
      return [problemId, latest?.verdict ?? (latest ? 'submitted' : 'not-started')]
    }),
  )
}

export interface GroupProblemScore {
  groupId: string
  synonymGroupId: string
  score: number
}

export function scoreGroupSheets(items: GroupProblemScore[]): Record<string, number> {
  const groupSynonyms = new Map<string, number>()
  for (const item of items) {
    const key = `${item.groupId}\u0000${item.synonymGroupId}`
    groupSynonyms.set(key, Math.max(groupSynonyms.get(key) ?? 0, item.score))
  }
  const totals: Record<string, number> = {}
  for (const [key, score] of groupSynonyms) {
    const groupId = key.split('\u0000')[0]!
    totals[groupId] = (totals[groupId] ?? 0) + score
  }
  return totals
}

export function selectBestLessonGroup(
  scores: Record<string, number>,
  groupSortOrder: Record<string, number>,
): string | null {
  return (
    Object.keys(scores).sort(
      (left, right) =>
        scores[right]! - scores[left]! ||
        (groupSortOrder[left] ?? Number.MAX_SAFE_INTEGER) -
          (groupSortOrder[right] ?? Number.MAX_SAFE_INTEGER),
    )[0] ?? null
  )
}

export interface ClassroomAssignmentProjection {
  studentUserId: string
  groupId: string
  classroomId: string
}

export function inheritClassroomAssignments(
  selectedGroupIds: string[],
  previous: ClassroomAssignmentProjection[],
): ClassroomAssignmentProjection[] {
  const selected = new Set(selectedGroupIds)
  return previous
    .filter(({ groupId }) => selected.has(groupId))
    .map((assignment) => ({ ...assignment }))
}

export function resolveCourseNotification(
  defaultEnabled: boolean,
  courseOverride: boolean | undefined,
): boolean {
  return courseOverride ?? defaultEnabled
}
