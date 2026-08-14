import {
  Bell,
  CalendarClock,
  CircleHelp,
  Eye,
  EyeOff,
  Mail,
  MessageCircleQuestion,
  Send,
  ShieldCheck,
  Video,
} from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import { MathDocument } from '@vmsh/content'
import {
  AccountSessionManager,
  PageLayout,
  PageSection,
  PageStatePanel,
  type PageDisplayState,
} from '@vmsh/app-shell'
import type { StudentLoginRequest } from '@vmsh/contracts'
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
  Input,
  Label,
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
  code: 'н',
  name: 'Начинающие',
  colorIndex: 1 as const,
}
const continuingLevel: GroupView = {
  id: 'math-continuing',
  courseId: 'math-5-7',
  code: 'п',
  name: 'Продолжающие',
  colorIndex: 2,
}
const physicsIntro: GroupView = {
  id: 'physics-intro',
  courseId: 'physics-experiment',
  code: 'вв',
  name: 'Вводная',
  colorIndex: 4,
}
const mathCourse: CourseView = {
  id: 'math-5-7',
  code: 'MATH-5-7',
  name: 'Математика 5–7',
  subjectCode: 'Математика',
  accentIndex: 1,
}
const physicsCourse: CourseView = {
  id: 'physics-experiment',
  code: 'PHYS-EXP',
  name: 'Физика: эксперимент',
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
    number: '41н.1',
    title: 'Разнообразные вагоны',
    type: 'test',
    status: { kind: 'accepted', label: 'Зачтено', tone: 'success' },
    verdict: acceptedVerdict,
  },
  {
    id: '41n-6',
    number: '41н.6',
    title: 'Расстановка ладей',
    type: 'written',
    status: { kind: 'needs-work', label: 'Нужно дополнить', tone: 'warning' },
    verdict: partialVerdict,
    hasNewFeedback: true,
  },
  {
    id: '41n-8',
    number: '41н.8',
    title: 'Четыре разреза',
    type: 'oral',
    status: { kind: 'not-started', label: 'Не начато', tone: 'neutral' },
  },
  {
    id: '41n-9',
    number: '41н.9',
    title: 'Клетчатый прямоугольник',
    type: 'written',
    status: { kind: 'queued', label: 'В очереди', tone: 'info' },
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
        actionLabel={state === 'error' ? 'Повторить' : undefined}
        onAction={state === 'error' ? () => undefined : undefined}
        state={state}
      />
    </PageLayout>
  )
}

