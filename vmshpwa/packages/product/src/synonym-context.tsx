import { GitMerge, GitPullRequest, Link2Off, MessageSquareText } from 'lucide-react'
import type { ReactNode } from 'react'

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
  cn,
} from '@vmsh/ui'

import { FeedbackThread, type ThreadMessageView } from './feedback-thread'

/* Logical synonym projection. Concrete submissions/results remain attached to
 * problemId; the projection can therefore be merged or split retrospectively.
 * See docs/courses-groups-and-lessons.md and development-plan Phase 6.
 */

export interface SynonymProblemView {
  problemId: string
  courseName: string
  groupName: string
  lessonNumber: number
  taskNumber: string
  title: string
  taskType: string
  answerType?: string
  submissionCount: number
  reviewCount: number
}

function countLabel(count: number, one: string, few: string, many: string): string {
  const lastTwo = count % 100
  const last = count % 10
  const word =
    last === 1 && lastTwo !== 11
      ? one
      : last >= 2 && last <= 4 && (lastTwo < 12 || lastTwo > 14)
        ? few
        : many
  return `${count} ${word}`
}

export function SynonymMergeSplitPreview({
  problems,
  mode,
  onConfirm,
  onCancel,
  confirmDisabled = false,
  className,
}: {
  problems: SynonymProblemView[]
  mode: 'merge' | 'split'
  onConfirm?: () => void
  onCancel?: () => void
  confirmDisabled?: boolean
  className?: string
}) {
  const submissions = problems.reduce((total, problem) => total + problem.submissionCount, 0)
  const reviews = problems.reduce((total, problem) => total + problem.reviewCount, 0)
  const Icon = mode === 'merge' ? GitMerge : Link2Off
  return (
    <section
      className={cn('max-w-3xl space-y-3', className)}
      aria-labelledby="synonym-preview-title"
    >
      <div>
        <h2
          className="inline-flex items-center gap-2 text-section font-semibold text-foreground"
          id="synonym-preview-title"
        >
          <Icon aria-hidden="true" className="size-4" />
          {mode === 'merge' ? 'Объединить задачи логически' : 'Разделить задачи'}
        </h2>
        <p className="text-small text-muted-foreground">
          Курс и номер занятия совпадают. Тип ответа и способ сдачи не блокируют действие.
        </p>
      </div>

      <div className="space-y-2">
        {problems.map((problem) => (
          <Card key={problem.problemId}>
            <CardContent className="grid gap-2 py-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <div>
                <p className="font-medium text-foreground">
                  {problem.taskNumber} · {problem.title}
                </p>
                <p className="text-caption text-muted-foreground">
                  {problem.courseName} · {problem.groupName} · занятие {problem.lessonNumber}
                </p>
              </div>
              <div className="flex flex-wrap gap-1.5">
                <Badge variant="neutral">{problem.taskType}</Badge>
                {problem.answerType ? <Badge variant="neutral">{problem.answerType}</Badge> : null}
                <Badge variant="info">
                  {countLabel(problem.submissionCount, 'посылка', 'посылки', 'посылок')}
                </Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Alert tone={mode === 'split' ? 'warning' : 'info'}>
        <GitPullRequest aria-hidden="true" />
        <AlertContent>
          <AlertTitle>
            Исходные записи не изменятся: {countLabel(submissions, 'посылка', 'посылки', 'посылок')}
            , {countLabel(reviews, 'проверка', 'проверки', 'проверок')}
          </AlertTitle>
          <AlertDescription>
            {mode === 'merge'
              ? 'Карточки получат общий вычисляемый статус и хронологию, но каждая запись сохранит исходный problem_id.'
              : 'Общий verdict останется у задачи последней включённой посылки; остальные ветки снова вычислят собственный статус.'}
          </AlertDescription>
        </AlertContent>
      </Alert>

      <div className="flex flex-wrap gap-2">
        <Button disabled={confirmDisabled} onClick={onConfirm}>
          {mode === 'merge' ? 'Объединить' : 'Разделить'}
        </Button>
        <Button onClick={onCancel} variant="ghost">
          Отмена
        </Button>
      </div>
    </section>
  )
}

export function SynonymMergedTimeline({
  messages,
  status,
  className,
}: {
  messages: ThreadMessageView[]
  status: string
  className?: string
}) {
  return (
    <section
      className={cn('max-w-2xl space-y-3', className)}
      aria-labelledby="synonym-timeline-title"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-section font-semibold text-foreground" id="synonym-timeline-title">
            Общая история решения
          </h2>
          <p className="text-caption text-muted-foreground">
            Ветки показаны по времени; источник каждой записи остаётся видимым.
          </p>
        </div>
        <Badge variant="info">{status}</Badge>
      </div>
      <FeedbackThread messages={messages} />
    </section>
  )
}

export interface SynonymSubmissionEvidence {
  id: string
  problemId: string
  courseName: string
  groupName: string
  taskNumber: string
  submittedAt: string
  body: ReactNode
  latest?: boolean
}

export function SynonymReviewCase({
  studentName,
  taskTitle,
  submissions,
  className,
}: {
  studentName: string
  taskTitle: string
  submissions: SynonymSubmissionEvidence[]
  className?: string
}) {
  const latest = submissions.find((submission) => submission.latest) ?? submissions.at(-1)
  const originLabel = (submission: SynonymSubmissionEvidence) =>
    `${submission.courseName} · ${submission.groupName} · ${submission.taskNumber}`
  return (
    <Card className={cn('max-w-3xl', className)}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <p className="text-caption text-muted-foreground">Один логический кейс</p>
            <CardTitle>{taskTitle}</CardTitle>
            <p className="text-small text-muted-foreground">{studentName}</p>
          </div>
          <Badge variant="warning">{submissions.length} посылки объединены</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <ol className="space-y-2">
          {submissions.map((submission) => (
            <li
              className="rounded-md border border-border bg-surface-subtle p-3"
              key={submission.id}
            >
              <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                <p className="text-label font-medium text-foreground">{originLabel(submission)}</p>
                <time className="font-num text-caption text-muted-foreground">
                  {submission.submittedAt}
                </time>
              </div>
              <div className="text-small text-foreground">{submission.body}</div>
            </li>
          ))}
        </ol>
        {latest ? (
          <Alert tone="info">
            <MessageSquareText aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Вердикт будет записан в {originLabel(latest)}</AlertTitle>
              <AlertDescription>
                Проверка сохранит неизменяемый список всех увиденных посылок. При разделении задач
                ответ останется у последней посылки.
              </AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
      </CardContent>
    </Card>
  )
}
