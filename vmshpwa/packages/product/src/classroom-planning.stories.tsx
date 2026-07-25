import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { Button, Tabs, TabsContent, TabsList, TabsTrigger } from '@vmsh/ui'

import {
  ClassroomAssignmentStatus,
  ClassroomCatalog,
  ClassroomGroupLayout,
  ClassroomStudentPlanner,
  type ClassroomCatalogFilter,
  type ClassroomCatalogRoom,
  type ClassroomGroupOption,
  type ClassroomLayoutRoom,
  type ClassroomNameConflict,
  type ClassroomPlanRoom,
  type ClassroomPlanState,
  type ClassroomPlanStudent,
} from './classroom-planning'

const meta = {
  title: 'Product/Classrooms',
  parameters: { layout: 'padded' },
  globals: { density: 'staff' },
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

const groups: ClassroomGroupOption[] = [
  {
    id: 'beginner',
    name: 'Начинающие',
    shortCode: 'н',
    colorIndex: 1,
    inPersonCount: 84,
    assignedCount: 79,
  },
  {
    id: 'continuing',
    name: 'Продолжающие',
    shortCode: 'п',
    colorIndex: 2,
    inPersonCount: 68,
    assignedCount: 67,
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
  {
    id: 'old-305',
    name: '305',
    status: 'archived',
    version: 7,
    usageLabel: 'Скрыта 18 января · использовалась в 12 занятиях',
  },
]

function normalizedRoomName(name: string) {
  return name.trim().normalize('NFKC').toLocaleLowerCase('ru')
}

function CatalogHarness({ initialFilter = 'active' }: { initialFilter?: ClassroomCatalogFilter }) {
  const [rooms, setRooms] = useState(catalogRooms)
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<ClassroomCatalogFilter>(initialFilter)
  const [newRoomName, setNewRoomName] = useState('')
  const [conflict, setConflict] = useState<ClassroomNameConflict | null>(null)

  return (
    <ClassroomCatalog
      conflict={conflict}
      newRoomName={newRoomName}
      onArchive={(roomId) =>
        setRooms((current) =>
          current.map((room) =>
            room.id === roomId ? { ...room, status: 'archived' as const } : room,
          ),
        )
      }
      onCreate={(name) => {
        const existing = rooms.find(
          (room) => normalizedRoomName(room.name) === normalizedRoomName(name),
        )
        if (existing) {
          setConflict({
            inputName: newRoomName,
            existingRoomId: existing.id,
            existingRoomName: existing.name,
          })
          return
        }
        setRooms((current) => [
          ...current,
          { id: `room-${current.length + 1}`, name, status: 'active', version: 1 },
        ])
        setConflict(null)
        setNewRoomName('')
      }}
      onNewRoomNameChange={(value) => {
        setNewRoomName(value)
        setConflict(null)
      }}
      onQueryChange={setQuery}
      onRename={(roomId, name) =>
        setRooms((current) =>
          current.map((room) => (room.id === roomId ? { ...room, name } : room)),
        )
      }
      onRestore={(roomId) =>
        setRooms((current) =>
          current.map((room) =>
            room.id === roomId ? { ...room, status: 'active' as const } : room,
          ),
        )
      }
      onRevealConflict={(roomId) => {
        const existing = rooms.find((room) => room.id === roomId)
        setStatusFilter('all')
        setQuery(existing?.name ?? '')
      }}
      onStatusFilterChange={setStatusFilter}
      query={query}
      rooms={rooms}
      statusFilter={statusFilter}
    />
  )
}

export const CatalogActive: Story = {
  name: 'Каталог · активные аудитории',
  render: () => <CatalogHarness />,
}

export const CatalogHiddenAndRestore: Story = {
  name: 'Каталог · скрытая и восстановление',
  render: () => <CatalogHarness initialFilter="archived" />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('305')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Восстановить' }))
    await expect(canvas.getByText('Аудитории не найдены')).toBeInTheDocument()
    await userEvent.selectOptions(canvas.getByLabelText('Показывать'), 'active')
    await expect(canvas.getByText('305')).toBeInTheDocument()
  },
}

export const CatalogDuplicate: Story = {
  name: 'Каталог · Unicode/case duplicate',
  render: () => <CatalogHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getByLabelText('Новая аудитория')
    await userEvent.type(input, ' АКТОВЫЙ ЗАЛ ')
    await userEvent.click(canvas.getByRole('button', { name: 'Добавить' }))
    await expect(canvas.getByRole('alert')).toHaveTextContent('Такая аудитория уже есть')
    await expect(input).toHaveValue(' АКТОВЫЙ ЗАЛ ')
    await userEvent.click(canvas.getByRole('button', { name: 'Показать существующую' }))
    await expect(canvas.getByText('Актовый зал')).toBeInTheDocument()
  },
}

