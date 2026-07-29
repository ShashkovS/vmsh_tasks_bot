import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { CourseScheduleEditor } from './course-schedule-editor'

const values = new Map<string, string>()
const storage: Storage = {
  get length() {
    return values.size
  },
  clear: () => values.clear(),
  getItem: (key) => values.get(key) ?? null,
  key: (index) => [...values.keys()][index] ?? null,
  removeItem: (key) => values.delete(key),
  setItem: (key, value) => values.set(key, value),
}

describe('course schedule editor', () => {
  beforeAll(() => Object.defineProperty(globalThis, 'localStorage', { value: storage }))
  beforeEach(() => storage.clear())
  afterEach(() => cleanup())

  it('restores an unsent time after remount and submits the visible value', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    const props = {
      field: 'opens_at' as const,
      open: true,
      saving: false,
      storageKey: 'staff:schedule:course:opens',
      onOpenChange: vi.fn(),
      onSave,
    }
    const rendered = render(<CourseScheduleEditor {...props} />)
    await user.clear(screen.getByLabelText('Время'))
    await user.type(screen.getByLabelText('Время'), '18:15')
    rendered.unmount()

    render(<CourseScheduleEditor {...props} />)
    expect(screen.getByLabelText<HTMLInputElement>('Время').value).toBe('18:15')
    await user.click(screen.getByRole('button', { name: 'Показать изменения' }))
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ field: 'opens_at', localTime: '18:15' }),
    )
  })

  it('sends no time fields when a group inherits the course rule', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <CourseScheduleEditor
        field="hint_scheduled_at"
        mode="override"
        onOpenChange={vi.fn()}
        onSave={onSave}
        open
        saving={false}
        storageKey="staff:schedule:group:hint"
      />,
    )
    await user.selectOptions(screen.getByLabelText('Режим'), 'inherit')
    await user.click(screen.getByRole('button', { name: 'Показать изменения' }))
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        mode: 'inherit',
        dayOffset: null,
        localTime: null,
        timezone: null,
      }),
    )
  })
})
