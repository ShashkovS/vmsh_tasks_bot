import Dexie, { type EntityTable } from 'dexie'
import { z } from 'zod'

import {
  createBrowserStorageNamespace,
  runtimeInstanceSchema,
  type BrowserStorageNamespace,
  type RuntimeConfig,
} from '@vmsh/contracts'

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

export interface CachedAuthenticationSnapshot {
  key: 'current'
  ownerId: string
  expiresAt: string
  cachedAt: string
  payload: unknown
}

export const offlineAudienceSchema = z.enum(['student', 'family'])
export type OfflineAudience = z.infer<typeof offlineAudienceSchema>
export type OfflineRuntime = Pick<RuntimeConfig, 'instance'> & { audience: OfflineAudience }

const offlineRuntimeSchema = z
  .object({
    audience: offlineAudienceSchema,
    instance: runtimeInstanceSchema,
  })
  .strict()

export function offlineDatabaseName(runtime: OfflineRuntime): BrowserStorageNamespace {
  const parsedRuntime = offlineRuntimeSchema.parse(runtime)
  return createBrowserStorageNamespace(parsedRuntime)
}

export class VmshOfflineDatabase extends Dexie {
  outbox!: EntityTable<OutboxItem, 'id'>
  documents!: EntityTable<CachedDocument, 'key'>
  authentication!: EntityTable<CachedAuthenticationSnapshot, 'key'>

  constructor(runtime: OfflineRuntime) {
    // The Dexie name is exactly the canonical Phase-0 namespace. Adding a
    // second package prefix here would defeat cross-runtime isolation proofs.
    // See `docs/runtime-isolation.md` and `packages/contracts/src/index.ts`.
    super(offlineDatabaseName(runtime))
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
    this.version(3).stores({
      outbox: '&id, &idempotencyKey, ownerId, status, createdAtClient, kind',
      documents: '&key, ownerId, version, cachedAt',
      authentication: '&key, ownerId, expiresAt',
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
