import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { createContentApiClient } from '@vmsh/content'
import {
  contentEtagSchema,
  ApiResponseError,
  parseRuntimeConfigForAudience,
  type ProblemMatchReview,
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

function mount() {
  const client = createContentApiClient(
    parseRuntimeConfigForAudience('staff', runtimeFixture.response),
  )
  vi.spyOn(client, 'problemMatches').mockResolvedValue({ etag, data: review })
  const resolve = vi.spyOn(client, 'resolveProblemMatches')
  const metadata = vi.spyOn(client, 'metadataGrid').mockResolvedValue({
    etag,
    data: {
      revisionId: review.revisionId,
      groupLessonId: review.groupLessonId,
      version: 2,
      etag,
      requestId: 'fresh-grid',
      testRechecks: [],
      rows: review.items.map((item, index) => ({
        ...item,
        problemId: 101 + index,
        title: '',
        problemType: 2,
        answerType: null,
        answerValidation: null,
        validationError: null,
        correctAnswer: null,
        correctAnswerChecker: null,
        wrongAnswer: null,
        congratulation: null,
        reviewed: false,
      })),
    },
  })
  const ready = vi.fn()
  render(
    <ProblemReviewWorkflow
      client={client}
      draftNamespace="fresh"
      groupLessonId={review.groupLessonId}
      revisionId={review.revisionId}
      kind="condition"
      onReadyChange={ready}
    />,
  )
  return { resolve, metadata, ready }
}

it('replaces every selection in one request and opens a clean editable table', async () => {
  const { resolve, metadata } = mount()
  const button = await screen.findByRole('button', { name: 'Не метчить, начать с нуля' })
  fireEvent.change(screen.getByRole('combobox', { name: 'Сопоставление задачи 1а' }), {
    target: { value: 'manual_match:5' },
  })
  fireEvent.change(screen.getByRole('combobox', { name: 'Сопоставление задачи 1б' }), {
    target: { value: 'omit' },
  })
  const draftKey = problemReviewDraftStorageKey(
    'fresh',
    'metadata',
    review.groupLessonId,
    review.revisionId,
  )
  localStorage.setItem(draftKey, 'old metadata')
  let finish!: (value: { etag: typeof etag; data: ProblemMatchReview }) => void
  resolve.mockImplementation(
    () =>
      new Promise((accept) => {
        finish = accept
      }),
  )
  fireEvent.click(button)
  expect(button.hasAttribute('disabled')).toBe(true)
  expect(metadata).not.toHaveBeenCalled()
  expect(resolve).toHaveBeenCalledExactlyOnceWith({
    revisionId: review.revisionId,
    etag,
    startFresh: true,
    matches: review.items.map((item) => ({
      sourceOrdinal: item.sourceOrdinal,
      sourceItem: item.sourceItem,
      decision: 'insert_new',
      problemId: null,
    })),
  })
  finish({
    etag,
    data: {
      ...review,
      items: review.items.map((item, index) => ({
        ...item,
        match: { decision: 'insert_new', problemId: 101 + index },
      })),
    },
  })
  await screen.findByRole('grid')
  expect(localStorage.getItem(draftKey)).toBeNull()
  expect(screen.queryByText('42')).toBeNull()
  expect(screen.getByRole('button', { name: 'Сохранить метаданные' })).toBeTruthy()
})

it('keeps the matching screen and draft when saving fails, allowing retry', async () => {
  const { resolve, metadata } = mount()
  const button = await screen.findByRole('button', { name: 'Не метчить, начать с нуля' })
  fireEvent.change(screen.getByRole('combobox', { name: 'Сопоставление задачи 1а' }), {
    target: { value: 'manual_match:5' },
  })
  resolve.mockRejectedValue(new Error('Failed to save'))
  fireEvent.click(button)
  await screen.findByRole('alert')
  await waitFor(() => expect(button.hasAttribute('disabled')).toBe(false))
  expect(
    screen.getByRole<HTMLSelectElement>('combobox', { name: 'Сопоставление задачи 1а' }).value,
  ).toBe('manual_match:5')
  expect(metadata).not.toHaveBeenCalled()
})

it('shows the refreshed matching state after a conflict and requires an explicit retry', async () => {
  const { resolve, metadata } = mount()
  const button = await screen.findByRole('button', { name: 'Не метчить, начать с нуля' })
  resolve.mockRejectedValue(
    new ApiResponseError(409, {
      error: { code: 'version_conflict', message: 'Changed', requestId: 'fresh-conflict' },
    }),
  )
  fireEvent.click(button)
  await screen.findByRole('alert')
  await waitFor(() => expect(button.hasAttribute('disabled')).toBe(false))
  expect(resolve).toHaveBeenCalledTimes(1)
  expect(metadata).not.toHaveBeenCalled()
})
