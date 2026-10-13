import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import { Checkbox, FieldLabel, RadioGroup, RadioGroupItem, Switch } from '@vmsh/ui'

const meta = { title: 'UI/Selection', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const States: Story = {
  name: 'Состояния',
  render: () => (
    <div className="max-w-sm space-y-4">
      <div className="flex items-center gap-2">
        <Checkbox id="c-checked" defaultChecked />
        <FieldLabel htmlFor="c-checked">Проверил перед отправкой</FieldLabel>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox id="c-indeterminate" indeterminate />
        <FieldLabel htmlFor="c-indeterminate">Выполнена часть пунктов</FieldLabel>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox id="c-off" />
        <FieldLabel htmlFor="c-off">Не отмечено</FieldLabel>
      </div>
      <div className="flex items-center gap-2">
        <Checkbox id="c-disabled" disabled />
        <FieldLabel htmlFor="c-disabled">Недоступно</FieldLabel>
      </div>

      <div className="flex items-center justify-between border-t border-border pt-4">
        <FieldLabel htmlFor="s-push">Push-уведомления</FieldLabel>
        <Switch id="s-push" defaultChecked aria-label="Push-уведомления" />
      </div>
    </div>
  ),
}

/** Radio group is the SELECT_ONE test-answer input; one answer at a time. */
function AnswerChoice() {
  return (
    <fieldset className="max-w-sm space-y-2">
      <legend className="text-label font-medium text-foreground">Какое утверждение верно?</legend>
      <RadioGroup defaultValue="b" aria-label="Варианты ответа">
        {[
          ['a', 'Число делится на 3'],
          ['b', 'Число делится на 7'],
          ['c', 'Число простое'],
        ].map(([value, label]) => (
          <div className="flex items-center gap-2" key={value}>
            <RadioGroupItem id={`opt-${value}`} value={value} />
            <FieldLabel htmlFor={`opt-${value}`}>{label}</FieldLabel>
          </div>
        ))}
      </RadioGroup>
    </fieldset>
  )
}

export const SingleChoice: Story = {
  name: 'Один выбор (тестовый ответ)',
  render: () => <AnswerChoice />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const optionA = canvas.getByRole('radio', { name: 'Число делится на 3' })
    const optionB = canvas.getByRole('radio', { name: 'Число делится на 7' })

    await expect(optionB).toBeChecked()
    await userEvent.click(optionA)
    await expect(optionA).toBeChecked()
    await expect(optionB).not.toBeChecked()
  },
}

export const Density: Story = {
  name: 'Плотность',
  render: () => (
    <div className="grid max-w-2xl gap-6 sm:grid-cols-2">
      {(['student', 'staff'] as const).map((density) => (
        <div className="space-y-3" data-density={density} key={density}>
          <p className="text-label font-medium text-muted-foreground">
            {density === 'student' ? 'Школьник' : 'Учитель'}
          </p>
          <AnswerChoice />
        </div>
      ))}
    </div>
  ),
}
