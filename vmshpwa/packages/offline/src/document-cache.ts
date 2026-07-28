import { z } from 'zod'

import { publicIdSchema } from '@vmsh/contracts'

import { type CachedDocument, type VmshOfflineDatabase } from './database'

/**
 * Durable read cache from Phase 3. Only already contract-validated JSON enters
 * this store; callers must provide the same Zod parser when reading it back.
 * See `dev/development-plan/07-phase-3-student-reading.md`.
 */
export const offlineDocumentKindSchema = z.enum([
  'student-home',
  'student-course-access',
  'student-course-enrollment',
  'student-lesson-list',
  'student-lesson',
  'student-problem-list',
  'published-content',
  'student-material-reveal',
])
export type OfflineDocumentKind = z.infer<typeof offlineDocumentKindSchema>

const resourcePartSchema = z.string().trim().min(1).max(300)
const cacheVersionSchema = z.string().trim().min(1).max(300)

export const offlineDocumentEnvelopeSchema = z
  .object({
    schemaVersion: z.literal(1),
    kind: offlineDocumentKindSchema,
    ownerId: publicIdSchema,
    resourceParts: z.array(resourcePartSchema).min(1).max(8),
    version: cacheVersionSchema,
    fetchedAt: z.iso.datetime(),
    expiresAt: z.iso.datetime(),
    payload: z.unknown(),
  })
  .strict()
  .superRefine((envelope, context) => {
    if (Date.parse(envelope.expiresAt) <= Date.parse(envelope.fetchedAt)) {
      context.addIssue({
        code: 'custom',
        message: 'Offline document expiry must follow its fetch time',
        path: ['expiresAt'],
      })
    }
  })
export type OfflineDocumentEnvelope = z.infer<typeof offlineDocumentEnvelopeSchema>

export interface OfflineDocumentDescriptor {
  ownerId: string
  kind: OfflineDocumentKind
  resourceParts: readonly string[]
}

export interface OfflineDocumentSnapshot<T> {
  data: T
  version: string
  fetchedAt: string
  expiresAt: string
  stale: boolean
}

export interface OfflineDocumentCacheOptions {
  now?: () => Date
  ttlMilliseconds?: number
  maxEntries?: number
  maxBytes?: number
}

export interface OfflineDocumentUsage {
  entries: number
  bytes: number
}

export const DEFAULT_OFFLINE_DOCUMENT_TTL_MS = 24 * 60 * 60 * 1_000
export const DEFAULT_OFFLINE_DOCUMENT_MAX_ENTRIES = 500
export const DEFAULT_OFFLINE_DOCUMENT_MAX_BYTES = 10 * 1_024 * 1_024

interface PayloadParser<T> {
  parse(payload: unknown): T
}

function parsedDescriptor(descriptor: OfflineDocumentDescriptor) {
  return {
    ownerId: publicIdSchema.parse(descriptor.ownerId),
    kind: offlineDocumentKindSchema.parse(descriptor.kind),
    resourceParts: z.array(resourcePartSchema).min(1).max(8).parse(descriptor.resourceParts),
  }
}

export function offlineDocumentKey(descriptor: OfflineDocumentDescriptor): string {
  const parsed = parsedDescriptor(descriptor)
  // JSON tuple encoding is unambiguous even when a public ID contains ':' or '/'.
  return JSON.stringify([parsed.ownerId, parsed.kind, ...parsed.resourceParts])
}

function approximateBytes(record: CachedDocument): number {
  return new TextEncoder().encode(JSON.stringify(record)).byteLength
}

export async function offlineDocumentUsage(
  database: VmshOfflineDatabase,
  ownerId: string,
): Promise<OfflineDocumentUsage> {
  const parsedOwnerId = publicIdSchema.parse(ownerId)
  const records = await database.documents.where('ownerId').equals(parsedOwnerId).toArray()
  return {
    entries: records.length,
    bytes: records.reduce((total, record) => total + approximateBytes(record), 0),
  }
}

