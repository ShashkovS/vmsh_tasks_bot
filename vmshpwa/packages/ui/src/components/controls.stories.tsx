import type { Meta, StoryObj } from '@storybook/react-vite'
import { useId, useState } from 'react'
import { expect, userEvent, waitFor, within } from 'storybook/test'

import {
  Badge,
  Button,
  Field,
  FieldDescription,
  FieldError,
  FieldLabel,
  Input,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
} from '@vmsh/ui'

/*
 * Controls — actions and inputs. Density is token-driven: the SAME component is
 * touch-sized (44/48px) for Student and compact (32px) for Staff via
 * `data-density`, not a one-off size prop.
 */

function ControlRow() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button size="lg">Отправить</Button>
      <Button variant="secondary">Черновик</Button>
      <Button variant="outline">Отмена</Button>
      <Button variant="ghost">Вопрос</Button>
      <Button variant="destructive">Удалить</Button>
    </div>
  )
}

function FieldRow() {
  return (
    <div className="flex flex-wrap items-end gap-2">
      <Input aria-label="Короткий ответ" className="w-40" placeholder="Например: 179" />
      <Select>
        <SelectTrigger aria-label="Уровень">
          <SelectValue placeholder="Уровень" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="n">Начинающие</SelectItem>
          <SelectItem value="p">Продолжающие</SelectItem>
          <SelectItem value="e">Эксперты</SelectItem>
        </SelectContent>
      </Select>
    </div>
  )
}

function DensityColumn({ density, title }: { density: 'student' | 'staff'; title: string }) {
  return (
    <div className="space-y-3" data-density={density}>
      <p className="text-label font-medium text-muted-foreground">{title}</p>
      <ControlRow />
      <FieldRow />
    </div>
  )
}

const meta = {
  title: 'UI/Controls',
  parameters: { layout: 'padded' },
} satisfies Meta

export default meta
type Story = StoryObj<typeof meta>

export const Density: Story = {
  name: 'Плотность (школьник ↔ учитель)',
  render: () => (
    <div className="grid max-w-3xl gap-6 sm:grid-cols-2">
      <DensityColumn density="student" title="Школьник · touch 44/48" />
      <DensityColumn density="staff" title="Учитель · compact 32" />
    </div>
  ),
}

export const States: Story = {
  name: 'Состояния',
  render: () => (
    <div className="max-w-md space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button>Активна</Button>
        <Button disabled>Недоступна</Button>
        <Button variant="outline">Вторичная</Button>
        <Button variant="destructive">Удалить</Button>
      </div>
      <Input aria-label="Обычное поле" placeholder="Обычное поле" />
      <Input aria-label="Поле с ошибкой" aria-invalid defaultValue="17я" />
      <Input aria-label="Только чтение" readOnly defaultValue="21н.6" />
      <Input aria-label="Недоступное поле" disabled placeholder="Недоступно" />
      <Textarea aria-label="Письменное решение" placeholder="Напишите решение…" />
    </div>
  ),
}

export const FileInputs: Story = {
  name: 'Выбор файла',
  render: () => (
    <div className="grid max-w-2xl gap-5 sm:grid-cols-2">
      <div className="space-y-1" data-density="staff">
        <label className="text-label font-medium" htmlFor="staff-file">
          LaTeX-файлы
        </label>
        <Input id="staff-file" multiple type="file" />
        <p className="text-caption text-muted-foreground">Компактная плотность Staff</p>
      </div>
      <div className="space-y-1" data-density="student">
        <label className="text-label font-medium" htmlFor="student-file">
          Фотографии решения
        </label>
        <Input accept="image/*" id="student-file" multiple type="file" />
        <p className="text-caption text-muted-foreground">Touch-размер Student</p>
      </div>
      <Input aria-label="Файл с ошибкой" aria-invalid type="file" />
      <Input aria-label="Недоступный выбор файла" disabled type="file" />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getByLabelText('LaTeX-файлы')
    await userEvent.upload(input, [
      new File(['condition'], '00-n.tex', { type: 'text/plain' }),
      new File(['condition'], '00-p.tex', { type: 'text/plain' }),
    ])
    await expect(input).toHaveProperty('files.length', 2)
    await expect(canvas.getByLabelText('Недоступный выбор файла')).toBeDisabled()
  },
}

export const Tones: Story = {
  name: 'Badge — семантические тона',
  render: () => (
    <div className="flex flex-wrap gap-2">
      <Badge>Тест</Badge>
      <Badge variant="outline">Черновик</Badge>
      <Badge variant="success">Зачтено</Badge>
      <Badge variant="warning">Нужна доработка</Badge>
      <Badge variant="danger">Ошибка отправки</Badge>
      <Badge variant="info">На проверке</Badge>
      <Badge variant="neutral">Не начата</Badge>
    </div>
  ),
}

/** Validation appears after submit, not on the first character; the value is
 * preserved and the error is associated with the field for screen readers. */
function AnswerForm() {
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)
  const errorId = useId()
  const hintId = useId()

  return (
    <form
      className="max-w-sm space-y-3"
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        if (value.trim() === '') {
          setError('Введите ответ перед отправкой.')
          setSent(false)
          return
        }
        setError(null)
        setSent(true)
      }}
    >
      <Field>
        <FieldLabel htmlFor="answer">
          Ответ
          <span aria-hidden="true" className="text-destructive">
            {' '}
            *
          </span>
          <span className="sr-only"> (обязательно)</span>
        </FieldLabel>
        <Input
          id="answer"
          value={value}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : hintId}
          placeholder="Например: 179"
          onChange={(event) => {
            setValue(event.target.value)
            if (error) setError(null)
          }}
        />
        {error ? (
          <FieldError id={errorId}>{error}</FieldError>
        ) : (
          <FieldDescription id={hintId}>Введите натуральное число.</FieldDescription>
        )}
      </Field>
      <Button size="lg" type="submit">
        Отправить
      </Button>
      {sent ? (
        <p className="text-small text-status-success" role="status">
          Ответ отправлен.
        </p>
      ) : null}
    </form>
  )
}

export const FormValidation: Story = {
  name: 'Валидация формы (после отправки)',
  render: () => <AnswerForm />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const input = canvas.getByLabelText(/Ответ/)
    const submit = canvas.getByRole('button', { name: 'Отправить' })

    // Ошибки нет до отправки.
    await expect(input).not.toHaveAttribute('aria-invalid', 'true')

    // Пустая отправка — ошибка появляется и связана с полем.
    await userEvent.click(submit)
    const error = await canvas.findByText('Введите ответ перед отправкой.')
    await expect(input).toHaveAttribute('aria-invalid', 'true')
    await expect(input).toHaveAttribute('aria-describedby', error.id)

    // Ввод сохраняется, ошибка снимается при исправлении.
    await userEvent.type(input, '179')
    await expect(input).toHaveValue('179')
    await expect(canvas.queryByText('Введите ответ перед отправкой.')).toBeNull()

    // Повторная отправка — успех.
    await userEvent.click(submit)
    await waitFor(() => expect(canvas.getByRole('status')).toHaveTextContent('Ответ отправлен.'))
  },
}
