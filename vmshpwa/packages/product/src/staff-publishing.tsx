import {
  AlertTriangle,
  CheckCircle2,
  Expand,
  FileWarning,
  LoaderCircle,
  Upload,
} from 'lucide-react'
import { useState } from 'react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Input,
  Label,
  Progress,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  cn,
} from '@vmsh/ui'

import { LevelChip } from './level-chip'
import type { GroupView } from './types'

/* ── Publication control ──────────────────────────────────────────────────
 * The fixed artifact column and block datetime editor implement the bounded
 * scheduling layout specified in dev/design-system/04-product-components.md.
 */

export type PublishState = 'published' | 'scheduled' | 'draft' | 'none'
export type PublicationArtifact = 'task' | 'hint' | 'solution'

export interface PublicationLevelRow {
  level: GroupView
  task: PublishState
  hint: PublishState
  solution: PublishState
  scheduledAt?: Partial<Record<PublicationArtifact, string>>
}

export interface PublicationControlProps {
  rows: PublicationLevelRow[]
  onPublish?: (levelCode: string, artifact: PublicationArtifact) => void
  onSchedule?: (levelCode: string, artifact: PublicationArtifact, at: string) => void
  onRollback?: (levelCode: string, artifact: PublicationArtifact) => void
  className?: string
}

const artifactLabels: Record<PublicationArtifact, string> = {
  task: 'условие',
  hint: 'подсказку',
  solution: 'решение',
}

function StateChip({ state }: { state: PublishState }) {
  switch (state) {
    case 'published':
      return <Badge variant="success">Опубликовано</Badge>
    case 'scheduled':
      return <Badge variant="info">По расписанию</Badge>
    case 'draft':
      return <Badge variant="neutral">Черновик</Badge>
    case 'none':
      return <span className="text-muted-foreground">—</span>
  }
}

