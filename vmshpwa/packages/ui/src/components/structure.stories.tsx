import type { Meta, StoryObj } from '@storybook/react-vite'
import { useMemo, useState } from 'react'
import { expect, userEvent, waitFor, within } from 'storybook/test'
import { WifiOff, RefreshCw, CheckCircle2 } from 'lucide-react'

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Alert,
  AlertContent,
  AlertDescription,
  AlertTitle,
  Badge,
  Progress,
  Skeleton,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@vmsh/ui'

const meta = { title: 'UI/Structure', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

/** Conscious disclosure: hint/solution stay closed until an explicit action. */
function HintSolution() {
  return (
    <Accordion className="max-w-md rounded-md border border-border">
      <AccordionItem className="px-3" value="hint">
        <AccordionTrigger>Подсказка</AccordionTrigger>
        <AccordionContent>Попробуйте начать с симметричной расстановки.</AccordionContent>
      </AccordionItem>
      <AccordionItem className="px-3" value="solution">
        <AccordionTrigger>Решение · опубликовано 1 февраля</AccordionTrigger>
        <AccordionContent>
          Поставьте ладьи по диагонали: в каждой строке и столбце ровно одна.
        </AccordionContent>
      </AccordionItem>
    </Accordion>
  )
}

export const Disclosure: Story = {
  name: 'Раскрытие подсказки/решения',
  render: () => <HintSolution />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const hint = canvas.getByRole('button', { name: 'Подсказка' })

    // Ничего не раскрыто до действия.
    await expect(hint).toHaveAttribute('aria-expanded', 'false')

    await userEvent.click(hint)
    await expect(hint).toHaveAttribute('aria-expanded', 'true')
    await waitFor(() => expect(canvas.getByText(/симметричной/)).toBeVisible())
  },
}

const queue = [
  { id: '1042', student: 'Морозова Аня', task: '21н.6 а)', level: 'Начинающие', waiting: 12 },
  { id: '1041', student: 'Гринёв Пётр', task: '21н.6 б)', level: 'Начинающие', waiting: 31 },
  { id: '1038', student: 'Ким Даша', task: '21п.4', level: 'Продолжающие', waiting: 64 },
  { id: '1035', student: 'Лебедев Слава', task: '21х.2', level: 'Эксперты', waiting: 140 },
]

function ReviewQueue({ density = 'staff' }: { density?: 'student' | 'staff' }) {
  const [asc, setAsc] = useState<boolean | null>(null)
  const rows = useMemo(() => {
    if (asc === null) return queue
    return [...queue].sort((a, b) => (asc ? a.waiting - b.waiting : b.waiting - a.waiting))
  }, [asc])

  return (
    <div data-density={density}>
      <Table>
        <TableCaption>Очередь письменной проверки · {queue.length} работы</TableCaption>
        <TableHeader>
          <TableRow>
            <TableHead>№</TableHead>
            <TableHead>Школьник</TableHead>
            <TableHead>Задача</TableHead>
            <TableHead>Уровень</TableHead>
            <TableHead aria-sort={asc === null ? 'none' : asc ? 'ascending' : 'descending'}>
              <button
                className="inline-flex items-center gap-1 font-medium"
                onClick={() => setAsc((value) => (value === null ? true : !value))}
                type="button"
              >
                Ждёт, мин {asc === null ? '' : asc ? '↑' : '↓'}
              </button>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, index) => (
            <TableRow data-state={index === 1 ? 'selected' : undefined} key={row.id}>
              <TableCell className="tabular-nums">{row.id}</TableCell>
              <TableCell>{row.student}</TableCell>
              <TableCell className="tabular-nums">{row.task}</TableCell>
              <TableCell>
                <Badge variant="neutral">{row.level}</Badge>
              </TableCell>
              <TableCell className="tabular-nums">{row.waiting}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

export const DataTable: Story = {
  name: 'Таблица (сортировка, выбор, Staff density)',
  render: () => <ReviewQueue />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const sortButton = canvas.getByRole('button', { name: /Ждёт/ })
    const header = sortButton.closest('th')

    await expect(header).toHaveAttribute('aria-sort', 'none')
    await userEvent.click(sortButton)
    await expect(header).toHaveAttribute('aria-sort', 'ascending')
  },
}

export const TableEmptyLoading: Story = {
  name: 'Таблица: пусто и загрузка',
  render: () => (
    <div className="space-y-6">
      <div>
        <p className="mb-2 text-label font-medium text-muted-foreground">Пусто</p>
        <div className="rounded-md border border-border p-8 text-center text-small text-muted-foreground">
          Очередь пуста — все работы проверены.
        </div>
      </div>
      <div>
        <p className="mb-2 text-label font-medium text-muted-foreground">Загрузка</p>
        <div className="space-y-2 rounded-md border border-border p-3" aria-hidden="true">
          {[0, 1, 2].map((row) => (
            <div className="flex gap-3" key={row}>
              <Skeleton className="h-5 w-12" />
              <Skeleton className="h-5 flex-1" />
              <Skeleton className="h-5 w-20" />
            </div>
          ))}
        </div>
      </div>
    </div>
  ),
}

export const Banners: Story = {
  name: 'Баннеры связи и прогресс',
  render: () => (
    <div className="max-w-md space-y-3">
      <Alert tone="warning">
        <WifiOff aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Вы не в сети · 1 отправка в очереди</AlertTitle>
          <AlertDescription>Отправим сразу после подключения.</AlertDescription>
        </AlertContent>
      </Alert>
      <Alert tone="info">
        <RefreshCw aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Синхронизируем…</AlertTitle>
        </AlertContent>
      </Alert>
      <Alert tone="success">
        <CheckCircle2 aria-hidden="true" />
        <AlertContent>
          <AlertTitle>Отправлено. Сервер принял в 19:47</AlertTitle>
        </AlertContent>
      </Alert>
      <div className="space-y-1">
        <p className="text-label text-muted-foreground">Сжатие фото · страница 2</p>
        <Progress aria-label="Сжатие фотографии" value={64} />
      </div>
    </div>
  ),
}
