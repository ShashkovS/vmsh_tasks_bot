import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it, vi } from 'vitest'

import { TestSubmissionNetworkError } from '@vmsh/app-shell'
import inputFixture from '@vmsh/contracts/fixtures/submissions/input.v1.json'
import { ApiResponseError, testAnswerInputResponseSchema } from '@vmsh/contracts'
import { VmshOfflineDatabase } from '@vmsh/offline'

import { createOfflineStudentTestAnswerInputClient } from './offline-student-data'

const databases = new Set<VmshOfflineDatabase>()
const INPUT = testAnswerInputResponseSchema.parse(inputFixture.response)

afterEach(async () => {
  await Promise.all(
    [...databases].map(async (database) => {
      database.close()
      await database.delete()
    }),
  )
  databases.clear()
})

function database(instance: string) {
  const value = new VmshOfflineDatabase({ audience: 'student', instance })
  databases.add(value)
  return value
}

describe('offline Student test-input read', () => {
  it('caches a validated input and restores it only after a network failure', async () => {
    const target = database('test-input-cache')
    const input = vi
      .fn()
      .mockResolvedValueOnce(INPUT)
      .mockRejectedValueOnce(new TestSubmissionNetworkError({ cause: new TypeError('offline') }))
    const client = createOfflineStudentTestAnswerInputClient({ input }, target, 'account-first')

    await expect(client.input(INPUT.problemId)).resolves.toEqual(INPUT)
    await expect(client.input(INPUT.problemId)).resolves.toEqual(INPUT)
    expect(input).toHaveBeenCalledTimes(2)
  })

  it('does not expose another account cache or hide an authoritative API denial', async () => {
    const target = database('test-input-owner')
    const first = createOfflineStudentTestAnswerInputClient(
      { input: () => Promise.resolve(INPUT) },
      target,
      'account-first',
    )
    await first.input(INPUT.problemId)

    const offline = new TestSubmissionNetworkError({ cause: new TypeError('offline') })
    const second = createOfflineStudentTestAnswerInputClient(
      { input: () => Promise.reject(offline) },
      target,
      'account-second',
    )
    await expect(second.input(INPUT.problemId)).rejects.toBe(offline)

    const forbidden = new ApiResponseError(403, {
      error: { code: 'forbidden', message: 'Нет доступа', requestId: 'request-forbidden' },
    })
    const denied = createOfflineStudentTestAnswerInputClient(
      { input: () => Promise.reject(forbidden) },
      target,
      'account-first',
    )
    await expect(denied.input(INPUT.problemId)).rejects.toBe(forbidden)
  })
})
