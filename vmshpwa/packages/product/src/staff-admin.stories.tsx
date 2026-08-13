import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { SosQueue, type SosItem } from './staff-outreach'
import {
  LatexUpload,
  MissingAssetsFlow,
  PublicationControl,
  type MissingAsset,
  type PublicationLevelRow,
} from './staff-publishing'
import type { GroupView } from './types'

const meta = { title: 'Product/Staff admin', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

const beginner: GroupView = {
  id: 'math-beginner',
  courseId: 'math-5-7',
  code: 'н',
  name: 'Начинающие',
  colorIndex: 1,
}
const continuing: GroupView = {
  id: 'math-continuing',
  courseId: 'math-5-7',
  code: 'п',
  name: 'Продолжающие',
  colorIndex: 2,
}

const pubRows: PublicationLevelRow[] = [
  { level: beginner, task: 'draft', hint: 'draft', solution: 'none' },
  {
    level: continuing,
    task: 'published',
    hint: 'published',
    solution: 'scheduled',
    scheduledAt: { solution: '1 фев, 13:00' },
  },
]

function PublicationHarness() {
  const [readout, setReadout] = useState('—')
  return (
    <div className="space-y-2">
      <PublicationControl
        onPublish={(code, artifact) => setReadout(`Опубликовано: ${code}/${artifact}`)}
        onRollback={(code, artifact) => setReadout(`Откачено: ${code}/${artifact}`)}
        onSchedule={(code, artifact, at) => setReadout(`Запланировано: ${code}/${artifact} ${at}`)}
        rows={pubRows}
      />
      <p className="text-small text-muted-foreground" data-testid="readout" role="status">
        {readout}
      </p>
    </div>
  )
}

export const Publication: Story = {
  name: 'Публикация по уровням',
  render: () => <PublicationHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(
      canvas.getByRole('button', { name: 'Опубликовать сейчас: условие, Начинающие' }),
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Опубликовано: н/task')
  },
}

export const PublicationScheduling: Story = {
  name: 'Публикация — редактор расписания',
  render: () => <PublicationHarness />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(
      canvas.getByRole('button', {
        name: 'Опубликовать по расписанию: подсказку, Начинающие',
      }),
    )

    const dateInput = canvas.getByLabelText('Когда опубликовать подсказку, Начинающие')
    const cell = dateInput.closest('td')
    const nextCell = cell?.nextElementSibling
    await expect(dateInput).toBeVisible()
    await expect(cell).not.toBeNull()
    await expect(nextCell).not.toBeNull()
    const inputRect = dateInput.getBoundingClientRect()
    await expect(inputRect.width).toBeLessThanOrEqual(192)
    await expect(inputRect.right).toBeLessThanOrEqual(nextCell!.getBoundingClientRect().left)
  },
}

export const Broadcast: Story = {
  name: 'Рассылка · граница второй фазы',
  render: () => (
    <section className="max-w-lg space-y-2 rounded-md border border-dashed border-border bg-surface-subtle p-4">
      <h2 className="text-subtitle font-semibold text-foreground">Рассылки — во второй фазе</h2>
      <p className="text-small text-muted-foreground">
        Здесь появится полноценный Markdown-редактор, выбор аудитории, предпросмотр PWA и Telegram,
        расписание и пробный прогон. Прототип первой фазы не имитирует отправку.
      </p>
    </section>
  ),
}

const sosItems: SosItem[] = [
  {
    id: 'q1',
    studentName: 'Аня',
    taskNumber: '21н.6',
    question: 'Не понимаю, как считать число расстановок для k = 1.',
    at: '12:20',
    status: 'open',
  },
  {
    id: 'q2',
    studentName: 'Боря',
    question: 'Спасибо, разобрался!',
    at: '11:05',
    status: 'answered',
  },
]

export const Sos: Story = {
  name: 'Вопросы и SOS',
  render: () => {
    function Harness() {
      const [readout, setReadout] = useState('—')
      return (
        <div className="max-w-lg space-y-2">
          <SosQueue items={sosItems} onOpen={(id) => setReadout(`Открыт вопрос ${id}`)} />
          <p className="text-small text-muted-foreground" data-testid="readout" role="status">
            {readout}
          </p>
        </div>
      )
    }
    return <Harness />
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Ответить' }))
    await expect(canvas.getByTestId('readout')).toHaveTextContent('Открыт вопрос q1')
  },
}

