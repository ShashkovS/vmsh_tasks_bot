import { z } from 'zod'

import {
  ApiResponseError,
  createWrittenEntryRequestSchema,
  publicIdSchema,
  submitWrittenEntryResponseSchema,
  writtenProblemRevisionSchema,
  type CreateWrittenAttachmentResponse,
  type CreateWrittenEntryRequest,
  type CreateWrittenEntryResponse,
  type MutateWrittenAttachmentsResponse,
  type ReorderWrittenAttachmentsRequest,
  type SubmitWrittenEntryRequest,
  type SubmitWrittenEntryResponse,
  type WrittenAttachmentUploadMetadata,
  type WrittenProblemRevision,
} from '@vmsh/contracts'

import { type OutboxItem, type VmshOfflineDatabase } from './database'
import {
  writtenDraftDescriptorSchema,
  writtenDraftServerStateSchema,
  type WrittenDraftDescriptor,
  type WrittenSubmissionDraftStore,
} from './written-submission-draft'

/**
 * Resumable Phase-5 pipeline. Every remote step owns a stable idempotency key,
 * while server versions and local→remote photo identity are checkpointed after
 * each receipt. See `dev/development-plan/09-phase-5-written-submissions.md`.
 */

export const WRITTEN_SUBMISSION_OUTBOX_VERSION = 1 as const

const writtenOutboxPhotoSchema = z
  .object({
    localPhotoId: z.uuid(),
    fileName: z.string().trim().min(1).max(255),
    mediaType: z.string().trim().min(1).max(100),
    byteSize: z
      .number()
      .int()
      .positive()
      .max(25 * 1024 * 1024),
    ordinal: z.number().int().min(0).max(9),
    uploadIdempotencyKey: z.uuid(),
    serverAttachmentId: publicIdSchema.nullable(),
  })
  .strict()
export type WrittenOutboxPhoto = z.infer<typeof writtenOutboxPhotoSchema>

export const writtenSubmissionOutboxPayloadSchema = z
  .object({
    schemaVersion: z.literal(WRITTEN_SUBMISSION_OUTBOX_VERSION),
    draftKey: z.string().min(1).max(1_024),
    descriptor: writtenDraftDescriptorSchema,
    problemRevision: writtenProblemRevisionSchema,
    text: z.string().max(100_000).nullable(),
    clientCreatedAt: z.iso.datetime(),
    createIdempotencyKey: z.uuid(),
    reorderIdempotencyKey: z.uuid(),
    submitIdempotencyKey: z.uuid(),
    photos: z.array(writtenOutboxPhotoSchema).max(10),
    serverState: writtenDraftServerStateSchema.nullable(),
    reordered: z.boolean(),
  })
  .strict()
  .superRefine((payload, context) => {
    if (
      payload.problemRevision.conditionRevisionId !== payload.descriptor.conditionRevisionId ||
      payload.problemRevision.configVersion !== payload.descriptor.configVersion
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Outbox revision must match its local draft descriptor',
        path: ['problemRevision'],
      })
    }
    const localIds = payload.photos.map((photo) => photo.localPhotoId)
    const ordinals = payload.photos.map((photo) => photo.ordinal)
    const attachmentIds = payload.photos
      .map((photo) => photo.serverAttachmentId)
      .filter((value): value is string => value !== null)
    if (
      new Set(localIds).size !== localIds.length ||
      new Set(ordinals).size !== ordinals.length ||
      new Set(attachmentIds).size !== attachmentIds.length
    ) {
      context.addIssue({
        code: 'custom',
        message: 'Written outbox photo identities and ordinals must be unique',
        path: ['photos'],
      })
    }
    if (payload.photos.some((photo, index) => photo.ordinal !== index)) {
      context.addIssue({
        code: 'custom',
        message: 'Written outbox photos must use dense snapshot order',
        path: ['photos'],
      })
    }
    if (
      payload.serverState === null &&
      payload.photos.some((photo) => photo.serverAttachmentId !== null)
    ) {
      context.addIssue({
        code: 'custom',
        message: 'A local-only entry cannot contain uploaded attachments',
        path: ['serverState'],
      })
    }
    if (payload.reordered && payload.photos.some((photo) => photo.serverAttachmentId === null)) {
      context.addIssue({
        code: 'custom',
        message: 'Reorder checkpoint requires every photo to be uploaded',
        path: ['reordered'],
      })
    }
  })
