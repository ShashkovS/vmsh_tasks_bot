import { Camera, FileUp, LockKeyhole, Send, Upload } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { PageLayout, PageSection, PageStatePanel, type PageDisplayState } from '@vmsh/app-shell'
import {
  ClassroomCatalog,
  ClassroomGroupLayout,
  ClassroomStudentPlanner,
  FeedbackThread,
  MetadataGrid,
  PublicationControl,
  ReviewFeedbackForm,
  ReviewQueue,
  ThreePaneReview,
  fullVerdictScale,
  type ClassroomCatalogRoom,
  type ClassroomGroupOption,
  type ClassroomLayoutRoom,
  type ClassroomPlanRoom,
  type ClassroomPlanStudent,
  type ReviewQueueItem,
  type ReviewSort,
  type ThreadMessageView,
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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@vmsh/ui'

/*
 * Staff compositions implement dev/design-system/05-pages-and-flows.md.
 * Product mechanics remain in @vmsh/product; this app owns permissions,
 * route-level composition and compact teacher/admin density.
 */
const beginner = { code: 'н', name: 'Начинающие', colorIndex: 1 as const }
const continuing = { code: 'п', name: 'Продолжающие', colorIndex: 2 as const }

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
    <PageLayout title={title} width="wide">
      <PageStatePanel
        actionLabel={state === 'error' ? 'Повторить' : undefined}
        onAction={state === 'error' ? () => undefined : undefined}
        state={state}
      />
    </PageLayout>
  )
}

export function StaffHomePage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Рабочая сводка">
      <PageLayout
        description="Публикации, проверка, вопросы, устные задачи и доставка за текущую неделю."
        eyebrow="Понедельник · фаза решения"
        title="Рабочая сводка"
        width="wide"
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['43', 'работы в очереди', '7 уже взяты коллегами'],
            ['12', 'открытых вопросов', '3 ждут больше часа'],
            ['3/3', 'уровня опубликовано', 'решения пока закрыты'],
            ['1', 'инцидент доставки', 'повторная отправка запущена'],
          ].map(([value, label, detail]) => (
            <Card key={label}>
              <CardContent className="pt-4">
                <p className="font-num text-title font-semibold">{value}</p>
                <p className="text-small font-medium">{label}</p>
                <p className="mt-1 text-caption text-muted-foreground">{detail}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

const queueItems: ReviewQueueItem[] = [
  {
    id: 'sub-1',
    taskNumber: '41н.6',
    taskTitle: 'Расстановка ладей',
    level: beginner,
    studentName: 'Анна Белова',
    groupName: 'Начинающие',
    waitingLabel: '3 ч 20 мин',
    waitingMinutes: 200,
  },
  {
    id: 'sub-2',
    taskNumber: '41н.7',
    taskTitle: 'Крылья бабочки',
    level: beginner,
    studentName: 'Борис Ветров',
    groupName: 'Начинающие',
    waitingLabel: '2 ч 10 мин',
    waitingMinutes: 130,
  },
  {
    id: 'sub-3',
    taskNumber: '41п.4',
    taskTitle: 'Числа на доске',
    level: continuing,
    studentName: 'Вера Орлова',
    groupName: 'Продолжающие',
    waitingLabel: '45 мин',
    waitingMinutes: 45,
    busyBy: 'И. Соколов',
  },
]

function QueueHarness({ compact = false }: { compact?: boolean }) {
  const [sort, setSort] = useState<ReviewSort>('waiting')
  return (
    <ReviewQueue
      {...(compact ? { className: 'text-caption' } : {})}
      items={queueItems}
      mode="list"
      onModeChange={() => undefined}
      onOpen={() => undefined}
      onSortChange={setSort}
      sort={sort}
    />
  )
}

export function ReviewQueuePage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Очередь проверки">
      <PageLayout
        description="Работа блокируется за одним учителем; очередь обновляется в реальном времени."
        eyebrow="Письменные задачи"
        title="Очередь проверки"
        width="wide"
      >
        <QueueHarness />
      </PageLayout>
    </StatefulPage>
  )
}

