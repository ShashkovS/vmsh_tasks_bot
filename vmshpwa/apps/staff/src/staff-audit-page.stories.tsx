import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { auditListResponseSchema, type AuditObjectType } from '@vmsh/contracts'

import { StaffAuditView } from './staff-audit-page'

const data = auditListResponseSchema.parse({
  schemaVersion: 1,
  items: [
    {
      eventId: 'audit.news-source-deleted',
      occurredAt: '2026-08-02T11:30:00Z',
      audience: 'staff',
      action: 'news_source.marked_deleted',
      objectType: 'news_post',
      objectId: 'news.lesson-41',
      requestId: 'request-news-source-41',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: { visibility: 'visible', sourceDeletedAt: null, version: 1 },
      after: {
        visibility: 'source_deleted',
        sourceDeletedAt: '2026-08-02T11:30:00Z',
        reconciliationReason: 'Пост отсутствует в канале',
        version: 2,
      },
    },
    {
      eventId: 'audit.staff-scope-replaced',
      occurredAt: '2026-08-02T11:25:00Z',
      audience: 'staff',
      action: 'staff_scope.replaced',
      objectType: 'staff_scope',
      objectId: 'user.teacher-1',
      requestId: 'request-staff-scope-4',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: {
        scopeCount: 1,
        scopes: 'course.math/group.beginner',
      },
      after: {
        scopeCount: 1,
        scopes: 'course.math',
        addedCount: 1,
        removedCount: 1,
      },
    },
    {
      eventId: 'audit.problem-synonym-split',
      occurredAt: '2026-08-02T11:20:00Z',
      audience: 'staff',
      action: 'problem_synonym.split',
      objectType: 'problem_synonym',
      objectId: 'problem-synonym.rooks',
      requestId: 'request-synonym-split-7',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: { status: 'active', version: 1, memberCount: 2 },
      after: {
        courseLessonId: 'course-lesson.41',
        status: 'split',
        version: 2,
        memberCount: 0,
        removedCount: 2,
        reason: 'Задачи были объединены по ошибке',
      },
    },
    {
      eventId: 'audit.telegram-binding-verified',
      occurredAt: '2026-08-02T11:15:00Z',
      audience: 'staff',
      action: 'telegram_binding.verified',
      objectType: 'telegram_binding',
      objectId: 'telegram-binding.math-news',
      requestId: 'request-telegram-binding-7',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: {
        ownerType: 'course',
        ownerId: 'course.math-5-7',
        chatId: -100179000001,
        status: 'draft',
        version: 2,
      },
      after: {
        ownerType: 'course',
        ownerId: 'course.math-5-7',
        chatId: -100179000001,
        status: 'verified',
        titleCached: 'Новости математики',
        version: 3,
      },
    },
    {
      eventId: 'audit.course-update',
      occurredAt: '2026-08-02T11:00:00Z',
      audience: 'staff',
      action: 'course.updated',
      objectType: 'course',
      objectId: 'course.physics-7',
      requestId: 'request-course-7',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: { code: 'physics-7', name: 'Физика', status: 'draft', version: 1 },
      after: { code: 'physics-7', name: 'Физика 7', status: 'active', version: 2 },
    },
    {
      eventId: 'audit.account-status',
      occurredAt: '2026-08-02T10:30:00Z',
      audience: 'staff',
      action: 'account.status_changed',
      objectType: 'account',
      objectId: 'account.student-179',
      requestId: 'request-admin-179',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: { status: 'active' },
      after: { status: 'blocked' },
    },
    {
      eventId: 'audit.enrollment',
      occurredAt: '2026-08-02T09:15:00Z',
      audience: 'staff',
      action: 'course_enrollment.updated',
      objectType: 'course_enrollment',
      objectId: 'enrollment.math-179',
      requestId: 'request-enrollment-41',
      actor: {
        userId: 'user.admin-1',
        accountId: 'account.admin-1',
        displayName: 'Петрова Анна',
      },
      before: {
        activeGroupId: 'group.beginner',
        attendanceMode: 'online',
        status: 'active',
      },
      after: {
        activeGroupId: 'group.continuing',
        attendanceMode: 'in_person',
        status: 'active',
      },
    },
    {
      eventId: 'audit.import',
      occurredAt: '2026-08-01T18:05:00Z',
      audience: 'staff',
      action: 'problem_import.applied',
      objectType: 'problem_import',
      objectId: 'problem-import.lesson-41',
      requestId: 'request-import-41',
      actor: {
        userId: 'user.admin-2',
        accountId: 'account.admin-2',
        displayName: 'Сергеев Иван',
      },
      before: null,
      after: {
        courseId: 'course.math',
        created: 18,
        rows: 56,
        sourceFilename: 'Задачи 41.xlsx',
        state: 'applied',
        updated: 7,
      },
    },
  ],
  nextCursor: 'audit.import',
  requestId: 'story-audit',
})

function Harness({ empty = false }: { empty?: boolean }) {
  const [objectType, setObjectType] = useState<AuditObjectType>('all')
  const [query, setQuery] = useState('')
  const filtered = empty
    ? []
    : data.items.filter(
        (event) =>
          (objectType === 'all' || event.objectType === objectType) &&
          (!query || `${event.action} ${event.objectId} ${event.requestId}`.includes(query)),
      )
  return (
    <StaffAuditView
      events={filtered}
      nextCursor={filtered.length > 0 ? data.nextCursor : null}
      objectType={objectType}
      onFilter={(nextObjectType, nextQuery) => {
        setObjectType(nextObjectType)
        setQuery(nextQuery)
      }}
      onNextPage={() => undefined}
      query={query}
    />
  )
}

const meta = {
  title: 'Pages/Staff/Audit',
  parameters: { canvasPadding: false, layout: 'fullscreen' },
  globals: { density: 'staff' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const SearchableTimeline: Story = {
  name: 'Searchable timeline',
  render: () => <Harness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getAllByText('Показать изменения')[0]!)
    await expect(canvas.getAllByText('Было')[0]).toBeInTheDocument()
    await userEvent.type(
      canvas.getByLabelText('Поиск по действию, объекту или request ID'),
      'request-import-41',
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Найти' }))
    await expect(canvas.getByText('Задачи 41.xlsx')).toBeInTheDocument()
    await expect(canvas.queryByText('account.student-179')).not.toBeInTheDocument()
  },
}

export const EmptySearch: Story = {
  name: 'Empty search',
  render: () => <Harness empty />,
}
