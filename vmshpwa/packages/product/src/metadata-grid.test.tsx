import { cleanup, fireEvent, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MetadataGrid } from './metadata-grid'
import { renderWithI18n as render } from '@vmsh/test-utils/i18n'

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

  it('edits a compact cell in the dialog and preserves a TSV paste as one undoable change', () => {
    const onRowsChange = vi.fn()
    render(
      <MetadataGrid
        columns={[
          { id: 'title', header: 'Название', width: 180 },
          {
            id: 'kind',
            header: 'Тип',
            editor: 'select',
            options: [{ value: '1', label: 'Тестовая' }],
          },
        ]}
        initialRows={[{ title: 'Задача 1', kind: '1' }]}
        onRowsChange={onRowsChange}
      />,
    )

    fireEvent.doubleClick(screen.getByRole('gridcell', { name: 'Название, строка 1' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByRole('textbox', { name: 'Название' }), {
      target: { value: 'Новое название' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Применить' }))
    expect(onRowsChange).toHaveBeenLastCalledWith([{ title: 'Новое название', kind: '1' }])

    fireEvent.keyDown(screen.getByRole('gridcell', { name: 'Название, строка 1' }), {
      key: 'z',
      ctrlKey: true,
    })
    expect(onRowsChange).toHaveBeenLastCalledWith([{ title: 'Задача 1', kind: '1' }])
  })

  it('accepts a full visible table with headers from the clipboard', () => {
    const onRowsChange = vi.fn()
    render(
      <MetadataGrid
        columns={[
          { id: 'title', header: 'Название' },
          {
            id: 'kind',
            header: 'Тип',
            editor: 'select',
            options: [{ value: '1', label: 'Тестовая' }],
          },
        ]}
        initialRows={[{ title: '', kind: '' }]}
        onRowsChange={onRowsChange}
      />,
    )

    fireEvent.paste(screen.getByRole('grid'), {
      clipboardData: { getData: () => 'Название\tТип\nПлощадь\tТестовая' },
    })
    expect(onRowsChange).toHaveBeenLastCalledWith([{ title: 'Площадь', kind: '1' }])
  })

  it('shows the label of a select value while retaining its stable code', () => {
    render(
      <MetadataGrid
        columns={[
          {
            id: 'kind',
            header: 'Тип задачи',
            editor: 'select',
            options: [{ value: '1', label: 'Тестовая' }],
          },
        ]}
        initialRows={[{ kind: '1' }]}
      />,
    )

    expect(screen.getByRole('gridcell', { name: 'Тип задачи, строка 1' }).textContent).toContain(
      'Тестовая',
    )
  })

  it('keeps the edit history when the table is opened full-screen', () => {
    const onRowsChange = vi.fn()
    render(
      <MetadataGrid
        columns={[{ id: 'title', header: 'Название' }]}
        initialRows={[{ title: 'До' }]}
        onRowsChange={onRowsChange}
      />,
    )

    fireEvent.paste(screen.getByRole('grid'), {
      clipboardData: { getData: () => 'После' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'На весь экран' }))
    const dialog = screen.getByRole('dialog')
    expect(
      within(dialog).getByRole('gridcell', { name: 'Название, строка 1' }).textContent,
    ).toContain('После')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Отменить' }))
    expect(onRowsChange).toHaveBeenLastCalledWith([{ title: 'До' }])
  })
})