export type WrittenSubmissionOutboxPayload = z.infer<typeof writtenSubmissionOutboxPayloadSchema>

const writtenSubmissionOutboxItemSchema = z
  .object({
    id: z.uuid(),
    idempotencyKey: z.uuid(),
    ownerId: publicIdSchema,
    kind: z.literal('written-answer'),
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
    payload: writtenSubmissionOutboxPayloadSchema,
    result: submitWrittenEntryResponseSchema.optional(),
    lastError: z.string().min(1).max(300).optional(),
    deliveryLeaseId: z.uuid().optional(),
  })
  .strict()
  .superRefine((item, context) => {
    if (item.id !== item.idempotencyKey) {
      context.addIssue({
        code: 'custom',
        message: 'Outbox identity must equal its queue idempotency key',
        path: ['idempotencyKey'],
      })
    }
    if (item.ownerId !== item.payload.descriptor.ownerId) {
      context.addIssue({
        code: 'custom',
        message: 'Outbox owner must match its draft owner',
        path: ['ownerId'],
      })
    }
    if ((item.status === 'synced') !== (item.result !== undefined)) {
      context.addIssue({
        code: 'custom',
        message: 'Only a synced outbox item may contain a submit receipt',
        path: ['result'],
      })
    }
    if ((item.status === 'sending') !== (item.deliveryLeaseId !== undefined)) {
      context.addIssue({
        code: 'custom',
        message: 'Only a sending item owns a delivery lease',
        path: ['deliveryLeaseId'],
      })
    }
  })
export type WrittenSubmissionOutboxItem = z.infer<typeof writtenSubmissionOutboxItemSchema>

export interface WrittenSubmissionTransport {
  create(problemId: string, request: CreateWrittenEntryRequest): Promise<CreateWrittenEntryResponse>
  upload(
    entryId: string,
    upload: {
      metadata: WrittenAttachmentUploadMetadata
      asset: Blob
      fileName: string
    },
  ): Promise<CreateWrittenAttachmentResponse>
  reorder(
    entryId: string,
    request: ReorderWrittenAttachmentsRequest,
  ): Promise<MutateWrittenAttachmentsResponse>
  submit(entryId: string, request: SubmitWrittenEntryRequest): Promise<SubmitWrittenEntryResponse>
}

export type WrittenSubmissionDeliveryResult =
  | { state: 'idle' }
  | {
      state: 'synced'
      item: WrittenSubmissionOutboxItem
      receipt: SubmitWrittenEntryResponse
    }
  | {
      state: 'retrying' | 'conflict' | 'failed'
      item: WrittenSubmissionOutboxItem
      error: unknown
    }

export interface WrittenSubmissionOutboxOptions {
  now?: () => Date
  randomUUID?: () => string
  payloadHasher?: (payload: WrittenSubmissionOutboxPayload) => Promise<string>
  sendingLeaseMilliseconds?: number
}

export interface WrittenSubmissionOutbox {
  enqueue(descriptor: WrittenDraftDescriptor): Promise<WrittenSubmissionOutboxItem>
  list(): Promise<WrittenSubmissionOutboxItem[]>
  deliverNext(transport: WrittenSubmissionTransport): Promise<WrittenSubmissionDeliveryResult>
  acknowledge(itemId: string): Promise<boolean>
}

export class WrittenSubmissionLocalEvidenceError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'WrittenSubmissionLocalEvidenceError'
  }
}

export class WrittenSubmissionLeaseLostError extends Error {
  constructor() {
    super('Written-submission delivery lease was superseded')
    this.name = 'WrittenSubmissionLeaseLostError'
  }
}

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

