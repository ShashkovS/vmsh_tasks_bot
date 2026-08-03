import { describe, expect, it } from 'vitest'

import {
  accountProvisioningPreviewResponseSchema,
  accountProvisioningReceiptSchema,
  familyProvisioningPreviewRequestSchema,
  studentProvisioningApplyRequestSchema,
  studentProvisioningPreviewRequestSchema,
} from './account-provisioning'

const studentRow = {
  surname: 'Иванов',
  name: 'Иван',
  login: 'ivanov',
  password: 'telegram-token',
}

describe('account provisioning contracts', () => {
  it('accepts optional Student fields and comma-separated Family emails', () => {
    expect(
      studentProvisioningPreviewRequestSchema.parse({ schemaVersion: 1, rows: [studentRow] }),
    ).toBeDefined()
    expect(
      familyProvisioningPreviewRequestSchema.parse({
        schemaVersion: 1,
        rows: [
          {
            name: 'Семья Ивановых',
            login: 'parent-ivanov',
            password: 'qwerty-family',
            emails: 'one@example.org, two@example.org',
            childLogins: ['ivanov'],
          },
        ],
      }),
    ).toBeDefined()
  })

  it('requires apply rows and reviewed logins to stay aligned', () => {
    expect(() =>
      studentProvisioningApplyRequestSchema.parse({
        schemaVersion: 1,
        rows: [studentRow],
        resolvedLogins: [],
        previewHash: 'a'.repeat(64),
      }),
    ).toThrow()
  })

  it('validates secret-free preview and receipt responses', () => {
    const preview = accountProvisioningPreviewResponseSchema.parse({
      schemaVersion: 1,
      previewHash: 'a'.repeat(64),
      counts: { total: 2, ready: 1, invalid: 1 },
      rows: [
        {
          rowNumber: 1,
          state: 'ready',
          resolvedLogin: 'ivanov-17',
          loginAdjusted: true,
          code: null,
        },
        {
          rowNumber: 2,
          state: 'invalid',
          resolvedLogin: null,
          loginAdjusted: false,
          code: 'invalid_grade',
        },
      ],
      requestId: 'test.request',
    })
    expect(preview.rows).toHaveLength(2)

    const receipt = accountProvisioningReceiptSchema.parse({
      schemaVersion: 1,
      counts: { total: 2, created: 1, skipped: 1 },
      rows: [
        {
          rowNumber: 1,
          state: 'created',
          login: 'ivanov-17',
          userId: 'user.17',
          accountId: 'student-account.17',
        },
        { rowNumber: 2, state: 'skipped', code: 'invalid_row' },
      ],
      requestId: 'test.request',
    })
    expect(receipt.counts.created).toBe(1)
    expect(JSON.stringify(receipt)).not.toContain('telegram-token')
  })
})
