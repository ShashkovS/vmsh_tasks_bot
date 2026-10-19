import { z } from 'zod'

import {
  browserStorageNamespaceSchema,
  createBrowserStorageNamespace,
  publicIdSchema,
  runtimeInstanceSchema,
  type BrowserStorageNamespace,
} from '@vmsh/contracts'

import { type LocalDraftStorage } from './test-answer-draft'

/**
 * Reload-safe text draft for the private Student/Staff dialogue described in
 * `dev/development-plan/10-phase-6-review-and-feedback.md`. The server thread
 * remains authoritative; this store protects only unsent browser text and its
 * stable idempotency identity.
 */

export const SUPPORT_DRAFT_VERSION = 1 as const

export const supportDraftAudienceSchema = z.enum(['student', 'staff'])
export type SupportDraftAudience = z.infer<typeof supportDraftAudienceSchema>

const supportDraftRuntimeSchema = z
  .object({
    audience: supportDraftAudienceSchema,
    instance: runtimeInstanceSchema,
  })
  .strict()
export type SupportDraftRuntime = z.infer<typeof supportDraftRuntimeSchema>

export const supportDraftTargetSchema = z.discriminatedUnion('kind', [
  z
    .object({
      kind: z.literal('existing_thread'),
      threadId: publicIdSchema,
    })
    .strict(),
  z
    .object({
      kind: z.literal('new_problem_question'),
      groupLessonId: publicIdSchema,
      problemId: publicIdSchema,
    })
    .strict(),
  z
    .object({
      kind: z.literal('new_general_question'),
      groupLessonId: publicIdSchema,
    })
    .strict(),
])
export type SupportDraftTarget = z.infer<typeof supportDraftTargetSchema>

export const supportDraftDescriptorSchema = z
  .object({
    ownerAccountId: publicIdSchema,
    target: supportDraftTargetSchema,
  })
  .strict()
export type SupportDraftDescriptor = z.infer<typeof supportDraftDescriptorSchema>

export const supportDraftSchema = z
  .object({
    schemaVersion: z.literal(SUPPORT_DRAFT_VERSION),
    namespace: browserStorageNamespaceSchema,
    audience: supportDraftAudienceSchema,
    ownerAccountId: publicIdSchema,
    target: supportDraftTargetSchema,
    text: z.string().max(100_000),
    idempotencyKey: z.string().trim().min(1).max(200),
    clientCreatedAt: z.iso.datetime(),
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
    if (draft.updatedAt < draft.clientCreatedAt) {
      context.addIssue({
        code: 'custom',
        message: 'Draft update cannot predate its creation',
        path: ['updatedAt'],
      })
    }
  })
export type SupportDraft = z.infer<typeof supportDraftSchema>

export type SupportDraftStorageOperation = 'enumerate' | 'read' | 'write' | 'remove'

export class SupportDraftStorageError extends Error {
  readonly operation: SupportDraftStorageOperation

  constructor(operation: SupportDraftStorageOperation, cause: unknown) {
    super(`Support draft storage failed during ${operation}`, { cause })
    this.name = 'SupportDraftStorageError'
    this.operation = operation
  }
}

export interface SupportDraftStoreOptions {
  now?: () => Date
  createIdempotencyKey?: () => string
}

export interface SupportDraftStore {
  readonly audience: SupportDraftAudience
  readonly namespace: BrowserStorageNamespace
  key(descriptor: SupportDraftDescriptor): string
  load(descriptor: SupportDraftDescriptor): SupportDraft | null
  save(descriptor: SupportDraftDescriptor, text: string): SupportDraft
  clear(descriptor: SupportDraftDescriptor): void
  clearOwner(ownerAccountId: string): void
}

const DRAFT_KEY_MARKER = ':draft:support:'

function storagePrefix(namespace: BrowserStorageNamespace): string {
  return `${namespace}${DRAFT_KEY_MARKER}`
}

function parsedDescriptor(descriptor: SupportDraftDescriptor): SupportDraftDescriptor {
  return supportDraftDescriptorSchema.parse(descriptor)
}