const typicalLayoutRooms: ClassroomLayoutRoom[] = [
  ...Array.from({ length: 6 }, (_, index) => ({
    id: `b-${index + 1}`,
    name: `${201 + index}`,
    groupId: 'beginner',
  })),
  ...Array.from({ length: 5 }, (_, index) => ({
    id: `c-${index + 1}`,
    name: `${301 + index}`,
    groupId: 'continuing',
  })),
  { id: 'e-1', name: '401', groupId: 'expert' },
  { id: 'e-2', name: 'Актовый зал', groupId: 'expert' },
  { id: 'unused', name: 'Библиотека', groupId: null },
]

function LayoutHarness({ initialState = 'inherited' }: { initialState?: 'inherited' | 'draft' }) {
  const [state, setState] = useState(initialState)
  const [rooms, setRooms] = useState(typicalLayoutRooms)
  const [confirmed, setConfirmed] = useState(false)

  return (
    <div className="space-y-2">
      <ClassroomGroupLayout
        groups={groups}
        lessonLabel="Занятие 41 · 26 января"
        onConfirm={() => confirmed || setConfirmed(true)}
        onMaterialize={() => setState('draft')}
        onRoomGroupChange={(roomId, groupId) =>
          setRooms((current) =>
            current.map((room) => (room.id === roomId ? { ...room, groupId } : room)),
          )
        }
        rooms={rooms}
        sourceLabel="наследуется с занятия 40"
        state={confirmed ? 'confirmed' : state}
        version={confirmed ? 8 : 7}
      />
      <p className="text-caption text-muted-foreground" data-testid="layout-readout" role="status">
        {confirmed ? 'Схема подтверждена' : 'Схема не подтверждена'}
      </p>
    </div>
  )
}

export const LayoutInheritedTypicalCounts: Story = {
  name: 'По группам · унаследовано, фактические 6/5/2',
  render: () => <LayoutHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Унаследовано')).toBeInTheDocument()
    const selects = canvas.getAllByLabelText(/Группа для аудитории/)
    await expect(selects[0]).toBeDisabled()
    await userEvent.click(canvas.getByRole('button', { name: 'Изменить для занятия' }))
    await expect(canvas.getByText('Черновик')).toBeInTheDocument()
    await expect(canvas.getAllByLabelText(/Группа для аудитории/)[0]).toBeEnabled()
  },
}

export const LayoutMaterializedAndConfirm: Story = {
  name: 'По группам · materialized draft и подтверждение',
  render: () => <LayoutHarness initialState="draft" />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.selectOptions(
      canvas.getByLabelText('Группа для аудитории Библиотека'),
      'beginner',
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить схему' }))
    await expect(canvas.getByTestId('layout-readout')).toHaveTextContent('Схема подтверждена')
    await expect(canvas.getByText('Подтверждено')).toBeInTheDocument()
  },
}

export const LayoutOptimisticConflict: Story = {
  name: 'По группам · optimistic conflict',
  render: () => (
    <ClassroomGroupLayout
      groups={groups}
      lessonLabel="Занятие 41 · 26 января"
      optimisticConflict="Администратор И. Соколов уже подтвердил версию 8. Обновите схему перед продолжением."
      rooms={typicalLayoutRooms}
      state="draft"
      version={7}
    />
  ),
}

const planRooms: ClassroomPlanRoom[] = [
  { id: '201', name: '201', groupId: 'beginner' },
  { id: '202', name: '202', groupId: 'beginner' },
  { id: '301', name: '301', groupId: 'continuing' },
  { id: 'hall', name: 'Актовый зал', groupId: 'expert' },
]

const assignedStudents: ClassroomPlanStudent[] = [
  {
    id: 's1',
    name: 'Анна Белова',
    groupId: 'beginner',
    classroomId: '201',
    status: 'assigned',
    source: 'previous-room',
    age: 13.3,
    schoolClass: 7,
    strength: 6.8,
    history: [
      { lessonLabel: 'Занятие 40', classroomName: '201', groupName: 'Начинающие' },
      { lessonLabel: 'Занятие 39', classroomName: '203', groupName: 'Начинающие' },
    ],
  },
  {
    id: 's2',
    name: 'Борис Ветров',
    groupId: 'beginner',
    classroomId: '202',
    status: 'assigned',
    source: 'least-loaded',
    age: 12.7,
    schoolClass: 6,
    strength: 5.2,
    history: [{ lessonLabel: 'Занятие 40', classroomName: '202', groupName: 'Начинающие' }],
  },
  {
    id: 's3',
    name: 'Вера Орлова',
    groupId: 'continuing',
    classroomId: '301',
    status: 'assigned',
    source: 'group-change',
    age: 14.1,
    schoolClass: 8,
    strength: null,
    history: [{ lessonLabel: 'Занятие 40', classroomName: '204', groupName: 'Начинающие' }],
  },
  {
    id: 's4',
    name: 'Григорий Яшин',
    groupId: 'expert',
    classroomId: 'hall',
    status: 'assigned',
    source: 'manual',
    age: null,
    schoolClass: null,
    strength: 8.4,
    history: [],
  },
]

