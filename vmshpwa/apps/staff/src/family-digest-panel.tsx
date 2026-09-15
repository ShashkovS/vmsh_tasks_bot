import { useMutation, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, CheckCircle2, Send } from 'lucide-react'
import { useState } from 'react'

import { useStaffFamilyDigestQuery, type StaffFamilyDigestClient } from '@vmsh/app-shell'
import {
  notificationQueryKeys,
  type FamilyDigestPreview,
  type PrincipalQueryScope,
} from '@vmsh/contracts'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@vmsh/ui'

/*
 * `dev/development-plan/12-phase-8-news-and-notifications.md` deliberately
 * keeps this action manual: an empty review queue is not proof that every
 * teacher has finished, so the administrator decides when the digest is ready.
 */
export function FamilyDigestPanelView({
  confirming = false,
  digest,
  error = false,
  loading = false,
  onCancel,
  onConfirm,
  onRetry,
  onStart,
  pending = false,
}: {
  confirming?: boolean
  digest?: FamilyDigestPreview
  error?: boolean
  loading?: boolean
  onCancel?: () => void
  onConfirm?: () => void
  onRetry?: () => void
  onStart?: () => void
  pending?: boolean
}) {
  const hasRecipients = digest !== undefined && digest.familyCount > 0
  const allSent = hasRecipients && digest.pendingFamilyCount === 0
  return (
    <Card>
      <CardHeader className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-start">
        <div className="space-y-1">
          <CardTitle>Итоги для семей</CardTitle>
          <p className="text-small text-muted-foreground">
            Один общий итог после завершения всей проверки занятия. Исправления результатов не
            отправляют повторный push автоматически.
          </p>
        </div>
        {hasRecipients ? (
          <Badge variant={allSent ? 'success' : 'neutral'}>
            {allSent ? 'Разослано' : `Ожидают ${digest.pendingFamilyCount}`}
          </Badge>
        ) : null}
      </CardHeader>
      <CardContent className="space-y-3">
        {loading ? (
          <p className="text-small text-muted-foreground">Проверяем получателей…</p>
        ) : null}
        {error ? (
          <Alert tone="danger">
            <AlertTriangle aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Не удалось проверить получателей</AlertTitle>
              <AlertDescription>
                Обновите данные. Ничего не будет отправлено без отдельного подтверждения.
              </AlertDescription>
              <Button className="mt-2" onClick={onRetry} size="xs" variant="outline">
                Повторить
              </Button>
            </AlertContent>
          </Alert>
        ) : null}
        {digest ? (
          <>
            <dl className="grid grid-cols-2 gap-2 text-small sm:grid-cols-4">
              <div>
                <dt className="text-muted-foreground">Группа</dt>
                <dd className="font-medium">{digest.groupName}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Занятие</dt>
                <dd className="font-num font-medium">{digest.lessonNumber}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Школьников</dt>
                <dd className="font-num font-medium">{digest.studentCount}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Семей</dt>
                <dd className="font-num font-medium">{digest.familyCount}</dd>
              </div>
            </dl>
            {digest.unlinkedStudents.length > 0 ? (
              <Alert tone="warning">
                <AlertTriangle aria-hidden="true" />
                <AlertContent>
                  <AlertTitle>
                    Без активного семейного аккаунта: {digest.unlinkedStudents.length}
                  </AlertTitle>
                  <AlertDescription>
                    {digest.unlinkedStudents.map((student) => student.displayName).join(', ')}
                  </AlertDescription>
                </AlertContent>
              </Alert>
            ) : null}
            {!hasRecipients ? (
              <Alert tone="warning">
                <AlertTriangle aria-hidden="true" />
                <AlertContent>
                  <AlertTitle>Нет семейных аккаунтов для рассылки</AlertTitle>
                  <AlertDescription>
                    Сначала свяжите хотя бы один активный семейный аккаунт со школьником этой
                    группы.
                  </AlertDescription>
                </AlertContent>
              </Alert>
            ) : allSent ? (
              <Alert tone="success">
                <CheckCircle2 aria-hidden="true" />
                <AlertContent>
                  <AlertTitle>Итог уже разослан</AlertTitle>
                  <AlertDescription>
                    Уведомлены {digest.alreadySentFamilyCount} семей. Повторных событий не создано.
                  </AlertDescription>
                </AlertContent>
              </Alert>
            ) : confirming ? (
              <div
                aria-labelledby="family-digest-confirmation-title"
                className="rounded-md border border-status-warning-border bg-status-warning-surface p-3"
                role="alertdialog"
              >
                <p className="font-medium" id="family-digest-confirmation-title">
                  Отправить итог {digest.pendingFamilyCount} семьям?
                </p>
                <p className="mt-1 text-small text-muted-foreground">
                  В PWA появится одно событие; при разрешённых push оно будет доставлено на
                  подписанные устройства.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button disabled={pending} onClick={onConfirm} size="sm">
                    Отправить
                  </Button>
                  <Button disabled={pending} onClick={onCancel} size="sm" variant="outline">
                    Отмена
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-small text-muted-foreground">
                  Уже уведомлены {digest.alreadySentFamilyCount}; сейчас будут уведомлены{' '}
                  {digest.pendingFamilyCount}.
                </p>
                <Button disabled={pending} onClick={onStart} size="sm">
                  <Send aria-hidden="true" />
                  Разослать итог
                </Button>
              </div>
            )}
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}

export function FamilyDigestPanel({
  client,
  groupLessonId,
  scope,
}: {
  client: StaffFamilyDigestClient
  groupLessonId: string
  scope: PrincipalQueryScope
}) {
  const [confirming, setConfirming] = useState(false)
  const queryClient = useQueryClient()
  const query = useStaffFamilyDigestQuery(client, scope, groupLessonId)
  const mutation = useMutation({
    mutationFn: () => client.send(groupLessonId),
    onSuccess: (response) => {
      queryClient.setQueryData(notificationQueryKeys.familyDigest(scope, groupLessonId), {
        schemaVersion: 1,
        digest: response.digest,
        requestId: response.requestId,
      })
      setConfirming(false)
    },
  })
  return (
    <FamilyDigestPanelView
      confirming={confirming}
      {...(query.data ? { digest: query.data.digest } : {})}
      error={query.isError || mutation.isError}
      loading={query.isPending}
      onCancel={() => setConfirming(false)}
      onConfirm={() => mutation.mutate()}
      onRetry={() => void query.refetch()}
      onStart={() => setConfirming(true)}
      pending={mutation.isPending}
    />
  )
}
