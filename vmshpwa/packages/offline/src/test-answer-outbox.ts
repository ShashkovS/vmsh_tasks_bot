import { z } from 'zod'

import {
  ApiResponseError,
  publicIdSchema,
  submitTestAnswerRequestSchema,
  submitTestAnswerResponseSchema,
  testProblemRevisionSchema,
  type SubmitTestAnswerRequest,
  type SubmitTestAnswerResponse,
  type TestProblemRevision,
} from '@vmsh/contracts'

import { type OutboxItem, type VmshOfflineDatabase } from './database'

/**
 * Durable Phase-4 mutation queue. The wire request, including its expected
 * problem revision and UUID, is stored once and reused byte-for-byte on every
 * delivery. See `dev/development-plan/08-phase-4-test-submissions.md` and the
 * transport in `packages/app-shell/src/submission-client.ts`.
 */

export const TEST_ANSWER_OUTBOX_VERSION = 1 as const

export const testAnswerOutboxPayloadSchema = z
  .object({
    schemaVersion: z.literal(TEST_ANSWER_OUTBOX_VERSION),
    problemId: publicIdSchema,
    request: submitTestAnswerRequestSchema,
  })
  .strict()
export type TestAnswerOutboxPayload = z.infer<typeof testAnswerOutboxPayloadSchema>

const testAnswerOutboxItemSchema = z
  .object({
    id: z.uuid(),
    idempotencyKey: z.uuid(),
    ownerId: publicIdSchema,
    kind: z.literal('test-answer'),
    createdAtClient: z.iso.datetime(),
    updatedAtClient: z.iso.datetime(),
    timezoneOffsetMinutes: z
      .number()
      .int()
      .min(-14 * 60)
      .max(14 * 60),
    payloadHash: z.string().regex(/^sha256:[0-9a-f]{64}$/),
    status: z.enum(['queued', 'sending', 'retrying', 'synced', 'conflict', 'failed']),
    attempts: z.number().int().nonnegative(),
    payload: testAnswerOutboxPayloadSchema,
    result: submitTestAnswerResponseSchema.optional(),
    lastError: z.string().min(1).max(300).optional(),
  })
  .strict()
  .superRefine((item, context) => {
    if (item.id !== item.idempotencyKey || item.id !== item.payload.request.idempotencyKey) {
      context.addIssue({
        code: 'custom',
        message: 'Outbox identity must equal its wire idempotency key',
        path: ['idempotencyKey'],
      })
    }
    if ((item.status === 'synced') !== (item.result !== undefined)) {
      context.addIssue({
        code: 'custom',
        message: 'Only a synced outbox item may contain a server receipt',
        path: ['result'],
      })
    }
  })
export type TestAnswerOutboxItem = z.infer<typeof testAnswerOutboxItemSchema>

export interface EnqueueTestAnswerInput {
  problemId: string
  problemRevision: TestProblemRevision
  displayAnswer: string
  timezoneOffsetMinutes?: number
}

export interface TestAnswerSubmissionTransport {
  submit(problemId: string, request: SubmitTestAnswerRequest): Promise<SubmitTestAnswerResponse>
}

export type TestAnswerDeliveryResult =
  | { state: 'idle' }
  | { state: 'synced'; item: TestAnswerOutboxItem; receipt: SubmitTestAnswerResponse }
  | {
      state: 'retrying' | 'conflict' | 'failed'
      item: TestAnswerOutboxItem
      error: unknown
    }

export interface TestAnswerOutboxOptions {
  now?: () => Date
  randomUUID?: () => string
  payloadHasher?: (payload: TestAnswerOutboxPayload) => Promise<string>
  sendingLeaseMilliseconds?: number
}

export interface TestAnswerOutbox {
  enqueue(input: EnqueueTestAnswerInput): Promise<TestAnswerOutboxItem>
  list(): Promise<TestAnswerOutboxItem[]>
  deliverNext(
    transport: TestAnswerSubmissionTransport,
    itemId?: string,
  ): Promise<TestAnswerDeliveryResult>
  acknowledge(itemId: string): Promise<boolean>
}

const sha256Schema = z.string().regex(/^sha256:[0-9a-f]{64}$/)

function canonicalJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value !== null && typeof value === 'object') {
    const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) =>
      left.localeCompare(right),
    )
    return `{${entries
      .map(([key, child]) => `${JSON.stringify(key)}:${canonicalJson(child)}`)
      .join(',')}}`
  }
  return JSON.stringify(value)
}

