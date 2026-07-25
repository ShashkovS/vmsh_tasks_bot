import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import {
  FamilyChildPage,
  FamilyChildrenPage,
  FamilyHomePage,
  FamilyLoginPage,
  FamilyNewsPage,
  FamilyNotificationsPage,
  FamilyProfilePage,
  FamilyTaskPage,
} from './pages'

/* Page evidence for dev/design-system/05-pages-and-flows.md (“Family PWA”). */
const meta = {
  title: 'Pages/Family',
  parameters: { canvasPadding: false, layout: 'fullscreen' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const CurrentLesson: Story = { render: () => <FamilyHomePage /> }
export const ChildSwitcher: Story = { render: () => <FamilyChildrenPage /> }
export const ChildActivity: Story = { render: () => <FamilyChildPage childId="vasily" /> }
export const ReadOnlyTask: Story = {
  render: () => <FamilyTaskPage taskId="41n-6" />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/нельзя отвечать за ребёнка/)).toBeInTheDocument()
    await expect(canvas.queryByRole('textbox')).not.toBeInTheDocument()
  },
}
export const News: Story = { render: () => <FamilyNewsPage /> }
export const Profile: Story = { render: () => <FamilyProfilePage /> }
export const Notifications: Story = { render: () => <FamilyNotificationsPage /> }
export const Login: Story = {
  render: () => <FamilyLoginPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const password = canvas.getByLabelText('Пароль')
    await userEvent.click(canvas.getByRole('button', { name: 'Показать пароль' }))
    await expect(password).toHaveAttribute('type', 'text')
  },
}
export const PageStates: Story = {
  render: () => (
    <div className="grid gap-5 bg-background p-4 lg:grid-cols-2">
      <FamilyHomePage state="loading" />
      <FamilyHomePage state="empty" />
      <FamilyHomePage state="error" />
      <FamilyHomePage state="offline" />
    </div>
  ),
}