function draftKey(namespace: BrowserStorageNamespace, descriptor: SupportDraftDescriptor): string {
  const parsed = parsedDescriptor(descriptor)
  // A JSON tuple keeps all target variants unambiguous while omitting text.
  return `${storagePrefix(namespace)}${JSON.stringify([parsed.ownerAccountId, parsed.target])}`
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
    throw new SupportDraftStorageError('enumerate', error)
  }
}

function readValue(storage: LocalDraftStorage, key: string): string | null {
  try {
    return storage.getItem(key)
  } catch (error) {
    throw new SupportDraftStorageError('read', error)
  }
}

function removeValue(storage: LocalDraftStorage, key: string): void {
  try {
    storage.removeItem(key)
  } catch (error) {
    throw new SupportDraftStorageError('remove', error)
  }
}

function parseStoredDraft(
  storage: LocalDraftStorage,
  key: string,
  expectedNamespace: BrowserStorageNamespace,
  expectedAudience: SupportDraftAudience,
): SupportDraft | null {
  const raw = readValue(storage, key)
  if (raw === null) return null
  let payload: unknown
  try {
    payload = JSON.parse(raw)
  } catch {
    removeValue(storage, key)
    return null
  }
  const parsed = supportDraftSchema.safeParse(payload)
  if (
    !parsed.success ||
    parsed.data.namespace !== expectedNamespace ||
    parsed.data.audience !== expectedAudience ||
    draftKey(expectedNamespace, {
      ownerAccountId: parsed.data.ownerAccountId,
      target: parsed.data.target,
    }) !== key
  ) {
    // Corrupt/tampered entries are not returned to another composer. Removing
    // only this exact namespaced key preserves every other account's draft.
    removeValue(storage, key)
    return null
  }
  return parsed.data
}

function defaultIdempotencyKey(): string {
  return globalThis.crypto.randomUUID()
}

export function createSupportDraftStore(
  runtime: SupportDraftRuntime,
  storage: LocalDraftStorage,
  options: SupportDraftStoreOptions = {},
): SupportDraftStore {
  const parsedRuntime = supportDraftRuntimeSchema.parse(runtime)
  const namespace = createBrowserStorageNamespace(parsedRuntime)
  const prefix = storagePrefix(namespace)
  const now = options.now ?? (() => new Date())
  const createIdempotencyKey = options.createIdempotencyKey ?? defaultIdempotencyKey

  return {
    audience: parsedRuntime.audience,
    namespace,

    key(descriptor) {
      return draftKey(namespace, descriptor)
    },

    load(descriptor) {
      return parseStoredDraft(
        storage,
        draftKey(namespace, descriptor),
        namespace,
        parsedRuntime.audience,
      )
    },

    save(descriptor, text) {
      const parsed = parsedDescriptor(descriptor)
      const key = draftKey(namespace, parsed)
      const existing = parseStoredDraft(storage, key, namespace, parsedRuntime.audience)
      const updatedAt = now().toISOString()
      const draft = supportDraftSchema.parse({
        schemaVersion: SUPPORT_DRAFT_VERSION,
        namespace,
        audience: parsedRuntime.audience,
        ...parsed,
        text,
        idempotencyKey: existing?.idempotencyKey ?? createIdempotencyKey(),
        clientCreatedAt: existing?.clientCreatedAt ?? updatedAt,
        updatedAt,
      })
      try {
        storage.setItem(key, JSON.stringify(draft))
      } catch (error) {
        // A caller must show that durability is unavailable instead of
        // promising a saved draft that a reload would lose.
        throw new SupportDraftStorageError('write', error)
      }
      return draft
    },

    clear(descriptor) {
      removeValue(storage, draftKey(namespace, descriptor))
    },

    clearOwner(ownerAccountId) {
      const parsedOwnerAccountId = publicIdSchema.parse(ownerAccountId)
      for (const key of enumerateKeys(storage, prefix)) {
        const draft = parseStoredDraft(storage, key, namespace, parsedRuntime.audience)
        if (draft?.ownerAccountId === parsedOwnerAccountId) removeValue(storage, key)
      }
    },
  }
}
