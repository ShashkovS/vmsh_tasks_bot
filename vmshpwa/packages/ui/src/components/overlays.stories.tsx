import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, screen, userEvent, waitFor, within } from 'storybook/test'

import {
  Button,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Popover,
  PopoverContent,
  PopoverDescription,
  PopoverTitle,
  PopoverTrigger,
  toast,
  toastManager,
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@vmsh/ui'

const meta = { title: 'UI/Overlays', parameters: { layout: 'padded' } } satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

/** Destructive confirm: focus enters the dialog, Escape closes and restores
 * focus to the trigger; confirming performs the action. */
function DeleteDraftDialog() {
  const [deleted, setDeleted] = useState(false)
  return (
    <div className="space-y-3">
      <Dialog>
        <DialogTrigger render={<Button variant="destructive">Удалить черновик</Button>} />
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Удалить черновик?</DialogTitle>
            <DialogDescription>
              Несохранённый текст решения будет потерян. Это действие необратимо.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline">Отмена</Button>} />
            <DialogClose
              render={
                <Button variant="destructive" onClick={() => setDeleted(true)}>
                  Удалить
                </Button>
              }
            />
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <p className="text-small text-muted-foreground" role="status">
        {deleted ? 'Черновик удалён.' : 'Черновик сохранён.'}
      </p>
    </div>
  )
}

export const ConfirmDialog: Story = {
  name: 'Диалог подтверждения',
  render: () => <DeleteDraftDialog />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const trigger = canvas.getByRole('button', { name: 'Удалить черновик' })

    // Открытие: диалог появляется, заголовок в нём.
    await userEvent.click(trigger)
    const dialog = await screen.findByRole('dialog')
    await within(dialog).findByText('Удалить черновик?')

    // Escape закрывает и возвращает фокус на триггер.
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await waitFor(() => expect(trigger).toHaveFocus())

    // Подтверждение выполняет действие.
    await userEvent.click(trigger)
    await userEvent.click(await screen.findByRole('button', { name: 'Удалить' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    await expect(canvas.getByRole('status')).toHaveTextContent('Черновик удалён.')
  },
}

/** Keyboard-operable menu: open, arrow to first item, Enter activates. */
function TaskActionsMenu() {
  const [action, setAction] = useState<string | null>(null)
  return (
    <div className="space-y-3">
      <DropdownMenu>
        <DropdownMenuTrigger render={<Button variant="outline">Действия</Button>} />
        <DropdownMenuContent>
          <DropdownMenuGroup>
            <DropdownMenuLabel>Задача 21н.6</DropdownMenuLabel>
            <DropdownMenuItem onClick={() => setAction('Открыть')}>Открыть</DropdownMenuItem>
            <DropdownMenuItem onClick={() => setAction('Скопировать номер')}>
              Скопировать номер
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuItem onClick={() => setAction('Задать вопрос')}>
            Задать вопрос
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <p className="text-small text-muted-foreground" role="status">
        {action ? `Выбрано: ${action}` : 'Ничего не выбрано'}
      </p>
    </div>
  )
}

export const Menu: Story = {
  name: 'Меню (клавиатура)',
  render: () => <TaskActionsMenu />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Действия' }))
    await screen.findByRole('menu')

    await userEvent.keyboard('{ArrowDown}')
    await userEvent.keyboard('{Enter}')
    await waitFor(() => expect(screen.queryByRole('menu')).toBeNull())
    await expect(canvas.getByRole('status')).toHaveTextContent('Выбрано: Открыть')
  },
}

function ToastDemo() {
  return (
    <div className="flex flex-wrap gap-2">
      <Button
        onClick={() => toast.success('Черновик сохранён', 'Можно продолжить с другого устройства.')}
      >
        Сохранить черновик
      </Button>
      <Button
        variant="outline"
        onClick={() =>
          toastManager.add({
            title: 'Отправка в очереди',
            type: 'info',
            actionProps: {
              children: 'Отменить',
              onClick: () => toast.success('Отправка отменена'),
            },
          })
        }
      >
        Отправить с отменой
      </Button>
    </div>
  )
}

export const ToastNotification: Story = {
  name: 'Тост с действием',
  render: () => <ToastDemo />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)

    // Base UI дублирует заголовок тоста в aria-live-регион — ищем все совпадения.
    await userEvent.click(canvas.getByRole('button', { name: 'Сохранить черновик' }))
    await screen.findAllByText('Черновик сохранён')

    await userEvent.click(canvas.getByRole('button', { name: 'Отправить с отменой' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Отменить' }))
    await screen.findAllByText('Отправка отменена')
  },
}

export const Gallery: Story = {
  name: 'Все оверлеи',
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Popover>
        <PopoverTrigger render={<Button variant="outline">Popover</Button>} />
        <PopoverContent>
          <PopoverTitle>Срок сдачи</PopoverTitle>
          <PopoverDescription>
            Письменные решения принимаем до воскресенья, 13:00.
          </PopoverDescription>
        </PopoverContent>
      </Popover>

      <Tooltip>
        <TooltipTrigger render={<Button variant="ghost">Подсказка при наведении</Button>} />
        <TooltipContent>Появится после субботы, 12:00</TooltipContent>
      </Tooltip>

      <DeleteDraftDialog />
      <TaskActionsMenu />
      <ToastDemo />
    </div>
  ),
}