export function StudentTodayPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Сейчас">
      <PageLayout eyebrow="Ваши курсы" title="Сейчас">
        <div className="space-y-5">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <ConnectionBanner state="online" />
          </div>

          <PageSection title="Сейчас по курсам">
            <div className="grid gap-3 lg:grid-cols-2">
              <CourseCard
                classroomName="201"
                enrollment={studentEnrollments[0]!}
                lessonDate="26 января"
                lessonNumber={41}
                phase="Решаем задачи · до воскресенья, 13:00 МСК"
                progressLabel="3 из 12 задач зачтено"
              />
              <CourseCard
                enrollment={studentEnrollments[1]!}
                lessonDate="29 января"
                lessonNumber={9}
                phase="Условие опубликовано · сдача до 5 февраля"
                progressLabel="1 из 4 задач зачтена"
              />
            </div>
          </PageSection>

          <Alert tone="info">
            <CalendarClock aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Разбор задач сегодня в 17:00</AlertTitle>
              <AlertDescription>
                Ссылка и код конференции появятся после открытия объявления.
              </AlertDescription>
              <Button className="mt-2" size="xs" variant="outline">
                Открыть объявление
              </Button>
            </AlertContent>
          </Alert>

          <ClassroomAssignmentStatus
            audience="student"
            classroomName="201"
            publishedAt="25 января, 18:40"
            status="assigned"
          />

          <Card>
            <CardContent className="grid gap-4 pt-5 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <div>
                <p className="text-caption text-muted-foreground">Текущая фаза</p>
                <p className="mt-1 font-medium text-foreground">Решаем задачи</p>
                <DeadlineNotice
                  absoluteLabel="воскресенья, 13:00 МСК"
                  closesAt="2026-02-01T13:00:00+03:00"
                  relativeLabel="через 2 дня"
                />
              </div>
              <div className="text-left sm:text-right">
                <p className="font-num text-title font-semibold">3 из 12</p>
                <p className="text-caption text-muted-foreground">задачи зачтено</p>
              </div>
            </CardContent>
          </Card>

          <PageSection
            action={
              <Button size="xs" variant="ghost">
                Открыть весь листок
              </Button>
            }
            description="Сначала показано то, где появилось новое или остался черновик."
            title="Продолжить"
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
    <StatefulPage state={state} title="Задачи">
      <PageLayout
        description="Текущий листок и архив занятий. Внутри листка задачи всегда идут по номеру."
        eyebrow="Курс и доступные группы"
        title="Задачи"
      >
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <CourseContext
              activeCourseId={courseId}
              courses={studentEnrollments.map(({ course }) => course)}
              onCourseChange={setCourseId}
            />
            <label className="space-y-1 text-label font-medium">
              Занятие
              <select className="min-h-(--touch-target) w-full rounded-md border border-input bg-surface px-3 text-small">
                <option>41 · 26 января</option>
                <option>40 · 19 января</option>
                <option>39 · 12 января</option>
              </select>
            </label>
          </div>
          <CourseGroupSwitcher
            activeGroupId={groupId}
            course={enrollment.course}
            groups={enrollment.allowedGroups}
            {...(courseId === mathCourse.id ? { onChange: setMathGroupId } : {})}
          />
          <div className="flex flex-wrap gap-2" aria-label="Фильтр задач">
            <Button size="sm">Все</Button>
            <Button size="sm" variant="outline">
              Не начаты
            </Button>
            <Button size="sm" variant="outline">
              Ждут вас
            </Button>
            <Button size="sm" variant="outline">
              Зачтены
            </Button>
          </div>
          <PageSection description="12 задач · 3 зачтено · 2 на проверке" title="Занятие 41">
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
    <StatefulPage state={state} title={`Задача ${taskId}`}>
      <PageLayout width="reading" title="Расстановка ладей" eyebrow="Занятие 41">
        <article className="space-y-5">
          <ProblemHeader
            deadline={
              <DeadlineNotice
                absoluteLabel="воскресенья, 13:00 МСК"
                closesAt="2026-02-01T13:00:00+03:00"
                relativeLabel="через 2 дня"
              />
            }
            level={beginnerLevel}
            number={taskKind === 'test' ? '41н.1' : taskKind === 'oral' ? '41н.8' : '41н.6'}
            onShowHistory={() => undefined}
            title={
              taskKind === 'test'
                ? 'Разнообразные вагоны'
                : taskKind === 'oral'
                  ? 'Четыре разреза'
                  : 'Расстановка ладей'
            }
            type={taskKind}
          />

          <MathDocument>
            <p>
              На доске <span data-math-inline="true">n × n</span> расставляют ладьи так, чтобы
              никакие две не били друг друга. Найдите число способов расставить ровно{' '}
              <span data-math-inline="true">k</span> ладей и объясните ответ.
            </p>
            <ol>
              <li>Разберите случай k = 1.</li>
              <li>Разберите случай k = n.</li>
              <li>Объясните общий ответ.</li>
            </ol>
          </MathDocument>

          <div className="space-y-2">
            <HintDisclosure meta="открыта 31 января">
              Сначала выберите строки и столбцы, в которых будут стоять ладьи.
            </HintDisclosure>
            <SolutionDisclosure lockedNote="откроется 1 февраля, 13:00">
              Решение появится после дедлайна.
            </SolutionDisclosure>
          </div>

          <Separator />

          {taskKind === 'test' ? (
            <Card>
              <CardHeader>
                <CardTitle>Ваш ответ</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <TestAnswer
                  label="Число способов"
                  onChange={setAnswer}
                  showFormatError={showFormatError}
                  spec={{ type: 'natural' }}
                />
                <Button
                  disabled={!answer.trim()}
                  onClick={() => setShowFormatError(true)}
                  className="w-full sm:w-auto"
                >
                  Проверить
                </Button>
                <p className="text-caption text-muted-foreground">Осталось 4 попытки.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {taskKind === 'oral' ? (
                <Alert tone="info">
                  <Video aria-hidden="true" />
                  <AlertContent>
                    <AlertTitle>Устный приём открыт до 19:30</AlertTitle>
                    <AlertDescription>
                      Данные конференции показываются только после вашего действия. Позиции в
                      очереди нет.
                    </AlertDescription>
                    <Button className="mt-2" size="sm" variant="outline">
                      Показать данные для входа
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
            Задать вопрос по задаче
          </Button>
        </article>
      </PageLayout>
    </StatefulPage>
  )
}

const threadMessages: ThreadMessageView[] = [
  {
    id: 'student-1',
    author: { kind: 'student', name: 'Вы' },
    at: '25 января, 21:04',
    channel: 'pwa',
    own: true,
    body: 'Я сначала разобрал случай k = n. На второй странице — общий случай.',
  },
  {
    id: 'teacher-1',
    author: { kind: 'teacher', name: 'И. Соколов' },
    at: '26 января, 12:30',
    channel: 'pwa',
    body: 'Идея верная. Не хватает отдельного объяснения для k = 1.',
  },
]

const resultTimeline: TimelineEntry[] = [
  { id: 'v1', at: '26 января, 12:30', label: 'Проверено', verdict: partialVerdict },
  { id: 's1', at: '25 января, 21:04', label: 'Решение отправлено' },
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
    <StatefulPage state={state} title="Результат и обсуждение">
      <PageLayout
        description={`Запись ${submissionId} · последнее обновление 26 января, 12:30`}
        eyebrow="41н.6 · Расстановка ладей"
        title="Нужно дополнить решение"
        width="reading"
      >
        <div className="space-y-5">
          <div className="flex justify-end">
            <FeedbackAttention label="Новая проверка" />
          </div>
          <VerdictPanel
            at="26 января, 12:30"
            author="И. Соколов"
            comment="Идея верная. Не хватает разбора случая k = 1 — дополните и присылайте."
            verdict={partialVerdict}
          />
          <PageSection title="Обсуждение">
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
                Ответ и пересдача — продолжение этого же обсуждения.
              </p>
            </CardContent>
          </Card>
          <ReactionPicker
            legend="Ваша реакция на проверку"
            onSelect={setReaction}
            options={reactionsForScope('student-written')}
            value={reaction}
          />
          <PageSection title="История">
            <AttemptTimeline entries={resultTimeline} />
          </PageSection>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

const lessonPost: TelegramPostView = {
  id: 'post-41',
  attribution: { channel: 'ВМШ 179' },
  at: '26 января, 16:30',
  state: 'published',
  blocks: [
    { kind: 'heading', level: 2, text: 'Задачи 41-го занятия' },
    {
      kind: 'text',
      text: 'Опубликованы условия для всех уровней. Письменные решения принимаются до воскресенья, 13:00 МСК.',
    },
    {
      kind: 'list',
      items: [
        { text: 'Начните с тестовых задач.' },
        { text: 'После самостоятельной попытки можно открыть подсказку.' },
      ],
    },
  ],
}

export function StudentNewsPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Новости">
      <PageLayout
        description="Публикации Telegram-канала и объявления кружка, сохранённые для чтения без сети."
        title="Новости"
      >
        <div className="space-y-3">
          <TelegramRichPost post={lessonPost} variant="card" />
          <TelegramRichPost
            post={{
              ...lessonPost,
              id: 'post-hints',
              at: '31 января, 12:00',
              blocks: [
                { kind: 'heading', level: 3, text: 'Подсказки открыты' },
                {
                  kind: 'text',
                  text: 'Если задача не поддаётся, попробуйте воспользоваться подсказкой.',
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
    <StatefulPage state={state} title="Публикация">
      <PageLayout description={`Публикация ${postId}`} title="Задачи 41-го занятия" width="reading">
        <TelegramRichPost post={lessonPost} />
      </PageLayout>
    </StatefulPage>
  )
}

const strengthLessons = [
  { lesson: '37', simple: 6.8, complex: 3.1, difficulty: 7.4, solved: '5/12', group: 'н' },
  { lesson: '38', simple: 7.5, complex: 3.8, difficulty: 7.1, solved: '7/13', group: 'н' },
  { lesson: '39', simple: 7.1, complex: 4.6, difficulty: 7.8, solved: '6/12', group: 'н' },
  { lesson: '40', simple: 8.0, complex: 5.1, difficulty: 7.2, solved: '8/14', group: 'н' },
  { lesson: '41', simple: 8.4, complex: 5.4, difficulty: 7.6, solved: '3/12', group: 'н' },
]

export function StudentProgressPage({ state = 'ready' }: { state?: PageDisplayState }) {
  const [courseId, setCourseId] = useState(mathCourse.id)
  const course = courseId === mathCourse.id ? mathCourse : physicsCourse
  const isMath = courseId === mathCourse.id
  return (
    <StatefulPage state={state} title="Прогресс">
      <PageLayout
        description="Ваша личная динамика. Здесь нет рейтинга и сравнения с другими школьниками."
        title="Прогресс"
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
                    ? ['Первое письменное решение зачтено', 'Работа в три разных дня недели']
                    : ['Первый физический эксперимент описан']
                }
                attemptedCount={isMath ? 12 : 4}
                solvedCount={isMath ? 3 : 1}
                {...(isMath ? { streakDays: 4 } : {})}
              />
            </CardContent>
          </Card>
          <PageSection
            description="0 — пока трудно, 10 — получается почти любая задача."
            title="Как меняется работа"
          >
            <StrengthTrend
              caption={`Личная динамика только по курсу «${course.name}».`}
              points={
                isMath
                  ? strengthLessons
                  : [
                      {
                        lesson: '7',
                        simple: 5.8,
                        complex: 2.7,
                        solved: '2/4',
                        group: 'вв',
                      },
                      {
                        lesson: '8',
                        simple: 6.4,
                        complex: 3.5,
                        solved: '3/4',
                        group: 'вв',
                      },
                      {
                        lesson: '9',
                        simple: 6.9,
                        complex: 3.9,
                        solved: '1/3',
                        group: 'вв',
                      },
                    ]
              }
            />
          </PageSection>
          <PageSection title="Активность по дням">
            <div
              className="grid grid-cols-7 gap-1"
              aria-label="Число отправок за последние четыре недели"
            >
              {Array.from({ length: 28 }, (_, index) => {
                const count = [0, 1, 2, 1, 0, 3, 1][index % 7]!
                return (
                  <span
                    aria-label={`${count} отправок`}
                    className={`aspect-square rounded-sm border border-border ${count === 0 ? 'bg-surface-sunken' : count > 2 ? 'bg-chart-2' : 'bg-chart-2/30'}`}
                    key={index}
                    role="img"
                    title={`${count} отправок`}
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
    <StatefulPage state={state} title="Профиль">
      <PageLayout description="Начинающие · очный режим" title="Василий Петров">
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Учёба</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-small">
              <p>
                <strong>Активная группа:</strong> Начинающие
              </p>
              <p>
                <strong>Доступны:</strong> Начинающие, Продолжающие
              </p>
              <Button size="sm" variant="outline">
                Изменить уровень
              </Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Режим участия</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-small">
              <p>
                <strong>Сейчас:</strong> очно в школе
              </p>
              <p className="text-muted-foreground">
                Если вы не придёте, переключитесь в online: для вас резервируют место и печатают
                листок.
              </p>
              <Button size="sm" variant="outline">
                Переключить режим
              </Button>
            </CardContent>
          </Card>
          {sessionManagement ?? <AccountSessionManager />}
          <Card>
            <CardHeader>
              <CardTitle>Помощь</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-small">
              <a
                className={buttonVariants({ size: 'sm', variant: 'outline' })}
                href="/student/questions"
              >
                <MessageCircleQuestion aria-hidden="true" /> Мои вопросы
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

const notificationCategories = [
  ['Новый урок', 'Условия нового занятия'],
  ['Подсказки и решения', 'Когда материалы становятся доступны'],
  ['Проверка завершена', 'Уведомления объединяются в течение 30 минут'],
  ['Комментарии', 'Новая запись в обсуждении'],
  ['Дедлайн', 'Напоминание до публикации решений'],
] as const

export function StudentNotificationsPage({ state = 'ready' }: { state?: PageDisplayState }) {
  const [coursePreferences, setCoursePreferences] = useState([
    { course: mathCourse, category: 'Проверка завершена', enabled: true, inherited: true },
    { course: physicsCourse, category: 'Новый урок', enabled: false, inherited: false },
  ])
  return (
    <StatefulPage state={state} title="Уведомления">
      <PageLayout
        description="Push можно включать и отключать по категориям."
        eyebrow="Профиль"
        title="Уведомления"
      >
        <div className="space-y-5">
          <PushPermissionCard
            categories={notificationCategories
              .slice(0, 3)
              .map(([label, description], index) => ({ id: String(index), label, description }))}
          />
          <Card>
            <CardContent className="divide-y divide-border pt-1">
              {notificationCategories.map(([label, description], index) => (
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
              <AlertTitle>Звук только с 9:00 до 21:00</AlertTitle>
              <AlertDescription>
                Ночью новые события видны в приложении, но не будят вас.
              </AlertDescription>
            </AlertContent>
          </Alert>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export type StudentLoginState =
  | 'idle'
  | 'pending'
  | 'invalid'
  | 'rate-limited'
  | 'account-unavailable'
  | 'blocked'
  | 'network'
  | 'error'

export function StudentLoginPage({
  loginState = 'idle',
  onSubmit,
}: {
  loginState?: StudentLoginState
  onSubmit?: (request: StudentLoginRequest) => void | Promise<void>
}) {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [telegramToken, setTelegramToken] = useState('')
  const errorCopy = {
    invalid: 'Логин или токен не подошли. Проверьте раскладку и попробуйте ещё раз.',
    'rate-limited': 'Слишком много попыток. Подождите немного и попробуйте ещё раз.',
    'account-unavailable':
      'Вход для этой учётной записи сейчас недоступен. Напишите администраторам.',
    blocked: 'Доступ к аккаунту приостановлен. Напишите администраторам.',
    network: 'Не удалось связаться с сервером. Проверьте интернет и попробуйте ещё раз.',
    error: 'Не удалось безопасно завершить вход. Повторите попытку или напишите администраторам.',
  } as const
  const pending = loginState === 'pending'
  const errorState = loginState === 'idle' || pending ? null : loginState

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending || !username.trim() || !telegramToken) return
    await onSubmit?.({ username, telegramToken })
  }

  return (
    <main className="grid min-h-svh place-items-center bg-background p-4">
      <PageLayout
        description="Используйте логин из письма после регистрации и текущий токен Telegram-бота как пароль."
        eyebrow="ВМШ 179"
        title="Личный кабинет школьника"
        width="reading"
      >
        <Card className="mx-auto max-w-md">
          <CardContent className="pt-5">
            <form className="space-y-4" onSubmit={handleSubmit}>
              {errorState ? (
                <Alert role="alert" tone="danger">
                  <ShieldCheck aria-hidden="true" />
                  <AlertContent>
                    <AlertTitle>Не удалось войти</AlertTitle>
                    <AlertDescription>{errorCopy[errorState]}</AlertDescription>
                  </AlertContent>
                </Alert>
              ) : null}
              <div className="space-y-1.5">
                <Label htmlFor="student-login">Логин</Label>
                <Input
                  autoComplete="username"
                  disabled={pending}
                  id="student-login"
                  maxLength={128}
                  name="username"
                  onChange={(event) => setUsername(event.target.value)}
                  placeholder="petrov-14"
                  required
                  value={username}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="student-password">Токен Telegram-бота</Label>
                <div className="relative">
                  <Input
                    autoComplete="current-password"
                    className="pr-11"
                    disabled={pending}
                    id="student-password"
                    maxLength={512}
                    name="telegramToken"
                    onChange={(event) => setTelegramToken(event.target.value)}
                    required
                    type={showPassword ? 'text' : 'password'}
                    value={telegramToken}
                  />
                  <Button
                    aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
                    className="absolute top-1/2 right-1 -translate-y-1/2"
                    disabled={pending}
                    onClick={() => setShowPassword((value) => !value)}
                    size="icon-sm"
                    type="button"
                    variant="ghost"
                  >
                    {showPassword ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                  </Button>
                </div>
              </div>
              <Button
                aria-busy={pending}
                className="w-full"
                disabled={pending || !username.trim() || !telegramToken}
                type="submit"
              >
                <Send aria-hidden="true" /> {pending ? 'Входим…' : 'Войти'}
              </Button>
              <p className="text-center text-caption text-muted-foreground">
                Не помните доступ? Напишите на{' '}
                <a className="text-link underline" href="mailto:vmsh@179.ru">
                  vmsh@179.ru
                </a>
                .
              </p>
            </form>
          </CardContent>
        </Card>
      </PageLayout>
    </main>
  )
}
