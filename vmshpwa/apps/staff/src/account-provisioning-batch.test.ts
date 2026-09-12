import { expect, it, vi } from 'vitest'

import type {
  AccountProvisioningPreviewResponse,
  AccountProvisioningReceipt,
} from '@vmsh/contracts'

import { applyProvisioningInChunks } from './account-provisioning-batch'

it('applies ready rows in small chunks and preserves original error row numbers', async () => {
  const rows = Array.from({ length: 42 }, (_, index) => ({ login: `parent-${index + 1}` }))
  const initialPreview: AccountProvisioningPreviewResponse = {
    schemaVersion: 1,
    previewHash: 'a'.repeat(64),
    counts: { total: 42, ready: 41, invalid: 1 },
    rows: rows.map((row, index) =>
      index === 21
        ? {
            rowNumber: index + 1,
            state: 'invalid' as const,
            resolvedLogin: null,
            loginAdjusted: false as const,
            code: 'child_login_not_found',
          }
        : {
            rowNumber: index + 1,
            state: 'ready' as const,
            resolvedLogin: row.login,
            loginAdjusted: false,
            code: null,
          },
    ),
    requestId: 'initial-preview',
  }
  const preview = vi.fn((chunk: typeof rows): Promise<AccountProvisioningPreviewResponse> =>
    Promise.resolve({
      schemaVersion: 1,
      previewHash: 'b'.repeat(64),
      counts: { total: chunk.length, ready: chunk.length, invalid: 0 },
      rows: chunk.map((row, index) => ({
        rowNumber: index + 1,
        state: 'ready',
        resolvedLogin: row.login,
        loginAdjusted: false,
        code: null,
      })),
      requestId: `preview-${chunk[0]!.login}`,
    }),
  )
  const apply = vi.fn(
    (
      chunk: typeof rows,
      currentPreview: AccountProvisioningPreviewResponse,
    ): Promise<AccountProvisioningReceipt> => {
      expect(currentPreview.counts.ready).toBe(chunk.length)
      return Promise.resolve({
        schemaVersion: 1,
        counts: { total: chunk.length, created: chunk.length, skipped: 0 },
        rows: chunk.map((row, index) => ({
          rowNumber: index + 1,
          state: 'created',
          login: row.login,
          accountId: `a-${index + 1}`,
        })),
        requestId: `apply-${chunk[0]!.login}`,
      })
    },
  )
  const progress = vi.fn()
  const completedChunks = vi.fn()

  const receipt = await applyProvisioningInChunks({
    rows,
    initialPreview,
    preview,
    apply,
    onProgress: progress,
    onChunkCompleted: completedChunks,
  })

  expect(preview.mock.calls.map(([chunk]) => chunk.length)).toEqual([20, 20, 1])
  expect(apply).toHaveBeenCalledTimes(3)
  expect(receipt.counts).toEqual({ total: 42, created: 41, skipped: 1 })
  expect(receipt.rows[21]).toEqual({
    rowNumber: 22,
    state: 'skipped',
    code: 'child_login_not_found',
  })
  expect(receipt.rows[41]).toEqual(
    expect.objectContaining({ rowNumber: 42, state: 'created', login: 'parent-42' }),
  )
  expect(progress).toHaveBeenLastCalledWith(42, 42)
  expect(completedChunks).toHaveBeenCalledTimes(3)
  expect(completedChunks.mock.calls[0]?.[0]).toHaveLength(20)
})