export function PublicationControl({
  rows,
  onPublish,
  onSchedule,
  onRollback,
  className,
}: PublicationControlProps) {
  const [confirming, setConfirming] = useState<{
    code: string
    artifact: PublicationArtifact
    kind: 'publish' | 'rollback'
  } | null>(null)
  const [scheduling, setScheduling] = useState<{
    code: string
    artifact: PublicationArtifact
    at: string
  } | null>(null)

  const renderArtifact = (row: PublicationLevelRow, artifact: PublicationArtifact) => {
    const state = row[artifact]
    const label = artifactLabels[artifact]
    const isConfirming = confirming?.code === row.level.code && confirming.artifact === artifact
    const isScheduling = scheduling?.code === row.level.code && scheduling.artifact === artifact

    return (
      <div className="w-48 min-w-48 max-w-48 space-y-1.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <StateChip state={state} />
          {row.scheduledAt?.[artifact] ? (
            <span className="font-num text-caption text-muted-foreground">
              {row.scheduledAt[artifact]}
            </span>
          ) : null}
        </div>

        {isScheduling ? (
          <div className="min-w-0 space-y-1.5">
            <input
              aria-label={`Когда опубликовать ${label}, ${row.level.name}`}
              className="block h-8 w-full min-w-0 max-w-full rounded-md border border-input bg-surface px-2 font-num text-caption text-foreground"
              onChange={(event) => setScheduling({ ...scheduling, at: event.target.value })}
              type="datetime-local"
              value={scheduling.at}
            />
            <div className="flex flex-wrap gap-1">
              <Button
                disabled={!scheduling.at}
                onClick={() => {
                  onSchedule?.(row.level.code, artifact, scheduling.at)
                  setScheduling(null)
                }}
                size="xs"
              >
                Запланировать
              </Button>
              <Button onClick={() => setScheduling(null)} size="xs" variant="ghost">
                Отмена
              </Button>
            </div>
          </div>
        ) : isConfirming ? (
          <div className="space-y-1 text-caption text-foreground">
            <p>
              {confirming.kind === 'publish' ? 'Опубликовать' : 'Откатить'} {label}?
            </p>
            <span className="inline-flex gap-1">
              <Button
                onClick={() => {
                  if (confirming.kind === 'publish') onPublish?.(row.level.code, artifact)
                  else onRollback?.(row.level.code, artifact)
                  setConfirming(null)
                }}
                size="xs"
              >
                Подтвердить
              </Button>
              <Button onClick={() => setConfirming(null)} size="xs" variant="ghost">
                Отмена
              </Button>
            </span>
          </div>
        ) : (
          <div className="flex flex-wrap gap-1">
            {state === 'published' || state === 'scheduled' ? (
              <Button
                aria-label={`${state === 'scheduled' ? 'Отменить расписание' : 'Откатить'}: ${label}, ${row.level.name}`}
                onClick={() => setConfirming({ code: row.level.code, artifact, kind: 'rollback' })}
                size="xs"
                variant="ghost"
              >
                {state === 'scheduled' ? 'Отменить' : 'Откатить'}
              </Button>
            ) : (
              <Button
                aria-label={`Опубликовать сейчас: ${label}, ${row.level.name}`}
                onClick={() => setConfirming({ code: row.level.code, artifact, kind: 'publish' })}
                size="xs"
                variant="outline"
              >
                Сейчас
              </Button>
            )}
            {state !== 'published' ? (
              <Button
                aria-label={`Опубликовать по расписанию: ${label}, ${row.level.name}`}
                onClick={() =>
                  setScheduling({
                    code: row.level.code,
                    artifact,
                    at: '',
                  })
                }
                size="xs"
                variant="ghost"
              >
                По расписанию
              </Button>
            ) : null}
          </div>
        )}
      </div>
    )
  }

  return (
    <div
      className={cn('overflow-x-auto rounded-md border border-border', className)}
      data-density="staff"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Уровень</TableHead>
            <TableHead>Условие</TableHead>
            <TableHead>Подсказка</TableHead>
            <TableHead>Решение</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            return (
              <TableRow key={row.level.code}>
                <TableCell>
                  <LevelChip level={row.level} />
                </TableCell>
                <TableCell>{renderArtifact(row, 'task')}</TableCell>
                <TableCell>{renderArtifact(row, 'hint')}</TableCell>
                <TableCell>{renderArtifact(row, 'solution')}</TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>
    </div>
  )
}

/* ── LaTeX upload ───────────────────────────────────────────────────────── */

export type LatexFileStatus = 'queued' | 'processing' | 'done' | 'error'

export interface LatexFile {
  id: string
  name: string
  status: LatexFileStatus
  progress?: number
  diagnostics?: string[]
}

export interface LatexUploadProps {
  files: LatexFile[]
  sourcePreview?: string
  onRetry?: (id: string) => void
  className?: string
}

export function LatexUpload({ files, sourcePreview, onRetry, className }: LatexUploadProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <ul className="space-y-2">
        {files.map((file) => (
          <li className="space-y-1 rounded-md border border-border bg-surface p-2" key={file.id}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-mono text-small text-foreground">{file.name}</span>
              {file.status === 'error' ? (
                <Button onClick={() => onRetry?.(file.id)} size="xs" variant="outline">
                  Повторить
                </Button>
              ) : (
                <span className="shrink-0 text-caption text-muted-foreground">
                  {file.status === 'done'
                    ? 'готово'
                    : file.status === 'queued'
                      ? 'в очереди'
                      : 'обработка'}
                </span>
              )}
            </div>
            {file.status === 'processing' ? (
              <Progress aria-label={`Обработка ${file.name}`} value={file.progress ?? null} />
            ) : null}
            {file.diagnostics && file.diagnostics.length > 0 ? (
              <ul className="space-y-0.5 text-caption text-status-danger">
                {file.diagnostics.map((message, index) => (
                  <li className="flex items-start gap-1" key={index}>
                    <FileWarning aria-hidden="true" className="mt-0.5 size-3 shrink-0" />
                    {message}
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
      {sourcePreview ? (
        <div className="space-y-1">
          <p className="text-label font-medium text-foreground">Исходник</p>
          <pre className="overflow-x-auto rounded-md border border-border bg-surface-sunken p-3 font-mono text-caption text-foreground">
            {sourcePreview}
          </pre>
        </div>
      ) : null}
    </div>
  )
}

/* ── Missing assets flow ────────────────────────────────────────────────── */

export interface MissingAsset {
  id: string
  ref: string
  sourceKind: 'figure' | 'tikz'
  acceptedUploadKinds: Array<'raster' | 'svg' | 'tikz'>
  status: 'missing' | 'uploading' | 'attached' | 'reused' | 'error'
  fileName?: string
  assetHref?: string
  errorMessage?: string
}

export interface MissingAssetsFlowProps {
  assets: MissingAsset[]
  disabled?: boolean
  onFileSelect?: (assetId: string, file: File | undefined) => void
  onResolve?: (assetId: string) => void
  className?: string
}

const assetFileAccept =
  '.svg,.png,.jpg,.jpeg,.webp,.heic,.heif,image/svg+xml,image/png,image/jpeg,image/webp,image/heic,image/heif'

/** Compact Staff preview from the original attached asset; see the Phase 2
 * missing-assets flow in dev/development-plan/06-phase-2-content.md. */
function AttachedAssetPreview({ asset }: { asset: MissingAsset & { assetHref: string } }) {
  const [previewFailed, setPreviewFailed] = useState(false)
  const imageAlt = `Прикреплённый ресурс ${asset.ref}`

  if (previewFailed) {
    return (
      <a
        className="inline-flex text-small font-medium text-link underline-offset-4 hover:underline focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        href={asset.assetHref}
        rel="noreferrer"
        target="_blank"
      >
        Открыть изображение
      </a>
    )
  }

  return (
    <Dialog>
      <DialogTrigger
        render={
          <button
            aria-label={`Увеличить ресурс ${asset.ref}`}
            className="group relative grid h-28 w-44 max-w-full place-items-center overflow-hidden rounded-md border border-border bg-surface-sunken p-1 outline-none transition-colors hover:border-border-strong focus-visible:ring-3 focus-visible:ring-ring/50"
            type="button"
          >
            <img
              alt={imageAlt}
              className="max-h-full max-w-full object-contain"
              decoding="async"
              loading="lazy"
              onError={() => setPreviewFailed(true)}
              src={asset.assetHref}
            />
            <span className="absolute right-1 bottom-1 inline-flex items-center gap-1 rounded-sm bg-surface/90 px-1.5 py-0.5 text-caption text-muted-foreground shadow-sm group-hover:text-foreground">
              <Expand aria-hidden="true" className="size-3" /> Увеличить
            </span>
          </button>
        }
      />
      <DialogContent className="max-h-[calc(100svh-2rem)] overflow-hidden sm:max-w-[min(92vw,72rem)]">
        <DialogHeader>
          <DialogTitle>{asset.ref}</DialogTitle>
          <DialogDescription>Оригинальный прикреплённый ресурс</DialogDescription>
        </DialogHeader>
        <div className="grid min-h-0 place-items-center overflow-auto rounded-md bg-surface-sunken p-2">
          <img
            alt={imageAlt}
            className="max-h-[calc(100svh-9rem)] max-w-full object-contain"
            decoding="async"
            src={asset.assetHref}
          />
        </div>
      </DialogContent>
    </Dialog>
  )
}

export function MissingAssetsFlow({
  assets,
  disabled = false,
  onFileSelect,
  onResolve,
  className,
}: MissingAssetsFlowProps) {
  const unresolvedCount = assets.filter(
    (asset) => asset.status !== 'attached' && asset.status !== 'reused',
  ).length

  return (
    <div className={cn('space-y-3', className)}>
      <Alert role="status" tone={unresolvedCount === 0 ? 'success' : 'danger'}>
        {unresolvedCount === 0 ? (
          <CheckCircle2 aria-hidden="true" />
        ) : (
          <AlertTriangle aria-hidden="true" />
        )}
        <AlertContent>
          <AlertTitle>
            {unresolvedCount === 0
              ? 'Все ресурсы прикреплены'
              : `Не хватает ресурсов: ${unresolvedCount}`}
          </AlertTitle>
          <AlertDescription>
            {unresolvedCount === 0
              ? 'Можно повторить сборку материала.'
              : 'Публикация недоступна, пока все ссылки не разрешены.'}
          </AlertDescription>
        </AlertContent>
      </Alert>
      <ul className="space-y-2">
        {assets.map((asset, index) => {
          const inputId = `missing-asset-file-${index}`
          const resolved = asset.status === 'attached' || asset.status === 'reused'
          const needsFile = asset.sourceKind !== 'tikz'
          return (
            <li className="space-y-2 rounded-md border border-border bg-surface p-3" key={asset.id}>
              <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-all font-mono text-small text-foreground">{asset.ref}</p>
                  <p className="text-caption text-muted-foreground">
                    {asset.sourceKind === 'tikz' ? 'TikZ-фрагмент' : 'Рисунок из LaTeX'}
                  </p>
                </div>
                {asset.status === 'uploading' ? (
                  <Badge variant="info">
                    <LoaderCircle aria-hidden="true" className="animate-spin" /> Обрабатываем
                  </Badge>
                ) : asset.status === 'reused' ? (
                  <Badge variant="success">Переиспользован</Badge>
                ) : asset.status === 'attached' ? (
                  <Badge variant="success">Прикреплён</Badge>
                ) : asset.status === 'error' ? (
                  <Badge variant="danger">Ошибка</Badge>
                ) : (
                  <Badge variant="warning">Нужен ресурс</Badge>
                )}
              </div>

              {resolved ? (
                asset.assetHref ? (
                  <AttachedAssetPreview asset={{ ...asset, assetHref: asset.assetHref }} />
                ) : null
              ) : (
                <div className="grid min-w-0 gap-2 sm:grid-cols-[minmax(12rem,1fr)_auto] sm:items-end">
                  {needsFile ? (
                    <div className="min-w-0 space-y-1">
                      <Label htmlFor={inputId}>Изображение</Label>
                      <Input
                        accept={assetFileAccept}
                        disabled={disabled || asset.status === 'uploading'}
                        id={inputId}
                        onChange={(event) => onFileSelect?.(asset.id, event.target.files?.[0])}
                        type="file"
                      />
                      {asset.fileName ? (
                        <p className="truncate text-caption text-muted-foreground">
                          Выбран: {asset.fileName}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                  <Button
                    disabled={
                      disabled ||
                      asset.status === 'uploading' ||
                      (needsFile && asset.fileName === undefined)
                    }
                    onClick={() => onResolve?.(asset.id)}
                    size="sm"
                    variant={asset.status === 'error' ? 'outline' : 'default'}
                  >
                    {asset.status === 'uploading' ? (
                      <LoaderCircle aria-hidden="true" className="animate-spin" />
                    ) : (
                      <Upload aria-hidden="true" />
                    )}
                    {asset.status === 'error'
                      ? 'Повторить'
                      : asset.sourceKind === 'tikz'
                        ? 'Повторить обработку'
                        : 'Загрузить'}
                  </Button>
                </div>
              )}
              {asset.errorMessage ? (
                <p className="text-caption text-status-error" role="alert">
                  {asset.errorMessage}
                </p>
              ) : null}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
