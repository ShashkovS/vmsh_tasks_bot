import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Bell, CalendarClock, CircleHelp, Mail, MessageCircleQuestion, Video } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { MathDocument } from '@vmsh/content'
import {
  AccountSessionManager,
  PageLayout,
  PageSection,
  PageStatePanel,
  type PageDisplayState,
} from '@vmsh/app-shell'
import {
  AttemptTimeline,
  ClassroomAssignmentStatus,
  ConnectionBanner,
  CourseCard,
  CourseContext,
  CourseGroupSwitcher,
  CourseNotificationSettings,
  DeadlineNotice,
  FeedbackAttention,
  FeedbackThread,
  HintDisclosure,
  ProblemHeader,
  PushPermissionCard,
  ReactionPicker,
  SolutionDisclosure,
  StrengthTrend,
  StudentProgress,
  SubmissionComposer,
  TaskListItem,
  TelegramRichPost,
  TestAnswer,
  VerdictPanel,
  findVerdict,
  fullVerdictScale,
  reactionsForScope,
  type TaskListItemView,
  type TaskType,
  type TelegramPostView,
  type ThreadMessageView,
  type TimelineEntry,
  type CourseEnrollmentView,
  type CourseView,
  type GroupView,
} from '@vmsh/product'
import {
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Separator,
  Switch,
  buttonVariants,
} from '@vmsh/ui'

/*
 * Student page compositions implement dev/design-system/05-pages-and-flows.md
 * (“Student PWA”) and docs/product-ux-decisions-2026-07.md. Route files own
 * navigation; apps/student/src/pages.stories.tsx proves page states and flows.
 */

const beginnerLevel = {
  id: 'math-beginner',
  courseId: 'math-5-7',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  code: 'н',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Начинающие',
  colorIndex: 1 as const,
}
const continuingLevel: GroupView = {
  id: 'math-continuing',
  courseId: 'math-5-7',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  code: 'п',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Продолжающие',
  colorIndex: 2,
}
const physicsIntro: GroupView = {
  id: 'physics-intro',
  courseId: 'physics-experiment',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  code: 'вв',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Вводная',
  colorIndex: 4,
}
const mathCourse: CourseView = {
  id: 'math-5-7',
  code: 'MATH-5-7',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Математика 5–7',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  subjectCode: 'Математика',
  accentIndex: 1,
}
const physicsCourse: CourseView = {
  id: 'physics-experiment',
  code: 'PHYS-EXP',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Физика: эксперимент',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  subjectCode: 'Физика',
  accentIndex: 4,
}
const studentEnrollments: CourseEnrollmentView[] = [
  {
    course: mathCourse,
    activeGroupId: beginnerLevel.id,
    allowedGroups: [beginnerLevel, continuingLevel],
    attendanceMode: 'in-person',
  },
  {
    course: physicsCourse,
    activeGroupId: physicsIntro.id,
    allowedGroups: [physicsIntro],
    attendanceMode: 'online',
  },
]
const acceptedVerdict = findVerdict(fullVerdictScale, 'plus')!
const partialVerdict = findVerdict(fullVerdictScale, 'plus-minus')!

const currentTasks: TaskListItemView[] = [
  {
    id: '41n-1',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    number: '41н.1',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    title: 'Разнообразные вагоны',
    type: 'test',
    status: {
      kind: 'accepted',
      get label() {
        return t`Зачтено`
      },
      tone: 'success',
    },
    verdict: acceptedVerdict,
  },
  {
    id: '41n-6',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    number: '41н.6',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    title: 'Расстановка ладей',
    type: 'written',
    status: {
      kind: 'needs-work',
      get label() {
        return t`Нужно дополнить`
      },
      tone: 'warning',
    },
    verdict: partialVerdict,
    hasNewFeedback: true,
  },
  {
    id: '41n-8',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    number: '41н.8',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    title: 'Четыре разреза',
    type: 'oral',
    status: {
      kind: 'not-started',
      get label() {
        return t`Не начато`
      },
      tone: 'neutral',
    },
  },
  {
    id: '41n-9',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    number: '41н.9',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    title: 'Клетчатый прямоугольник',
    type: 'written',
    status: {
      kind: 'queued',
      get label() {
        return t`В очереди`
      },
      tone: 'info',
    },
  },
]

