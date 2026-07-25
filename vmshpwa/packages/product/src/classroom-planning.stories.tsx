import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@vmsh/ui'

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
  { id: 'beginner', name: 'Начинающие', shortCode: 'н' },
  { id: 'continuing', name: 'Продолжающие', shortCode: 'п' },
  { id: 'expert', name: 'Углублённые', shortCode: 'х' },
]

const catalogRooms: ClassroomCatalogRoom[] = [
  { id: '201', name: '201', status: 'active', version: 3, usageLabel: 'Начинающие · с занятия 38' },
  { id: '202', name: '202', status: 'active', version: 1, usageLabel: 'Начинающие · с занятия 39' },
  {
    id: 'hall',
    name: 'Актовый зал',
    status: 'active',
    version: 4,
    usageLabel: 'Углублённые · с занятия 37',
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
  },
  {
    id: 's2',
    name: 'Борис Ветров',
    groupId: 'beginner',
    classroomId: '202',
    status: 'assigned',
    source: 'least-loaded',
  },
  {
    id: 's3',
    name: 'Вера Орлова',
    groupId: 'continuing',
    classroomId: '301',
    status: 'assigned',
    source: 'group-change',
  },
  {
    id: 's4',
    name: 'Григорий Яшин',
    groupId: 'expert',
    classroomId: 'hall',
    status: 'assigned',
    source: 'manual',
  },
]

function PlanHarness() {
  const [students, setStudents] = useState(assignedStudents)
  const [state, setState] = useState<ClassroomPlanState>('draft')
  const [readout, setReadout] = useState('План не подтверждён')

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
        onRecalculate={() => setReadout('Предпросмотр пересчитан')}
        rooms={planRooms}
        state={state}
        students={students}
        version={12}
      />
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
    await expect(canvas.getByRole('button', { name: 'Подтвердить план' })).toBeEnabled()
  },
}
