/**
 * Calm, shared labels for the first course achievements.
 * Phase 9 keeps rule codes in the API and localized text at the UI boundary;
 * Student and Family must describe the same earned fact consistently.
 */
const COURSE_ACHIEVEMENT_LABELS: Readonly<Record<string, string>> = {
  first_submission: 'Первая задача отправлена',
  first_accepted: 'Первая задача зачтена',
  first_written_submission: 'Первая письменная работа',
}

export function courseAchievementLabel(code: string): string | undefined {
  return COURSE_ACHIEVEMENT_LABELS[code]
}