function StatefulPage({
  state,
  title,
  children,
}: {
  state: PageDisplayState
  title: string
  children: ReactNode
}) {
  if (state === 'ready') return children
  return (
    <PageLayout title={title}>
      <PageStatePanel
        actionLabel={state === 'error' ? t`Повторить` : undefined}
        onAction={state === 'error' ? () => undefined : undefined}
        state={state}
      />
    </PageLayout>
  )
}

export function StudentTodayPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title={t`Сейчас`}>
      <PageLayout eyebrow={t`Ваши курсы`} title={t`Сейчас`}>
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <ConnectionBanner state="online" />
          </div>

          <PageSection title={t`Сейчас по курсам`}>
            <div className="grid gap-3 lg:grid-cols-2">
              <CourseCard
                classroomName="201"
                enrollment={studentEnrollments[0]!}
                lessonDate={t`26 января`}
                lessonNumber={41}
                phase={t`Решаем задачи · до воскресенья, 13:00 МСК`}
                progressLabel={t`3 из 12 задач зачтено`}
              />
              <CourseCard
                enrollment={studentEnrollments[1]!}
                lessonDate={t`29 января`}
                lessonNumber={9}
                phase={t`Условие опубликовано · сдача до 5 февраля`}
                progressLabel={t`1 из 4 задач зачтена`}
              />
            </div>
          </PageSection>

          <Alert tone="info">
            <CalendarClock aria-hidden="true" />
            <AlertContent>
              <AlertTitle>
                <>
                  {/* eslint-disable lingui/no-unlocalized-strings -- authored fixture content; docs/i18n.md */}
                  Разбор задач сегодня в 17:00{/* eslint-enable lingui/no-unlocalized-strings */}
                </>
              </AlertTitle>
              <AlertDescription>
                <Trans>Ссылка и код конференции появятся после открытия объявления.</Trans>
              </AlertDescription>
              <Button className="mt-2" size="xs" variant="outline">
                <Trans>Открыть объявление</Trans>
              </Button>
            </AlertContent>
          </Alert>

          <ClassroomAssignmentStatus
            audience="student"
            classroomName="201"
            publishedAt={t`25 января, 18:40`}
            status="assigned"
          />

          <Card>
            <CardContent className="grid gap-4 pt-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <div>
                <p className="text-caption text-muted-foreground">
                  <Trans>Текущая фаза</Trans>
                </p>
                <p className="mt-1 font-medium text-foreground">
                  <Trans>Решаем задачи</Trans>
                </p>
                <DeadlineNotice
                  absoluteLabel={t`воскресенья, 13:00 МСК`}
                  closesAt="2026-02-01T13:00:00+03:00"
                  relativeLabel={t`через 2 дня`}
                />
              </div>
              <div className="text-left sm:text-right">
                <p className="font-num text-title font-semibold">
                  <Trans>3 из 12</Trans>
                </p>
                <p className="text-caption text-muted-foreground">
                  <Trans>задачи зачтено</Trans>
                </p>
              </div>
            </CardContent>
          </Card>

          <PageSection
            action={
              <Button size="xs" variant="ghost">
                <Trans>Открыть весь листок</Trans>
              </Button>
            }
            description={t`Сначала показано то, где появилось новое или остался черновик.`}
            title={t`Продолжить`}
          >
            <div className="space-y-2">
              {currentTasks.slice(0, 3).map((task) => (
                <TaskListItem key={task.id} task={task} />
              ))}
            </div>
          </PageSection>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function StudentTasksPage({ state = 'ready' }: { state?: PageDisplayState }) {
  const [courseId, setCourseId] = useState(mathCourse.id)
  const enrollment =
    studentEnrollments.find((candidate) => candidate.course.id === courseId) ??
    studentEnrollments[0]!
  const [mathGroupId, setMathGroupId] = useState(beginnerLevel.id)
  const groupId = courseId === mathCourse.id ? mathGroupId : enrollment.activeGroupId
  return (
    <StatefulPage state={state} title={t`Задачи`}>
      <PageLayout
        description={t`Текущий листок и архив занятий. Внутри листка задачи всегда идут по номеру.`}
        eyebrow={t`Курс и доступные группы`}
        title={t`Задачи`}
      >
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <CourseContext
              activeCourseId={courseId}
              courses={studentEnrollments.map(({ course }) => course)}
              onCourseChange={setCourseId}
            />
            <label className="space-y-1 text-label font-medium">
              <Trans>Занятие</Trans>
              <select className="min-h-(--touch-target) w-full rounded-md border border-input bg-surface px-3 text-small">
                <option value={t`41 · 26 января`}>
                  <Trans>41 · 26 января</Trans>
                </option>
                <option value={t`40 · 19 января`}>
                  <Trans>40 · 19 января</Trans>
                </option>
                <option value={t`39 · 12 января`}>
                  <Trans>39 · 12 января</Trans>
                </option>
              </select>
            </label>
          </div>
          <CourseGroupSwitcher
            activeGroupId={groupId}
            course={enrollment.course}
            groups={enrollment.allowedGroups}
            {...(courseId === mathCourse.id ? { onChange: setMathGroupId } : {})}
          />
          <div className="flex flex-wrap gap-2" aria-label={t`Фильтр задач`}>
            <Button size="sm">
              <Trans>Все</Trans>
            </Button>
            <Button size="sm" variant="outline">
              <Trans>Не начаты</Trans>
            </Button>
            <Button size="sm" variant="outline">
              <Trans>Ждут вас</Trans>
            </Button>
            <Button size="sm" variant="outline">
              <Trans>Зачтены</Trans>
            </Button>
          </div>
          <PageSection description={t`12 задач · 3 зачтено · 2 на проверке`} title={t`Занятие 41`}>
            <div className="space-y-2">
              {currentTasks.map((task) => (
                <TaskListItem key={task.id} task={task} />
              ))}
            </div>
          </PageSection>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function StudentTaskPage({
  taskId,
  kind,
  state = 'ready',
}: {
  taskId: string
  kind?: TaskType
  state?: PageDisplayState
}) {
  const [answer, setAnswer] = useState('')
  const [showFormatError, setShowFormatError] = useState(false)
  const [solutionText, setSolutionText] = useState('')
  const taskKind: TaskType =
    kind ?? (taskId.endsWith('1') ? 'test' : taskId.endsWith('8') ? 'oral' : 'written')

  return (
    <StatefulPage state={state} title={t`Задача ${taskId}`}>
      <PageLayout
        width="reading"
        title={
          /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Расстановка ладей' /* eslint-enable lingui/no-unlocalized-strings */
        }
        eyebrow={t`Занятие 41`}
      >
        <article className="space-y-5">
          <ProblemHeader
            deadline={
              <DeadlineNotice
                absoluteLabel={t`воскресенья, 13:00 МСК`}
                closesAt="2026-02-01T13:00:00+03:00"
                relativeLabel={t`через 2 дня`}
              />
            }
            level={beginnerLevel}
            number={
              taskKind === 'test'
                ? /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ '41н.1' /* eslint-enable lingui/no-unlocalized-strings */
                : taskKind === 'oral'
                  ? /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ '41н.8' /* eslint-enable lingui/no-unlocalized-strings */
                  : /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ '41н.6' /* eslint-enable lingui/no-unlocalized-strings */
            }
            onShowHistory={() => undefined}
            title={
              taskKind === 'test'
                ? /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Разнообразные вагоны' /* eslint-enable lingui/no-unlocalized-strings */
                : taskKind === 'oral'
                  ? /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Четыре разреза' /* eslint-enable lingui/no-unlocalized-strings */
                  : /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Расстановка ладей' /* eslint-enable lingui/no-unlocalized-strings */
            }
            type={taskKind}
          />

          <MathDocument>
            <p>
              <>
                {/* eslint-disable lingui/no-unlocalized-strings -- authored fixture content; docs/i18n.md */}
                На доске <span data-math-inline="true">n × n</span> расставляют ладьи так, чтобы
                никакие две не били друг друга. Найдите число способов расставить ровно{' '}
                <span data-math-inline="true">k</span> ладей и объясните ответ.
                {/* eslint-enable lingui/no-unlocalized-strings */}
              </>
            </p>
            <ol>
              <li>
                <>
                  {/* eslint-disable lingui/no-unlocalized-strings -- authored fixture content; docs/i18n.md */}
                  Разберите случай k = 1.{/* eslint-enable lingui/no-unlocalized-strings */}
                </>
              </li>
              <li>
                <>
                  {/* eslint-disable lingui/no-unlocalized-strings -- authored fixture content; docs/i18n.md */}
                  Разберите случай k = n.{/* eslint-enable lingui/no-unlocalized-strings */}
                </>
              </li>
              <li>
                <>
                  {/* eslint-disable lingui/no-unlocalized-strings -- authored fixture content; docs/i18n.md */}
                  Объясните общий ответ.{/* eslint-enable lingui/no-unlocalized-strings */}
                </>
              </li>
            </ol>
          </MathDocument>

          <div className="space-y-2">
            <HintDisclosure meta={t`открыта 31 января`}>
              <>
                {/* eslint-disable lingui/no-unlocalized-strings -- authored fixture content; docs/i18n.md */}
                Сначала выберите строки и столбцы, в которых будут стоять ладьи.
                {/* eslint-enable lingui/no-unlocalized-strings */}
              </>
            </HintDisclosure>
            <SolutionDisclosure lockedNote={t`откроется 1 февраля, 13:00`}>
              <Trans>Решение появится после дедлайна.</Trans>
            </SolutionDisclosure>
          </div>

          <Separator />

          {taskKind === 'test' ? (
            <Card>
              <CardHeader>
                <CardTitle>
                  <Trans>Ваш ответ</Trans>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <TestAnswer
                  label={t`Число способов`}
                  onChange={setAnswer}
                  showFormatError={showFormatError}
                  spec={{ type: 'natural' }}
                />
                <Button
                  disabled={!answer.trim()}
                  onClick={() => setShowFormatError(true)}
                  className="w-full sm:w-auto"
                >
                  <Trans>Проверить</Trans>
                </Button>
                <p className="text-caption text-muted-foreground">
                  <Trans>Осталось 4 попытки.</Trans>
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {taskKind === 'oral' ? (
                <Alert tone="info">
                  <Video aria-hidden="true" />
                  <AlertContent>
                    <AlertTitle>
                      <Trans>Устный приём открыт до 19:30</Trans>
                    </AlertTitle>
                    <AlertDescription>
                      <Trans>
                        Данные конференции показываются только после вашего действия. Позиции в
                        очереди нет.
                      </Trans>
                    </AlertDescription>
                    <Button className="mt-2" size="sm" variant="outline">
                      <Trans>Показать данные для входа</Trans>
                    </Button>
                  </AlertContent>
                </Alert>
              ) : null}
              <SubmissionComposer
                attachments={[]}
                draftSavedAt="12:08"
                onAddPhotos={() => undefined}
                onSubmit={() => undefined}
                onTextChange={setSolutionText}
                taskType={taskKind}
                text={solutionText}
              />
            </div>
          )}

          <Button variant="ghost">
            <CircleHelp aria-hidden="true" />
            <Trans>Задать вопрос по задаче</Trans>
          </Button>
        </article>
      </PageLayout>
    </StatefulPage>
  )
}

const threadMessages: ThreadMessageView[] = [
  {
    id: 'student-1',
    author: {
      kind: 'student',
      get name() {
        return t`Вы`
      },
    },
    get at() {
      return t`25 января, 21:04`
    },
    channel: 'pwa',
    own: true,
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    body: 'Я сначала разобрал случай k = n. На второй странице — общий случай.',
  },
  {
    id: 'teacher-1',
    author: {
      kind: 'teacher',
      // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
      name: 'И. Соколов',
    },
    get at() {
      return t`26 января, 12:30`
    },
    channel: 'pwa',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    body: 'Идея верная. Не хватает отдельного объяснения для k = 1.',
  },
]

const resultTimeline: TimelineEntry[] = [
  {
    id: 'v1',
    get at() {
      return t`26 января, 12:30`
    },
    get label() {
      return t`Проверено`
    },
    verdict: partialVerdict,
  },
  {
    id: 's1',
    get at() {
      return t`25 января, 21:04`
    },
    get label() {
      return t`Решение отправлено`
    },
  },
]

export function StudentSubmissionPage({
  submissionId,
  state = 'ready',
}: {
  submissionId: string
  state?: PageDisplayState
}) {
  const [reaction, setReaction] = useState<number | null>(null)
  const [reply, setReply] = useState('')

  return (
    <StatefulPage state={state} title={t`Результат и обсуждение`}>
      <PageLayout
        description={t`Запись ${submissionId} · последнее обновление 26 января, 12:30`}
        eyebrow={t`41н.6 · Расстановка ладей`}
        title={t`Нужно дополнить решение`}
        width="reading"
      >
        <div className="space-y-5">
          <div className="flex justify-end">
            <FeedbackAttention label={t`Новая проверка`} />
          </div>
          <VerdictPanel
            at={t`26 января, 12:30`}
            author={
              /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'И. Соколов' /* eslint-enable lingui/no-unlocalized-strings */
            }
            comment={
              /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Идея верная. Не хватает разбора случая k = 1 — дополните и присылайте.' /* eslint-enable lingui/no-unlocalized-strings */
            }
            verdict={partialVerdict}
          />
          <PageSection title={t`Обсуждение`}>
            <FeedbackThread messages={threadMessages} />
          </PageSection>
          <Card>
            <CardContent className="space-y-3 pt-5">
              <SubmissionComposer
                attachments={[]}
                draftSavedAt="12:42"
                onAddPhotos={() => undefined}
                onSubmit={() => undefined}
                onTextChange={setReply}
                taskType="written"
                text={reply}
              />
              <p className="text-caption text-muted-foreground">
                <Trans>Ответ и пересдача — продолжение этого же обсуждения.</Trans>
              </p>
            </CardContent>
          </Card>
          <ReactionPicker
            legend={t`Ваша реакция на проверку`}
            onSelect={setReaction}
            options={reactionsForScope('student-written')}
            value={reaction}
          />
          <PageSection title={t`История`}>
            <AttemptTimeline entries={resultTimeline} />
          </PageSection>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

const lessonPost: TelegramPostView = {
  id: 'post-41',
  attribution: {
    get channel() {
      return t`ВМШ 179`
    },
  },
  get at() {
    return t`26 января, 16:30`
  },
  state: 'published',
  blocks: [
    {
      kind: 'heading',
      level: 2,
      // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
      text: 'Задачи 41-го занятия',
    },
    {
      kind: 'text',
      // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
      text: 'Опубликованы условия для всех уровней. Письменные решения принимаются до воскресенья, 13:00 МСК.',
    },
    {
      kind: 'list',
      items: [
        {
          // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
          text: 'Начните с тестовых задач.',
        },
        {
          // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
          text: 'После самостоятельной попытки можно открыть подсказку.',
        },
      ],
    },
  ],
}

export function StudentNewsPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title={t`Новости`}>
      <PageLayout
        description={t`Публикации Telegram-канала и объявления кружка, сохранённые для чтения без сети.`}
        title={t`Новости`}
      >
        <div className="space-y-3">
          <TelegramRichPost post={lessonPost} variant="card" />
          <TelegramRichPost
            post={{
              ...lessonPost,
              id: 'post-hints',
              at: t`31 января, 12:00`,
              blocks: [
                {
                  kind: 'heading',
                  level: 3,
                  text: /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Подсказки открыты' /* eslint-enable lingui/no-unlocalized-strings */,
                },
                {
                  kind: 'text',
                  text: /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Если задача не поддаётся, попробуйте воспользоваться подсказкой.' /* eslint-enable lingui/no-unlocalized-strings */,
                },
              ],
            }}
            variant="card"
          />
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function StudentNewsDetailPage({
  postId,
  state = 'ready',
}: {
  postId: string
  state?: PageDisplayState
}) {
  return (
    <StatefulPage state={state} title={t`Публикация`}>
      <PageLayout
        description={t`Публикация ${postId}`}
        title={
          /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Задачи 41-го занятия' /* eslint-enable lingui/no-unlocalized-strings */
        }
        width="reading"
      >
        <TelegramRichPost post={lessonPost} />
      </PageLayout>
    </StatefulPage>
  )
}

const strengthLessons = [
  {
    lesson: '37',
    simple: 6.8,
    complex: 3.1,
    difficulty: 7.4,
    solved: '5/12',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    group: 'н',
  },
  {
    lesson: '38',
    simple: 7.5,
    complex: 3.8,
    difficulty: 7.1,
    solved: '7/13',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    group: 'н',
  },
  {
    lesson: '39',
    simple: 7.1,
    complex: 4.6,
    difficulty: 7.8,
    solved: '6/12',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    group: 'н',
  },
  {
    lesson: '40',
    simple: 8.0,
    complex: 5.1,
    difficulty: 7.2,
    solved: '8/14',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    group: 'н',
  },
  {
    lesson: '41',
    simple: 8.4,
    complex: 5.4,
    difficulty: 7.6,
    solved: '3/12',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    group: 'н',
  },
]

export function StudentProgressPage({ state = 'ready' }: { state?: PageDisplayState }) {
  const [courseId, setCourseId] = useState(mathCourse.id)
  const course = courseId === mathCourse.id ? mathCourse : physicsCourse
  const isMath = courseId === mathCourse.id
  return (
    <StatefulPage state={state} title={t`Прогресс`}>
      <PageLayout
        description={t`Ваша личная динамика. Здесь нет рейтинга и сравнения с другими школьниками.`}
        title={t`Прогресс`}
      >
        <div className="space-y-6">
          <CourseContext
            activeCourseId={courseId}
            courses={[mathCourse, physicsCourse]}
            onCourseChange={setCourseId}
          />
          <Card>
            <CardContent className="pt-5">
              <StudentProgress
                achievements={
                  isMath
                    ? [t`Первое письменное решение зачтено`, t`Работа в три разных дня недели`]
                    : [t`Первый физический эксперимент описан`]
                }
                attemptedCount={isMath ? 12 : 4}
                solvedCount={isMath ? 3 : 1}
                {...(isMath ? { streakDays: 4 } : {})}
              />
            </CardContent>
          </Card>
          <PageSection
            description={t`0 — пока трудно, 10 — получается почти любая задача.`}
            title={t`Как меняется работа`}
          >
            <StrengthTrend
              caption={t`Личная динамика только по курсу «${course.name}».`}
              points={
                isMath
                  ? strengthLessons
                  : [
                      {
                        lesson: '7',
                        simple: 5.8,
                        complex: 2.7,
                        solved: '2/4',
                        group:
                          /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'вв' /* eslint-enable lingui/no-unlocalized-strings */,
                      },
                      {
                        lesson: '8',
                        simple: 6.4,
                        complex: 3.5,
                        solved: '3/4',
                        group:
                          /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'вв' /* eslint-enable lingui/no-unlocalized-strings */,
                      },
                      {
                        lesson: '9',
                        simple: 6.9,
                        complex: 3.9,
                        solved: '1/3',
                        group:
                          /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'вв' /* eslint-enable lingui/no-unlocalized-strings */,
                      },
                    ]
              }
            />
          </PageSection>
          <PageSection title={t`Активность по дням`}>
            <div
              className="grid grid-cols-7 gap-1"
              aria-label={t`Число отправок за последние четыре недели`}
            >
              {Array.from({ length: 28 }, (_, index) => {
                const count = [0, 1, 2, 1, 0, 3, 1][index % 7]!
                return (
                  <span
                    aria-label={t`${count} отправок`}
                    className={`aspect-square rounded-sm border border-border ${count === 0 ? 'bg-surface-sunken' : count > 2 ? 'bg-chart-2' : 'bg-chart-2/30'}`}
                    key={index}
                    role="img"
                    title={t`${count} отправок`}
                  />
                )
              })}
            </div>
          </PageSection>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function StudentProfilePage({
  state = 'ready',
  sessionManagement,
}: {
  state?: PageDisplayState
  sessionManagement?: ReactNode
}) {
  return (
    <StatefulPage state={state} title={t`Профиль`}>
      <PageLayout
        description={t`Начинающие · очный режим`}
        title={
          /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Василий Петров' /* eslint-enable lingui/no-unlocalized-strings */
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>
                <Trans>Учёба</Trans>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-small">
              <p>
                <Trans>
                  <strong>Активная группа:</strong> Начинающие
                </Trans>
              </p>
              <p>
                <Trans>
                  <strong>Доступны:</strong> Начинающие, Продолжающие
                </Trans>
              </p>
              <Button size="sm" variant="outline">
                <Trans>Изменить уровень</Trans>
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>
                <Trans>Режим участия</Trans>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-small">
              <p>
                <Trans>
                  <strong>Сейчас:</strong> очно в школе
                </Trans>
              </p>
              <p className="text-muted-foreground">
                <Trans>
                  Если вы не придёте, переключитесь в online: для вас резервируют место и печатают
                  листок.
                </Trans>
              </p>
              <Button size="sm" variant="outline">
                <Trans>Переключить режим</Trans>
              </Button>
            </CardContent>
          </Card>
          {sessionManagement ?? <AccountSessionManager />}
          <Card>
            <CardHeader>
              <CardTitle>
                <Trans>Помощь</Trans>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-x-5 gap-y-3 text-small">
              <a
                className={buttonVariants({ size: 'sm', variant: 'outline' })}
                href="/student/questions"
              >
                <MessageCircleQuestion aria-hidden="true" /> <Trans>Мои вопросы</Trans>
              </a>
              <a
                className="inline-flex items-center gap-2 text-link underline-offset-2 hover:underline"
                href="mailto:vmsh@179.ru"
              >
                <Mail aria-hidden="true" className="size-4" /> vmsh@179.ru
              </a>
            </CardContent>
          </Card>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

const notificationCategories = () =>
  [
    [t`Новый урок`, t`Условия нового занятия`],
    [t`Подсказки и решения`, t`Когда материалы становятся доступны`],
    [t`Проверка завершена`, t`Уведомления объединяются в течение 30 минут`],
    [t`Комментарии`, t`Новая запись в обсуждении`],
    [t`Дедлайн`, t`Напоминание до публикации решений`],
  ] as const

export function StudentNotificationsPage({ state = 'ready' }: { state?: PageDisplayState }) {
  const [coursePreferences, setCoursePreferences] = useState([
    { course: mathCourse, category: t`Проверка завершена`, enabled: true, inherited: true },
    { course: physicsCourse, category: t`Новый урок`, enabled: false, inherited: false },
  ])
  return (
    <StatefulPage state={state} title={t`Уведомления`}>
      <PageLayout
        description={t`Push можно включать и отключать по категориям.`}
        eyebrow={t`Профиль`}
        title={t`Уведомления`}
      >
        <div className="space-y-5">
          <PushPermissionCard
            categories={notificationCategories()
              .slice(0, 3)
              .map(([label, description], index) => ({ id: String(index), label, description }))}
          />
          <Card>
            <CardContent className="divide-y divide-border pt-1">
              {notificationCategories().map(([label, description], index) => (
                <div className="flex items-center justify-between gap-4 py-3" key={label}>
                  <div>
                    <p className="text-small font-medium">{label}</p>
                    <p className="text-caption text-muted-foreground">{description}</p>
                  </div>
                  <Switch aria-label={label} defaultChecked={index !== 4} />
                </div>
              ))}
            </CardContent>
          </Card>
          <CourseNotificationSettings
            onToggle={(courseId, category, enabled) =>
              setCoursePreferences((current) =>
                current.map((preference) =>
                  preference.course.id === courseId && preference.category === category
                    ? { ...preference, enabled, inherited: false }
                    : preference,
                ),
              )
            }
            preferences={coursePreferences}
          />
          <Alert tone="neutral">
            <Bell aria-hidden="true" />
            <AlertContent>
              <AlertTitle>
                <Trans>Звук только с 9:00 до 21:00</Trans>
              </AlertTitle>
              <AlertDescription>
                <Trans>Ночью новые события видны в приложении, но не будят вас.</Trans>
              </AlertDescription>
            </AlertContent>
          </Alert>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export { StudentLoginPage, type StudentLoginState } from './login-page'
