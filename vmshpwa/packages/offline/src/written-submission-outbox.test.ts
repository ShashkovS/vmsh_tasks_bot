// @vitest-environment node

import 'fake-indexeddb/auto'

import { afterEach, describe, expect, it } from 'vitest'

import {
  ApiResponseError,
  type CreateWrittenAttachmentResponse,
  type CreateWrittenEntryRequest,
  type CreateWrittenEntryResponse,
  type MutateWrittenAttachmentsResponse,
  type ReorderWrittenAttachmentsRequest,
  type ReplaceWrittenEntryRequest,
  type ReplaceWrittenEntryResponse,
  type SubmitWrittenEntryRequest,
  type SubmitWrittenEntryResponse,
  type WrittenAttachment,
  type WrittenAttachmentUploadMetadata,
} from '@vmsh/contracts'

import { VmshOfflineDatabase } from './database'
import {
  createWrittenSubmissionDraftStore,
  type WrittenDraftDescriptor,
} from './written-submission-draft'
import {
  createWrittenSubmissionOutbox,
  type WrittenSubmissionTransport,
} from './written-submission-outbox'
import { type LocalDraftStorage } from './test-answer-draft'

const NOW = new Date('2026-07-28T13:00:00.000Z')
const HASH = `sha256:${'0'.repeat(64)}`
const PHOTO_ONE = '00000000-0000-4000-8000-000000000001'
const PHOTO_TWO = '00000000-0000-4000-8000-000000000002'

class MemoryStorage implements LocalDraftStorage {
  readonly values = new Map<string, string>()

  get length() {
    return this.values.size
  }

  getItem(key: string) {
    return this.values.get(key) ?? null
  }

  key(index: number) {
    return [...this.values.keys()][index] ?? null
  }

  removeItem(key: string) {
    this.values.delete(key)
  }

  setItem(key: string, value: string) {
    this.values.set(key, value)
  }
}

const databases = new Set<VmshOfflineDatabase>()

afterEach(async () => {
  await Promise.all(
    [...databases].map(async (database) => {
      database.close()
      await database.delete()
    }),
  )
  databases.clear()
})

function database(instance: string): VmshOfflineDatabase {
  const value = new VmshOfflineDatabase({ audience: 'student', instance })
  databases.add(value)
  return value
}

function descriptor(): WrittenDraftDescriptor {
  return {
    ownerId: 'account-student-one',
    problemId: 'problem-written-one',
    conditionRevisionId: 'condition-revision-one',
    configVersion: 3,
  }
}

function uuidFactory() {
  let next = 100
  return () => `00000000-0000-4000-8000-${String(next++).padStart(12, '0')}`
}

function stores(instance: string) {
  const storage = new MemoryStorage()
  const target = database(instance)
  const draft = createWrittenSubmissionDraftStore(
    { audience: 'student', instance },
    storage,
    target,
    { now: () => NOW, randomUUID: uuidFactory() },
  )
  const outbox = createWrittenSubmissionOutbox(target, descriptor().ownerId, draft, {
    now: () => NOW,
    randomUUID: uuidFactory(),
    payloadHasher: () => Promise.resolve(HASH),
  })
  return { storage, target, draft, outbox }
}

async function addPhoto(
  draft: ReturnType<typeof createWrittenSubmissionDraftStore>,
  id: string,
  value: string,
) {
  await draft.addPhoto(descriptor(), {
    id,
    fileName: `${id}.webp`,
    blob: new Blob([value], { type: 'image/webp' }),
    width: 100,
    height: 100,
    processing: 'client-webp',
  })
}

class RecordingTransport implements WrittenSubmissionTransport {
  readonly calls: Array<{ operation: string; request: unknown }> = []
  readonly attachments: WrittenAttachment[] = []
  entryVersion = 0
  threadVersion = 0
  failUploadOrdinalOnce: number | null = null

