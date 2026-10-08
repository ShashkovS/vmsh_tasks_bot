import { z } from 'zod'

import {
  browserStorageNamespaceSchema,
  createBrowserStorageNamespace,
  publicIdSchema,
  runtimeInstanceSchema,
  type BrowserStorageNamespace,
} from '@vmsh/contracts'

import { offlineAudienceSchema, type OfflineAudience } from './database'

/**
 * Durable serializable draft for a single test-answer editor. Blobs and queued
 * mutations deliberately do not belong here. See the local draft contract in
 * `dev/development-plan/08-phase-4-test-submissions.md`; the submitting client
 * lives in `packages/app-shell/src/submission-client.ts`.
 */

export const TEST_ANSWER_DRAFT_VERSION = 1 as const

const testAnswerDraftRuntimeSchema = z
  .object({
    audience: offlineAudienceSchema,
    instance: runtimeInstanceSchema,
  })
  .strict()

export type TestAnswerDraftRuntime = z.infer<typeof testAnswerDraftRuntimeSchema>

export const testAnswerDraftDescriptorSchema = z
  .object({
    ownerId: publicIdSchema,
    problemId: publicIdSchema,
    conditionRevisionId: publicIdSchema,
    configVersion: z.number().int().positive(),
  })
  .strict()
export type TestAnswerDraftDescriptor = z.infer<typeof testAnswerDraftDescriptorSchema>

export const testAnswerDraftSchema = z
  .object({
    schemaVersion: z.literal(TEST_ANSWER_DRAFT_VERSION),
    namespace: browserStorageNamespaceSchema,
    audience: offlineAudienceSchema,
    ownerId: publicIdSchema,
    problemId: publicIdSchema,
    conditionRevisionId: publicIdSchema,
    configVersion: z.number().int().positive(),
    displayAnswer: z.string().max(16_384),
    updatedAt: z.iso.datetime(),
  })
  .strict()
  .superRefine((draft, context) => {
    const [, , namespaceAudience] = draft.namespace.split(':')
    if (namespaceAudience !== draft.audience) {
      context.addIssue({
        code: 'custom',
        message: 'Draft audience must match its browser namespace',
        path: ['audience'],
      })
    }
  })
export type TestAnswerDraft = z.infer<typeof testAnswerDraftSchema>

export interface TestAnswerDraftLoadResult {
  compatible: TestAnswerDraft | null
  incompatible: TestAnswerDraft[]
}

export interface LocalDraftStorage {
  readonly length: number
  getItem(key: string): string | null
  key(index: number): string | null
  removeItem(key: string): void
  setItem(key: string, value: string): void
}

export type TestAnswerDraftStorageOperation = 'enumerate' | 'read' | 'write' | 'remove'

export class TestAnswerDraftStorageError extends Error {
  readonly operation: TestAnswerDraftStorageOperation

  constructor(operation: TestAnswerDraftStorageOperation, cause: unknown) {
    super(`Test-answer draft storage failed during ${operation}`, { cause })
    this.name = 'TestAnswerDraftStorageError'
    this.operation = operation
  }
}

export interface TestAnswerDraftStoreOptions {
  now?: () => Date
}

export interface TestAnswerDraftStore {
  readonly audience: OfflineAudience
  readonly namespace: BrowserStorageNamespace
  key(descriptor: TestAnswerDraftDescriptor): string
  load(descriptor: TestAnswerDraftDescriptor): TestAnswerDraftLoadResult
  save(descriptor: TestAnswerDraftDescriptor, displayAnswer: string): TestAnswerDraft
  clear(descriptor: TestAnswerDraftDescriptor): void
  clearOwner(ownerId: string): void
}

const DRAFT_KEY_MARKER = ':draft:test-answer:'

function storagePrefix(namespace: BrowserStorageNamespace): string {
  return `${namespace}${DRAFT_KEY_MARKER}`
}

function parsedDescriptor(descriptor: TestAnswerDraftDescriptor): TestAnswerDraftDescriptor {
  return testAnswerDraftDescriptorSchema.parse(descriptor)
}

function draftKey(
  namespace: BrowserStorageNamespace,
  descriptor: TestAnswerDraftDescriptor,
): string {
  const parsed = parsedDescriptor(descriptor)
  // A JSON tuple avoids delimiter ambiguity without leaking answer content.
  return `${storagePrefix(namespace)}${JSON.stringify([
    parsed.ownerId,
    parsed.problemId,
    parsed.conditionRevisionId,
    parsed.configVersion,
  ])}`
}

