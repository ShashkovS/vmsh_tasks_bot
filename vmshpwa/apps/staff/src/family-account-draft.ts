import { z } from 'zod'

const commonFields = {
  schemaVersion: z.literal(1),
  relationshipLabel: z.string().trim().min(1).max(100),
  isPrimary: z.boolean(),
}

export const familyAccountDraftSchema = z.discriminatedUnion('kind', [
  z
    .object({
      ...commonFields,
      kind: z.literal('create'),
      username: z.string().trim().max(100),
      displayName: z.string().trim().max(200),
    })
    .strict(),
  z
    .object({
      ...commonFields,
      kind: z.literal('link'),
      familyUsername: z.string().trim().max(100),
    })
    .strict(),
])
export type FamilyAccountDraft = z.infer<typeof familyAccountDraftSchema>
export type FamilyAccountDraftKind = FamilyAccountDraft['kind']

/**
 * Phase 10 keeps meaningful Staff edits across reloads, but credentials are
 * deliberately absent from this schema and therefore cannot reach storage.
 * See `dev/development-plan/14-phase-10-admin-and-google-exit.md`.
 */
export function familyAccountDraftKey(
  storageNamespace: string,
  staffAccountId: string,
  studentId: string,
  kind: FamilyAccountDraftKind,
): string {
  return `${storageNamespace}:family-account:${staffAccountId}:${studentId}:${kind}`
}

export function readFamilyAccountDraft(
  storage: Pick<Storage, 'getItem'>,
  key: string,
  fallback: FamilyAccountDraft,
): FamilyAccountDraft {
  try {
    const parsed = familyAccountDraftSchema.safeParse(JSON.parse(storage.getItem(key) ?? 'null'))
    return parsed.success && parsed.data.kind === fallback.kind ? parsed.data : fallback
  } catch {
    return fallback
  }
}

export function writeFamilyAccountDraft(
  storage: Pick<Storage, 'setItem'>,
  key: string,
  value: FamilyAccountDraft,
): boolean {
  try {
    storage.setItem(key, JSON.stringify(familyAccountDraftSchema.parse(value)))
    return true
  } catch {
    return false
  }
}

export function clearFamilyAccountDraft(storage: Pick<Storage, 'removeItem'>, key: string): void {
  try {
    storage.removeItem(key)
  } catch {
    // A successful server write is authoritative; stale storage can only refill
    // non-secret text fields and may be cleared manually on the next edit.
  }
}
