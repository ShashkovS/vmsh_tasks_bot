import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { CourseCatalogEditor, GroupCatalogEditor } from './course-catalog-editors'

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

describe('course catalog editors', () => {
  beforeAll(() => Object.defineProperty(globalThis, 'localStorage', { value: storage }))
  beforeEach(() => storage.clear())
  afterEach(() => cleanup())

  it('restores an unsent new-course draft after remount', async () => {
    const user = userEvent.setup()
    const props = {
      course: null,
      open: true,
      saving: false,
      storageKey: 'staff:course:new',
      onOpenChange: vi.fn(),
      onSave: vi.fn(),
    }
    const rendered = render(<CourseCatalogEditor {...props} />)
    await user.type(screen.getByLabelText('Название'), 'Физика 7')
    rendered.unmount()

    render(<CourseCatalogEditor {...props} />)
    expect(screen.getByLabelText<HTMLInputElement>('Название').value).toBe('Физика 7')
    expect(storage.getItem(props.storageKey)).toContain('Физика 7')
  })

  it('submits all group fields in one compact request', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn()
    render(
      <GroupCatalogEditor
        group={null}
        onOpenChange={vi.fn()}
        onSave={onSave}
        open
        saving={false}
        storageKey="staff:group:new"
      />,
    )
    await user.type(screen.getByLabelText('Короткий код'), 'dp2')
    await user.type(screen.getByLabelText('Название'), 'Динамика')
    await user.click(screen.getByLabelText('Разрешить самостоятельный переход'))
    await user.click(screen.getByRole('button', { name: 'Сохранить' }))

    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({
        shortCode: 'dp2',
        name: 'Динамика',
        allowSelfSwitch: true,
        scoreWeight: 1,
      }),
    )
  })
})
