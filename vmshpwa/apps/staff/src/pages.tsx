import { t } from '@lingui/core/macro'
import { Trans } from '@lingui/react/macro'
import { Camera, FileUp, LockKeyhole, Send, Upload } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { PageLayout, PageSection, PageStatePanel, type PageDisplayState } from '@vmsh/app-shell'
import {
  ClassroomCatalog,
  ClassroomGroupLayout,
  ClassroomStudentPlanner,
  CourseGroupCatalog,
  FeedbackThread,
  InPersonEventComposer,
  IndependentScheduleMatrix,
  MetadataGrid,
  PublicationControl,
  ReviewFeedbackForm,
  ReviewQueue,
  ThreePaneReview,
  TelegramBindingsEditor,
  fullVerdictScale,
  type ClassroomCatalogRoom,
  type ClassroomGroupOption,
  type ClassroomLayoutRoom,
  type ClassroomPlanRoom,
  type ClassroomPlanStudent,
  type CourseView,
  type InPersonGroupLessonView,
  type IndependentScheduleRow,
  type ManagedCourse,
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
const beginner = {
  id: 'math-beginner',
  courseId: 'math-5-7',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  code: 'н',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Начинающие',
  colorIndex: 1 as const,
}
const continuing = {
  id: 'math-continuing',
  courseId: 'math-5-7',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  code: 'п',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Продолжающие',
  colorIndex: 2 as const,
}
const expert = {
  id: 'math-expert',
  courseId: 'math-5-7',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  code: 'э',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Эксперты',
  colorIndex: 3 as const,
}
const physicsIntro = {
  id: 'physics-intro',
  courseId: 'physics-experiment',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  code: 'вв',
  // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
  name: 'Вводная',
  colorIndex: 4 as const,
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
        actionLabel={state === 'error' ? t`Повторить` : undefined}
        onAction={state === 'error' ? () => undefined : undefined}
        state={state}
      />
    </PageLayout>
  )
}