const reviewMessages: ThreadMessageView[] = [
  {
    id: 's1',
    author: { kind: 'student', name: 'Анна Белова' },
    at: '25 января, 20:54',
    channel: 'pwa',
    body: 'На первой странице — идея, на второй я закончил подсчёт.',
  },
  {
    id: 't1',
    author: { kind: 'teacher', name: 'М. Иванова' },
    at: '25 января, 21:15',
    channel: 'pwa',
    body: 'Почему выбранные ладьи не бьют друг друга?',
  },
  {
    id: 's2',
    author: { kind: 'student', name: 'Анна Белова' },
    at: '25 января, 21:31',
    channel: 'pwa',
    body: 'У каждой своя строка и свой столбец; дописала пояснение.',
  },
]

export function ReviewWorkspacePage({
  submissionId,
  state = 'ready',
}: {
  submissionId: string
  state?: PageDisplayState
}) {
  return (
    <StatefulPage state={state} title="Проверка работы">
      <PageLayout
        description={`${submissionId} · Анна Белова · Начинающие`}
        eyebrow="41н.6 · Расстановка ладей"
        title="Проверка работы"
        width="wide"
      >
        <ThreePaneReview
          queue={<QueueHarness compact />}
          evidence={
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Присланная работа · 2 страницы</CardTitle>
                <Badge variant="success">
                  <LockKeyhole className="size-3" /> Взята вами
                </Badge>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                {[1, 2].map((page) => (
                  <div
                    className="grid min-h-72 place-items-center rounded-md border bg-surface-sunken"
                    key={page}
                  >
                    <Camera className="size-12 text-muted-foreground" />
                    <span className="sr-only">Страница {page}</span>
                  </div>
                ))}
              </CardContent>
            </Card>
          }
          discussion={
            <PageSection
              description="Новый ответ добавляется после всей существующей переписки."
              title="Обсуждение"
            >
              <FeedbackThread messages={reviewMessages} />
            </PageSection>
          }
          feedback={<ReviewFeedbackForm onSubmit={() => undefined} verdicts={fullVerdictScale} />}
        />
      </PageLayout>
    </StatefulPage>
  )
}

const publicationRows = [
  {
    level: beginner,
    task: 'published' as const,
    hint: 'scheduled' as const,
    solution: 'draft' as const,
    scheduledAt: { hint: '31 января, 12:00' },
  },
  {
    level: continuing,
    task: 'published' as const,
    hint: 'draft' as const,
    solution: 'none' as const,
  },
]

export function StaffLessonsPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Уроки и публикации">
      <PageLayout
        actions={
          <Button>
            <FileUp /> Загрузить LaTeX
          </Button>
        }
        description="Условие, подсказка и решение публикуются или планируются независимо для каждого уровня."
        eyebrow="LaTeX — единственный источник"
        title="Уроки и публикации"
        width="wide"
      >
        <PublicationControl rows={publicationRows} />
      </PageLayout>
    </StatefulPage>
  )
}

const metadataColumns = [
  { id: 'level', header: 'Группа' },
  { id: 'problem', header: 'Задача' },
  { id: 'title', header: 'Название' },
  {
    id: 'taskType',
    header: 'Тип задачи',
    editor: 'select' as const,
    options: [
      { value: 'test', label: 'Тестовая' },
      { value: 'written', label: 'Письменная' },
      { value: 'oral', label: 'Устная' },
    ],
  },
  {
    id: 'answerType',
    header: 'Тип ответа',
    editor: 'select' as const,
    options: [
      { value: 'natural', label: 'Натуральное' },
      { value: 'integer', label: 'Целое' },
      { value: 'date', label: 'Дата' },
    ],
  },
]