async function sha256Payload(payload: TestAnswerOutboxPayload): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error('Web Crypto is unavailable')
  const bytes = new TextEncoder().encode(canonicalJson(payload))
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes)
  return `sha256:${[...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')}`
}

function failureLabel(error: unknown): string {
  if (error instanceof ApiResponseError)
    return `api:${error.status}:${error.code.slice(0, 100)}:request=${error.requestId.slice(0, 128)}`
  if (error instanceof DOMException) return `dom:${error.name}`
  if (error instanceof Error) return `client:${error.name}`
  return 'client:unknown'
}

function failureState(error: unknown): 'retrying' | 'conflict' | 'failed' {
  if (error instanceof ApiResponseError) {
    if (['test_attempt_hour_limit', 'test_attempt_day_limit'].includes(error.code)) return 'failed'
    if (
      error.code === 'idempotency_payload_mismatch' ||
      error.code === 'test_problem_revision_changed'
    ) {
      return 'conflict'
    }
    if (error.status === 429 || error.status >= 500) return 'retrying'
    return 'failed'
  }
  if (
    error instanceof TypeError ||
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'TestSubmissionNetworkError')
  ) {
    return 'retrying'
  }
  return 'failed'
}

function validatedItem(item: OutboxItem): TestAnswerOutboxItem {
  const parsed = testAnswerOutboxItemSchema.parse(item)
  if (
    ['queued', 'retrying'].includes(parsed.status) &&
    /\btest_attempt_(hour|day)_limit\b/.test(parsed.lastError ?? '')
  ) {
    return { ...parsed, status: 'failed' }
  }
  return parsed
}

function receiptMatchesPayload(
  payload: TestAnswerOutboxPayload,
  receipt: SubmitTestAnswerResponse,
): boolean {
  return (
    receipt.problemId === payload.problemId &&
    receipt.problemRevision.conditionRevisionId ===
      payload.request.problemRevision.conditionRevisionId &&
    receipt.problemRevision.configVersion === payload.request.problemRevision.configVersion &&
    Date.parse(receipt.clientCreatedAt) === Date.parse(payload.request.clientCreatedAt)
  )
}

