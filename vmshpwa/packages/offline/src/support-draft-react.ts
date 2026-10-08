import { useCallback, useMemo, useState } from 'react'

import {
  createSupportDraftStore,
  type SupportDraft,
  type SupportDraftDescriptor,
  type SupportDraftRuntime,
  type SupportDraftStore,
  type SupportDraftStoreOptions,
} from './support-draft'
import { type LocalDraftStorage } from './test-answer-draft'

export interface SupportDraftEditorOptions extends SupportDraftStoreOptions {
  storage?: LocalDraftStorage | null
}

export interface SupportDraftDeliveryIdentity {
  idempotencyKey: string
  clientCreatedAt: string
}

export interface SupportDraftEditor {
  text: string
  draft: SupportDraft | null
  delivery: SupportDraftDeliveryIdentity
  saveState: 'idle' | 'saved' | 'unavailable'
  storageError: unknown
  setText: (text: string) => void
  clearAfterConfirmedSend: () => void
}

function browserStorage(): LocalDraftStorage | null {
  try {
    return globalThis.localStorage ?? null
  } catch {
    return null
  }
}

function browserIdempotencyKey(): string {
  return globalThis.crypto.randomUUID()
}

interface InitialEditorState {
  text: string
  draft: SupportDraft | null
  saveState: SupportDraftEditor['saveState']
  storageError: unknown
}

function initialState(
  store: SupportDraftStore | null,
  descriptor: SupportDraftDescriptor,
): InitialEditorState {
  if (!store) {
    return { text: '', draft: null, saveState: 'unavailable', storageError: null }
  }
  try {
    const draft = store.load(descriptor)
    return {
      text: draft?.text ?? '',
      draft,
      saveState: draft ? 'saved' : 'idle',
      storageError: null,
    }
  } catch (error) {
    return { text: '', draft: null, saveState: 'unavailable', storageError: error }
  }
}

/**
 * React binding for `SupportDraftStore`. Consumers key the owning component by
 * `store.key(descriptor)` when a route can switch compose targets without an
 * unmount; this prevents one target's in-memory text crossing into another.
 */
export function useSupportDraftEditor(
  runtime: SupportDraftRuntime,
  descriptor: SupportDraftDescriptor,
  options: SupportDraftEditorOptions = {},
): SupportDraftEditor {
  const storage = options.storage === undefined ? browserStorage() : options.storage
  const createIdempotencyKey = options.createIdempotencyKey ?? browserIdempotencyKey
  const now = options.now ?? (() => new Date())
  const store = useMemo(
    () =>
      storage
        ? createSupportDraftStore(runtime, storage, {
            createIdempotencyKey,
            now,
          })
        : null,
    // A route-level keyed boundary freezes these dependencies for one editor.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )
  const [fallbackDelivery] = useState<SupportDraftDeliveryIdentity>(() => ({
    idempotencyKey: createIdempotencyKey(),
    clientCreatedAt: now().toISOString(),
  }))
  const [state, setState] = useState<InitialEditorState>(() => initialState(store, descriptor))

  const setText = useCallback(
    (text: string) => {
      if (!store) {
        setState((current) => ({
          ...current,
          text,
          saveState: 'unavailable',
        }))
        return
      }
      try {
        const draft = store.save(descriptor, text)
        setState({ text, draft, saveState: 'saved', storageError: null })
      } catch (error) {
        setState((current) => ({
          ...current,
          text,
          saveState: 'unavailable',
          storageError: error,
        }))
      }
    },
    [descriptor, store],
  )

  const clearAfterConfirmedSend = useCallback(() => {
    try {
      store?.clear(descriptor)
      setState({
        text: '',
        draft: null,
        saveState: store ? 'idle' : 'unavailable',
        storageError: null,
      })
    } catch (error) {
      // The message is already committed. Clear the visible composer while
      // reporting that a stale local copy may remain for the next mount.
      setState({ text: '', draft: null, saveState: 'unavailable', storageError: error })
    }
  }, [descriptor, store])

  return {
    ...state,
    delivery: state.draft
      ? {
          idempotencyKey: state.draft.idempotencyKey,
          clientCreatedAt: state.draft.clientCreatedAt,
        }
      : fallbackDelivery,
    setText,
    clearAfterConfirmedSend,
  }
}
