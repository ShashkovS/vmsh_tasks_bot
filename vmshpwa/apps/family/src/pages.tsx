import { Bell, Eye, EyeOff, Mail, Users } from 'lucide-react'
import { useState, type FormEvent, type ReactNode } from 'react'

import {
  AccountSessionManager,
  PageLayout,
  PageSection,
  PageStatePanel,
  type PageDisplayState,
} from '@vmsh/app-shell'
import { MathDocument } from '@vmsh/content'
import type { FamilyLoginRequest } from '@vmsh/contracts'
import {
  ClassroomAssignmentStatus,
  CourseCard,
  DeadlineNotice,
  FeedbackThread,
  ProblemHeader,
  StudentProgress,
  TaskListItem,
  TelegramRichPost,
  VerdictPanel,
  findVerdict,
  fullVerdictScale,
  type TaskListItemView,
  type TelegramPostView,
  type ThreadMessageView,
  type CourseEnrollmentView,
  type CourseView,
  type GroupView,
} from '@vmsh/product'
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
  Input,
  Label,
  Switch,
} from '@vmsh/ui'

/*
 * Family compositions implement dev/design-system/05-pages-and-flows.md and
 * docs/product-ux-decisions-2026-07.md. The family account observes the same
 * published child-visible state; it never submits or self-checks a task.
 */
