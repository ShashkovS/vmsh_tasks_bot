import type { Meta, StoryObj } from '@storybook/react-vite'
import { expect, userEvent, within } from 'storybook/test'

import {
  StudentLoginPage,
  StudentNewsPage,
  StudentNotificationsPage,
  StudentProfilePage,
  StudentProgressPage,
  StudentSubmissionPage,
  StudentTaskPage,
  StudentTasksPage,
  StudentTodayPage,
} from './pages'

/*
 * Phase-5 page evidence for dev/design-system/05-pages-and-flows.md and the
 * deterministic page-state matrix required by 06-storybook-and-testing.md.
 */
const meta = {
  title: 'Pages/Student',
  parameters: { canvasPadding: false, layout: 'fullscreen' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const Today: Story = { render: () => <StudentTodayPage /> }
export const Tasks: Story = { render: () => <StudentTasksPage /> }
export const TestTask: Story = {
  render: () => <StudentTaskPage kind="test" taskId="41n-1" />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const answer = canvas.getByLabelText('Число способов')
    await userEvent.type(answer, '12x')
    await expect(canvas.queryByRole('alert')).not.toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить' }))
    await expect(canvas.getByRole('alert')).toHaveTextContent('Ответ не соответствует формату')
  },
}
export const WrittenTask: Story = {
  render: () => <StudentTaskPage kind="written" taskId="41n-6" />,
}
export const OralTask: Story = { render: () => <StudentTaskPage kind="oral" taskId="41n-8" /> }
export const ResultAndThread: Story = {
  render: () => <StudentSubmissionPage submissionId="sub-179" />,
}
export const News: Story = { render: () => <StudentNewsPage /> }
export const Progress: Story = { render: () => <StudentProgressPage /> }
export const Profile: Story = { render: () => <StudentProfilePage /> }
export const Notifications: Story = { render: () => <StudentNotificationsPage /> }

export const Login: Story = {
  render: () => <StudentLoginPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const password = canvas.getByLabelText('Токен Telegram-бота')
    await expect(password).toHaveAttribute('type', 'password')
    await userEvent.click(canvas.getByRole('button', { name: 'Показать пароль' }))
    await expect(password).toHaveAttribute('type', 'text')
  },
}

export const LoginErrors: Story = {
  render: () => <StudentLoginPage loginState="rate-limited" />,
}

export const PageStates: Story = {
  render: () => (
    <div className="grid gap-6 bg-background p-4 lg:grid-cols-2">
      <StudentTodayPage state="loading" />
      <StudentTodayPage state="empty" />
      <StudentTodayPage state="error" />
      <StudentTodayPage state="offline" />
    </div>
  ),
}
