import { z } from 'zod'

import {
  staffScopeSelectionSchema,
  type StaffAccessScope,
  type StaffScopeSelection,
} from '@vmsh/contracts'

const draftSchema = z.array(staffScopeSelectionSchema).max(100)

export function staffAccessDraftKey(
  namespace: string,
  accountId: string,
  staffUserId: string,
  scopes: StaffAccessScope[],
): string {
  const baseVersion = [...scopes]
    .sort((left, right) =>
      `${left.courseId}:${left.groupId ?? ''}`.localeCompare(
        `${right.courseId}:${right.groupId ?? ''}`,
      ),
    )
    .map((scope) => `${scope.courseId}:${scope.groupId ?? '*'}:v${scope.version}`)
    .join(',')
  return `${namespace}:draft:staff-access:${accountId}:${staffUserId}:${baseVersion || 'empty'}`
}

export function readStaffAccessDraft(
  storage: Pick<Storage, 'getItem'>,
  key: string,
  fallback: StaffScopeSelection[],
): StaffScopeSelection[] {
  try {
    const value = storage.getItem(key)
    return value === null ? fallback : draftSchema.parse(JSON.parse(value))
  } catch {
    return fallback
  }
}

export function writeStaffAccessDraft(
  storage: Pick<Storage, 'setItem'>,
  key: string,
  value: StaffScopeSelection[],
): boolean {
  try {
    storage.setItem(key, JSON.stringify(draftSchema.parse(value)))
    return true
  } catch {
    return false
  }
}

export function clearStaffAccessDraft(storage: Pick<Storage, 'removeItem'>, key: string): void {
  try {
    storage.removeItem(key)
  } catch {
    // A denied cleanup does not turn a successful server write into an error.
  }
}
