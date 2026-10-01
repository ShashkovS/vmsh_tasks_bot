import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, afterAll, expect, it, vi } from 'vitest'
import { renderWithI18n } from '@vmsh/test-utils/i18n'
import fixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import { problemReleaseResponseSchema, webContentDocumentSchema } from '@vmsh/contracts'
import { ProblemReleasePreview } from './staff-problem-release-preview'

beforeAll(() => vi.stubGlobal('PointerEvent', MouseEvent))
afterAll(() => vi.unstubAllGlobals())
afterEach(cleanup)

const document = webContentDocumentSchema.parse(fixture.document)
const initial = problemReleaseResponseSchema.parse({
  groupLessonId: 'gl-1',
  conditionRevisionId: document.revisionId,
  version: 1,
  etag: '"gl-1-release:v1"',
  editable: true,
  problems: document.problems.map((problem) => ({ sourceOrdinal: problem.ordinal, isOpen: true })),
})

it('saves all switches atomically and keeps hidden statements visible to Staff', async () => {
  const user = userEvent.setup()
  const client = {
    get: vi.fn().mockResolvedValue(initial),
    save: vi.fn().mockImplementation((_id, _etag, input) =>
      Promise.resolve({
        ...initial,
        version: 2,
        etag: '"gl-1-release:v2"',
        problems: input.changes,
      }),
    ),
  }
  renderWithI18n(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ProblemReleasePreview
        client={client}
        groupLessonId="gl-1"
        revisionId={document.revisionId}
        document={document}
        condition={undefined}
        submissionClosed={false}
      />
    </QueryClientProvider>,
  )
  await screen.findAllByRole('switch', { name: /Открыта ученикам: задача/ })
  await user.click(screen.getByRole('button', { name: 'Закрыть все' }))
  await waitFor(() =>
    expect(client.save).toHaveBeenCalledWith('gl-1', initial.etag, {
      conditionRevisionId: document.revisionId,
      changes: initial.problems.map((problem) => ({ ...problem, isOpen: false })),
    }),
  )
  await waitFor(() =>
    expect(
      screen.getAllByRole('switch').every((item) => item.getAttribute('aria-checked') === 'false'),
    ).toBe(true),
  )
  expect(screen.getByText(document.problems[0]!.title!, { exact: false })).toBeTruthy()
}, 15_000)

it('retains confirmed On after a failed toggle and refetches the authority', async () => {
  const user = userEvent.setup()
  const client = {
    get: vi.fn().mockResolvedValue(initial),
    save: vi.fn().mockRejectedValue(new Error('conflict')),
  }
  renderWithI18n(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ProblemReleasePreview
        client={client}
        groupLessonId="gl-1"
        revisionId={document.revisionId}
        document={document}
        condition={undefined}
        submissionClosed={false}
      />
    </QueryClientProvider>,
  )
  const switches = await screen.findAllByRole('switch')
  await user.click(switches[0]!)
  await screen.findByRole('alert')
  await waitFor(() => expect(client.get).toHaveBeenCalledTimes(2))
  expect(switches[0]!.getAttribute('aria-checked')).toBe('true')
}, 15_000)
