import { AlertTriangle, FileWarning, Upload } from 'lucide-react'
import { useState } from 'react'

import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
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
import type { LevelView } from './types'

/* ── Publication control ────────────────────────────────────────────────── */

export type PublishState = 'published' | 'scheduled' | 'draft' | 'none'

export interface PublicationLevelRow {
  level: LevelView
  task: PublishState
  hint: PublishState
  solution: PublishState
  scheduledAt?: string
}

export interface PublicationControlProps {
  rows: PublicationLevelRow[]
  onPublish?: (levelCode: string) => void
  onRollback?: (levelCode: string) => void
  className?: string
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
  onRollback,
  className,
}: PublicationControlProps) {
  const [confirming, setConfirming] = useState<{
    code: string
    kind: 'publish' | 'rollback'
  } | null>(null)

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
            <TableHead>Когда</TableHead>
            <TableHead className="text-right">Действие</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => {
            const published = row.task === 'published'
            const isConfirming = confirming?.code === row.level.code
            return (
              <TableRow key={row.level.code}>
                <TableCell>
                  <LevelChip level={row.level} />
                </TableCell>
                <TableCell>
                  <StateChip state={row.task} />
                </TableCell>
                <TableCell>
                  <StateChip state={row.hint} />
                </TableCell>
                <TableCell>
                  <StateChip state={row.solution} />
                </TableCell>
                <TableCell className="font-num text-muted-foreground">
                  {row.scheduledAt ?? '—'}
                </TableCell>
                <TableCell className="text-right">
                  {isConfirming ? (
                    <span className="inline-flex gap-1">
                      <Button
                        onClick={() => {
                          if (confirming.kind === 'publish') onPublish?.(row.level.code)
                          else onRollback?.(row.level.code)
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
                  ) : published ? (
                    <Button
                      onClick={() => setConfirming({ code: row.level.code, kind: 'rollback' })}
                      size="xs"
                      variant="ghost"
                    >
                      Откатить
                    </Button>
                  ) : (
                    <Button
                      onClick={() => setConfirming({ code: row.level.code, kind: 'publish' })}
                      size="xs"
                      variant="outline"
                    >
                      Опубликовать
                    </Button>
                  )}
                </TableCell>
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
  candidates?: { id: string; label: string }[]
}

export interface MissingAssetsFlowProps {
  assets: MissingAsset[]
  onReuse?: (assetId: string, candidateId: string) => void
  onUpload?: (assetId: string) => void
  className?: string
}

export function MissingAssetsFlow({
  assets,
  onReuse,
  onUpload,
  className,
}: MissingAssetsFlowProps) {
  return (
    <div className={cn('space-y-3', className)}>
      <Alert role="alert" tone="danger">
        <AlertTriangle aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Не хватает {assets.length} ресурс(ов)</AlertTitle>
          <AlertDescription>Публикация недоступна, пока все ссылки не разрешены.</AlertDescription>
        </AlertContent>
      </Alert>
      <ul className="space-y-2">
        {assets.map((asset) => (
          <li className="space-y-1.5 rounded-md border border-border bg-surface p-2" key={asset.id}>
            <p className="font-mono text-small text-foreground">{asset.ref}</p>
            <div className="flex flex-wrap items-center gap-1.5">
              {(asset.candidates ?? []).map((candidate) => (
                <Button
                  key={candidate.id}
                  onClick={() => onReuse?.(asset.id, candidate.id)}
                  size="xs"
                  variant="outline"
                >
                  Взять: {candidate.label}
                </Button>
              ))}
              <Button onClick={() => onUpload?.(asset.id)} size="xs" variant="ghost">
                <Upload aria-hidden="true" />
                Загрузить
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
