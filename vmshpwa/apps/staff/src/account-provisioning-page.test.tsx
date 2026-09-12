import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import type {
  AccountProvisioningPreviewResponse,
  AccountProvisioningReceipt,
} from '@vmsh/contracts'

import { AccountProvisioningView } from './account-provisioning-page'

afterEach(cleanup)

it('counts duplicate parents and leaves only actual errors in the editor', async () => {
  const preview: AccountProvisioningPreviewResponse = {
    schemaVersion: 1,
    previewHash: 'a'.repeat(64),
    counts: { total: 3, ready: 2, invalid: 1 },
    rows: [
      {
        rowNumber: 1,
        state: 'ready',
        resolvedLogin: 'parent-one',
        loginAdjusted: false,
        code: null,
      },
      {
        rowNumber: 2,
        state: 'invalid',
        resolvedLogin: null,
        loginAdjusted: false as const,
        code: 'family_email_duplicate',
      },
      {
        rowNumber: 3,
        state: 'ready',
        resolvedLogin: 'parent-three',
        loginAdjusted: false,
        code: null,
      },
    ],
    requestId: 'preview',
  }
  const receipt: AccountProvisioningReceipt = {
    schemaVersion: 1,
    counts: { total: 3, created: 1, skipped: 2 },
    rows: [
      { rowNumber: 1, state: 'created', login: 'parent-one', accountId: 'a-1', childCount: 1 },
      { rowNumber: 2, state: 'skipped', code: 'family_email_duplicate' },
      { rowNumber: 3, state: 'skipped', code: 'child_login_not_found' },
    ],
    requestId: 'apply',
  }
  render(
    <AccountProvisioningView
      accountId="a-admin"
      storageNamespace="test-provisioning"
      onSectionChange={() => undefined}
      previewStudents={vi.fn()}
      applyStudents={vi.fn()}
      previewFamilies={vi.fn().mockResolvedValue(preview)}
      applyFamilies={vi.fn().mockResolvedValue(receipt)}
      previewCourseEnrollments={vi.fn()}
      applyCourseEnrollments={vi.fn()}
    />,
  )
  const editor = screen.getAllByLabelText('Вставьте строки из таблицы')[1]!
  const first = 'Первый родитель\tparent-one\tpassword-one\tone@example.org\tstudent-one'
  const second = 'Дубль родителя\tparent-two\tpassword-two\tone@example.org\tstudent-one'
  const third =
    'Проблемный родитель\tparent-three\tpassword-three\tthree@example.org\tmissing-child'
  fireEvent.change(editor, { target: { value: `${first}\n${second}\n${third}` } })
  fireEvent.click(screen.getAllByRole('button', { name: 'Проверить таблицу' })[1]!)
  await screen.findByRole('button', { name: 'Создать готовые · 2' })
  expect(screen.getByText('Дубли: 1')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Создать готовые · 2' }))

  await screen.findByText('Пропущены')
  expect(screen.getByText('Дубль родителя · parent-two')).toBeTruthy()
  expect(screen.getByText('родитель с таким email уже есть')).toBeTruthy()
  expect(screen.getByText('Проблемный родитель · parent-three')).toBeTruthy()
  expect(screen.getByText('школьник с таким логином не найден')).toBeTruthy()
  expect(screen.getByText(/Дубликатов проигнорировано: 1/)).toBeTruthy()
  await waitFor(() => expect((editor as HTMLTextAreaElement).value).toBe(third))
  expect(screen.getByText(/оставлены только строки, которые нужно исправить/)).toBeTruthy()
})
