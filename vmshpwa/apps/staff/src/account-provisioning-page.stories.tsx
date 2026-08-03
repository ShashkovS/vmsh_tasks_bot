import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, fireEvent, userEvent, within } from 'storybook/test'

import type {
  AccountProvisioningPreviewResponse,
  AccountProvisioningReceipt,
  CourseEnrollmentProvisioningPreviewResponse,
  CourseEnrollmentProvisioningReceipt,
} from '@vmsh/contracts'

import { AccountProvisioningView } from './account-provisioning-page'

const preview: AccountProvisioningPreviewResponse = {
  schemaVersion: 1,
  previewHash: 'a'.repeat(64),
  counts: { total: 1, ready: 1, invalid: 0 },
  rows: [
    {
      rowNumber: 1,
      state: 'ready',
      resolvedLogin: 'ivanov-17',
      loginAdjusted: true,
      code: null,
    },
  ],
  requestId: 'storybook.preview',
}

const receipt: AccountProvisioningReceipt = {
  schemaVersion: 1,
  counts: { total: 1, created: 1, skipped: 0 },
  rows: [
    {
      rowNumber: 1,
      state: 'created',
      login: 'ivanov-17',
      userId: 'user.ivanov',
      accountId: 'student-account.ivanov',
    },
  ],
  requestId: 'storybook.apply',
}

const enrollmentPreview: CourseEnrollmentProvisioningPreviewResponse = {
  schemaVersion: 1,
  previewHash: 'b'.repeat(64),
  counts: { total: 1, ready: 1, invalid: 0 },
  rows: [
    {
      rowNumber: 1,
      state: 'ready',
      login: 'ivanov-17',
      courseCode: 'math-57',
      activeGroupCode: 'н',
      allowedGroupCodes: ['н', 'п', 'э'],
      code: null,
    },
  ],
  requestId: 'storybook.enrollment-preview',
}

const enrollmentReceipt: CourseEnrollmentProvisioningReceipt = {
  schemaVersion: 1,
  counts: { total: 1, created: 1, skipped: 0 },
  rows: [
    {
      rowNumber: 1,
      state: 'created',
      login: 'ivanov-17',
      courseCode: 'math-57',
      activeGroupCode: 'н',
      allowedGroupCodes: ['н', 'п', 'э'],
      enrollmentId: 'course-enrollment.ivanov',
    },
  ],
  requestId: 'storybook.enrollment-apply',
}

// Phase 1/10 account batches: development plan 05 and design-system page flow 05.
const meta = {
  title: 'Pages/Staff/Account provisioning',
  component: AccountProvisioningView,
  parameters: { layout: 'fullscreen' },
  args: {
    accountId: 'storybook-admin',
    storageNamespace: 'vmsh-179:v1:staff:storybook-provisioning',
    onSectionChange: () => undefined,
    previewStudents: () => Promise.resolve(preview),
    applyStudents: () => Promise.resolve(receipt),
    previewFamilies: () => Promise.resolve(preview),
    applyFamilies: () =>
      Promise.resolve({
        ...receipt,
        rows: [
          {
            rowNumber: 1,
            state: 'created',
            login: 'parent-ivanov',
            accountId: 'family-account.ivanov',
            childCount: 1,
          },
        ],
      }),
    previewCourseEnrollments: () => Promise.resolve(enrollmentPreview),
    applyCourseEnrollments: () => Promise.resolve(enrollmentReceipt),
  },
} satisfies Meta<typeof AccountProvisioningView>

export default meta
type Story = StoryObj<typeof meta>

export const Empty: Story = {}

export const StudentPreviewAndApply: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getAllByLabelText('Вставьте строки из таблицы')[0]!
    await fireEvent.change(input, {
      target: {
        value: 'Иванов\tИван\tИванович\t05.04.2013\t7\tivanov\tTelegramToken',
      },
    })
    await userEvent.click(canvas.getAllByRole('button', { name: 'Проверить таблицу' })[0]!)
    await expect(canvas.getByText('ivanov-17 · изменён')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Создать готовые · 1' }))
    await expect(canvas.getByText('Создано: 1. Пропущено: 0.')).toBeVisible()
    await expect(input).toHaveValue('')
  },
}

export const CourseEnrollmentPreviewAndApply: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getByLabelText('Вставьте строки зачисления')
    await fireEvent.change(input, {
      target: { value: 'ivanov-17\tmath-57\tэ, н, п' },
    })
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить зачисление' }))
    await expect(canvas.getByText('ivanov-17 · math-57')).toBeVisible()
    await expect(canvas.getByText('н')).toBeVisible()
    await expect(canvas.getByText('н, п, э')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Зачислить готовых · 1' }))
    await expect(canvas.getByText('Зачислено: 1. Пропущено: 0.')).toBeVisible()
    await expect(input).toHaveValue('')
  },
}