async function sha256Payload(payload: WrittenSubmissionOutboxPayload): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error('Web Crypto is unavailable')
  const bytes = new TextEncoder().encode(canonicalJson(payload))
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes)
  return `sha256:${[...new Uint8Array(digest)]
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')}`
}

function validatedItem(item: OutboxItem): WrittenSubmissionOutboxItem {
  return writtenSubmissionOutboxItemSchema.parse(item)
}

function serverState(
  response:
    CreateWrittenEntryResponse | MutateWrittenAttachmentsResponse | SubmitWrittenEntryResponse,
) {
  return writtenDraftServerStateSchema.parse({
    threadId: response.threadId,
    threadVersion: response.threadVersion,
    entryId: response.entry.entryId,
    entryVersion: response.entry.version,
  })
}

function failureLabel(error: unknown): string {
  if (error instanceof ApiResponseError) return `api:${error.status}:${error.code}`
  if (error instanceof WrittenSubmissionLocalEvidenceError) return 'client:local-evidence-missing'
  if (error instanceof WrittenSubmissionLeaseLostError) return 'client:delivery-lease-lost'
  if (error instanceof DOMException) return `dom:${error.name}`
  if (error instanceof Error) return `client:${error.name}`
  return 'client:unknown'
}

function failureState(error: unknown): 'retrying' | 'conflict' | 'failed' {
  if (
    error instanceof WrittenSubmissionLocalEvidenceError ||
    error instanceof WrittenSubmissionLeaseLostError
  ) {
    return 'conflict'
  }
  if (error instanceof ApiResponseError) {
    if (
      error.code === 'idempotency_payload_mismatch' ||
      error.code === 'written_problem_revision_changed' ||
      error.code.includes('version_conflict') ||
      error.code === 'written_attachment_ordinal_conflict' ||
      error.code.includes('locked')
    ) {
      return 'conflict'
    }
    if (error.status === 429 || error.status >= 500) return 'retrying'
    return 'failed'
  }
  if (
    error instanceof TypeError ||
    (error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'WrittenSubmissionNetworkError')
  ) {
    return 'retrying'
  }
  return 'failed'
}

function assertResponseIdentity(
  item: WrittenSubmissionOutboxItem,
  response: CreateWrittenEntryResponse,
): void {
  if (
    response.problemId !== item.payload.descriptor.problemId ||
    response.entry.problemRevision?.conditionRevisionId !==
      item.payload.problemRevision.conditionRevisionId ||
    response.entry.problemRevision.configVersion !== item.payload.problemRevision.configVersion
  ) {
    throw new WrittenSubmissionLocalEvidenceError('Server receipt does not match queued evidence')
  }
}

function isBlobLike(value: unknown): value is Blob {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Blob).size === 'number' &&
    typeof (value as Blob).type === 'string' &&
    typeof (value as Blob).arrayBuffer === 'function'
  )
}

