import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import { SessionManagementView } from '@vmsh/app-shell'
import studentAuthFixture from '@vmsh/contracts/fixtures/auth/student.v1.json'
import { authSessionsResponseSchema } from '@vmsh/contracts'

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
  type StudentLoginState,
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
export const TodayMultipleCourses: Story = {
  name: 'Сейчас · несколько курсов',
  render: () => <StudentTodayPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Математика 5–7')).toBeInTheDocument()
    await expect(canvas.getByText('Физика: эксперимент')).toBeInTheDocument()
    await expect(canvas.getAllByText(/занятие/i).length).toBeGreaterThan(1)
  },
}
export const Tasks: Story = { render: () => <StudentTasksPage /> }
export const TasksCourseAndGroup: Story = {
  name: 'Задачи · курс и группа',
  render: () => <StudentTasksPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.selectOptions(canvas.getByLabelText('Курс'), 'physics-experiment')
    await expect(canvas.getByText(/Группа курса «Физика: эксперимент»/)).toBeInTheDocument()
    await expect(canvas.getByText('Вводная')).toBeInTheDocument()
  },
}
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
export const ProgressByCourse: Story = {
  name: 'Прогресс · курсы раздельно',
  render: () => <StudentProgressPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText(/задачи зачтено/)).toHaveTextContent('3 задачи зачтено')
    await userEvent.selectOptions(canvas.getByLabelText('Курс'), 'physics-experiment')
    await expect(canvas.getByText(/задача зачтена/)).toHaveTextContent('1 задача зачтена')
    await expect(canvas.queryByText(/медиана|место|процентиль/i)).not.toBeInTheDocument()
  },
}
const studentProfileSessions = authSessionsResponseSchema.parse(
  studentAuthFixture.sessionsResponse,
).sessions

export const Profile: Story = {
  render: () => (
    <StudentProfilePage
      sessionManagement={
        <SessionManagementView
          onEndSession={() => Promise.resolve()}
          state={{ status: 'ready', sessions: studentProfileSessions }}
        />
      }
    />
  ),
}
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

const studentLoginStates: Array<{ value: StudentLoginState; label: string }> = [
  { value: 'invalid', label: 'Неверные данные' },
  { value: 'rate-limited', label: 'Слишком много попыток' },
  { value: 'account-unavailable', label: 'Аккаунт недоступен' },
  { value: 'blocked', label: 'Доступ приостановлен' },
  { value: 'network', label: 'Нет связи' },
  { value: 'error', label: 'Небезопасный ответ' },
  { value: 'pending', label: 'Отправка' },
]

function StudentLoginStateMatrix() {
  const [loginState, setLoginState] = useState<StudentLoginState>('invalid')
  return (
    <div className="relative">
      <label
        className="absolute top-3 right-3 z-10 grid gap-1 text-caption"
        htmlFor="student-login-state"
      >
        Состояние формы
        <select
          className="rounded-md border border-border bg-surface px-2 py-1 text-small text-foreground"
          id="student-login-state"
          onChange={(event) => setLoginState(event.target.value as StudentLoginState)}
          value={loginState}
        >
          {studentLoginStates.map((state) => (
            <option key={state.value} value={state.value}>
              {state.label}
            </option>
          ))}
        </select>
      </label>
      <StudentLoginPage loginState={loginState} />
    </div>
  )
}

export const LoginStateMatrix: Story = {
  name: 'Вход · состояния ответа',
  render: () => <StudentLoginStateMatrix />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const state = canvas.getByLabelText('Состояние формы')
    const cases = [
      ['invalid', 'Логин или токен не подошли'],
      ['rate-limited', 'Слишком много попыток'],
      ['account-unavailable', 'учётной записи сейчас недоступен'],
      ['blocked', 'Доступ к аккаунту приостановлен'],
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
    await expect(canvas.getByLabelText('Токен Telegram-бота')).toBeDisabled()
  },
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