export function StaffHomePage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title={t`Рабочая сводка`}>
      <PageLayout
        description={t`Публикации, проверка, вопросы, устные задачи и доставка за текущую неделю.`}
        eyebrow={t`Понедельник · фаза решения`}
        title={t`Рабочая сводка`}
        width="wide"
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[
            ['43', t`работы в очереди`, t`7 уже взяты коллегами`],
            ['12', t`открытых вопросов`, t`3 ждут больше часа`],
            ['3/3', t`уровня опубликовано`, t`решения пока закрыты`],
            ['1', t`инцидент доставки`, t`повторная отправка запущена`],
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

const managedCourses: ManagedCourse[] = [
  {
    course: mathCourse,
    status: 'active',
    groups: [beginner, continuing, expert].map((group, index) => ({
      ...group,
      status: 'active' as const,
      activeStudents: [142, 118, 39][index]!,
      get scheduleLabel() {
        return index === 1 ? t`своё расписание` : t`шаблон курса`
      },
    })),
  },
  {
    course: physicsCourse,
    status: 'active',
    groups: [
      {
        ...physicsIntro,
        status: 'active' as const,
        activeStudents: 32,
        get scheduleLabel() {
          return t`своё расписание`
        },
      },
    ],
  },
]

const independentSchedules: IndependentScheduleRow[] = [
  {
    group: beginner,
    source: 'course',
    get conditionAt() {
      return t`пн 16:30`
    },
    get hintAt() {
      return t`сб 12:00`
    },
    get closesAt() {
      return t`вс 13:00`
    },
    get solutionAt() {
      return t`вс 14:00`
    },
    get snapshotLabel() {
      return t`снимок шаблона v4`
    },
  },
  {
    group: continuing,
    source: 'group',
    get conditionAt() {
      return t`вт 17:00`
    },
    get hintAt() {
      return t`сб 15:00`
    },
    get closesAt() {
      return t`вс 15:00`
    },
    get solutionAt() {
      return t`вс 16:00`
    },
    get snapshotLabel() {
      return t`расписание группы v2`
    },
  },
  {
    group: expert,
    source: 'lesson',
    get conditionAt() {
      return t`пн 18:10`
    },
    hintAt: '—',
    get closesAt() {
      return t`пн 17:00`
    },
    get solutionAt() {
      return t`пн 18:00`
    },
    get snapshotLabel() {
      return t`занятие изменено отдельно`
    },
  },
]

export function StaffCoursesPage({
  state = 'ready',
  telegram,
}: {
  state?: PageDisplayState
  telegram?: ReactNode
}) {
  return (
    <StatefulPage state={state} title={t`Курсы и группы`}>
      <PageLayout
        description={t`Курс задаёт общий контекст, а группы имеют собственные расписания, публикации и Telegram-привязки.`}
        eyebrow={t`Сезон 2025–2026`}
        title={t`Курсы и группы`}
        width="wide"
      >
        <div className="space-y-6">
          <CourseGroupCatalog courses={managedCourses} />
          <IndependentScheduleMatrix
            course={mathCourse}
            lessonNumber={41}
            rows={independentSchedules}
          />
          {telegram ?? (
            <TelegramBindingsEditor
              bindings={[
                {
                  id: 'math-news',
                  owner: 'course',
                  ownerLabel: mathCourse.name,
                  purpose: 'news-source',
                  chatLabel: '@vmsh_math_5_7',
                  status: 'verified',
                },
                {
                  id: 'beginner-materials',
                  owner: 'group',
                  ownerLabel: beginner.name,
                  purpose: 'materials-target',
                  chatLabel: '-100179000201',
                  topicLabel:
                    /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'материалы начинающих' /* eslint-enable lingui/no-unlocalized-strings */,
                  status: 'verified',
                },
              ]}
              course={mathCourse}
            />
          )}
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

const queueItems: ReviewQueueItem[] = [
  {
    id: 'sub-1',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    taskNumber: '41н.6',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    taskTitle: 'Расстановка ладей',
    level: beginner,
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    studentName: 'Анна Белова',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    groupName: 'Начинающие',
    get waitingLabel() {
      return t`3 ч 20 мин`
    },
    waitingMinutes: 200,
  },
  {
    id: 'sub-2',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    taskNumber: '41н.7',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    taskTitle: 'Крылья бабочки',
    level: beginner,
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    studentName: 'Борис Ветров',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    groupName: 'Начинающие',
    get waitingLabel() {
      return t`2 ч 10 мин`
    },
    waitingMinutes: 130,
  },
  {
    id: 'sub-3',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    taskNumber: '41п.4',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    taskTitle: 'Числа на доске',
    level: continuing,
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    studentName: 'Вера Орлова',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    groupName: 'Продолжающие',
    get waitingLabel() {
      return t`45 мин`
    },
    waitingMinutes: 45,
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
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
    <StatefulPage state={state} title={t`Очередь проверки`}>
      <PageLayout
        description={t`Работа блокируется за одним учителем; очередь обновляется в реальном времени.`}
        eyebrow={t`Письменные задачи`}
        title={t`Очередь проверки`}
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
    author: {
      kind: 'student',
      // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
      name: 'Анна Белова',
    },
    get at() {
      return t`25 января, 20:54`
    },
    channel: 'pwa',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    body: 'На первой странице — идея, на второй я закончил подсчёт.',
  },
  {
    id: 't1',
    author: {
      kind: 'teacher',
      // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
      name: 'М. Иванова',
    },
    get at() {
      return t`25 января, 21:15`
    },
    channel: 'pwa',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    body: 'Почему выбранные ладьи не бьют друг друга?',
  },
  {
    id: 's2',
    author: {
      kind: 'student',
      // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
      name: 'Анна Белова',
    },
    get at() {
      return t`25 января, 21:31`
    },
    channel: 'pwa',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
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
    <StatefulPage state={state} title={t`Проверка работы`}>
      <PageLayout
        description={t`${submissionId} · Анна Белова · Начинающие`}
        eyebrow={
          /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ '41н.6 · Расстановка ладей' /* eslint-enable lingui/no-unlocalized-strings */
        }
        title={t`Проверка работы`}
        width="wide"
      >
        <ThreePaneReview
          queue={<QueueHarness compact />}
          evidence={
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>
                  <Trans>Присланная работа · 2 страницы</Trans>
                </CardTitle>
                <Badge variant="success">
                  <LockKeyhole className="size-3" /> <Trans>Взята вами</Trans>
                </Badge>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-2">
                {[1, 2].map((page) => (
                  <div
                    className="grid min-h-72 place-items-center rounded-md border bg-surface-sunken"
                    key={page}
                  >
                    <Camera className="size-12 text-muted-foreground" />
                    <span className="sr-only">
                      <Trans>Страница {page}</Trans>
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>
          }
          discussion={
            <PageSection
              description={t`Новый ответ добавляется после всей существующей переписки.`}
              title={t`Обсуждение`}
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
    scheduledAt: {
      get hint() {
        return t`31 января, 12:00`
      },
    },
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
    <StatefulPage state={state} title={t`Уроки и публикации`}>
      <PageLayout
        actions={
          <Button>
            <FileUp /> <Trans>Загрузить LaTeX</Trans>
          </Button>
        }
        description={t`Условие, подсказка и решение публикуются или планируются независимо для каждого уровня.`}
        eyebrow={t`LaTeX — единственный источник`}
        title={t`Уроки и публикации`}
        width="wide"
      >
        <PublicationControl rows={publicationRows} />
      </PageLayout>
    </StatefulPage>
  )
}

const metadataColumns = [
  {
    id: 'level',
    get header() {
      return t`Группа`
    },
  },
  {
    id: 'problem',
    get header() {
      return t`Задача`
    },
  },
  {
    id: 'title',
    get header() {
      return t`Название`
    },
  },
  {
    id: 'taskType',
    get header() {
      return t`Тип задачи`
    },
    editor: 'select' as const,
    options: [
      {
        value: 'test',
        get label() {
          return t`Тестовая`
        },
      },
      {
        value: 'written',
        get label() {
          return t`Письменная`
        },
      },
      {
        value: 'oral',
        get label() {
          return t`Устная`
        },
      },
    ],
  },
  {
    id: 'answerType',
    get header() {
      return t`Тип ответа`
    },
    editor: 'select' as const,
    options: [
      {
        value: 'natural',
        get label() {
          return t`Натуральное`
        },
      },
      {
        value: 'integer',
        get label() {
          return t`Целое`
        },
      },
      {
        value: 'date',
        get label() {
          return t`Дата`
        },
      },
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
    <StatefulPage state={state} title={t`Импорт и метаданные`}>
      <PageLayout
        actions={
          <Button variant="outline">
            <Upload /> <Trans>Новый файл</Trans>
          </Button>
        }
        description={t`Парсер сначала делает dry-run и отдельно запрашивает недостающие assets.`}
        eyebrow={t`Урок ${lessonId}`}
        title={t`Импорт и метаданные`}
        width="wide"
      >
        <div className="grid gap-4 xl:grid-cols-[20rem_minmax(0,1fr)]">
          <Card>
            <CardHeader>
              <CardTitle>
                <Trans>Диагностика</Trans>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-small">
              <p className="text-status-success">
                <Trans>12 задач распознано</Trans>
              </p>
              <p className="text-status-success">
                <Trans>8 изображений переиспользовано</Trans>
              </p>
              <p className="text-status-danger">
                <Trans>diagram-41-7.pdf отсутствует</Trans>
              </p>
              <Button className="w-full" variant="outline">
                <Trans>Загрузить недостающее</Trans>
              </Button>
            </CardContent>
          </Card>
          <MetadataGrid
            columns={metadataColumns}
            initialRows={[
              {
                level:
                  /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'н' /* eslint-enable lingui/no-unlocalized-strings */,
                problem: '41.1',
                title:
                  /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Разнообразные вагоны' /* eslint-enable lingui/no-unlocalized-strings */,
                taskType: 'test',
                answerType: 'natural',
              },
              {
                level:
                  /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'н' /* eslint-enable lingui/no-unlocalized-strings */,
                problem: '41.6',
                title:
                  /* eslint-disable lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md */ 'Расстановка ладей' /* eslint-enable lingui/no-unlocalized-strings */,
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
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    name: 'Начинающие',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    shortCode: 'н',
    colorIndex: 1,
    inPersonCount: 84,
    assignedCount: 82,
  },
  {
    id: 'continuing',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    name: 'Продолжающие',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    shortCode: 'п',
    colorIndex: 2,
    inPersonCount: 68,
    assignedCount: 68,
  },
  {
    id: 'expert',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    name: 'Эксперты',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    shortCode: 'х',
    colorIndex: 3,
    inPersonCount: 27,
    assignedCount: 27,
  },
]
const catalogRooms: ClassroomCatalogRoom[] = [
  {
    id: '201',
    name: '201',
    status: 'active',
    version: 3,
    get usageLabel() {
      return t`Начинающие · с занятия 38`
    },
  },
  {
    id: '202',
    name: '202',
    status: 'active',
    version: 1,
    get usageLabel() {
      return t`Начинающие · с занятия 39`
    },
  },
  {
    id: 'hall',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    name: 'Актовый зал',
    status: 'active',
    version: 4,
    get usageLabel() {
      return t`Эксперты · с занятия 37`
    },
  },
]
const layoutRooms: ClassroomLayoutRoom[] = [
  { id: '201', name: '201', groupId: 'beginner' },
  { id: '202', name: '202', groupId: 'beginner' },
  { id: '301', name: '301', groupId: 'continuing' },
  {
    id: 'hall',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
    name: 'Актовый зал',
    groupId: 'expert',
  },
]
const planRooms: ClassroomPlanRoom[] = layoutRooms.flatMap((room) =>
  room.groupId ? [{ id: room.id, name: room.name, groupId: room.groupId }] : [],
)
const planStudents: ClassroomPlanStudent[] = [
  {
    id: 'anna',
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
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
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
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
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
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
    // eslint-disable-next-line lingui/no-unlocalized-strings -- fixture domain content; docs/i18n.md
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

const initialInPersonGroupLessons: InPersonGroupLessonView[] = [
  {
    id: 'math-beginner-41',
    course: mathCourse,
    group: beginner,
    lessonNumber: 41,
    inPersonCount: 84,
    assignedCount: 82,
    inheritedRooms: ['201', '202', '203', '204', '205', '206'],
    selected: true,
  },
  {
    id: 'math-continuing-41',
    course: mathCourse,
    group: continuing,
    lessonNumber: 41,
    inPersonCount: 68,
    assignedCount: 68,
    inheritedRooms: ['301', '302', '303', '304', '305'],
    selected: true,
  },
  {
    id: 'physics-intro-9',
    course: physicsCourse,
    group: physicsIntro,
    lessonNumber: 9,
    inPersonCount: 24,
    assignedCount: 23,
    inheritedRooms: ['401', '402'],
    selected: false,
  },
]

export type ClassroomPageTab = 'catalog' | 'groups' | 'students'

export function StaffClassroomsPage({
  state = 'ready',
  tab: controlledTab,
  onTabChange,
  event,
  catalog,
  layout,
  students,
}: {
  state?: PageDisplayState
  tab?: ClassroomPageTab
  onTabChange?: (tab: ClassroomPageTab) => void
  event?: ReactNode
  catalog?: ReactNode
  layout?: ReactNode
  students?: ReactNode
}) {
  const [localTab, setLocalTab] = useState<ClassroomPageTab>('catalog')
  const [eventGroupLessons, setEventGroupLessons] = useState(initialInPersonGroupLessons)
  const tab = controlledTab ?? localTab
  const setTab = (value: string) => {
    const next = value as ClassroomPageTab
    if (controlledTab === undefined) setLocalTab(next)
    onTabChange?.(next)
  }
  return (
    <StatefulPage state={state} title={t`Аудитории`}>
      <PageLayout
        description={t`Каталог, схема по группам и версионируемый план для выбранного очного события.`}
        title={t`Аудитории`}
        width="wide"
      >
        <div className="space-y-6">
          {event ?? (
            <InPersonEventComposer
              groupLessons={eventGroupLessons}
              onToggle={(groupLessonId, selected) =>
                setEventGroupLessons((current) =>
                  current.map((groupLesson) =>
                    groupLesson.id === groupLessonId ? { ...groupLesson, selected } : groupLesson,
                  ),
                )
              }
              startsAt={t`1 февраля, 10:00–13:00`}
              title={t`Очное воскресенье`}
            />
          )}
          <Tabs onValueChange={setTab} value={tab}>
            <TabsList>
              <TabsTrigger value="catalog">
                <Trans>Каталог</Trans>
              </TabsTrigger>
              <TabsTrigger value="groups">
                <Trans>По группам</Trans>
              </TabsTrigger>
              <TabsTrigger value="students">
                <Trans>Школьники</Trans>
              </TabsTrigger>
            </TabsList>
            <TabsContent value="catalog">
              {catalog ?? (
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
              )}
            </TabsContent>
            <TabsContent value="groups">
              {layout ?? (
                <ClassroomGroupLayout
                  groups={classroomGroups}
                  lessonLabel={t`Очное событие 1 февраля · Математика, занятие 41`}
                  rooms={layoutRooms}
                  sourceLabel={t`наследуется с прошлого события этих групп`}
                  state="inherited"
                  version={7}
                />
              )}
            </TabsContent>
            <TabsContent value="students">
              {students ?? (
                <ClassroomStudentPlanner
                  groups={classroomGroups}
                  incidents={[
                    {
                      id: 'no-room',
                      title: t`У группы экспертов нет свободной аудитории`,
                      description: t`Григорий Яшин остаётся в разделе переназначения.`,
                      blocking: true,
                    },
                  ]}
                  lessonLabel={t`Очное событие 1 февраля · черновик наследованного плана`}
                  onMove={() => undefined}
                  onRequestGroupChange={() => undefined}
                  onShowHistory={() => undefined}
                  rooms={planRooms}
                  state="draft"
                  students={planStudents}
                  version={13}
                />
              )}
            </TabsContent>
          </Tabs>
        </div>
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
              <p className="font-medium">
                <Trans>Рабочее состояние</Trans>
              </p>
              <p className="mt-1 text-small text-muted-foreground">
                <Trans>Маршрут включён в информационную архитектуру первой версии.</Trans>
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-5">
              <p className="font-medium">
                <Trans>Нет элементов</Trans>
              </p>
              <p className="mt-1 text-small text-muted-foreground">
                <Trans>Пустое состояние не прячет фильтры и контекст.</Trans>
              </p>
            </CardContent>
          </Card>
        </div>
      </PageLayout>
    </StatefulPage>
  )
}

export function BroadcastComposerPage({ state = 'ready' }: { state?: PageDisplayState }) {
  return (
    <StatefulPage state={state} title={t`Рассылки`}>
      <PageLayout
        description={t`Полный Markdown-редактор и отправка появятся во второй продуктовой фазе.`}
        eyebrow="Admin only"
        title={t`Рассылки`}
        width="wide"
      >
        <Alert tone="info">
          <Send />
          <AlertContent>
            <AlertTitle>
              <Trans>Запланировано на вторую фазу</Trans>
            </AlertTitle>
            <AlertDescription>
              <Trans>Здесь будут preview, dry-run, категории и отдельный выбор PWA/Telegram.</Trans>
            </AlertDescription>
          </AlertContent>
        </Alert>
      </PageLayout>
    </StatefulPage>
  )
}

export { StaffLoginPage, type StaffLoginState } from './login-page'
