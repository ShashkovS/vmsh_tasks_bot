import { describe, expect, it } from 'vitest'
import { teacherWorkInputsSchema, teacherWorkReceiptSchema } from '@vmsh/contracts'
import { acceptAliasReceipt } from './teacher-work-inputs'

const inputs = teacherWorkInputsSchema.parse({
  timezone: 'Europe/Moscow',
  shifts: [],
  events: [],
  rosters: [],
  settings: { norm_hours: 2.3, version: 0 },
  signatures: ['Принимающий Ёж', 'принимающий еж', 'Другой'].map((name, index) => ({
    name,
    normalizedName: index < 2 ? 'принимающий еж' : 'другой',
    count: 1,
    firstAt: '',
    lastAt: '',
    teacherLike: true,
    alias: null,
    examples: [],
    candidates: [],
  })),
})
const receipt = teacherWorkReceiptSchema.parse({
  version: 2,
  alias: { normalized_name: 'принимающий еж', teacher_id: 1, state: 'mapped', version: 2 },
})
describe('Accepted Zoom correspondence', () => {
  it('updates every canonical variant while preserving unrelated inputs', () => {
    const saved = acceptAliasReceipt(inputs, receipt, 'Принимающий Ёж')!
    expect(saved.signatures.map((s) => s.alias?.version ?? 0)).toEqual([2, 2, 0])
    expect(saved.signatures[2]).toBe(inputs.signatures[2])
    expect(saved.settings).toBe(inputs.settings)
    expect(inputs.signatures[0]!.alias).toBeNull()
  })
  it('does not roll back a newer edit when an older idempotent receipt arrives', () => {
    const newer = acceptAliasReceipt(
      inputs,
      { version: 3, alias: { ...receipt.alias!, version: 3, state: 'ignored', teacher_id: null } },
      inputs.signatures[0]!.name,
    )!
    expect(acceptAliasReceipt(newer, receipt, inputs.signatures[0]!.name)).toEqual(newer)
  })
})
