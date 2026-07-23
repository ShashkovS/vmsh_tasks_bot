import Dexie, { type EntityTable } from 'dexie'
import { z } from 'zod'

export const outboxStatusSchema = z.enum([
  'queued',
  'sending',
  'retrying',
  'synced',
  'conflict',
  'failed',
])
export type OutboxStatus = z.infer<typeof outboxStatusSchema>

export interface OutboxItem {
  id: string
  idempotencyKey: string
  ownerId: string
  kind: 'test-answer' | 'written-answer' | 'question' | 'attendance'
  createdAtClient: string
  updatedAtClient: string
  timezoneOffsetMinutes: number
  payloadHash: string
  status: OutboxStatus
  attempts: number
  payload: unknown
  lastError?: string
}

export interface CachedDocument {
  key: string
  ownerId: string
  version: string
  cachedAt: string
  payload: unknown
}

export class VmshOfflineDatabase extends Dexie {
  outbox!: EntityTable<OutboxItem, 'id'>
  documents!: EntityTable<CachedDocument, 'key'>

  constructor(audience: 'student' | 'family', instance: string) {
    super(`vmsh-179-${audience}-${instance}`)
    this.version(1).stores({
      outbox: '&id, ownerId, status, createdAtClient, kind',
      documents: '&key, ownerId, version, cachedAt',
    })
    this.version(2)
      .stores({
        outbox: '&id, &idempotencyKey, ownerId, status, createdAtClient, kind',
        documents: '&key, ownerId, version, cachedAt',
      })
      .upgrade(async (transaction) => {
        await transaction
          .table<OutboxItem, string>('outbox')
          .toCollection()
          .modify((item) => {
            item.idempotencyKey ||= item.id
            item.payloadHash ||= 'legacy-unverified'
            item.timezoneOffsetMinutes ??= 0
          })
      })
  }
}

export function createOutboxItem(
  input: Pick<OutboxItem, 'ownerId' | 'kind' | 'payload' | 'payloadHash'> & {
    timezoneOffsetMinutes?: number
  },
  now = new Date(),
): OutboxItem {
  const timestamp = now.toISOString()
  const idempotencyKey = crypto.randomUUID()
  return {
    id: idempotencyKey,
    idempotencyKey,
    ownerId: input.ownerId,
    kind: input.kind,
    payload: input.payload,
    payloadHash: input.payloadHash,
    timezoneOffsetMinutes: input.timezoneOffsetMinutes ?? now.getTimezoneOffset(),
    createdAtClient: timestamp,
    updatedAtClient: timestamp,
    status: 'queued',
    attempts: 0,
  }
}

export function classifyIdempotencyReplay(
  storedPayloadHash: string,
  incomingPayloadHash: string,
): 'replay' | 'conflict' {
  return storedPayloadHash === incomingPayloadHash ? 'replay' : 'conflict'
}
