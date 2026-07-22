import Dexie, { type EntityTable } from 'dexie'
import { z } from 'zod'

export const outboxStatusSchema = z.enum(['queued', 'sending', 'failed'])
export type OutboxStatus = z.infer<typeof outboxStatusSchema>

export interface OutboxItem {
  id: string
  ownerId: string
  kind: 'test-answer' | 'written-answer' | 'question' | 'attendance'
  createdAtClient: string
  updatedAtClient: string
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
  }
}

export function createOutboxItem(
  input: Pick<OutboxItem, 'ownerId' | 'kind' | 'payload'>,
  now = new Date(),
): OutboxItem {
  const timestamp = now.toISOString()
  return {
    id: crypto.randomUUID(),
    ownerId: input.ownerId,
    kind: input.kind,
    payload: input.payload,
    createdAtClient: timestamp,
    updatedAtClient: timestamp,
    status: 'queued',
    attempts: 0,
  }
}