  create(
    problemId: string,
    request: CreateWrittenEntryRequest,
  ): Promise<CreateWrittenEntryResponse> {
    this.calls.push({ operation: 'create', request })
    this.entryVersion = 1
    this.threadVersion = 1
    return Promise.resolve({
      schemaVersion: 1,
      threadId: 'written-thread-one',
      problemId,
      threadStatus: 'open',
      threadVersion: this.threadVersion,
      entry: {
        entryId: 'written-entry-one',
        authorKind: 'student',
        entryKind: 'submission',
        state: 'draft',
        text: request.text,
        problemRevision: request.problemRevision,
        version: this.entryVersion,
        clientCreatedAt: request.clientCreatedAt,
        serverReceivedAt: '2026-07-28T13:00:01.000Z',
        attachments: [],
      },
      requestId: 'request-create',
    })
  }

  upload(
    _entryId: string,
    upload: {
      metadata: WrittenAttachmentUploadMetadata
      asset: Blob
      fileName: string
    },
  ): Promise<CreateWrittenAttachmentResponse> {
    this.calls.push({ operation: `upload-${upload.metadata.ordinal}`, request: upload })
    if (this.failUploadOrdinalOnce === upload.metadata.ordinal) {
      this.failUploadOrdinalOnce = null
      const error = new Error('offline')
      error.name = 'WrittenSubmissionNetworkError'
      return Promise.reject(error)
    }
    expect(upload.metadata.expectedEntryVersion).toBe(this.entryVersion)
    expect(upload.metadata.expectedThreadVersion).toBe(this.threadVersion)
    this.entryVersion += 1
    this.threadVersion += 1
    this.attachments.push({
      attachmentId: `written-attachment-${upload.metadata.ordinal}`,
      ordinal: upload.metadata.ordinal,
      uploadStatus: 'stored',
      mediaId: `written-media-${upload.metadata.ordinal}`,
      publicUrl: null,
      mediaPath: `/student/api/v1/thread-entries/written-entry-one/attachments/written-attachment-${upload.metadata.ordinal}/media`,
      mediaType: 'image/webp',
      width: 100,
      height: 100,
    })
    return Promise.resolve(
      this.mutation<CreateWrittenAttachmentResponse>('draft', 'open', 'request-upload'),
    )
  }

  reorder(
    _entryId: string,
    request: ReorderWrittenAttachmentsRequest,
  ): Promise<MutateWrittenAttachmentsResponse> {
    this.calls.push({ operation: 'reorder', request })
    expect(request.expectedEntryVersion).toBe(this.entryVersion)
    expect(request.expectedThreadVersion).toBe(this.threadVersion)
    return Promise.resolve({
      ...this.mutation<MutateWrittenAttachmentsResponse>('draft', 'open', 'request-reorder'),
      changed: false,
    })
  }

  submit(
    _entryId: string,
    request: SubmitWrittenEntryRequest,
  ): Promise<SubmitWrittenEntryResponse> {
    this.calls.push({ operation: 'submit', request })
    expect(request.expectedEntryVersion).toBe(this.entryVersion)
    expect(request.expectedThreadVersion).toBe(this.threadVersion)
    this.entryVersion += 1
    this.threadVersion += 1
    return Promise.resolve({
      ...this.mutation<SubmitWrittenEntryResponse>(
        'submitted',
        'awaiting_review',
        'request-submit',
      ),
      clockSuspicious: false,
    })
  }

  replace(
    _entryId: string,
    request: ReplaceWrittenEntryRequest,
  ): Promise<ReplaceWrittenEntryResponse> {
    this.calls.push({ operation: 'replace', request })
    expect(request.expectedEntryVersion).toBe(this.entryVersion)
    expect(request.expectedThreadVersion).toBe(this.threadVersion)
    this.entryVersion += 1
    this.threadVersion += 1
    return Promise.resolve({
      ...this.mutation<ReplaceWrittenEntryResponse>(
        'submitted',
        'awaiting_review',
        'request-replace',
      ),
      replacedEntryId: request.replacedEntryId,
      replacementEventId: 'written-replacement-one',
      clockSuspicious: false,
    })
  }

