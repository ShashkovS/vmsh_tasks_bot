import type { Meta, StoryObj } from '@storybook/react-vite'
import { useEffect, useRef } from 'react'
import { expect } from 'storybook/test'
import type { ServiceAvailability } from '@vmsh/contracts'
import { useLocale } from '@vmsh/i18n'
import { renderBrandingWaiting } from './startup'

function BrandingWaitingPreview({ state }: { state: ServiceAvailability }) {
  const root = useRef<HTMLDivElement>(null)
  const { locale } = useLocale()
  useEffect(() => {
    if (root.current) renderBrandingWaiting(root.current, state)
  }, [state, locale])
  return <div ref={root} />
}
const meta = {
  title: 'Branding/Startup recovery',
  component: BrandingWaitingPreview,
  args: { state: { state: 'updating', since: 1, prolonged: false } },
} satisfies Meta<typeof BrandingWaitingPreview>
export default meta
type Story = StoryObj<typeof meta>
export const Updating: Story = {
  play: async ({ canvas }) => {
    await expect(canvas.getByRole('heading', { name: 'Обновляем сервис' })).toBeInTheDocument()
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
  },
}
export const Reconnecting: Story = {
  args: { state: { state: 'reconnecting', since: 1, prolonged: false } },
}
export const Prolonged: Story = {
  args: { state: { state: 'updating', since: 1, prolonged: true } },
  play: async ({ canvas }) => {
    await expect(canvas.getByRole('status')).toHaveTextContent('Мы продолжаем подключаться.')
  },
}