function PlanHarness() {
  const [students, setStudents] = useState(assignedStudents)
  const [state, setState] = useState<ClassroomPlanState>('draft')
  const [readout, setReadout] = useState('План не подтверждён')
  const [groupChange, setGroupChange] = useState<{
    studentId: string
    groupId: string
    classroomId: string
  } | null>(null)

  return (
    <div className="space-y-2">
      <ClassroomStudentPlanner
        groups={groups}
        lessonLabel="Занятие 41 · 26 января"
        onConfirm={() => {
          setState('confirmed')
          setReadout('План подтверждён')
        }}
        onMove={(studentId, classroomId) =>
          setStudents((current) =>
            current.map((student) =>
              student.id === studentId
                ? {
                    ...student,
                    classroomId,
                    source: 'manual' as const,
                    status: 'assigned' as const,
                  }
                : student,
            ),
          )
        }
        onRequestGroupChange={(studentId, groupId, classroomId) =>
          setGroupChange({ studentId, groupId, classroomId })
        }
        onShowHistory={(studentId) => setReadout(`Открыта история ${studentId}`)}
        onRecalculate={() => setReadout('Предпросмотр пересчитан')}
        rooms={planRooms}
        state={state}
        students={students}
        version={12}
      />
      {groupChange ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-status-warning-border bg-status-warning-surface p-3 text-small">
          <p className="text-foreground">Сменить группу школьника вместе с аудиторией?</p>
          <button
            className="rounded-md bg-primary px-2 py-1 text-primary-foreground"
            onClick={() => {
              setStudents((current) =>
                current.map((student) =>
                  student.id === groupChange.studentId
                    ? {
                        ...student,
                        groupId: groupChange.groupId,
                        classroomId: groupChange.classroomId,
                        source: 'group-change' as const,
                      }
                    : student,
                ),
              )
              setGroupChange(null)
            }}
            type="button"
          >
            Сменить группу и аудиторию
          </button>
          <button onClick={() => setGroupChange(null)} type="button">
            Отмена
          </button>
        </div>
      ) : null}
      <p className="text-caption text-muted-foreground" data-testid="plan-readout" role="status">
        {readout}
      </p>
    </div>
  )
}

export const PlanPreviewAndConfirm: Story = {
  name: 'Школьники · предпросмотр и подтверждение',
  render: () => <PlanHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.selectOptions(canvas.getByLabelText('Аудитория для Анна Белова'), '202')
    await userEvent.click(canvas.getByRole('button', { name: 'Пересчитать' }))
    await expect(canvas.getByTestId('plan-readout')).toHaveTextContent('Предпросмотр пересчитан')
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить план' }))
    await expect(canvas.getByTestId('plan-readout')).toHaveTextContent('План подтверждён')
  },
}

export const PlanStale: Story = {
  name: 'Школьники · stale plan',
  render: () => (
    <ClassroomStudentPlanner
      groups={groups}
      lessonLabel="Занятие 41 · 26 января"
      rooms={planRooms}
      staleReason="Аудитория 202 скрыта после публикации плана. Нужен новый предпросмотр."
      state="stale"
      students={assignedStudents}
      version={12}
    />
  ),
}

export const PlanReassigningAndNoRoom: Story = {
  name: 'Школьники · reassigning и блокирующий инцидент',
  render: () => (
    <ClassroomStudentPlanner
      groups={groups}
      incidents={[
        {
          id: 'no-expert-room',
          title: 'У углублённой группы нет аудитории',
          description: 'Григорий Яшин остаётся без назначения. Подтвердить план нельзя.',
          blocking: true,
        },
      ]}
      lessonLabel="Занятие 41 · 26 января"
      rooms={planRooms.filter((room) => room.groupId !== 'expert')}
      state="draft"
      students={[
        ...assignedStudents.filter((student) => student.groupId !== 'expert'),
        {
          id: 's4',
          name: 'Григорий Яшин',
          groupId: 'expert',
          classroomId: null,
          status: 'reassigning',
          source: 'mode-change',
          age: 13.9,
          schoolClass: 8,
          strength: 8.4,
          history: [{ lessonLabel: 'Занятие 40', classroomName: '401', groupName: 'Эксперты' }],
        },
      ]}
      version={13}
    />
  ),
}

