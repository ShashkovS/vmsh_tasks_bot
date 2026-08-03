import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { familyDigestPreviewSchema, type FamilyDigestPreview } from '@vmsh/contracts'

import { FamilyDigestPanelView } from './family-digest-panel'

// Executable states from dev/development-plan/12-phase-8-news-and-notifications.md.
const ready = familyDigestPreviewSchema.parse({
  groupLessonId: 'lesson.math.41.n',
  courseId: 'course.math',
  courseName: 'Математика 5–7',
  groupId: 'group.beginner',
  groupName: 'Начинающие',
  lessonNumber: 41,
  studentCount: 28,
  familyCount: 26,
  alreadySentFamilyCount: 0,
  pendingFamilyCount: 26,
  unlinkedStudents: [
    { studentId: 'student.one', displayName: 'Иванов Иван' },
    { studentId: 'student.two', displayName: 'Петрова Анна' },
  ],
})

const meta = {
  title: 'Product/Staff admin/Family digest',
  component: FamilyDigestPanelView,
  parameters: { layout: 'padded' },
} satisfies Meta<typeof FamilyDigestPanelView>
export default meta
type Story = StoryObj<typeof meta>

function InteractiveDigest({ initial }: { initial: FamilyDigestPreview }) {
  const [digest, setDigest] = useState(initial)
  const [confirming, setConfirming] = useState(false)
  return (
    <FamilyDigestPanelView
      confirming={confirming}
      digest={digest}
      onCancel={() => setConfirming(false)}
      onConfirm={() => {
        setDigest({
          ...digest,
          alreadySentFamilyCount: digest.familyCount,
          pendingFamilyCount: 0,
        })
        setConfirming(false)
      }}
      onStart={() => setConfirming(true)}
    />
  )
}

export const ReadyToSend: Story = {
  render: () => <InteractiveDigest initial={ready} />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Без активного семейного аккаунта: 2')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Разослать итог' }))
    await expect(canvas.getByRole('alertdialog')).toHaveTextContent('Отправить итог 26 семьям?')
    await userEvent.click(canvas.getByRole('button', { name: 'Отправить' }))
    await expect(canvas.getByText('Итог уже разослан')).toBeVisible()
  },
}

export const LateFamilyPending: Story = {
  args: {
    digest: {
      ...ready,
      familyCount: 27,
      alreadySentFamilyCount: 26,
      pendingFamilyCount: 1,
    },
    onStart: () => undefined,
  },
}

export const AlreadySent: Story = {
  args: {
    digest: {
      ...ready,
      alreadySentFamilyCount: 26,
      pendingFamilyCount: 0,
    },
  },
}

export const NoRecipients: Story = {
  args: {
    digest: {
      ...ready,
      familyCount: 0,
      pendingFamilyCount: 0,
      unlinkedStudents: ready.unlinkedStudents.slice(0, 1),
    },
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Нет семейных аккаунтов для рассылки')).toBeVisible()
    await expect(canvas.queryByRole('button', { name: 'Разослать итог' })).not.toBeInTheDocument()
    await expect(canvas.queryByText('Итог уже разослан')).not.toBeInTheDocument()
  },
}

export const Loading: Story = { args: { loading: true } }

export const Error: Story = {
  args: { error: true, onRetry: () => undefined },
  play: async ({ canvasElement }) => {
    await expect(within(canvasElement).getByRole('button', { name: 'Повторить' })).toBeVisible()
  },
}
