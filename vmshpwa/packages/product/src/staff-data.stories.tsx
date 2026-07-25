import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { DenseDataTable, type DenseColumn } from './dense-data-table'
import { MetadataGrid, type MetadataError, type MetadataRow } from './metadata-grid'

const meta = { title: 'Product/Staff data', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

interface StudentRow {
  id: string
  name: string
  group: string
  solved: number
}

const students: StudentRow[] = [
  { id: 's1', name: 'Аня Иванова', group: 'Начинающие', solved: 12 },
  { id: 's2', name: 'Боря Петров', group: 'Начинающие', solved: 7 },
  { id: 's3', name: 'Вика Смирнова', group: 'Продолжающие', solved: 15 },
]

const columns: DenseColumn<StudentRow>[] = [
  { id: 'name', header: 'Ученик', cell: (row) => row.name, sortValue: (row) => row.name },
  { id: 'group', header: 'Группа', cell: (row) => row.group, sortValue: (row) => row.group },
  {
    id: 'solved',
    header: 'Зачтено',
    cell: (row) => <span className="font-num">{row.solved}</span>,
    sortValue: (row) => row.solved,
    align: 'end',
  },
]

export const DataTable: Story = {
  name: 'Плотная таблица с выбором',
  render: () => {
    function Harness() {
      const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())
      return (
        <div className="space-y-2">
          <DenseDataTable
            caption="Ученики группы"
            columns={columns}
            onSelectedChange={setSelected}
            rowKey={(row) => row.id}
            rows={students}
            selectable
            selected={selected}
          />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            Выбрано: {selected.size}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    await userEvent.click(canvas.getByRole('checkbox', { name: 'Выбрать все строки' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Выбрано: 3')

    await userEvent.click(canvas.getByRole('button', { name: /Зачтено/ }))
    await expect(canvas.getByRole('columnheader', { name: /Зачтено/ })).toHaveAttribute(
      'aria-sort',
      'ascending',
    )
  },
}

const metadataColumns = [
  { id: 'number', header: 'Номер' },
  { id: 'name', header: 'Название' },
  {
    id: 'taskType',
    header: 'Тип задачи',
    editor: 'select' as const,
    options: [
      { value: 'Тест', label: 'Тестовая' },
      { value: 'Письменно', label: 'Письменная' },
      { value: 'Устно', label: 'Устная' },
    ],
  },
  {
    id: 'ansType',
    header: 'Тип ответа',
    editor: 'select' as const,
    options: [
      'Цифра',
      'Натуральное',
      'Целое',
      'Отношение',
      'Действительное',
      'Дробь',
      'СмешДробь',
      'ПоследЦелых',
      'МножЦелых',
      'ДваЦелых',
      'ТриЦелых',
      'ЧетыреЦелых',
      'Многочлен',
      'ЧислоТочность',
      'Время',
      'Дата',
      'ДеньНедели',
      'ПоследДробей',
      'МультиМнож',
      'Символьное',
      'Эквивалентно',
      'Выбор',
      'Строка',
    ].map((value) => ({ value, label: value })),
  },
]

const metadataRows: MetadataRow[] = [
  {
    number: '21н.1',
    name: 'Разнообразные вагоны',
    taskType: 'Тест',
    ansType: 'Натуральное',
  },
  {
    number: '21н.6',
    name: 'Расстановка ладей',
    taskType: 'Письменно',
    ansType: '',
  },
]

function validateMetadata(rows: MetadataRow[]): MetadataError[] {
  const errors: MetadataError[] = []
  rows.forEach((row, index) => {
    if (!row.name?.trim()) errors.push({ row: index, col: 'name', message: 'Заполните название' })
    if (!row.taskType?.trim())
      errors.push({ row: index, col: 'taskType', message: 'Выберите тип задачи' })
    if (row.taskType === 'Тест' && !row.ansType?.trim())
      errors.push({ row: index, col: 'ansType', message: 'Для тестовой задачи нужен тип ответа' })
  })
  return errors
}

export const Metadata: Story = {
  name: 'Метаданные: правка, dry-run, отмена',
  render: () => {
    function Harness() {
      const [saved, setSaved] = useState(false)
      return (
        <div className="max-w-5xl space-y-2">
          <MetadataGrid
            columns={metadataColumns}
            initialRows={metadataRows}
            onCommit={() => setSaved(true)}
            validate={validateMetadata}
          />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {saved ? 'Сохранено' : 'Не сохранено'}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    const nameCell = canvas.getByLabelText('Название, строка 1')
    await userEvent.clear(nameCell)
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить (dry-run)' }))
    await expect(canvas.getByRole('alert')).toHaveTextContent('Заполните название')

    // Правка убирает ошибку.
    await userEvent.type(nameCell, 'Вагоны')
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
  },
}