export const PlanEmptyGroup: Story = {
  name: 'Школьники · пустая группа без аудитории',
  render: () => (
    <ClassroomStudentPlanner
      groups={groups}
      lessonLabel="Занятие 41 · 26 января"
      rooms={planRooms.filter((room) => room.groupId !== 'expert')}
      state="draft"
      students={assignedStudents.filter((student) => student.groupId !== 'expert')}
      version={13}
    />
  ),
}

const draftStorageKey = 'vmsh-story-classroom-plan-draft'

function PersistentDraftPlan({ onFixed }: { onFixed: () => void }) {
  const stored = window.localStorage.getItem(draftStorageKey)
  const [students, setStudents] = useState<ClassroomPlanStudent[]>(() =>
    stored ? (JSON.parse(stored) as ClassroomPlanStudent[]) : assignedStudents,
  )

  const move = (studentId: string, classroomId: string) => {
    setStudents((current) => {
      const next = current.map((student) =>
        student.id === studentId ? { ...student, classroomId, source: 'manual' as const } : student,
      )
      window.localStorage.setItem(draftStorageKey, JSON.stringify(next))
      return next
    })
  }

  return (
    <div className="space-y-2">
      <p className="text-small text-muted-foreground" role="status">
        {stored ? 'Локальный черновик восстановлен' : 'Локальных изменений нет'}
      </p>
      <ClassroomStudentPlanner
        groups={groups}
        lessonLabel="Занятие 41 · 26 января"
        onConfirm={() => {
          window.localStorage.removeItem(draftStorageKey)
          onFixed()
        }}
        onMove={move}
        rooms={planRooms}
        state="draft"
        students={students}
        version={12}
      />
    </div>
  )
}

function DraftPersistenceHarness() {
  const [generation, setGeneration] = useState(0)
  const [fixed, setFixed] = useState(false)
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Button
          onClick={() => {
            window.localStorage.removeItem(draftStorageKey)
            setFixed(false)
            setGeneration((value) => value + 1)
          }}
          size="sm"
          variant="outline"
        >
          Сбросить фикстуру
        </Button>
        <Button onClick={() => setGeneration((value) => value + 1)} size="sm" variant="outline">
          Симулировать перезагрузку
        </Button>
      </div>
      {fixed ? (
        <p className="text-small text-status-success" role="status">
          План зафиксирован, локальный черновик очищен
        </p>
      ) : (
        <PersistentDraftPlan key={generation} onFixed={() => setFixed(true)} />
      )}
    </div>
  )
}

export const PlanLocalDraftRestored: Story = {
  name: 'Школьники · local draft переживает reload',
  render: () => <DraftPersistenceHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Сбросить фикстуру' }))
    await userEvent.selectOptions(canvas.getByLabelText('Аудитория для Анна Белова'), '202')
    await userEvent.click(canvas.getByRole('button', { name: 'Симулировать перезагрузку' }))
    await expect(canvas.getByText('Локальный черновик восстановлен')).toBeInTheDocument()
    await expect(canvas.getByLabelText('Аудитория для Анна Белова')).toHaveValue('202')
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить план' }))
    await expect(
      canvas.getByText('План зафиксирован, локальный черновик очищен'),
    ).toBeInTheDocument()
  },
}

const denseRooms: ClassroomPlanRoom[] = Array.from({ length: 15 }, (_, index) => {
  const groupId = index < 6 ? 'beginner' : index < 11 ? 'continuing' : 'expert'
  return { id: `dense-room-${index + 1}`, name: `${201 + index}`, groupId }
})

const denseStudents: ClassroomPlanStudent[] = Array.from({ length: 200 }, (_, index) => {
  const groupId = index < 84 ? 'beginner' : index < 152 ? 'continuing' : 'expert'
  const rooms = denseRooms.filter((room) => room.groupId === groupId)
  return {
    id: `dense-student-${index + 1}`,
    name: `Ученик ${String(index + 1).padStart(3, '0')} Фамилия`,
    groupId,
    classroomId: rooms[index % rooms.length]!.id,
    status: 'assigned',
    source: index % 3 === 0 ? 'previous-room' : 'least-loaded',
    age: index % 17 === 0 ? null : 11.5 + (index % 45) / 10,
    schoolClass: index % 19 === 0 ? null : 5 + (index % 6),
    strength: index % 13 === 0 ? null : 3 + (index % 70) / 10,
  }
})

