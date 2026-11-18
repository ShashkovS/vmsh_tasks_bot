import { render, screen, cleanup } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import type { WebContentProblem } from '@vmsh/contracts'
import { studentProblemListResponseSchema } from '@vmsh/contracts'
import fixture from '../../../packages/contracts/fixtures/courses/student-problems.v1.json'
import { studentWorksheetBindings } from './student-worksheet-bindings'

afterEach(cleanup)
const base = studentProblemListResponseSchema.parse(fixture.response).problems[0]!
const parts = ['а', 'б'].map((label) => ({
  ...base,
  sourceOrdinal: 4,
  displayNumber: `4${label}`,
  problemId: `part-${label}`,
}))
const documentProblem = {
  ordinal: 4,
  blocks: [{ type: 'subpart', label: 'а', blocks: [] }],
} as unknown as WebContentProblem

describe('shared worksheet task placement', () => {
  it('binds each subpart to its own answer and status without a duplicate parent form', () => {
    const bindings = studentWorksheetBindings(
      parts,
      (problem) => <input aria-label={problem.problemId} />,
      (problem) => <span>{problem.displayNumber}</span>,
    )
    render(
      <>
        {bindings.renderProblemActions(documentProblem)}
        {bindings.renderAfterProblem(documentProblem)}
        {['а', 'б'].map((label) => (
          <section key={label}>
            {bindings.renderSubpartActions(documentProblem, label)}
            {bindings.renderAfterSubpart(documentProblem, label)}
          </section>
        ))}
      </>,
    )
    expect(screen.getAllByRole('textbox')).toHaveLength(2)
    expect(screen.getByRole('textbox', { name: 'part-а' })).toBeTruthy()
    expect(screen.getByRole('textbox', { name: 'part-б' })).toBeTruthy()
    expect(screen.getByText('4а')).toBeTruthy()
    expect(screen.getByText('4б')).toBeTruthy()
    expect(bindings.renderAfterSubpart(documentProblem, 'в')).toBeNull()
    expect(bindings.renderAfterSubpart({ ...documentProblem, ordinal: 5 }, 'а')).toBeNull()
  })

  it('keeps a single form and status for a task without subparts', () => {
    const bindings = studentWorksheetBindings(
      [parts[0]!],
      (problem) => <input aria-label={problem.problemId} />,
      (problem) => <span>{problem.displayNumber}</span>,
    )
    const plain = { ...documentProblem, blocks: [] }
    render(
      <>
        {bindings.renderProblemActions(plain)}
        {bindings.renderAfterProblem(plain)}
      </>,
    )
    expect(screen.getAllByRole('textbox')).toHaveLength(1)
    expect(screen.getByText('4а')).toBeTruthy()
  })
})
