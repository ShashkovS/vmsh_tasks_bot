import {
  updateAdminStudentEnrollmentRequestSchema,
  type UpdateAdminStudentEnrollmentRequest,
} from '@vmsh/contracts'

export function enrollmentDraftKey(
  storageNamespace: string,
  accountId: string,
  enrollmentId: string,
  version: number,
): string {
  return `${storageNamespace}:student-enrollment:${accountId}:${enrollmentId}:v${version}`
}

export function readEnrollmentDraft(
  storage: Pick<Storage, 'getItem'>,
  key: string,
  fallback: UpdateAdminStudentEnrollmentRequest,
): UpdateAdminStudentEnrollmentRequest {
  try {
    const stored: unknown = JSON.parse(storage.getItem(key) ?? 'null')
    const parsed = updateAdminStudentEnrollmentRequestSchema.safeParse(stored)
    return parsed.success ? parsed.data : fallback
  } catch {
    return fallback
  }
}

export function writeEnrollmentDraft(
  storage: Pick<Storage, 'setItem'>,
  key: string,
  value: UpdateAdminStudentEnrollmentRequest,
): boolean {
  try {
    const parsed = updateAdminStudentEnrollmentRequestSchema.parse(value)
    storage.setItem(key, JSON.stringify(parsed))
    return true
  } catch {
    return false
  }
}

export function clearEnrollmentDraft(storage: Pick<Storage, 'removeItem'>, key: string): void {
  try {
    storage.removeItem(key)
  } catch {
    // Saving succeeded on the server; a stale local draft is harmless because
    // the next authoritative version uses another key.
  }
}
