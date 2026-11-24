import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { createContentApiClient } from '@vmsh/content'
import {
  contentEtagSchema,
  parseRuntimeConfigForAudience,
  type ProblemMatchReview,
  type ProblemMetadataGrid,
} from '@vmsh/contracts'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

import { ProblemReviewWorkflow } from './problem-review-workflow'
import { problemReviewDraftStorageKey } from './problem-review-draft'

const etag = contentEtagSchema.parse('"fresh-review:v1"')
const review: ProblemMatchReview = {
  revisionId: 'fresh-review',
  groupLessonId: 'fresh-lesson',
  version: 1,
  etag,
  requestId: 'fresh-test',
  items: ['а', 'б'].map((item) => ({
    sourceOrdinal: 1,
    sourceItem: item,
    displayNumber: `1${item}`,
    sourceTitle: null,
    suggestedProblemId: null,
    match: null,
  })),
  candidates: [
    {
      problemId: 5,
      problemNumber: 1,
      item: 'old',
      title: 'Old task',
      problemType: 1,
      answerType: 2,
      answerValidation: null,
      validationError: null,
      correctAnswer: '42',
      correctAnswerChecker: null,
      wrongAnswer: null,
      congratulation: null,
    },
  ],
}

beforeEach(() => {
  const stored = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => stored.get(key) ?? null,
    setItem: (key: string, value: string) => stored.set(key, value),
    removeItem: (key: string) => stored.delete(key),
  })
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const grid: ProblemMetadataGrid = {
  revisionId: review.revisionId,
  groupLessonId: review.groupLessonId,
  version: 2,
  etag,
  requestId: 'reload-grid',
  testRechecks: [],
  rows: [
    {
      ...review.items[0]!,
      problemId: 101,
      title: 'Серверное название',
      problemType: 2,
      answerType: null,
      answerValidation: null,
      validationError: null,
      correctAnswer: null,
      correctAnswerChecker: null,
      wrongAnswer: null,
      congratulation: null,
      reviewed: false,
    },
  ],
}
const draftKey = problemReviewDraftStorageKey(
  'reload',
  'metadata',
  review.groupLessonId,
  review.revisionId,
)
function mount() {
  const client = createContentApiClient(
    parseRuntimeConfigForAudience('staff', runtimeFixture.response),
  )
  vi.spyOn(client, 'problemMatches').mockResolvedValue({
    etag,
    data: {
      ...review,
      items: review.items.map((item) => ({
        ...item,
        match: { decision: 'insert_new', problemId: 101 },
      })),
    },
  })
  const metadata = vi.spyOn(client, 'metadataGrid').mockResolvedValue({ etag, data: grid })
  const save = vi.spyOn(client, 'saveMetadataGrid')
  render(
    <ProblemReviewWorkflow
      client={client}
      draftNamespace="reload"
      groupLessonId={review.groupLessonId}
      revisionId={review.revisionId}
      kind="condition"
      onReadyChange={vi.fn()}
    />,
  )
  return { metadata, save }
}
async function editTitle() {
  await screen.findByRole('grid')
  fireEvent.doubleClick(screen.getByRole('gridcell', { name: 'Название, строка 1' }))
  const dialog = screen.getByRole('dialog')
  fireEvent.change(within(dialog).getByRole('textbox', { name: 'Название' }), {
    target: { value: 'Локальный черновик' },
  })
  fireEvent.click(within(dialog).getByRole('button', { name: 'Применить' }))
}
it('reloads current server rows without saving and discards the draft only after success', async () => {
  const { metadata, save } = mount()
  await editTitle()
  const stored = localStorage.getItem(draftKey)
  expect(stored).toContain('Локальный черновик')
  let finish!: (value: { etag: typeof etag; data: ProblemMetadataGrid }) => void
  metadata.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve
      }),
  )
  fireEvent.click(screen.getByRole('button', { name: 'Отбросить черновик и загрузить с сервера' }))
  expect(
    screen.getByRole('button', { name: 'Загружаем с сервера…' }).hasAttribute('disabled'),
  ).toBe(true)
  expect(
    screen.getByRole('button', { name: 'Сохранить метаданные' }).hasAttribute('disabled'),
  ).toBe(true)
  expect(localStorage.getItem(draftKey)).toBe(stored)
  finish({
    etag: contentEtagSchema.parse('"reload:v3"'),
    data: { ...grid, rows: grid.rows.map((row) => ({ ...row, title: 'Новое с сервера' })) },
  })
  await screen.findByText('Новое с сервера')
  expect(screen.queryByText('Локальный черновик')).toBeNull()
  expect(localStorage.getItem(draftKey)).toBeNull()
  expect(save).not.toHaveBeenCalled()
  expect(metadata).toHaveBeenCalledTimes(2)
})
it('preserves edited rows and the stored draft on a failed read, then allows retry', async () => {
  const { metadata, save } = mount()
  await editTitle()
  const stored = localStorage.getItem(draftKey)
  metadata.mockRejectedValueOnce(new Error('Offline'))
  fireEvent.click(screen.getByRole('button', { name: 'Отбросить черновик и загрузить с сервера' }))
  await screen.findByText('Не удалось загрузить таблицу с сервера')
  expect(screen.getByText('Локальный черновик')).toBeTruthy()
  expect(localStorage.getItem(draftKey)).toBe(stored)
  const reload = screen.getByRole('button', { name: 'Отбросить черновик и загрузить с сервера' })
  await waitFor(() => expect(reload.hasAttribute('disabled')).toBe(false))
  fireEvent.click(reload)
  await screen.findByText('Серверное название')
  expect(screen.queryByText('Не удалось загрузить таблицу с сервера')).toBeNull()
  expect(localStorage.getItem(draftKey)).toBeNull()
  expect(save).not.toHaveBeenCalled()
})