  private mutation<T>(
    state: 'draft' | 'submitted',
    threadStatus: 'open' | 'awaiting_review',
    requestId: string,
  ): T {
    return {
      schemaVersion: 1,
      threadId: 'written-thread-one',
      problemId: descriptor().problemId,
      threadStatus,
      threadVersion: this.threadVersion,
      entry: {
        entryId: 'written-entry-one',
        authorKind: 'student',
        entryKind: 'submission',
        state,
        text: 'Текст решения',
        problemRevision: {
          conditionRevisionId: descriptor().conditionRevisionId,
          configVersion: descriptor().configVersion,
        },
        version: this.entryVersion,
        clientCreatedAt: NOW.toISOString(),
        serverReceivedAt: '2026-07-28T13:00:01.000Z',
        attachments: this.attachments,
      },
      requestId,
    } as T
  }
}

describe('written-submission outbox', () => {
  it('snapshots text/order/bytes and returns the same queue item for duplicate enqueue', async () => {
    const { draft, outbox } = stores('written-enqueue')
    draft.saveText(descriptor(), 'Текст решения')
    draft.recordPaste(descriptor(), 14)
    await addPhoto(draft, PHOTO_ONE, 'first')
    await addPhoto(draft, PHOTO_TWO, 'second')
    draft.reorderPhotos(descriptor(), [PHOTO_TWO, PHOTO_ONE])

    const first = await outbox.enqueue(descriptor())
    const repeated = await outbox.enqueue(descriptor())

    expect(repeated.id).toBe(first.id)
    expect(first).toMatchObject({
      status: 'queued',
      payloadHash: HASH,
      payload: {
        text: 'Текст решения',
        pasteEvidence: {
          pasteCount: 1,
          pastedCharacterCount: 14,
          lastPastedAt: NOW.toISOString(),
        },
        problemRevision: { conditionRevisionId: 'condition-revision-one', configVersion: 3 },
        photos: [
          { localPhotoId: PHOTO_TWO, ordinal: 0, serverAttachmentId: null },
          { localPhotoId: PHOTO_ONE, ordinal: 1, serverAttachmentId: null },
        ],
      },
    })
    expect(
      new Set([
        first.payload.createIdempotencyKey,
        first.payload.reorderIdempotencyKey,
        first.payload.submitIdempotencyKey,
        ...first.payload.photos.map((photo) => photo.uploadIdempotencyKey),
      ]).size,
    ).toBe(5)
  })

  it('checkpoints create, every upload, reorder and submit before clearing on acknowledgement', async () => {
    const { target, draft, outbox } = stores('written-delivery')
    draft.saveText(descriptor(), 'Текст решения')
    await addPhoto(draft, PHOTO_ONE, 'first')
    await addPhoto(draft, PHOTO_TWO, 'second')
    const queued = await outbox.enqueue(descriptor())
    const transport = new RecordingTransport()

    const result = await outbox.deliverNext(transport)

    expect(result.state, 'item' in result ? result.item.lastError : undefined).toBe('synced')
    expect(transport.calls.map(({ operation }) => operation)).toEqual([
      'create',
      'upload-0',
      'upload-1',
      'reorder',
      'submit',
    ])
    const stored = (await outbox.list())[0]
    expect(stored).toMatchObject({
      id: queued.id,
      status: 'synced',
      attempts: 1,
      payload: {
        reordered: true,
        photos: [
          { serverAttachmentId: 'written-attachment-0' },
          { serverAttachmentId: 'written-attachment-1' },
        ],
        serverState: { entryVersion: 4, threadVersion: 4 },
      },
      result: { threadStatus: 'awaiting_review' },
    })
    expect((await draft.load(descriptor())).compatible?.text).toBe('Текст решения')

    await expect(outbox.acknowledge(queued.id)).resolves.toBe(true)
    expect(await outbox.list()).toEqual([])
    expect((await draft.load(descriptor())).compatible).toBeNull()
    expect(await target.writtenDraftPhotos.count()).toBe(0)
  })

  it('resumes at the failed photo without recreating or reuploading acknowledged pages', async () => {
    const { draft, outbox } = stores('written-resume')
    draft.saveText(descriptor(), 'Текст решения')
    await addPhoto(draft, PHOTO_ONE, 'first')
    await addPhoto(draft, PHOTO_TWO, 'second')
    await outbox.enqueue(descriptor())
    const transport = new RecordingTransport()
    transport.failUploadOrdinalOnce = 1

    const first = await outbox.deliverNext(transport)
    expect(first).toMatchObject({
      state: 'retrying',
      item: {
        status: 'retrying',
        payload: {
          photos: [{ serverAttachmentId: 'written-attachment-0' }, { serverAttachmentId: null }],
        },
      },
    })

    const second = await outbox.deliverNext(transport)
    expect(second.state).toBe('synced')
    expect(transport.calls.map(({ operation }) => operation)).toEqual([
      'create',
      'upload-0',
      'upload-1',
      'upload-1',
      'reorder',
      'submit',
    ])
    const failedUpload = transport.calls[2]?.request as {
      metadata: WrittenAttachmentUploadMetadata
    }
    const repeatedUpload = transport.calls[3]?.request as {
      metadata: WrittenAttachmentUploadMetadata
    }
    expect(repeatedUpload.metadata).toEqual(failedUpload.metadata)
    expect((await outbox.list())[0]?.attempts).toBe(2)
  })

  it('submits a text-only draft without inventing photo or reorder work', async () => {
    const { draft, outbox } = stores('written-text-only')
    draft.saveText(descriptor(), 'Только подробный текст')
    await outbox.enqueue(descriptor())
    const transport = new RecordingTransport()

    const result = await outbox.deliverNext(transport)

    expect(result.state).toBe('synced')
    expect(transport.calls.map(({ operation }) => operation)).toEqual(['create', 'submit'])
    expect((transport.calls[1]?.request as SubmitWrittenEntryRequest).attachmentIds).toEqual([])
  })

  it('persists replacement intent and atomically completes through replace instead of submit', async () => {
    const { draft, outbox } = stores('written-replacement')
    draft.saveText(descriptor(), 'Исправленное решение')
    draft.saveReplacementTarget(descriptor(), {
      entryId: 'written-entry-original',
      entryVersion: 7,
    })
    const queued = await outbox.enqueue(descriptor())
    const transport = new RecordingTransport()

    const result = await outbox.deliverNext(transport)

    expect(result.state).toBe('synced')
    expect(transport.calls.map(({ operation }) => operation)).toEqual(['create', 'replace'])
    expect(transport.calls[1]?.request).toMatchObject({
      replacedEntryId: 'written-entry-original',
      expectedReplacedEntryVersion: 7,
    })
    const stored = (await outbox.list())[0]
    expect(stored).toMatchObject({
      id: queued.id,
      status: 'synced',
      payload: {
        replacementTarget: { entryId: 'written-entry-original', entryVersion: 7 },
      },
      result: {
        replacedEntryId: 'written-entry-original',
        replacementEventId: 'written-replacement-one',
      },
    })
  })

  it.each([
    'written_replacement_unavailable',
    'written_replacement_target_changed',
    'written_attachment_locked',
  ])('recovers persisted %s with photos once, without erasing evidence', async (code) => {
    const { target, draft, outbox } = stores('replacement-recovery')
    draft.saveText(descriptor(), 'Исправление после проверки')
    await addPhoto(draft, PHOTO_ONE, 'photo evidence')
    draft.saveReplacementTarget(descriptor(), {
      entryId: 'written-entry-original',
      entryVersion: 7,
    })
    const queued = await outbox.enqueue(descriptor())
    const transport = new RecordingTransport()
    transport.replace = () =>
      Promise.reject(
        new ApiResponseError(409, {
          error: {
            code,
            message: 'Already reviewed',
            requestId: 'req-replacement',
          },
        }),
      )
    expect((await outbox.deliverNext(transport)).state).toBe(
      code.includes('locked') ? 'conflict' : 'failed',
    )
    const restored = createWrittenSubmissionOutbox(target, descriptor().ownerId, draft)
    const [first, second] = await Promise.all([
      restored.recoverReplacement(queued.id),
      restored.recoverReplacement(queued.id),
    ])
    expect(first.payload.createIdempotencyKey).toBe(second.payload.createIdempotencyKey)
    expect(first.payload.submitIdempotencyKey).not.toBe(queued.payload.submitIdempotencyKey)
    expect(first.payload.replacementTarget).toBeNull()
    expect(first.payload.text).toBe('Исправление после проверки')
    expect(first.payload.photos).toHaveLength(1)
    expect((await draft.load(descriptor())).compatible?.photos).toHaveLength(1)
    const freshTransport = new RecordingTransport()
    expect((await restored.deliverNext(freshTransport)).state).toBe('synced')
    expect(freshTransport.calls.map((call) => call.operation)).toEqual([
      'create',
      'upload-0',
      'submit',
    ])
    expect((await restored.deliverNext(transport)).state).toBe('idle')
    expect(await restored.acknowledge(queued.id)).toBe(true)
  })

  it('does not issue a redundant reorder request for one photo', async () => {
    const { draft, outbox } = stores('written-one-photo')
    await addPhoto(draft, PHOTO_ONE, 'first')
    await outbox.enqueue(descriptor())
    const transport = new RecordingTransport()

    const result = await outbox.deliverNext(transport)

    expect(result.state).toBe('synced')
    expect(transport.calls.map(({ operation }) => operation)).toEqual([
      'create',
      'upload-0',
      'submit',
    ])
  })

  it('stops with a recoverable conflict when local photo evidence disappeared', async () => {
    const { target, draft, outbox } = stores('written-missing')
    draft.saveText(descriptor(), 'Текст решения')
    await addPhoto(draft, PHOTO_ONE, 'first')
    await outbox.enqueue(descriptor())
    await target.writtenDraftPhotos.delete(PHOTO_ONE)
    const transport = new RecordingTransport()

    const result = await outbox.deliverNext(transport)

    expect(result).toMatchObject({
      state: 'conflict',
      item: { status: 'conflict', lastError: 'client:local-evidence-missing' },
    })
    expect(transport.calls.map(({ operation }) => operation)).toEqual(['create'])
  })

  it('does not overwrite a delivery lease superseded by another tab', async () => {
    const { target, draft, outbox } = stores('written-lease')
    draft.saveText(descriptor(), 'Текст решения')
    const queued = await outbox.enqueue(descriptor())
    const transport = new RecordingTransport()
    const originalCreate = transport.create.bind(transport)
    transport.create = async (problemId, request) => {
      const response = await originalCreate(problemId, request)
      await target.outbox.update(queued.id, {
        deliveryLeaseId: '00000000-0000-4000-8000-000000999999',
        updatedAtClient: '2026-07-28T13:00:01.000Z',
      })
      return response
    }

    await expect(outbox.deliverNext(transport)).resolves.toEqual({ state: 'idle' })
    expect((await target.outbox.get(queued.id))?.status).toBe('sending')
  })

  it('classifies an authoritative revision conflict without losing the queued snapshot', async () => {
    const { draft, outbox } = stores('written-api-conflict')
    draft.saveText(descriptor(), 'Текст решения')
    await outbox.enqueue(descriptor())
    const envelope = {
      error: {
        code: 'written_problem_revision_changed',
        message: 'Условие задачи изменилось',
        requestId: 'request-conflict',
      },
    }
    const transport = new RecordingTransport()
    transport.create = () => Promise.reject(new ApiResponseError(409, envelope))

    const result = await outbox.deliverNext(transport)

    expect(result).toMatchObject({
      state: 'conflict',
      item: {
        status: 'conflict',
        lastError: 'api:409:written_problem_revision_changed:request=request-conflict',
      },
    })
    expect((await draft.load(descriptor())).compatible?.text).toBe('Текст решения')
  })
})
