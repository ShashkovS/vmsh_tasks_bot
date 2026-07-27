import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import {
  BroadcastComposerPage,
  ReviewQueuePage,
  ReviewWorkspacePage,
  StaffClassroomsPage,
  StaffCoursesPage,
  StaffGenericPage,
  StaffHomePage,
  StaffLessonDetailPage,
  StaffLessonsPage,
  StaffLoginPage,
  type StaffLoginState,
} from './pages'

/* Page evidence for dev/design-system/05-pages-and-flows.md (“Staff SPA”). */
const meta = {
  title: 'Pages/Staff',
  parameters: { canvasPadding: false, layout: 'fullscreen' },
  globals: { density: 'staff' },
} satisfies Meta
export default meta
type Story = StoryObj<typeof meta>

export const WeeklyDashboard: Story = { render: () => <StaffHomePage /> }
export const ReviewQueue: Story = { render: () => <ReviewQueuePage /> }
export const ReviewWorkspace: Story = {
  render: () => <ReviewWorkspacePage submissionId="sub-179" />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getAllByRole('button', { name: /Зачтено/ })[0]!)
    await expect(canvas.getByRole('button', { name: 'Отправить вердикт' })).toBeEnabled()
  },
}
export const LessonsAndPublication: Story = { render: () => <StaffLessonsPage /> }
export const CourseAndGroupAdministration: Story = {
  name: 'Курсы, группы и независимые настройки',
  render: () => <StaffCoursesPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getAllByText('Курсы и группы')).toHaveLength(2)
    await expect(canvas.getByText(/снимок шаблона v4/)).toBeInTheDocument()
    await expect(canvas.getByText('@vmsh_math_5_7')).toBeInTheDocument()
  },
}
export const LessonImport: Story = { render: () => <StaffLessonDetailPage lessonId="41" /> }
export const Classrooms: Story = {
  render: () => <StaffClassroomsPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('tab', { name: 'Школьники' }))
    await expect(canvas.getByText('Григорий Яшин')).toBeInTheDocument()
    await expect(canvas.getByText('сила 8.1')).toBeInTheDocument()
  },
}
export const MultiCourseClassroomEvent: Story = {
  name: 'Очное событие · несколько курсов',
  render: () => <StaffClassroomsPage />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Очное воскресенье')).toBeInTheDocument()
    await userEvent.click(
      canvas.getByRole('checkbox', { name: 'Включить Физика: эксперимент, Вводная' }),
    )
    await expect(canvas.getByRole('status')).toHaveTextContent('13 аудиторий и 173 назначения')
  },
}
export const BroadcastPhaseTwo: Story = { render: () => <BroadcastComposerPage /> }
export const TeacherForbidden: Story = {
  render: () => <StaffGenericPage description="Только admin." forbidden title="Аудит" />,
}
export const Login: Story = { render: () => <StaffLoginPage /> }

const staffLoginStates: Array<{ value: StaffLoginState; label: string }> = [
  { value: 'invalid', label: 'Неверные данные' },
  { value: 'rate-limited', label: 'Слишком много попыток' },
  { value: 'account-unavailable', label: 'Аккаунт недоступен' },
  { value: 'network', label: 'Нет связи' },
  { value: 'error', label: 'Небезопасный ответ' },
  { value: 'pending', label: 'Отправка' },
]

function StaffLoginStateMatrix() {
  const [loginState, setLoginState] = useState<StaffLoginState>('invalid')
  return (
    <div className="relative">
      <label
        className="absolute top-3 right-3 z-10 grid gap-1 text-caption"
        htmlFor="staff-login-state"
      >
        Состояние формы
        <select
          className="rounded-md border border-border bg-surface px-2 py-1 text-small text-foreground"
          id="staff-login-state"
          onChange={(event) => setLoginState(event.target.value as StaffLoginState)}
          value={loginState}
        >
          {staffLoginStates.map((state) => (
            <option key={state.value} value={state.value}>
              {state.label}
            </option>
          ))}
        </select>
      </label>
      <StaffLoginPage loginState={loginState} />
    </div>
  )
}

export const LoginStateMatrix: Story = {
  name: 'Вход · состояния ответа',
  render: () => <StaffLoginStateMatrix />,
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
      <StaffHomePage state="loading" />
      <StaffHomePage state="empty" />
      <StaffHomePage state="error" />
      <StaffHomePage state="offline" />
    </div>
  ),
}
