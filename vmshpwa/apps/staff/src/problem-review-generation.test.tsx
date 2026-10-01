import { cleanup, fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { createContentApiClient } from '@vmsh/content'
import {
  contentEtagSchema,
  parseRuntimeConfigForAudience,
  type ProblemMetadataGrid,
} from '@vmsh/contracts'
import runtimeFixture from '@vmsh/contracts/fixtures/runtime/staff.v1.json'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

import { ProblemReviewWorkflow } from './problem-review-workflow'

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

const etag = contentEtagSchema.parse('"review-types:v1"')
const grid: ProblemMetadataGrid = {
  revisionId: 'revision-types',
  groupLessonId: 'lesson-types',
  version: 1,
  etag,
  requestId: 'test-types',
  canGenerateMetadata: true,
  metadataGenerationRequiresConfirmation: false,
  testRechecks: [],
  rows: ['а', 'б'].map((item, index) => ({
    problemId: 101 + index,
    sourceOrdinal: 1,
    sourceItem: item,
    displayNumber: `1${item}`,
    title: `Task ${item}`,
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
}

function mount() {
  const client = createContentApiClient(
    parseRuntimeConfigForAudience('staff', runtimeFixture.response),
  )
  vi.spyOn(client, 'problemMatches').mockResolvedValue({
    etag,
    data: {
      revisionId: grid.revisionId,
      groupLessonId: grid.groupLessonId,
      version: 1,
      etag,
      requestId: 'test-types',
      candidates: [],
      items: grid.rows.map((row) => ({
        sourceOrdinal: row.sourceOrdinal,
        sourceItem: row.sourceItem,
        displayNumber: row.displayNumber,
        sourceTitle: null,
        suggestedProblemId: row.problemId,
        match: { decision: 'auto_position', problemId: row.problemId },
      })),
    },
  })
  vi.spyOn(client, 'metadataGrid').mockResolvedValue({ etag, data: grid })
  const generate = vi.spyOn(client, 'generateMetadata').mockImplementation((input) =>
    Promise.resolve({
      revisionId: grid.revisionId,
      groupLessonId: grid.groupLessonId,
      requestId: 'generated',
      warnings: [],
      rows: grid.rows.map((row) => ({
        ...row,
        title: 'Generated',
        problemType:
          input.problemTypes?.find((item) => item.problemId === row.problemId)?.problemType ?? 2,
      })),
    }),
  )
  const save = vi.spyOn(client, 'saveMetadataGrid')
  render(
    <ProblemReviewWorkflow
      client={client}
      draftNamespace="test-types"
      groupLessonId={grid.groupLessonId}
      revisionId={grid.revisionId}
      kind="condition"
      onReadyChange={() => undefined}
    />,
  )
  return { generate, save }
}

async function setOralType(row: number) {
  const cell = await screen.findByRole('gridcell', { name: `Тип задачи, строка ${row}` })
  fireEvent(cell, new MouseEvent('pointerdown', { bubbles: true, button: 0 }))
  fireEvent(window, new MouseEvent('pointerup', { bubbles: true, button: 0 }))
  fireEvent.paste(screen.getByRole('grid'), { clipboardData: { getData: () => 'Устная' } })
  expect(cell.textContent).toContain('Устная')
}

it('uses live unsaved subpart types even without localStorage, including edits after generation', async () => {
  const { generate, save } = mount()
  await screen.findByRole('button', { name: 'Сгенерировать с типами из таблицы' })
  vi.spyOn(localStorage, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(globalThis, 'confirm').mockReturnValue(true)
  await setOralType(2)
  fireEvent.click(screen.getByRole('button', { name: 'Сгенерировать с типами из таблицы' }))
  await screen.findByText('Черновик metadata обновлён')
  expect(generate).toHaveBeenLastCalledWith(
    expect.objectContaining({
      problemTypes: [
        { problemId: 101, problemType: 2 },
        { problemId: 102, problemType: 3 },
      ],
    }),
  )
  expect(save).not.toHaveBeenCalled()
  await setOralType(1)
  fireEvent.click(screen.getByRole('button', { name: 'Сгенерировать с типами из таблицы' }))
  await waitFor(() => expect(generate).toHaveBeenCalledTimes(2))
  expect(generate).toHaveBeenLastCalledWith(
    expect.objectContaining({
      problemTypes: [
        { problemId: 101, problemType: 3 },
        { problemId: 102, problemType: 3 },
      ],
    }),
  )
})

it('keeps the edited grid when regeneration is cancelled', async () => {
  const { generate } = mount()
  vi.spyOn(globalThis, 'confirm').mockReturnValue(false)
  await setOralType(2)
  fireEvent.click(screen.getByRole('button', { name: 'Сгенерировать с типами из таблицы' }))
  expect(generate).not.toHaveBeenCalled()
  expect(screen.getByRole('gridcell', { name: 'Тип задачи, строка 2' }).textContent).toContain(
    'Устная',
  )
})

it('keeps automatic generation available without explicit types', async () => {
  const { generate } = mount()
  fireEvent.click(await screen.findByRole('button', { name: 'Сгенерировать metadata' }))
  await screen.findByText('Черновик metadata обновлён')
  expect(generate).toHaveBeenCalledWith({
    groupLessonId: grid.groupLessonId,
    revisionId: grid.revisionId,
  })
})

it('preserves selected types and the local draft when generation fails', async () => {
  const { generate, save } = mount()
  generate.mockRejectedValueOnce(new Error('Generation unavailable'))
  vi.spyOn(globalThis, 'confirm').mockReturnValue(true)
  await setOralType(2)
  fireEvent.click(screen.getByRole('button', { name: 'Сгенерировать с типами из таблицы' }))
  await screen.findByText('Generation unavailable')
  expect(screen.getByRole('gridcell', { name: 'Тип задачи, строка 2' }).textContent).toContain(
    'Устная',
  )
  expect(
    localStorage.getItem(
      'vmshpwa:staff:content:test-types:metadata:v1:lesson-types:revision-types',
    ),
  ).toContain('"problemType":"3"')
  expect(save).not.toHaveBeenCalled()
})