export const PlanDenseTwoHundredStudents: Story = {
  name: 'Школьники · 15 аудиторий и 200 строк',
  render: () => (
    <ClassroomStudentPlanner
      groups={groups.map((group) => ({
        ...group,
        inPersonCount: denseStudents.filter((student) => student.groupId === group.id).length,
        assignedCount: denseStudents.filter((student) => student.groupId === group.id).length,
      }))}
      lessonLabel="Занятие 41 · плотная фикстура"
      onMove={() => undefined}
      onShowHistory={() => undefined}
      rooms={denseRooms}
      state="draft"
      students={denseStudents}
      version={14}
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getAllByLabelText(/^Аудитория для Ученик/)).toHaveLength(200)
    await userEvent.type(canvas.getByLabelText('Быстрый поиск школьника'), 'Ученик 179')
    await expect(canvas.getByRole('button', { name: /^Ученик 179 Фамилия$/ })).toBeInTheDocument()
  },
}

export const PublicAssignmentStates: Story = {
  name: 'Student и Family · все публичные состояния',
  render: () => (
    <div className="grid max-w-4xl gap-4 md:grid-cols-2" data-density="student">
      <div className="space-y-2">
        <p className="text-label font-medium text-foreground">Школьник</p>
        <ClassroomAssignmentStatus
          audience="student"
          classroomName="201"
          onOpenNotificationSettings={() => undefined}
          publishedAt="26 января, 15:40"
          status="assigned"
        />
        <ClassroomAssignmentStatus
          audience="student"
          onOpenNotificationSettings={() => undefined}
          status="reassigning"
        />
        <ClassroomAssignmentStatus audience="student" status="not_applicable" />
      </div>
      <div className="space-y-2" data-density="family">
        <p className="text-label font-medium text-foreground">Семья</p>
        <ClassroomAssignmentStatus
          audience="family"
          classroomName="201"
          publishedAt="26 января, 15:40"
          status="assigned"
          studentName="Анна"
        />
        <ClassroomAssignmentStatus
          audience="family"
          publishedAt="26 января, 16:10"
          status="reassigning"
          studentName="Анна"
        />
        <ClassroomAssignmentStatus audience="family" status="not_applicable" studentName="Анна" />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getAllByRole('button', { name: /уведомлен/i })).toHaveLength(2)
    await expect(canvas.getByText('Аудитория: Анна')).toBeInTheDocument()
  },
}

function MobileClassroomHarness() {
  const [tab, setTab] = useState('catalog')
  return (
    <Tabs className="min-w-0 flex-col" onValueChange={setTab} value={tab}>
      <TabsList aria-label="Разделы аудиторий" className="w-full" variant="line">
        <TabsTrigger value="catalog">Каталог</TabsTrigger>
        <TabsTrigger value="groups">По группам</TabsTrigger>
        <TabsTrigger value="students">Школьники</TabsTrigger>
      </TabsList>
      <TabsContent className="min-w-0" value="catalog">
        <CatalogHarness />
      </TabsContent>
      <TabsContent className="min-w-0" value="groups">
        <LayoutHarness />
      </TabsContent>
      <TabsContent className="min-w-0" value="students">
        <PlanHarness />
      </TabsContent>
    </Tabs>
  )
}

export const MobileStaffLayout: Story = {
  name: 'Staff mobile · три последовательных шага',
  parameters: { layout: 'fullscreen', viewport: { defaultViewport: 'mobile2' } },
  render: () => (
    <div className="min-h-svh bg-background p-3" data-density="staff">
      <MobileClassroomHarness />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('tab', { name: 'Школьники' }))
    await expect(canvas.getByText('Школьники по аудиториям')).toBeInTheDocument()
    await expect(canvas.getAllByText(/возраст 13\.3/).length).toBeGreaterThan(0)
    await expect(canvas.getAllByText(/класс 7/).length).toBeGreaterThan(0)
    await expect(canvas.getAllByText(/сила 6\.8/).length).toBeGreaterThan(0)
    await expect(
      canvas.getByText(/1 уч\. · возраст 13\.3 · класс 7\.0 · сила 6\.8/),
    ).toBeInTheDocument()
    await userEvent.type(canvas.getByLabelText('Быстрый поиск школьника'), 'Белофа')
    await expect(canvas.getByRole('button', { name: /^Анна Белова$/ })).toBeInTheDocument()
    await expect(canvas.getByRole('button', { name: 'Подтвердить план' })).toBeEnabled()
  },
}
