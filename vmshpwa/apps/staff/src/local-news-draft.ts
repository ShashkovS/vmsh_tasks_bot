import { browserTimeZone, instantToWallTime, wallTimeToInstant } from '@vmsh/i18n'

export interface LocalNewsDraft {
  courseId: string
  groupId: string
  audience: 'student' | 'family' | 'both'
  attendanceMode: 'all' | 'online' | 'in_person'
  text: string
  publishedLocal: string
}

export const EMPTY_LOCAL_NEWS_DRAFT: LocalNewsDraft = {
  courseId: '',
  groupId: '',
  audience: 'both',
  attendanceMode: 'all',
  text: '',
  publishedLocal: '',
}

function isDraft(value: unknown): value is LocalNewsDraft {
  if (value === null || typeof value !== 'object') return false
  const item = value as Record<string, unknown>
  return (
    Object.keys(item).length === 6 &&
    typeof item.courseId === 'string' &&
    item.courseId.length <= 128 &&
    typeof item.groupId === 'string' &&
    item.groupId.length <= 128 &&
    (item.audience === 'student' || item.audience === 'family' || item.audience === 'both') &&
    (item.attendanceMode === 'all' ||
      item.attendanceMode === 'online' ||
      item.attendanceMode === 'in_person') &&
    typeof item.text === 'string' &&
    item.text.length <= 32_768 &&
    typeof item.publishedLocal === 'string' &&
    item.publishedLocal.length <= 32
  )
}

type LegacyTargetDefaults = Pick<
  LocalNewsDraft,
  'courseId' | 'groupId' | 'audience' | 'attendanceMode'
>

function migrateLegacyDraft(
  value: unknown,
  targetDefaults: LegacyTargetDefaults,
): LocalNewsDraft | null {
  if (value === null || typeof value !== 'object') return null
  const item = value as Record<string, unknown>
  if (
    Object.keys(item).length !== 3 ||
    typeof item.owner !== 'string' ||
    typeof item.text !== 'string' ||
    typeof item.publishedLocal !== 'string' ||
    item.text.length > 32_768 ||
    item.publishedLocal.length > 32
  )
    return null
  const separator = item.owner.indexOf(':')
  if (separator < 1) return null
  const ownerType = item.owner.slice(0, separator)
  const ownerId = item.owner.slice(separator + 1)
  if ((ownerType !== 'course' && ownerType !== 'group') || ownerId.length > 128) return null
  return {
    ...targetDefaults,
    courseId: ownerType === 'course' ? ownerId : targetDefaults.courseId,
    groupId: ownerType === 'group' ? ownerId : '',
    text: item.text,
    publishedLocal: item.publishedLocal,
  }
}

/** Reload-safe Staff draft; server data still remains authoritative. */
export function loadLocalNewsDraft(
  storage: Storage,
  key: string,
  legacyTargetDefaults: LegacyTargetDefaults = EMPTY_LOCAL_NEWS_DRAFT,
): LocalNewsDraft {
  try {
    const raw = storage.getItem(key)
    if (raw === null) return EMPTY_LOCAL_NEWS_DRAFT
    const parsed: unknown = JSON.parse(raw)
    return isDraft(parsed)
      ? parsed
      : (migrateLegacyDraft(parsed, legacyTargetDefaults) ?? EMPTY_LOCAL_NEWS_DRAFT)
  } catch {
    return EMPTY_LOCAL_NEWS_DRAFT
  }
}

export function saveLocalNewsDraft(storage: Storage, key: string, draft: LocalNewsDraft): void {
  try {
    storage.setItem(key, JSON.stringify(draft))
  } catch {
    // Storage denial must not crash the editor; the visible draft remains in React state.
  }
}

export function clearLocalNewsDraft(storage: Storage, key: string): void {
  try {
    storage.removeItem(key)
  } catch {
    // A denied cleanup is harmless; account-scoped keys are validated on the next load.
  }
}

// Staff type publication times in their own browser zone
// (dev/ui-audit-20261104/BACKLOG.md, «Часовые пояса»).
export function localDateTimeToIso(
  value: string,
  timeZone: string = browserTimeZone(),
): string | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(value)) return null
  return wallTimeToInstant(value, timeZone)?.toISOString() ?? null
}

export function isoToLocalDateTime(
  value: string,
  timeZone: string = browserTimeZone(),
): string | null {
  const date = new Date(value)
  if (Number.isNaN(date.valueOf())) return null
  return instantToWallTime(date, timeZone)
}
