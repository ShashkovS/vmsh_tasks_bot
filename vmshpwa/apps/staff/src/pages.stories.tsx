import type { Meta, StoryObj } from '@storybook/react-vite'
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
