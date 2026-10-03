import { describe, expect, it } from 'vitest'

import {
  clearFamilyAccountDraft,
  familyAccountDraftKey,
  readFamilyAccountDraft,
  writeFamilyAccountDraft,
  type FamilyAccountDraft,
} from './family-account-draft'

const fallback: FamilyAccountDraft = {
  schemaVersion: 1,
  kind: 'create',
  username: '',
  displayName: '',
  relationshipLabel: 'родитель',
  isPrimary: true,
}

describe('Family account draft', () => {
  it('isolates a non-secret draft by runtime, Staff account, Student and action', () => {
    const key = familyAccountDraftKey('vmsh-179:v1:staff:agent', 'admin', 'student-one', 'create')
    expect(key).toBe('vmsh-179:v1:staff:agent:family-account:admin:student-one:create')
    expect(key).not.toBe(
      familyAccountDraftKey('vmsh-179:v1:staff:agent', 'admin', 'student-one', 'link'),
    )
  })

  it('restores valid fields and never accepts a password for storage', () => {
    const values = new Map<string, string>()
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    }
    const key = 'draft'
    const changed = { ...fallback, username: 'family-login', displayName: 'Семья Ивановых' }

    expect(writeFamilyAccountDraft(storage, key, changed)).toBe(true)
    expect(readFamilyAccountDraft(storage, key, fallback)).toEqual(changed)
    expect(values.get(key)).not.toContain('password')

    expect(
      writeFamilyAccountDraft(storage, key, {
        ...changed,
        password: 'must-not-be-persisted',
      } as FamilyAccountDraft),
    ).toBe(false)
    expect(values.get(key)).not.toContain('must-not-be-persisted')

    clearFamilyAccountDraft(storage, key)
    expect(readFamilyAccountDraft(storage, key, fallback)).toEqual(fallback)
  })

  it('ignores malformed and wrong-action storage', () => {
    const malformed = { getItem: () => '{broken' }
    expect(readFamilyAccountDraft(malformed, 'draft', fallback)).toEqual(fallback)

    const link = {
      schemaVersion: 1,
      kind: 'link',
      familyUsername: 'family-login',
      relationshipLabel: 'родитель',
      isPrimary: false,
    }
    expect(
      readFamilyAccountDraft({ getItem: () => JSON.stringify(link) }, 'draft', fallback),
    ).toEqual(fallback)
  })
})
