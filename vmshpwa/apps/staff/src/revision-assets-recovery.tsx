import { AlertTriangle, RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'

import {
  ContentNetworkError,
  ContentProtocolError,
  useContentRevisionAssetsQuery,
  type ContentApiClient,
  type VersionedContentResource,
} from '@vmsh/content'
import {
  ApiResponseError,
  type ContentAssetUploadKind,
  type StaffContentRevision,
} from '@vmsh/contracts'
import { MissingAssetsFlow, type MissingAsset } from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle, Button, Skeleton } from '@vmsh/ui'

interface AssetDraft {
  kind: ContentAssetUploadKind
  file?: File | undefined
  phase?: 'uploading' | 'error' | 'attached' | 'reused' | undefined
  errorMessage?: string | undefined
}

export type RevisionAssetRecoveryClient = Pick<
  ContentApiClient,
  'diagnostics' | 'revisionAssets' | 'resolveRevisionAssets' | 'uploadRevisionAsset'
>

export interface RevisionAssetsRecoveryProps {
  client: RevisionAssetRecoveryClient
  revisionId: string
  onCompile: (revision: VersionedContentResource<StaffContentRevision>) => Promise<void>
}

function describeError(error: unknown): string {
  if (error instanceof ApiResponseError && error.status === 409) {
    return 'Revision уже изменилась. Список ресурсов обновлён; проверьте его и повторите действие.'
  }
  if (error instanceof ApiResponseError) {
    return `${error.message} Код обращения: ${error.requestId}.`
  }
  if (error instanceof ContentNetworkError) {
    return 'Нет связи с сервером. Проверьте подключение и повторите действие.'
  }
  if (error instanceof ContentProtocolError) {
    return 'Сервер вернул неожиданный ответ. Обновите страницу и повторите действие.'
  }
  return 'Не удалось обработать ресурс. Повторите действие.'
}

function uploadKindForFile(file: File): 'raster' | 'svg' {
  return file.type === 'image/svg+xml' || file.name.toLocaleLowerCase('en').endsWith('.svg')
    ? 'svg'
    : 'raster'
}

/**
 * Exact-revision asset recovery for the Staff content workflow. The server
 * owns conversion, deduplication and TikZ source lookup; this component keeps
 * only recoverable browser draft state. See Phase 2 in
 * `dev/development-plan/06-phase-2-content.md` and `MissingAssetsFlow`.
 */