export function createTestAnswerOutbox(
  database: VmshOfflineDatabase,
  ownerId: string,
  options: TestAnswerOutboxOptions = {},
): TestAnswerOutbox {
  const parsedOwnerId = publicIdSchema.parse(ownerId)
  const now = options.now ?? (() => new Date())
  const randomUUID = options.randomUUID ?? (() => globalThis.crypto.randomUUID())
  const payloadHasher = options.payloadHasher ?? sha256Payload
  const sendingLeaseMilliseconds = options.sendingLeaseMilliseconds ?? 60_000
  if (!Number.isSafeInteger(sendingLeaseMilliseconds) || sendingLeaseMilliseconds < 1) {
    throw new RangeError('Outbox sending lease must be a positive integer')
  }

  async function settle(
    claimed: TestAnswerOutboxItem,
    state: 'retrying' | 'conflict' | 'failed',
    error: unknown,
  ): Promise<TestAnswerOutboxItem> {
    const updatedAtClient = now().toISOString()
    await database.transaction('rw', database.outbox, async () => {
      const current = await database.outbox.get(claimed.id)
      if (
        current?.ownerId === parsedOwnerId &&
        current.kind === 'test-answer' &&
        current.status === 'sending'
      ) {
        await database.outbox.update(claimed.id, {
          status: state,
          updatedAtClient,
          lastError: failureLabel(error),
        })
      }
    })
    const stored = await database.outbox.get(claimed.id)
    return stored ? validatedItem(stored) : { ...claimed, status: state, updatedAtClient }
  }

  async function claimNext(itemId?: string): Promise<TestAnswerOutboxItem | null> {
    return database.transaction('rw', database.outbox, async () => {
      const leaseCutoff = new Date(now().getTime() - sendingLeaseMilliseconds).toISOString()
      // Retire retries persisted by older clients, without another HTTP attempt.
      // See docs/support-problem-context.md: business limits are not transport failures.
      for (const item of await database.outbox.where('ownerId').equals(parsedOwnerId).toArray()) {
        if (
          item.kind === 'test-answer' &&
          ['queued', 'retrying'].includes(item.status) &&
          /\btest_attempt_(hour|day)_limit\b/.test(item.lastError ?? '')
        ) {
          await database.outbox.update(item.id, {
            status: 'failed',
            updatedAtClient: now().toISOString(),
          })
        }
      }
      const candidates = (await database.outbox.where('ownerId').equals(parsedOwnerId).toArray())
        .filter(
          (item) =>
            item.kind === 'test-answer' &&
            (itemId === undefined || item.id === itemId) &&
            (item.status === 'queued' ||
              item.status === 'retrying' ||
              (item.status === 'sending' && item.updatedAtClient <= leaseCutoff)),
        )
        .sort(
          (left, right) =>
            left.createdAtClient.localeCompare(right.createdAtClient) ||
            left.id.localeCompare(right.id),
        )
      const candidate = candidates[0]
      if (!candidate) return null

      const parsed = testAnswerOutboxItemSchema.safeParse(candidate)
      if (!parsed.success) {
        await database.outbox.update(candidate.id, {
          status: 'failed',
          updatedAtClient: now().toISOString(),
          lastError: 'client:invalid-outbox-record',
        })
        return null
      }
      const claimed = {
        ...parsed.data,
        status: 'sending' as const,
        attempts: parsed.data.attempts + 1,
        updatedAtClient: now().toISOString(),
      }
      delete claimed.lastError
      await database.outbox.put(claimed)
      return claimed
    })
  }

  return {
    async enqueue(input) {
      const created = now()
      const idempotencyKey = randomUUID()
      const request = submitTestAnswerRequestSchema.parse({
        schemaVersion: 1,
        idempotencyKey,
        problemRevision: testProblemRevisionSchema.parse(input.problemRevision),
        displayAnswer: input.displayAnswer,
        clientCreatedAt: created.toISOString(),
      })
      const payload = testAnswerOutboxPayloadSchema.parse({
        schemaVersion: TEST_ANSWER_OUTBOX_VERSION,
        problemId: input.problemId,
        request,
      })
      const item = testAnswerOutboxItemSchema.parse({
        id: idempotencyKey,
        idempotencyKey,
        ownerId: parsedOwnerId,
        kind: 'test-answer',
        createdAtClient: request.clientCreatedAt,
        updatedAtClient: request.clientCreatedAt,
        timezoneOffsetMinutes: input.timezoneOffsetMinutes ?? created.getTimezoneOffset(),
        payloadHash: sha256Schema.parse(await payloadHasher(payload)),
        status: 'queued',
        attempts: 0,
        payload,
      })
      await database.outbox.add(item)
      return item
    },

    async list() {
      const records = await database.outbox.where('ownerId').equals(parsedOwnerId).toArray()
      return records
        .filter((item) => item.kind === 'test-answer')
        .map(validatedItem)
        .sort(
          (left, right) =>
            left.createdAtClient.localeCompare(right.createdAtClient) ||
            left.id.localeCompare(right.id),
        )
    },

    async deliverNext(transport, itemId) {
      const claimed = await claimNext(itemId === undefined ? undefined : z.uuid().parse(itemId))
      if (!claimed) return { state: 'idle' }
      try {
        const receipt = submitTestAnswerResponseSchema.parse(
          await transport.submit(claimed.payload.problemId, claimed.payload.request),
        )
        if (!receiptMatchesPayload(claimed.payload, receipt)) {
          throw new Error('Test-submission receipt does not match its queued request')
        }
        const synced = testAnswerOutboxItemSchema.parse({
          ...claimed,
          status: 'synced',
          result: receipt,
          updatedAtClient: now().toISOString(),
        })
        await database.transaction('rw', database.outbox, async () => {
          const current = await database.outbox.get(claimed.id)
          if (
            current?.ownerId === parsedOwnerId &&
            current.kind === 'test-answer' &&
            current.status === 'sending'
          ) {
            await database.outbox.put(synced)
          }
        })
        return { state: 'synced', item: synced, receipt }
      } catch (error) {
        const state = failureState(error)
        return { state, item: await settle(claimed, state, error), error }
      }
    },

    async acknowledge(itemId) {
      const parsedItemId = z.uuid().parse(itemId)
      return database.transaction('rw', database.outbox, async () => {
        const current = await database.outbox.get(parsedItemId)
        if (
          !current ||
          current.ownerId !== parsedOwnerId ||
          current.kind !== 'test-answer' ||
          current.status !== 'synced'
        ) {
          return false
        }
        validatedItem(current)
        await database.outbox.delete(parsedItemId)
        return true
      })
    },
  }
}
