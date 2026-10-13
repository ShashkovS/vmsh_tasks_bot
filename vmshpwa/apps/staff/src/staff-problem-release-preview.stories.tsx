import type { Meta, StoryObj } from '@storybook/react-vite'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'
import fixture from '@vmsh/contracts/fixtures/content/web-document.v1.json'
import { webContentDocumentSchema, type ProblemReleaseResponse } from '@vmsh/contracts'
import { ProblemReleasePreview } from './staff-problem-release-preview'

const document = webContentDocumentSchema.parse(fixture.document)
for (const problem of document.problems) {
  for (const block of problem.blocks) {
    if (block.type === 'figure' && block.asset.status === 'available')
      block.asset.src = '/content/geometry.svg'
  }
}

function ReleaseStory({ isOpen = true, editable = true }) {
  const [queryClient] = useState(() => new QueryClient())
  const [client] = useState(() => {
    let snapshot: ProblemReleaseResponse = {
      groupLessonId: 'gl-1',
      conditionRevisionId: document.revisionId,
      version: 1,
      etag: '"gl-1-release:v1"',
      editable,
      problems: document.problems.map((problem) => ({ sourceOrdinal: problem.ordinal, isOpen })),
    }
    return {
      get: () => Promise.resolve(snapshot),
      save: (
        _id: string,
        _etag: string,
        input: { changes: ProblemReleaseResponse['problems'] },
      ) => {
        snapshot = {
          ...snapshot,
          version: snapshot.version + 1,
          etag: `"gl-1-release:v${snapshot.version + 1}"`,
          problems: snapshot.problems.map(
            (problem) =>
              input.changes.find((change) => change.sourceOrdinal === problem.sourceOrdinal) ??
              problem,
          ),
        }
        return Promise.resolve(snapshot)
      },
    }
  })
  return (
    <QueryClientProvider client={queryClient}>
      <ProblemReleasePreview
        client={client}
        groupLessonId="gl-1"
        revisionId={document.revisionId}
        document={document}
        condition={undefined}
        submissionClosed={false}
      />
    </QueryClientProvider>
  )
}

const meta = { title: 'Pages/Staff/Task release', component: ReleaseStory } satisfies Meta<
  typeof ReleaseStory
>
export default meta
type Story = StoryObj<typeof meta>
export const AllOpen: Story = {
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await canvas.findAllByRole('switch')
    await userEvent.click(canvas.getByRole('button', { name: 'Закрыть все' }))
    for (const control of canvas.getAllByRole('switch')) await expect(control).not.toBeChecked()
    await userEvent.click(canvas.getByRole('button', { name: 'Открыть все' }))
    for (const control of canvas.getAllByRole('switch')) await expect(control).toBeChecked()
  },
}
export const AllClosed: Story = { args: { isOpen: false } }
export const RevisionPreview: Story = { args: { editable: false } }
