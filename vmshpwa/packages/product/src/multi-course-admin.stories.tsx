import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import {
  CourseGroupCatalog,
  IndependentScheduleMatrix,
  TelegramBindingsEditor,
  type IndependentScheduleRow,
  type ManagedCourse,
} from './course-admin'
import { mathCourse, mathGroups, physicsCourse, physicsGroups } from './course-fixtures'

const meta = {
  title: 'Product/Staff admin',
  parameters: { layout: 'padded' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const courses: ManagedCourse[] = [
  {
    course: mathCourse,
    status: 'active',
    groups: mathGroups.map((group, index) => ({
      ...group,
      status: 'active',
      activeStudents: [84, 71, 28][index] ?? 0,
      scheduleLabel: index === 1 ? 'своё расписание' : 'шаблон курса',
    })),
  },
  {
    course: physicsCourse,
    status: 'active',
    groups: physicsGroups.map((group, index) => ({
      ...group,
      status: 'active',
      activeStudents: [32, 27][index] ?? 0,
      scheduleLabel: index === 0 ? 'шаблон курса' : 'своё расписание',
    })),
  },
]

function CatalogHarness() {
  const [status, setStatus] = useState('Изменений нет')
  return (
    <div className="space-y-3">
      <CourseGroupCatalog
        courses={courses}
        onAddCourse={() => setStatus('Открыта форма нового курса')}
        onAddGroup={(courseId) => setStatus(`Новая группа для ${courseId}`)}
        onEditCourse={(courseId) => setStatus(`Настройки ${courseId}`)}
      />
      <p className="text-small text-muted-foreground" role="status">
        {status}
      </p>
    </div>
  )
}

export const CourseAndGroupCatalog: Story = {
  name: 'Course and group catalog',
  render: () => <CatalogHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Добавить курс' }))
    await expect(canvas.getByRole('status')).toHaveTextContent('Открыта форма нового курса')
  },
}

const scheduleRows: IndependentScheduleRow[] = [
  {
    group: mathGroups[0]!,
    source: 'course',
    conditionAt: 'пн 16:30',
    hintAt: 'сб 12:00',
    closesAt: 'вс 13:00',
    solutionAt: 'вс 14:00',
    snapshotLabel: 'снимок шаблона v4',
  },
  {
    group: mathGroups[1]!,
    source: 'group',
    conditionAt: 'вт 17:00',
    hintAt: 'сб 15:00',
    closesAt: 'вс 15:00',
    solutionAt: 'вс 16:00',
    snapshotLabel: 'расписание группы v2',
  },
  {
    group: mathGroups[2]!,
    source: 'lesson',
    conditionAt: 'пн 18:10',
    hintAt: '—',
    closesAt: 'пн 17:00',
    solutionAt: 'пн 18:00',
    snapshotLabel: 'занятие изменено отдельно',
  },
]

export const IndependentSchedules: Story = {
  name: 'Independent schedules',
  render: () => (
    <IndependentScheduleMatrix course={mathCourse} lessonNumber={41} rows={scheduleRows} />
  ),
}

export const TelegramBindings: Story = {
  name: 'Telegram bindings',
  render: () => (
    <TelegramBindingsEditor
      bindings={[
        {
          id: 'math-news',
          owner: 'course',
          ownerLabel: 'Математика 5–7',
          purpose: 'news-source',
          chatLabel: '@vmsh_math_5_7',
          status: 'verified',
        },
        {
          id: 'math-beginner-target',
          owner: 'group',
          ownerLabel: 'Начинающие',
          purpose: 'materials-target',
          chatLabel: '-100179000201',
          topicLabel: 'тема 41',
          status: 'verified',
        },
        {
          id: 'math-continuing-news',
          owner: 'group',
          ownerLabel: 'Продолжающие',
          purpose: 'news-source',
          chatLabel: '@vmsh_math_pro',
          status: 'verified',
        },
      ]}
      course={mathCourse}
    />
  ),
}

function TelegramBindingLifecycleHarness() {
  const [status, setStatus] = useState<'draft' | 'verified' | 'disabled'>('draft')
  return (
    <TelegramBindingsEditor
      bindings={[
        {
          id: 'math-news-draft',
          owner: 'course',
          ownerLabel: 'Математика 5–7',
          purpose: 'news-source',
          chatLabel: '-100179000001',
          status,
        },
      ]}
      course={mathCourse}
      onDisable={() => setStatus('disabled')}
      onRestore={() => setStatus('draft')}
      onVerify={() => setStatus('verified')}
    />
  )
}

export const TelegramBindingLifecycle: Story = {
  name: 'Telegram binding · проверка и отключение',
  render: () => <TelegramBindingLifecycleHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Черновик')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить' }))
    await expect(canvas.getByText('Проверена')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Отключить' }))
    await expect(canvas.getByText('Отключена')).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Вернуть в черновик' }))
    await expect(canvas.getByText('Черновик')).toBeInTheDocument()
  },
}
