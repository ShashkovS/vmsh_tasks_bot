import type { Meta, StoryObj } from '@storybook/react-vite'

import { AppStartupScreen } from './runtime-bootstrap'

const meta = {
  title: 'Product/App startup',
  component: AppStartupScreen,
  parameters: {
    layout: 'fullscreen',
    viewport: { defaultViewport: 'mobile2' },
  },
} satisfies Meta<typeof AppStartupScreen>

export default meta
type Story = StoryObj<typeof meta>

export const RuntimeLoading: Story = {
  args: {
    state: 'loading',
    title: 'Проверяем подключение',
    description: 'Подключаем личный кабинет к серверу ВМШ 179.',
  },
}

export const RuntimeRejected: Story = {
  args: {
    state: 'error',
    title: 'Не удалось безопасно открыть кабинет',
    description:
      'Сервер не подтвердил настройки этого раздела. Проверьте подключение и повторите попытку.',
    requestId: 'fixture-runtime-error-v1',
    onRetry: () => undefined,
  },
}

export const OfflineStorageUnavailable: Story = {
  args: {
    state: 'error',
    title: 'Не удалось подготовить работу без сети',
    description:
      'Локальное хранилище сейчас недоступно. Отправка без сети не будет надёжной, поэтому кабинет не открыт.',
    onRetry: () => undefined,
  },
}