export function RevisionAssetsRecovery({
  client,
  revisionId,
  onCompile,
}: RevisionAssetsRecoveryProps) {
  const assetsQuery = useContentRevisionAssetsQuery(client, revisionId)
  const [drafts, setDrafts] = useState<Record<string, AssetDraft>>({})
  const [busyAssetId, setBusyAssetId] = useState<string>()
  const [compilePending, setCompilePending] = useState(false)
  const [resolvePending, setResolvePending] = useState(false)
  const [compileError, setCompileError] = useState<string>()

  const items = useMemo<MissingAsset[]>(() => {
    if (!assetsQuery.data) return []
    return assetsQuery.data.data.assets.map((slot) => {
      const draft = drafts[slot.logicalName]
      const attached = slot.status === 'attached'
      const status: MissingAsset['status'] = attached
        ? draft?.phase === 'reused'
          ? 'reused'
          : 'attached'
        : draft?.phase === 'uploading'
          ? 'uploading'
          : draft?.phase === 'error'
            ? 'error'
            : 'missing'
      return {
        id: slot.logicalName,
        ref: slot.logicalName,
        sourceKind: slot.sourceKind,
        acceptedUploadKinds: slot.acceptedUploadKinds,
        status,
        ...(draft?.file ? { fileName: draft.file.name } : {}),
        ...(slot.asset ? { assetHref: slot.asset.src } : {}),
        ...(draft?.errorMessage ? { errorMessage: draft.errorMessage } : {}),
      }
    })
  }, [assetsQuery.data, drafts])

  const updateDraft = (logicalName: string, update: Partial<AssetDraft>) => {
    setDrafts((current) => {
      const slot = assetsQuery.data?.data.assets.find(
        (candidate) => candidate.logicalName === logicalName,
      )
      const existing =
        current[logicalName] ?? (slot ? { kind: slot.acceptedUploadKinds[0]! } : undefined)
      if (!existing) return current
      return { ...current, [logicalName]: { ...existing, ...update } }
    })
  }

  const resolveAsset = async (logicalName: string) => {
    const resource = assetsQuery.data
    const slot = resource?.data.assets.find((asset) => asset.logicalName === logicalName)
    const draft = drafts[logicalName] ?? (slot ? { kind: slot.acceptedUploadKinds[0]! } : undefined)
    if (!resource || !slot || !draft || busyAssetId || slot.status === 'attached') return
    if (draft.kind !== 'tikz' && !draft.file) return

    setBusyAssetId(logicalName)
    setCompileError(undefined)
    updateDraft(logicalName, { phase: 'uploading', errorMessage: undefined })
    try {
      const uploaded = await client.uploadRevisionAsset({
        revisionId,
        etag: resource.etag,
        logicalName,
        kind: draft.kind,
        ...(draft.file ? { asset: draft.file } : {}),
      })
      updateDraft(logicalName, { phase: uploaded.data.reused ? 'reused' : 'attached' })
      const refreshed = await assetsQuery.refetch()
      if (refreshed.error) throw refreshed.error
      const refreshedSlot = refreshed.data?.data.assets.find(
        (asset) => asset.logicalName === logicalName,
      )
      if (!refreshedSlot || refreshedSlot.status !== 'attached') {
        throw new Error('Сервер не подтвердил прикрепление ресурса')
      }
    } catch (error) {
      updateDraft(logicalName, { phase: 'error', errorMessage: describeError(error) })
      if (error instanceof ApiResponseError && error.status === 409) await assetsQuery.refetch()
    } finally {
      setBusyAssetId(undefined)
    }
  }

  const compileResolvedRevision = async () => {
    if (compilePending) return
    setCompilePending(true)
    setCompileError(undefined)
    try {
      const refreshedAssets = await assetsQuery.refetch()
      if (refreshedAssets.error) throw refreshedAssets.error
      if (!refreshedAssets.data || refreshedAssets.data.data.missingAssets.length > 0) {
        throw new Error('Сначала прикрепите все недостающие ресурсы')
      }
      // Diagnostics is intentionally fetched after the asset list so compile
      // receives the latest strong revision ETag, not the one shown initially.
      const revision = await client.diagnostics(revisionId)
      await onCompile(revision)
    } catch (error) {
      setCompileError(describeError(error))
    } finally {
      setCompilePending(false)
    }
  }

  const resolveKnownAssets = async () => {
    const resource = assetsQuery.data
    if (!resource || !client.resolveRevisionAssets || resolvePending || busyAssetId) return
    setResolvePending(true)
    setCompileError(undefined)
    try {
      const resolved = await client.resolveRevisionAssets(revisionId, resource.etag)
      for (const slot of resolved.data.assets) {
        const previous = resource.data.assets.find(
          (candidate) => candidate.logicalName === slot.logicalName,
        )
        if (previous?.status === 'missing' && slot.status === 'attached') {
          updateDraft(slot.logicalName, { phase: 'reused', errorMessage: undefined })
        }
      }
      await assetsQuery.refetch()
    } catch (error) {
      setCompileError(describeError(error))
      if (error instanceof ApiResponseError && error.status === 409) await assetsQuery.refetch()
    } finally {
      setResolvePending(false)
    }
  }

  if (assetsQuery.isPending) {
    return (
      <section aria-label="Загрузка списка ресурсов" className="space-y-2">
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-24 w-full" />
      </section>
    )
  }

  if (assetsQuery.error) {
    return (
      <Alert role="alert" tone="danger">
        <AlertTriangle aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Не удалось загрузить список ресурсов</AlertTitle>
          <AlertDescription className="space-y-2">
            <span className="block">{describeError(assetsQuery.error)}</span>
            <Button onClick={() => void assetsQuery.refetch()} size="xs" variant="outline">
              <RefreshCw aria-hidden="true" /> Повторить
            </Button>
          </AlertDescription>
        </AlertContent>
      </Alert>
    )
  }

  const allResolved = assetsQuery.data.data.missingAssets.length === 0

  return (
    <section aria-label="Ресурсы revision" className="space-y-3">
      {!allResolved && client.resolveRevisionAssets ? (
        <Button
          disabled={busyAssetId !== undefined || compilePending || resolvePending}
          onClick={() => void resolveKnownAssets()}
          size="sm"
          variant="outline"
        >
          <RefreshCw aria-hidden="true" />
          {resolvePending ? 'Ищем в банке…' : 'Найти уже загруженные картинки'}
        </Button>
      ) : null}
      <MissingAssetsFlow
        assets={items}
        disabled={busyAssetId !== undefined || compilePending || resolvePending}
        onFileSelect={(logicalName, file) =>
          updateDraft(logicalName, {
            ...(file ? { kind: uploadKindForFile(file) } : {}),
            file,
            phase: undefined,
            errorMessage: undefined,
          })
        }
        onResolve={(logicalName) => void resolveAsset(logicalName)}
      />
      {allResolved ? (
        <Button disabled={compilePending} onClick={() => void compileResolvedRevision()} size="sm">
          <RefreshCw aria-hidden="true" className={compilePending ? 'animate-spin' : undefined} />
          {compilePending ? 'Собираем материал…' : 'Повторить сборку материала'}
        </Button>
      ) : null}
      {compileError ? (
        <p className="text-small text-status-error" role="alert">
          {compileError}
        </p>
      ) : null}
    </section>
  )
}
