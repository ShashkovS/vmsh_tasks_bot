import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { SessionManagementView } from '@vmsh/app-shell'
import familyAuthFixture from '@vmsh/contracts/fixtures/auth/family.v1.json'
import preferencesFixture from '@vmsh/contracts/fixtures/notifications/preferences.v1.json'
import {
  authSessionsResponseSchema,
  notificationPreferenceListResponseSchema,
} from '@vmsh/contracts'
import { PushDeviceControls } from '@vmsh/product'

import {
  FamilyChildPage,
  FamilyChildrenPage,
  FamilyHomePage,
  FamilyLoginPage,
  FamilyNewsPage,
  FamilyProfilePage,
  FamilyTaskPage,
  type FamilyLoginState,
} from './pages'
import { FamilyCourseAchievements } from './family-children-page'
import { FamilyNotificationSettingsView } from './family-notifications-page'

/* Page evidence for dev/design-system/05-pages-and-flows.md (“Family PWA”). */
const meta = {
  title: 'Pages/Family',
  parameters: { canvasPadding: false, layout: 'fullscreen' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const CurrentLesson: Story = { render: () => <FamilyHomePage /> }
export const ActivityByCourse: Story = {
  name: 'Активность · несколько курсов',
  render: () => <FamilyHomePage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Математика 5–7')).toBeInTheDocument()
    await expect(canvas.getByText('Физика: эксперимент')).toBeInTheDocument()
    await expect(canvas.queryByText(/место|процентиль|лучше группы/i)).not.toBeInTheDocument()
  },
}
export const ChildSwitcher: Story = { render: () => <FamilyChildrenPage /> }
export const ChildActivity: Story = { render: () => <FamilyChildPage childId="vasily" /> }
export const CourseAchievements: Story = {
  name: 'Достижения курса ребёнка',
  render: () => (
    <div className="max-w-sm rounded-lg border border-border bg-surface p-4">
      <FamilyCourseAchievements
        achievements={[
          { code: 'first_submission', earnedAt: '2026-01-12T12:00:00Z' },
          { code: 'first_accepted', earnedAt: '2026-01-13T12:00:00Z' },
          { code: 'future_rule', earnedAt: '2026-01-14T12:00:00Z' },
        ]}
      />
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('region', { name: 'Достижения курса' })).toBeInTheDocument()
    await expect(canvas.getByText('Первая задача отправлена')).toBeInTheDocument()
    await expect(canvas.getByText('Первая задача зачтена')).toBeInTheDocument()
    await expect(canvas.queryByText('future_rule')).not.toBeInTheDocument()
    await expect(canvas.queryByText(/рейтинг|место|процентиль/i)).not.toBeInTheDocument()
  },
}
export const ReadOnlyTask: Story = {
  render: () => <FamilyTaskPage taskId="41n-6" />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/нельзя отвечать за ребёнка/)).toBeInTheDocument()
    await expect(canvas.queryByRole('textbox')).not.toBeInTheDocument()
  },
}
export const News: Story = { render: () => <FamilyNewsPage /> }
const familyProfileSessions = authSessionsResponseSchema.parse(
  familyAuthFixture.sessionsResponse,
).sessions

export const Profile: Story = {
  render: () => (
    <FamilyProfilePage
      sessionManagement={
        <SessionManagementView
          onEndSession={() => Promise.resolve()}
          state={{ status: 'ready', sessions: familyProfileSessions }}
        />
      }
    />
  ),
}
const notificationPreferences =
  notificationPreferenceListResponseSchema.parse(preferencesFixture).items
export const Notifications: Story = {
  render: () => (
    <FamilyNotificationSettingsView
      preferences={notificationPreferences}
      pushControls={
        <PushDeviceControls
          categories={[]}
          onDisable={() => undefined}
          onDismiss={() => undefined}
          onEnable={() => undefined}
          state="enabled"
        />
      }
    />
  ),
}
export const Login: Story = {
  render: () => <FamilyLoginPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const password = canvas.getByLabelText('Пароль')
    await userEvent.click(canvas.getByRole('button', { name: 'Показать пароль' }))
    await expect(password).toHaveAttribute('type', 'text')
  },
}

const familyLoginStates: Array<{ value: FamilyLoginState; label: string }> = [
  { value: 'invalid', label: 'Неверные данные' },
  { value: 'rate-limited', label: 'Слишком много попыток' },
  { value: 'account-unavailable', label: 'Аккаунт недоступен' },
  { value: 'network', label: 'Нет связи' },
  { value: 'error', label: 'Небезопасный ответ' },
  { value: 'pending', label: 'Отправка' },
]

function FamilyLoginStateMatrix() {
  const [loginState, setLoginState] = useState<FamilyLoginState>('invalid')
  return (
    <div className="relative">
      <label
        className="absolute top-3 right-3 z-10 grid gap-1 text-caption"
        htmlFor="family-login-state"
      >
        Состояние формы
        <select
          className="rounded-md border border-border bg-surface px-2 py-1 text-small text-foreground"
          id="family-login-state"
          onChange={(event) => setLoginState(event.target.value as FamilyLoginState)}
          value={loginState}
        >
          {familyLoginStates.map((state) => (
            <option key={state.value} value={state.value}>
              {state.label}
            </option>
          ))}
        </select>
      </label>
      <FamilyLoginPage loginState={loginState} />
    </div>
  )
}

export const LoginStateMatrix: Story = {
  name: 'Вход · состояния ответа',
  render: () => <FamilyLoginStateMatrix />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const state = canvas.getByLabelText('Состояние формы')
    const cases = [
      ['invalid', 'Логин или пароль не подошли'],
      ['rate-limited', 'Слишком много попыток'],
      ['account-unavailable', 'учётной записи сейчас недоступен'],
      ['network', 'Не удалось связаться с сервером'],
      ['error', 'Не удалось безопасно завершить вход'],
    ] as const
    for (const [value, copy] of cases) {
      await userEvent.selectOptions(state, value)
      await expect(canvas.getByRole('alert')).toHaveTextContent(copy)
    }
    await userEvent.selectOptions(state, 'pending')
    await expect(canvas.getByRole('button', { name: 'Входим…' })).toBeDisabled()
    await expect(canvas.getByLabelText('Логин')).toBeDisabled()
    await expect(canvas.getByLabelText('Пароль')).toBeDisabled()
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