function enumerateKeys(storage: LocalDraftStorage, prefix: string): string[] {
  try {
    const keys: string[] = []
    for (let index = 0; index < storage.length; index += 1) {
      const key = storage.key(index)
      if (key?.startsWith(prefix)) keys.push(key)
    }
    return keys
  } catch (error) {
    throw new TestAnswerDraftStorageError('enumerate', error)
  }
}

function readValue(storage: LocalDraftStorage, key: string): string | null {
  try {
    return storage.getItem(key)
  } catch (error) {
    throw new TestAnswerDraftStorageError('read', error)
  }
}

function removeValue(storage: LocalDraftStorage, key: string): void {
  try {
    storage.removeItem(key)
  } catch (error) {
    throw new TestAnswerDraftStorageError('remove', error)
  }
}

function parseStoredDraft(
  storage: LocalDraftStorage,
  key: string,
  expectedNamespace: BrowserStorageNamespace,
  expectedAudience: OfflineAudience,
): TestAnswerDraft | null {
  const raw = readValue(storage, key)
  if (raw === null) return null
  let payload: unknown
  try {
    payload = JSON.parse(raw)
  } catch {
    removeValue(storage, key)
    return null
  }
  const parsed = testAnswerDraftSchema.safeParse(payload)
  if (
    !parsed.success ||
    parsed.data.namespace !== expectedNamespace ||
    parsed.data.audience !== expectedAudience ||
    draftKey(expectedNamespace, {
      ownerId: parsed.data.ownerId,
      problemId: parsed.data.problemId,
      conditionRevisionId: parsed.data.conditionRevisionId,
      configVersion: parsed.data.configVersion,
    }) !== key
  ) {
    removeValue(storage, key)
    return null
  }
  return parsed.data
}

export function createTestAnswerDraftStore(
  runtime: TestAnswerDraftRuntime,
  storage: LocalDraftStorage,
  options: TestAnswerDraftStoreOptions = {},
): TestAnswerDraftStore {
  const parsedRuntime = testAnswerDraftRuntimeSchema.parse(runtime)
  const namespace = createBrowserStorageNamespace(parsedRuntime)
  const prefix = storagePrefix(namespace)
  const now = options.now ?? (() => new Date())

  return {
    audience: parsedRuntime.audience,
    namespace,

    key(descriptor) {
      return draftKey(namespace, descriptor)
    },

    load(descriptor) {
      const expected = parsedDescriptor(descriptor)
      const expectedKey = draftKey(namespace, expected)
      let compatible: TestAnswerDraft | null = null
      const incompatible: TestAnswerDraft[] = []
      for (const key of enumerateKeys(storage, prefix)) {
        const draft = parseStoredDraft(storage, key, namespace, parsedRuntime.audience)
        if (
          !draft ||
          draft.ownerId !== expected.ownerId ||
          draft.problemId !== expected.problemId
        ) {
          continue
        }
        if (key === expectedKey) compatible = draft
        else incompatible.push(draft)
      }
      incompatible.sort(
        (left, right) =>
          right.updatedAt.localeCompare(left.updatedAt) ||
          right.conditionRevisionId.localeCompare(left.conditionRevisionId) ||
          right.configVersion - left.configVersion,
      )
      return { compatible, incompatible }
    },

    save(descriptor, displayAnswer) {
      const parsed = parsedDescriptor(descriptor)
      const draft = testAnswerDraftSchema.parse({
        schemaVersion: TEST_ANSWER_DRAFT_VERSION,
        namespace,
        audience: parsedRuntime.audience,
        ...parsed,
        displayAnswer,
        updatedAt: now().toISOString(),
      })
      try {
        storage.setItem(draftKey(namespace, parsed), JSON.stringify(draft))
      } catch (error) {
        // Callers must surface this condition: silently continuing would make
        // a reload lose work while the UI still claims the draft is saved.
        throw new TestAnswerDraftStorageError('write', error)
      }
      return draft
    },

    clear(descriptor) {
      removeValue(storage, draftKey(namespace, descriptor))
    },

    clearOwner(ownerId) {
      const parsedOwnerId = publicIdSchema.parse(ownerId)
      for (const key of enumerateKeys(storage, prefix)) {
        const draft = parseStoredDraft(storage, key, namespace, parsedRuntime.audience)
        if (draft?.ownerId === parsedOwnerId) removeValue(storage, key)
      }
    },
  }
}