export function StaffLessonDetailPage({
  lessonId,
  state = 'ready',
}: {
  lessonId: string
  state?: PageDisplayState
}) {
  return (
    <StatefulPage state={state} title="Импорт и метаданные">
      <PageLayout
        actions={
          <Button variant="outline">
            <Upload /> Новый файл
          </Button>
        }
        description="Парсер сначала делает dry-run и отдельно запрашивает недостающие assets."
        eyebrow={`Урок ${lessonId}`}
        title="Импорт и метаданные"
        width="wide"
      >
        <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>Диагностика</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-small">
              <p className="text-status-success">12 задач распознано</p>
              <p className="text-status-success">8 изображений переиспользовано</p>
              <p className="text-status-danger">diagram-41-7.pdf отсутствует</p>
              <Button className="w-full" variant="outline">
                Загрузить недостающее
              </Button>
            </CardContent>
          </Card>
          <MetadataGrid
            columns={metadataColumns}
            initialRows={[
              {
                level: 'н',
                problem: '41.1',
                title: 'Разнообразные вагоны',
                taskType: 'test',
                answerType: 'natural',
              },
              {
                level: 'н',
                problem: '41.6',
                title: 'Расстановка ладей',
                taskType: 'written',
                answerType: '',
              },
            ]}
          />
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

const classroomGroups: ClassroomGroupOption[] = [
  {
    id: 'beginner',
    name: 'Начинающие',
    shortCode: 'н',
    colorIndex: 1,
    inPersonCount: 84,
    assignedCount: 82,
  },
  {
    id: 'continuing',
    name: 'Продолжающие',
    shortCode: 'п',
    colorIndex: 2,
    inPersonCount: 68,
    assignedCount: 68,
  },
  {
    id: 'expert',
    name: 'Эксперты',
    shortCode: 'х',
    colorIndex: 3,
    inPersonCount: 27,
    assignedCount: 27,
  },
]
const catalogRooms: ClassroomCatalogRoom[] = [
  { id: '201', name: '201', status: 'active', version: 3, usageLabel: 'Начинающие · с занятия 38' },
  { id: '202', name: '202', status: 'active', version: 1, usageLabel: 'Начинающие · с занятия 39' },
  {
    id: 'hall',
    name: 'Актовый зал',
    status: 'active',
    version: 4,
    usageLabel: 'Эксперты · с занятия 37',
  },
]
const layoutRooms: ClassroomLayoutRoom[] = [
  { id: '201', name: '201', groupId: 'beginner' },
  { id: '202', name: '202', groupId: 'beginner' },
  { id: '301', name: '301', groupId: 'continuing' },
  { id: 'hall', name: 'Актовый зал', groupId: 'expert' },
]
const planRooms: ClassroomPlanRoom[] = layoutRooms.flatMap((room) =>
  room.groupId ? [{ id: room.id, name: room.name, groupId: room.groupId }] : [],
)
const planStudents: ClassroomPlanStudent[] = [
  {
    id: 'anna',
    name: 'Анна Белова',
    groupId: 'beginner',
    classroomId: '201',
    status: 'assigned',
    source: 'previous-room',
    age: 12.6,
    schoolClass: 6,
    strength: 6.8,
  },
  {
    id: 'boris',
    name: 'Борис Ветров',
    groupId: 'beginner',
    classroomId: '202',
    status: 'assigned',
    source: 'least-loaded',
    age: 13.2,
    schoolClass: 7,
    strength: null,
  },
  {
    id: 'vera',
    name: 'Вера Орлова',
    groupId: 'continuing',
    classroomId: '301',
    status: 'assigned',
    source: 'previous-room',
    age: 14.1,
    schoolClass: 8,
    strength: 7.4,
  },
  {
    id: 'grigory',
    name: 'Григорий Яшин',
    groupId: 'expert',
    classroomId: null,
    status: 'reassigning',
    source: 'mode-change',
    age: null,
    schoolClass: 9,
    strength: 8.1,
  },
]

export type ClassroomPageTab = 'catalog' | 'groups' | 'students'

export function StaffClassroomsPage({
  state = 'ready',
  tab: controlledTab,
  onTabChange,
}: {
  state?: PageDisplayState
  tab?: ClassroomPageTab
  onTabChange?: (tab: ClassroomPageTab) => void
}) {
  const [localTab, setLocalTab] = useState<ClassroomPageTab>('catalog')
  const tab = controlledTab ?? localTab
  const setTab = (value: string) => {
    const next = value as ClassroomPageTab
    if (controlledTab === undefined) setLocalTab(next)
    onTabChange?.(next)
  }
  return (
    <StatefulPage state={state} title="Аудитории">
      <PageLayout
        description="Каталог, схема по группам и версионируемый план школьников для занятия 41."
        title="Аудитории"
        width="wide"
      >
        <Tabs onValueChange={setTab} value={tab}>
          <TabsList>
            <TabsTrigger value="catalog">Каталог</TabsTrigger>
            <TabsTrigger value="groups">По группам</TabsTrigger>
            <TabsTrigger value="students">Школьники</TabsTrigger>
          </TabsList>
          <TabsContent value="catalog">
            <ClassroomCatalog
              newRoomName=""
              onCreate={() => undefined}
              onNewRoomNameChange={() => undefined}
              onQueryChange={() => undefined}
              onStatusFilterChange={() => undefined}
              query=""
              rooms={catalogRooms}
              statusFilter="active"
            />
          </TabsContent>
          <TabsContent value="groups">
            <ClassroomGroupLayout
              groups={classroomGroups}
              lessonLabel="Занятие 41 · 26 января"
              rooms={layoutRooms}
              sourceLabel="наследуется с занятия 40"
              state="inherited"
              version={7}
            />
          </TabsContent>
          <TabsContent value="students">
            <ClassroomStudentPlanner
              groups={classroomGroups}
              incidents={[
                {
                  id: 'no-room',
                  title: 'У группы экспертов нет свободной аудитории',
                  description: 'Григорий Яшин остаётся в разделе переназначения.',
                  blocking: true,
                },
              ]}
              lessonLabel="Занятие 41 · 26 января"
              onMove={() => undefined}
              onRequestGroupChange={() => undefined}
              onShowHistory={() => undefined}
              rooms={planRooms}
              state="draft"
              students={planStudents}
              version={13}
            />
          </TabsContent>
        </Tabs>
      </PageLayout>
    </StatefulPage>
  )
}

export function StaffGenericPage({
  title,
  description,
  state = 'ready',
  forbidden = false,
}: {
  title: string
  description: string
  state?: PageDisplayState
  forbidden?: boolean
}) {
  return (
    <StatefulPage state={forbidden ? 'forbidden' : state} title={title}>
      <PageLayout description={description} eyebrow="Teacher/Admin SPA" title={title} width="wide">
        <div className="grid gap-3 sm:grid-cols-2">
          <Card>
            <CardContent className="pt-5">
              <p className="font-medium">Рабочее состояние</p>
              <p className="mt-1 text-small text-muted-foreground">
                Маршрут включён в информационную архитектуру первой версии.
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5">
              <p className="font-medium">Нет элементов</p>
              <p className="mt-1 text-small text-muted-foreground">
                Пустое состояние не прячет фильтры и контекст.
              </p>
            </CardContent>
          </Card>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function StaffLoginPage({ invalid = false }: { invalid?: boolean }) {
  return (
    <main className="grid min-h-svh place-items-center bg-background p-4">
      <PageLayout
        description="Учитель видит разрешённые группы; admin — административные разделы."
        eyebrow="ВМШ 179"
        title="Вход для преподавателя"
        width="reading"
      >
        <Card className="mx-auto max-w-md">
          <CardContent className="space-y-4 pt-5">
            {invalid ? (
              <Alert role="alert" tone="danger">
                <AlertContent>
                  <AlertTitle>Не удалось войти</AlertTitle>
                  <AlertDescription>Проверьте логин и пароль.</AlertDescription>
                </AlertContent>
              </Alert>
            ) : null}
            <Input aria-label="Логин" autoComplete="username" />
            <Input aria-label="Пароль" autoComplete="current-password" type="password" />
            <Button className="w-full">Войти</Button>
          </CardContent>
        </Card>
      </PageLayout>
    </main>
  )
}

export function BroadcastComposerPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title="Рассылки">
      <PageLayout
        description="Полный Markdown-редактор и отправка появятся во второй продуктовой фазе."
        eyebrow="Admin only"
        title="Рассылки"
        width="wide"
      >
        <Alert tone="info">
          <Send />
          <AlertContent>
            <AlertTitle>Запланировано на вторую фазу</AlertTitle>
            <AlertDescription>
              Здесь будут preview, dry-run, категории и отдельный выбор PWA/Telegram.
            </AlertDescription>
          </AlertContent>
        </Alert>
      </PageLayout>
    </StatefulPage>
  )
}