const level = {
  id: 'math-beginner',
  courseId: 'math-5-7',
  code: 'н',
  name: 'Начинающие',
  colorIndex: 1 as const,
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
const physicsGroup: GroupView = {
  id: 'physics-intro',
  courseId: physicsCourse.id,
  code: 'вв',
  name: 'Вводная',
  colorIndex: 4,
}
const familyEnrollments: CourseEnrollmentView[] = [
  {
    course: mathCourse,
    activeGroupId: level.id,
    allowedGroups: [level],
    attendanceMode: 'in-person',
  },
  {
    course: physicsCourse,
    activeGroupId: physicsGroup.id,
    allowedGroups: [physicsGroup],
    attendanceMode: 'online',
  },
]
const accepted = findVerdict(fullVerdictScale, 'plus')!
const partial = findVerdict(fullVerdictScale, 'plus-minus')!

const tasks: TaskListItemView[] = [
  {
    id: '41n-1',
    number: '41н.1',
    title: 'Разнообразные вагоны',
    type: 'test',
    status: { kind: 'accepted', label: 'Зачтено', tone: 'success' },
    verdict: accepted,
  },
  {
    id: '41n-6',
    number: '41н.6',
    title: 'Расстановка ладей',
    type: 'written',
    status: { kind: 'needs-work', label: 'Нужно дополнить', tone: 'warning' },
    verdict: partial,
    hasNewFeedback: true,
  },
  {
    id: '41n-8',
    number: '41н.8',
    title: 'Четыре разреза',
    type: 'oral',
    status: { kind: 'not-started', label: 'Не начато', tone: 'neutral' },
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

function ChildSwitcher() {
  return (
    <label className="flex items-center gap-2 text-small font-medium">
      <span>Ребёнок</span>
      <select className="min-h-9 rounded-md border border-input bg-surface px-3">
        <option>Василий Петров</option>
        <option>Мария Петрова</option>
      </select>
    </label>
  )
}

export function FamilyHomePage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Сейчас">
      <PageLayout
        actions={<ChildSwitcher />}
        description="Режим, занятие и прогресс показаны отдельно для каждого курса."
        eyebrow="Василий · последняя активность сегодня в 12:08"
        title="Текущие занятия"
      >
        <div className="space-y-5">
          <PageSection
            description="Семья видит опубликованное состояние всех курсов ребёнка."
            title="Курсы"
          >
            <div className="grid gap-3 lg:grid-cols-2">
              <CourseCard
                classroomName="201"
                enrollment={familyEnrollments[0]!}
                lessonDate="26 января"
                lessonNumber={41}
                phase="Решает задачи · до воскресенья, 13:00 МСК"
                progressLabel="3 из 12 задач зачтено"
              />
              <CourseCard
                enrollment={familyEnrollments[1]!}
                lessonDate="29 января"
                lessonNumber={9}
                phase="Условие опубликовано"
                progressLabel="1 из 4 задач зачтена"
              />
            </div>
          </PageSection>
          <ClassroomAssignmentStatus
            audience="family"
            classroomName="201"
            publishedAt="25 января, 18:40"
            status="assigned"
          />
          <Card>
            <CardContent className="grid gap-4 pt-5 sm:grid-cols-3">
              {[
                ['3', 'задачи зачтено'],
                ['2', 'ответа на проверке'],
                ['1', 'ждёт дополнения'],
              ].map(([value, label]) => (
                <div key={label}>
                  <p className="font-num text-title font-semibold">{value}</p>
                  <p className="text-caption text-muted-foreground">{label}</p>
                </div>
              ))}
            </CardContent>
          </Card>
          <PageSection
            description="Семья видит те же опубликованные статусы, что и ребёнок."
            title="Занятие 41"
          >
            <div className="space-y-2">
              {tasks.map((task) => (
                <TaskListItem key={task.id} task={task} />
              ))}
            </div>
          </PageSection>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function FamilyChildrenPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Дети">
      <PageLayout
        description="Связи создаёт администратор при пакетной регистрации."
        title="Связанные дети"
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            ['Василий Петров', 'Начинающие · очно', '3 задачи зачтено'],
            ['Мария Петрова', 'Продолжающие · online', '5 задач зачтено'],
          ].map(([name, meta, result]) => (
            <Card key={name}>
              <CardContent className="space-y-2 pt-5">
                <CardTitle>{name}</CardTitle>
                <p className="text-small text-muted-foreground">{meta}</p>
                <Badge variant="outline">{result}</Badge>
                <Button className="w-full" size="sm" variant="outline">
                  Открыть
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

const messages: ThreadMessageView[] = [
  {
    id: 'student',
    author: { kind: 'student', name: 'Василий' },
    at: '25 января, 21:04',
    channel: 'pwa',
    body: 'На второй фотографии я разобрал общий случай.',
  },
  {
    id: 'teacher',
    author: { kind: 'teacher', name: 'И. Соколов' },
    at: '26 января, 12:30',
    channel: 'pwa',
    body: 'Идея верная. Не хватает объяснения для k = 1.',
  },
]

export function FamilyChildPage({
  childId,
  state = 'ready',
}: {
  childId: string
  state?: PageDisplayState
}) {
  return (
    <StatefulPage state={state} title="Активность ребёнка">
      <PageLayout
        actions={<ChildSwitcher />}
        description={`Профиль ${childId} · начинающие · очно`}
        title="Василий Петров"
      >
        <div className="space-y-5">
          <Card>
            <CardContent className="pt-5">
              <StudentProgress attemptedCount={12} solvedCount={3} />
            </CardContent>
          </Card>
          <PageSection title="Последняя проверка">
            <VerdictPanel
              at="26 января, 12:30"
              author="И. Соколов"
              comment="Идея верная. Не хватает разбора случая k = 1."
              verdict={partial}
            />
            <FeedbackThread messages={messages} />
          </PageSection>
          <Card>
            <CardContent className="flex items-start justify-between gap-4 pt-5">
              <div>
                <p className="font-medium">Постоянный режим: очно</p>
                <p className="mt-1 text-caption text-muted-foreground">
                  При изменении автор и время сохраняются. Если ребёнок не придёт, освободите место
                  заранее.
                </p>
              </div>
              <Switch aria-label="Очное участие" defaultChecked />
            </CardContent>
          </Card>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function FamilyTaskPage({
  taskId,
  state = 'ready',
}: {
  taskId: string
  state?: PageDisplayState
}) {
  return (
    <StatefulPage state={state} title={`Задача ${taskId}`}>
      <PageLayout
        description="Только чтение: сдача и реакции доступны в кабинете ребёнка."
        title="Расстановка ладей"
        width="reading"
      >
        <article className="space-y-5">
          <ProblemHeader
            deadline={
              <DeadlineNotice
                absoluteLabel="воскресенья, 13:00 МСК"
                closesAt="2026-02-01T13:00:00+03:00"
                relativeLabel="через 2 дня"
              />
            }
            level={level}
            number="41н.6"
            title="Расстановка ладей"
            type="written"
            verdict={partial}
          />
          <MathDocument>
            <p>На доске n × n расставляют ладьи так, чтобы никакие две не били друг друга.</p>
          </MathDocument>
          <VerdictPanel
            at="26 января, 12:30"
            author="И. Соколов"
            comment="Идея верная. Не хватает разбора случая k = 1."
            verdict={partial}
          />
          <FeedbackThread messages={messages} />
          <Alert tone="neutral">
            <Users aria-hidden="true" />
            <AlertContent>
              <AlertTitle>Режим просмотра семьи</AlertTitle>
              <AlertDescription>
                Здесь нельзя отвечать за ребёнка или влиять на его статистику.
              </AlertDescription>
            </AlertContent>
          </Alert>
        </article>
      </PageLayout>
    </StatefulPage>
  )
}

const newsPost: TelegramPostView = {
  id: 'family-news-41',
  attribution: { channel: 'ВМШ 179' },
  at: '26 января, 16:30',
  state: 'published',
  blocks: [
    { kind: 'heading', level: 2, text: 'Задачи 41-го занятия' },
    {
      kind: 'text',
      text: 'Опубликованы условия для всех уровней. Решения принимаются до воскресенья.',
    },
  ],
}

export function FamilyNewsPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Новости">
      <PageLayout
        actions={<ChildSwitcher />}
        description="Telegram-публикации и объявления для семей."
        title="Новости"
      >
        <div className="space-y-3">
          <TelegramRichPost post={newsPost} variant="card" />
          <ClassroomAssignmentStatus
            audience="family"
            classroomName="201"
            publishedAt="25 января, 18:40"
            status="assigned"
          />
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function FamilyNewsDetailPage({
  postId,
  state = 'ready',
}: {
  postId: string
  state?: PageDisplayState
}) {
  return (
    <StatefulPage state={state} title="Публикация">
      <PageLayout description={`Публикация ${postId}`} title="Задачи 41-го занятия" width="reading">
        <TelegramRichPost post={newsPost} />
      </PageLayout>
    </StatefulPage>
  )
}

export function FamilyProfilePage({
  state = 'ready',
  sessionManagement,
  organizerLink,
}: {
  state?: PageDisplayState
  organizerLink?: ReactNode
  sessionManagement?: ReactNode
}) {
  return (
    <StatefulPage state={state} title="Профиль">
      <PageLayout
        description="Отдельный семейный аккаунт без привязки к Telegram."
        title="Сергей Петров"
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Дети</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-small">2 связанных профиля</p>
            </CardContent>
          </Card>
          {sessionManagement ?? <AccountSessionManager />}
          <Card>
            <CardHeader>
              <CardTitle>Помощь</CardTitle>
            </CardHeader>
            <CardContent>
              {organizerLink}
              <a
                className="inline-flex items-center gap-2 text-link underline"
                href="mailto:vmsh@179.ru"
              >
                <Mail className="size-4" /> vmsh@179.ru
              </a>
            </CardContent>
          </Card>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export type FamilyLoginState =
  'idle' | 'pending' | 'invalid' | 'rate-limited' | 'account-unavailable' | 'network' | 'error'

export function FamilyLoginPage({
  invalid = false,
  loginState,
  onSubmit,
}: {
  invalid?: boolean
  loginState?: FamilyLoginState
  onSubmit?: (request: FamilyLoginRequest) => void | Promise<void>
}) {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const effectiveState = loginState ?? (invalid ? 'invalid' : 'idle')
  const pending = effectiveState === 'pending'
  const errorCopy = {
    invalid: 'Логин или пароль не подошли. Проверьте раскладку и попробуйте ещё раз.',
    'rate-limited': 'Слишком много попыток. Подождите немного и попробуйте ещё раз.',
    'account-unavailable':
      'Вход для этой учётной записи сейчас недоступен. Напишите администраторам.',
    network: 'Не удалось связаться с сервером. Проверьте интернет и попробуйте ещё раз.',
    error: 'Не удалось безопасно завершить вход. Повторите попытку или напишите администраторам.',
  } as const
  const errorState = effectiveState === 'idle' || pending ? null : effectiveState

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending || !username.trim() || !password) return
    await onSubmit?.({ username, password })
  }

  return (
    <main className="grid min-h-svh place-items-center bg-background p-4">
      <PageLayout
        description="Семейный аккаунт не связан с Telegram и не использует пароль ребёнка."
        eyebrow="ВМШ 179"
        title="Семейный кабинет"
        width="reading"
      >
        <Card className="mx-auto max-w-md">
          <CardContent className="pt-5">
            <form className="space-y-4" onSubmit={handleSubmit}>
              {errorState ? (
                <Alert role="alert" tone="danger">
                  <AlertContent>
                    <AlertTitle>Не удалось войти</AlertTitle>
                    <AlertDescription>{errorCopy[errorState]}</AlertDescription>
                  </AlertContent>
                </Alert>
              ) : null}
              <div className="space-y-1.5">
                <Label htmlFor="family-login">Логин</Label>
                <Input
                  autoComplete="username"
                  disabled={pending}
                  id="family-login"
                  maxLength={128}
                  name="username"
                  onChange={(event) => setUsername(event.target.value)}
                  required
                  value={username}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="family-password">Пароль</Label>
                <div className="relative">
                  <Input
                    autoComplete="current-password"
                    className="pr-11"
                    disabled={pending}
                    id="family-password"
                    maxLength={512}
                    name="password"
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    type={showPassword ? 'text' : 'password'}
                    value={password}
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
                    {showPassword ? <EyeOff /> : <Eye />}
                  </Button>
                </div>
              </div>
              <Button
                aria-busy={pending}
                className="w-full"
                disabled={pending || !username.trim() || !password}
                type="submit"
              >
                <Users aria-hidden="true" /> {pending ? 'Входим…' : 'Войти'}
              </Button>
              <p className="text-center text-caption text-muted-foreground">
                <Bell className="mr-1 inline size-3" /> Помощь:{' '}
                <a className="text-link underline" href="mailto:vmsh@179.ru">
                  vmsh@179.ru
                </a>
              </p>
            </form>
          </CardContent>
        </Card>
      </PageLayout>
    </main>
  )
}
