import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MetadataGrid } from './metadata-grid'

afterEach(() => cleanup())

describe('metadata grid confirmation', () => {
  it('allows a prefilled valid grid to be confirmed without a fake edit', () => {
    const onCommit = vi.fn()
    render(
      <MetadataGrid
        allowPristineCommit
        columns={[{ id: 'title', header: 'Название' }]}
        commitLabel="Подтвердить метаданные"
        initialRows={[{ title: 'Задача 1' }]}
        onCommit={onCommit}
        validate={() => []}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Проверить таблицу' }))
    expect(screen.getByText('Ошибок не найдено. Можно подтверждать метаданные.')).not.toBeNull()

    fireEvent.click(screen.getByRole('button', { name: 'Подтвердить метаданные' }))
    expect(onCommit).toHaveBeenCalledWith([{ title: 'Задача 1' }])
  })
})