export function createWrittenSubmissionOutbox(
  database: VmshOfflineDatabase,
  ownerId: string,
  draftStore: WrittenSubmissionDraftStore,
  options: WrittenSubmissionOutboxOptions = {},
): WrittenSubmissionOutbox {
  const parsedOwnerId = publicIdSchema.parse(ownerId)
  const now = options.now ?? (() => new Date())
  const randomUUID = options.randomUUID ?? (() => globalThis.crypto.randomUUID())
  const payloadHasher = options.payloadHasher ?? sha256Payload
  const sendingLeaseMilliseconds = options.sendingLeaseMilliseconds ?? 60_000
  if (!Number.isSafeInteger(sendingLeaseMilliseconds) || sendingLeaseMilliseconds < 1) {
    throw new RangeError('Outbox sending lease must be a positive integer')
  }

  async function claimNext(): Promise<WrittenSubmissionOutboxItem | null> {
    return database.transaction('rw', database.outbox, async () => {
      const leaseCutoff = new Date(now().getTime() - sendingLeaseMilliseconds).toISOString()
      const candidates = (await database.outbox.where('ownerId').equals(parsedOwnerId).toArray())
        .filter(
          (item) =>
            item.kind === 'written-answer' &&
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
      const parsed = writtenSubmissionOutboxItemSchema.safeParse(candidate)
      if (!parsed.success) {
        await database.outbox.update(candidate.id, {
          status: 'failed',
          updatedAtClient: now().toISOString(),
          lastError: 'client:invalid-outbox-record',
        })
        return null
      }
      const claimed = writtenSubmissionOutboxItemSchema.parse({
        ...parsed.data,
        status: 'sending',
        attempts: parsed.data.attempts + 1,
        updatedAtClient: now().toISOString(),
        deliveryLeaseId: randomUUID(),
        lastError: undefined,
      })
      await database.outbox.put(claimed)
      return claimed
    })
  }

  async function checkpoint(
    item: WrittenSubmissionOutboxItem,
    payload: WrittenSubmissionOutboxPayload,
  ): Promise<WrittenSubmissionOutboxItem> {
    const updated = await database.transaction('rw', database.outbox, async () => {
      const current = await database.outbox.get(item.id)
      const parsed = current ? writtenSubmissionOutboxItemSchema.parse(current) : null
      if (
        !parsed ||
        parsed.status !== 'sending' ||
        parsed.deliveryLeaseId !== item.deliveryLeaseId
      ) {
        throw new WrittenSubmissionLeaseLostError()
      }
      const next = writtenSubmissionOutboxItemSchema.parse({
        ...parsed,
        payload,
        updatedAtClient: now().toISOString(),
      })
      await database.outbox.put(next)
      return next
    })
    return updated
  }

  async function settle(
    item: WrittenSubmissionOutboxItem,
    state: 'retrying' | 'conflict' | 'failed',
    error: unknown,
  ): Promise<WrittenSubmissionOutboxItem> {
    await database.transaction('rw', database.outbox, async () => {
      const current = await database.outbox.get(item.id)
      const parsed = current ? writtenSubmissionOutboxItemSchema.safeParse(current) : null
      if (
        parsed?.success &&
        parsed.data.status === 'sending' &&
        parsed.data.deliveryLeaseId === item.deliveryLeaseId
      ) {
        const next = { ...parsed.data, status: state, updatedAtClient: now().toISOString() }
        delete next.deliveryLeaseId
        await database.outbox.put({ ...next, lastError: failureLabel(error) })
      }
    })
    const stored = await database.outbox.get(item.id)
    if (stored) return validatedItem(stored)
    const fallback = { ...item, status, updatedAtClient: now().toISOString() }
    delete fallback.deliveryLeaseId
    return writtenSubmissionOutboxItemSchema.parse({
      ...fallback,
      lastError: failureLabel(error),
    })
  }

  return {
    async enqueue(value) {
      const parsedDescriptor = writtenDraftDescriptorSchema.parse(value)
      if (parsedDescriptor.ownerId !== parsedOwnerId) {
        throw new TypeError('Written outbox owner does not match its draft')
      }
      const existing = (await database.outbox.where('ownerId').equals(parsedOwnerId).toArray())
        .filter((item) => item.kind === 'written-answer')
        .map((item) => writtenSubmissionOutboxItemSchema.safeParse(item))
        .filter((item) => item.success)
        .map((item) => item.data)
        .find(
          (item) =>
            item.payload.descriptor.problemId === parsedDescriptor.problemId &&
            item.payload.descriptor.conditionRevisionId === parsedDescriptor.conditionRevisionId &&
            item.payload.descriptor.configVersion === parsedDescriptor.configVersion,
        )
      if (existing) return existing

      const loaded = await draftStore.load(parsedDescriptor)
      const draft = loaded.compatible
      if (!draft) throw new WrittenSubmissionLocalEvidenceError('Written draft is unavailable')
      const text = draft.text.trim() ? draft.text : null
      if (text === null && draft.photos.length === 0) {
        throw new TypeError('Written submission cannot be empty')
      }
      const timestamp = now().toISOString()
      const problemRevision: WrittenProblemRevision = {
        conditionRevisionId: parsedDescriptor.conditionRevisionId,
        configVersion: parsedDescriptor.configVersion,
      }
      const payload = writtenSubmissionOutboxPayloadSchema.parse({
        schemaVersion: WRITTEN_SUBMISSION_OUTBOX_VERSION,
        draftKey: draftStore.key(parsedDescriptor),
        descriptor: parsedDescriptor,
        problemRevision,
        text,
        clientCreatedAt: timestamp,
        createIdempotencyKey: randomUUID(),
        reorderIdempotencyKey: randomUUID(),
        submitIdempotencyKey: randomUUID(),
        photos: draft.photos.map((photo, ordinal) => ({
          localPhotoId: photo.id,
          fileName: photo.fileName,
          mediaType: photo.mediaType,
          byteSize: photo.byteSize,
          ordinal,
          uploadIdempotencyKey: randomUUID(),
          serverAttachmentId: photo.serverAttachmentId,
        })),
        serverState: draft.serverState,
        reordered: false,
      })
      const idempotencyKey = randomUUID()
      const item = writtenSubmissionOutboxItemSchema.parse({
        id: idempotencyKey,
        idempotencyKey,
        ownerId: parsedOwnerId,
        kind: 'written-answer',
        createdAtClient: timestamp,
        updatedAtClient: timestamp,
        timezoneOffsetMinutes: now().getTimezoneOffset(),
        payloadHash: await payloadHasher(payload),
        status: 'queued',
        attempts: 0,
        payload,
      })
      await database.outbox.add(item)
      return item
    },

    async list() {
      return (await database.outbox.where('ownerId').equals(parsedOwnerId).toArray())
        .filter((item) => item.kind === 'written-answer')
        .map(validatedItem)
        .sort(
          (left, right) =>
            left.createdAtClient.localeCompare(right.createdAtClient) ||
            left.id.localeCompare(right.id),
        )
    },

    async deliverNext(transport) {
      let item = await claimNext()
      if (!item) return { state: 'idle' }
      try {
        if (item.payload.serverState === null) {
          const request = createWrittenEntryRequestSchema.parse({
            schemaVersion: 1,
            idempotencyKey: item.payload.createIdempotencyKey,
            problemRevision: item.payload.problemRevision,
            text: item.payload.text,
            clientCreatedAt: item.payload.clientCreatedAt,
          })
          const response = await transport.create(item.payload.descriptor.problemId, request)
          assertResponseIdentity(item, response)
          item = await checkpoint(item, {
            ...item.payload,
            serverState: serverState(response),
          })
        }

        for (const photo of item.payload.photos) {
          if (photo.serverAttachmentId !== null) continue
          const state = item.payload.serverState
          if (!state) throw new WrittenSubmissionLocalEvidenceError('Server draft is missing')
          const local = await database.writtenDraftPhotos.get(photo.localPhotoId)
          if (
            !local ||
            local.ownerId !== parsedOwnerId ||
            local.draftKey !== item.payload.draftKey ||
            local.byteSize !== photo.byteSize ||
            local.mediaType !== photo.mediaType ||
            !isBlobLike(local.blob) ||
            local.blob.size !== photo.byteSize ||
            local.blob.type !== photo.mediaType
          ) {
            throw new WrittenSubmissionLocalEvidenceError(
              `Local written photo ${photo.localPhotoId} is unavailable`,
            )
          }
          const response = await transport.upload(state.entryId, {
            metadata: {
              schemaVersion: 1,
              idempotencyKey: photo.uploadIdempotencyKey,
              expectedEntryVersion: state.entryVersion,
              expectedThreadVersion: state.threadVersion,
              ordinal: photo.ordinal,
            },
            asset: local.blob,
            fileName: photo.fileName,
          })
          assertResponseIdentity(item, response)
          const attachment = response.entry.attachments.find(
            (candidate) => candidate.ordinal === photo.ordinal,
          )
          if (!attachment) {
            throw new WrittenSubmissionLocalEvidenceError(
              'Attachment receipt does not contain the uploaded page',
            )
          }
          item = await checkpoint(item, {
            ...item.payload,
            serverState: serverState(response),
            photos: item.payload.photos.map((candidate) =>
              candidate.localPhotoId === photo.localPhotoId
                ? { ...candidate, serverAttachmentId: attachment.attachmentId }
                : candidate,
            ),
          })
        }

        if (item.payload.photos.length > 0 && !item.payload.reordered) {
          const state = item.payload.serverState
          if (!state) throw new WrittenSubmissionLocalEvidenceError('Server draft is missing')
          const attachmentIds = item.payload.photos.map((photo) => {
            if (!photo.serverAttachmentId) {
              throw new WrittenSubmissionLocalEvidenceError('Uploaded page identity is missing')
            }
            return photo.serverAttachmentId
          })
          const response = await transport.reorder(state.entryId, {
            schemaVersion: 1,
            idempotencyKey: item.payload.reorderIdempotencyKey,
            expectedEntryVersion: state.entryVersion,
            expectedThreadVersion: state.threadVersion,
            attachmentIds,
          })
          item = await checkpoint(item, {
            ...item.payload,
            serverState: serverState(response),
            reordered: true,
          })
        }

        const state = item.payload.serverState
        if (!state) throw new WrittenSubmissionLocalEvidenceError('Server draft is missing')
        const attachmentIds = item.payload.photos.map((photo) => {
          if (!photo.serverAttachmentId) {
            throw new WrittenSubmissionLocalEvidenceError('Uploaded page identity is missing')
          }
          return photo.serverAttachmentId
        })
        const receipt = await transport.submit(state.entryId, {
          schemaVersion: 1,
          idempotencyKey: item.payload.submitIdempotencyKey,
          expectedEntryVersion: state.entryVersion,
          expectedThreadVersion: state.threadVersion,
          attachmentIds,
        })
        if (
          receipt.problemId !== item.payload.descriptor.problemId ||
          receipt.entry.entryId !== state.entryId
        ) {
          throw new WrittenSubmissionLocalEvidenceError(
            'Submit receipt does not match queued evidence',
          )
        }
        const submittedItem = item
        const synced = await database.transaction('rw', database.outbox, async () => {
          const current = await database.outbox.get(submittedItem.id)
          const parsed = current ? writtenSubmissionOutboxItemSchema.parse(current) : null
          if (
            !parsed ||
            parsed.status !== 'sending' ||
            parsed.deliveryLeaseId !== submittedItem.deliveryLeaseId
          ) {
            throw new WrittenSubmissionLeaseLostError()
          }
          const next = { ...parsed, status: 'synced' as const, result: receipt }
          delete next.deliveryLeaseId
          const validated = writtenSubmissionOutboxItemSchema.parse({
            ...next,
            payload: { ...next.payload, serverState: serverState(receipt) },
            updatedAtClient: now().toISOString(),
          })
          await database.outbox.put(validated)
          return validated
        })
        return { state: 'synced', item: synced, receipt }
      } catch (error) {
        if (error instanceof WrittenSubmissionLeaseLostError) return { state: 'idle' }
        const state = failureState(error)
        const settled = await settle(item, state, error)
        return { state, item: settled, error }
      }
    },

    async acknowledge(itemId) {
      const parsedItemId = z.uuid().parse(itemId)
      const stored = await database.outbox.get(parsedItemId)
      if (!stored || stored.ownerId !== parsedOwnerId || stored.kind !== 'written-answer') {
        return false
      }
      const item = writtenSubmissionOutboxItemSchema.parse(stored)
      if (item.status !== 'synced') return false
      await draftStore.clear(item.payload.descriptor)
      await database.outbox.delete(item.id)
      return true
    },
  }
}