export const Latex: Story = {
  name: 'Загрузка LaTeX',
  render: () => (
    <div className="max-w-lg">
      <LatexUpload
        files={[
          { id: 'f1', name: '21н.tex', status: 'done' },
          { id: 'f2', name: '21п.tex', status: 'processing', progress: 55 },
          {
            id: 'f3',
            name: '21х.tex',
            status: 'error',
            diagnostics: ['Строка 42: неизвестная команда \\tikzz', 'Нет файла рисунка fig3.svg'],
          },
        ]}
        onRetry={() => undefined}
        sourcePreview={'\\begin{problem}\n  n^2 + 179 = k^2\n\\end{problem}'}
      />
    </div>
  ),
}

export const MissingAssets: Story = {
  name: 'Недостающие ресурсы',
  render: () => (
    <div className="max-w-lg">
      <MissingAssetsFlow
        assets={[
          {
            id: 'a1',
            ref: 'fig3.svg',
            sourceKind: 'figure',
            acceptedUploadKinds: ['raster', 'svg'],
            selectedUploadKind: 'svg',
            status: 'missing',
          },
          {
            id: 'a2',
            ref: 'tikz/diagram-2',
            sourceKind: 'tikz',
            acceptedUploadKinds: ['tikz'],
            selectedUploadKind: 'tikz',
            status: 'missing',
          },
        ]}
      />
    </div>
  ),
}

const assetState = (
  status: MissingAsset['status'],
  rest: Partial<MissingAsset> = {},
): MissingAsset => ({
  id: `asset-${status}`,
  ref: 'figures/rook.png',
  sourceKind: 'figure',
  acceptedUploadKinds: ['raster', 'svg'],
  selectedUploadKind: 'raster',
  status,
  ...rest,
})

const attachedAssetPreview = `data:image/svg+xml,${encodeURIComponent(`
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 180">
    <rect width="320" height="180" fill="#ffffff"/>
    <path d="M30 145 L110 35 L190 145 Z" fill="none" stroke="#176b87" stroke-width="8"/>
    <circle cx="245" cy="90" r="48" fill="none" stroke="#724e91" stroke-width="8"/>
  </svg>
`)}`

export const MissingAssetUploading: Story = {
  name: 'Недостающий ресурс · обработка',
  render: () => (
    <div className="max-w-2xl">
      <MissingAssetsFlow assets={[assetState('uploading', { fileName: 'rook.heic' })]} />
    </div>
  ),
}

export const MissingAssetError: Story = {
  name: 'Недостающий ресурс · ошибка с повтором',
  render: () => (
    <div className="max-w-2xl">
      <MissingAssetsFlow
        assets={[
          assetState('error', {
            fileName: 'rook.heic',
            errorMessage: 'Соединение прервалось. Выбранный файл сохранён — повторите загрузку.',
          }),
        ]}
      />
    </div>
  ),
}

export const MissingAssetReused: Story = {
  name: 'Недостающий ресурс · переиспользован',
  render: () => (
    <div className="max-w-2xl">
      <MissingAssetsFlow
        assets={[
          assetState('reused', {
            assetHref: attachedAssetPreview,
          }),
        ]}
      />
    </div>
  ),
}

export const MissingAssetsResolved: Story = {
  name: 'Недостающие ресурсы · разрешены',
  render: () => (
    <div className="max-w-2xl">
      <MissingAssetsFlow
        assets={[
          assetState('attached', {
            assetHref: attachedAssetPreview,
          }),
          {
            id: 'asset-tikz-attached',
            ref: 'tikz/diagram-2',
            sourceKind: 'tikz',
            acceptedUploadKinds: ['tikz'],
            selectedUploadKind: 'tikz',
            status: 'attached',
            assetHref: attachedAssetPreview,
          },
        ]}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const body = within(canvasElement.ownerDocument.body)
    await expect(
      await canvas.findByRole('button', { name: 'Увеличить ресурс figures/rook.png' }),
    ).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Увеличить ресурс figures/rook.png' }))
    const dialog = within(await body.findByRole('dialog'))
    await expect(dialog.getByRole('heading', { name: 'figures/rook.png' })).toBeInTheDocument()
    await expect(
      dialog.getByRole('img', { name: 'Прикреплённый ресурс figures/rook.png' }),
    ).toBeInTheDocument()
  },
}