export async function pruneOfflineDocuments(
  database: VmshOfflineDatabase,
  ownerId: string,
  options: Pick<OfflineDocumentCacheOptions, 'maxBytes' | 'maxEntries'> = {},
): Promise<OfflineDocumentUsage> {
  const parsedOwnerId = publicIdSchema.parse(ownerId)
  const maxEntries = options.maxEntries ?? DEFAULT_OFFLINE_DOCUMENT_MAX_ENTRIES
  const maxBytes = options.maxBytes ?? DEFAULT_OFFLINE_DOCUMENT_MAX_BYTES
  if (!Number.isSafeInteger(maxEntries) || maxEntries < 1) {
    throw new RangeError('Offline document entry budget must be a positive integer')
  }
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1) {
    throw new RangeError('Offline document byte budget must be a positive integer')
  }

  const records = (await database.documents.where('ownerId').equals(parsedOwnerId).toArray()).sort(
    (left, right) =>
      left.cachedAt.localeCompare(right.cachedAt) || left.key.localeCompare(right.key),
  )
  let bytes = records.reduce((total, record) => total + approximateBytes(record), 0)
  let entries = records.length
  const deleteKeys: string[] = []
  for (const record of records) {
    if (entries <= maxEntries && bytes <= maxBytes) break
    deleteKeys.push(record.key)
    entries -= 1
    bytes -= approximateBytes(record)
  }
  if (deleteKeys.length > 0) await database.documents.bulkDelete(deleteKeys)
  return { entries, bytes }
}

export async function writeOfflineDocument<T>(
  database: VmshOfflineDatabase,
  descriptor: OfflineDocumentDescriptor,
  version: string,
  payload: T,
  parser: PayloadParser<T>,
  options: OfflineDocumentCacheOptions = {},
): Promise<OfflineDocumentSnapshot<T>> {
  const parsed = parsedDescriptor(descriptor)
  const validatedPayload = parser.parse(payload)
  const now = options.now?.() ?? new Date()
  const ttlMilliseconds = options.ttlMilliseconds ?? DEFAULT_OFFLINE_DOCUMENT_TTL_MS
  if (!Number.isSafeInteger(ttlMilliseconds) || ttlMilliseconds < 1) {
    throw new RangeError('Offline document TTL must be a positive integer')
  }
  const envelope = offlineDocumentEnvelopeSchema.parse({
    schemaVersion: 1,
    ...parsed,
    version: cacheVersionSchema.parse(version),
    fetchedAt: now.toISOString(),
    expiresAt: new Date(now.getTime() + ttlMilliseconds).toISOString(),
    payload: validatedPayload,
  })
  await database.documents.put({
    key: offlineDocumentKey(parsed),
    ownerId: parsed.ownerId,
    version: envelope.version,
    cachedAt: envelope.fetchedAt,
    payload: envelope,
  })
  await pruneOfflineDocuments(database, parsed.ownerId, options)
  return {
    data: validatedPayload,
    version: envelope.version,
    fetchedAt: envelope.fetchedAt,
    expiresAt: envelope.expiresAt,
    stale: false,
  }
}

export async function readOfflineDocument<T>(
  database: VmshOfflineDatabase,
  descriptor: OfflineDocumentDescriptor,
  parser: PayloadParser<T>,
  options: Pick<OfflineDocumentCacheOptions, 'now'> = {},
): Promise<OfflineDocumentSnapshot<T> | null> {
  const parsed = parsedDescriptor(descriptor)
  const key = offlineDocumentKey(parsed)
  const stored = await database.documents.get(key)
  if (!stored) return null

  const envelopeResult = offlineDocumentEnvelopeSchema.safeParse(stored.payload)
  if (!envelopeResult.success) {
    await database.documents.delete(key)
    return null
  }
  const envelope = envelopeResult.data
  const matches =
    stored.ownerId === parsed.ownerId &&
    stored.version === envelope.version &&
    stored.cachedAt === envelope.fetchedAt &&
    envelope.ownerId === parsed.ownerId &&
    envelope.kind === parsed.kind &&
    envelope.resourceParts.length === parsed.resourceParts.length &&
    envelope.resourceParts.every((part, index) => part === parsed.resourceParts[index])
  let data: T
  try {
    data = parser.parse(envelope.payload)
  } catch {
    await database.documents.delete(key)
    return null
  }
  if (!matches) {
    await database.documents.delete(key)
    return null
  }

  return {
    data,
    version: envelope.version,
    fetchedAt: envelope.fetchedAt,
    expiresAt: envelope.expiresAt,
    stale: Date.parse(envelope.expiresAt) <= (options.now?.() ?? new Date()).getTime(),
  }
}
