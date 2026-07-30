import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import deliveryPreviewFixture from '@vmsh/contracts/fixtures/classrooms/delivery-preview.v1.json'
import studentDirectoryFixture from '@vmsh/contracts/fixtures/admin-enrollments/directory.v1.json'
import {
  adminStudentEnrollmentDirectoryResponseSchema,
  classroomDeliveryPreviewResponseSchema,
  problemImportPreviewResponseSchema,
  type AdminCourse,
  type StaffAccessMember,
} from '@vmsh/contracts'
import { ClassroomDeliveryPanel } from '@vmsh/product'

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
import { StudentDirectoryView } from './staff-student-directory-page'
import { StaffAccessView } from './staff-access-page'
import { ProblemImportView } from './problem-import-page'

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

const directoryCourse: AdminCourse = {
  courseId: 'course-math-5-7-fixture',
  code: 'math-5-7',
  name: 'Математика 5–7',
  subjectCode: 'math',
  status: 'active',
  sortOrder: 1,
  accentKey: 'math',
  activeStudents: 2,
  groups: [
    {
      groupId: 'group-fixture-beginner',
      shortCode: 'н',
      name: 'Начинающие',
      status: 'active',
      colorKey: 'level-1',
      sortOrder: 10,
      allowSelfSwitch: true,
      isDefault: true,
      isSystem: false,
      scoreWeight: 1,
      activeStudents: 1,
      version: 1,
    },
    {
      groupId: 'group-fixture-continuing',
      shortCode: 'п',
      name: 'Продолжающие',
      status: 'active',
      colorKey: 'level-2',
      sortOrder: 20,
      allowSelfSwitch: true,
      isDefault: false,
      isSystem: false,
      scoreWeight: 1,
      activeStudents: 1,
      version: 1,
    },
  ],
  version: 1,
}

export const LessonImport: Story = { render: () => <StaffLessonDetailPage lessonId="41" /> }

const problemImportPreview = problemImportPreviewResponseSchema.parse({
  schemaVersion: 1,
  course: {
    courseId: directoryCourse.courseId,
    code: directoryCourse.code,
    name: directoryCourse.name,
  },
  source: { filename: 'ВМШ — задачи.xlsx', sha256: 'a'.repeat(64) },
  previewSha256: 'b'.repeat(64),
  summary: { rows: 2, create: 1, update: 0, unchanged: 0, invalid: 1 },
  rows: [
    {
      sheet: 'Задачи',
      row: 24,
      groupCode: 'н',
      groupId: directoryCourse.groups[0]!.groupId,
      lessonNumber: 41,
      problemNumber: 3,
      item: '',
      title: 'Орехи и клетки',
      problemText: '',
      problemType: 1,
      answerType: 2,
      answerValidation: null,
      validationError: 'Введите ответ — сколько орехов',
      correctAnswer: '29',
      correctAnswerChecker: null,
      wrongAnswer: 'Нет, не столько орехов',
      congratulation: 'Да, всё верно!',
      action: 'create',
      problemId: null,
      diagnostics: [],
    },
    {
      sheet: 'Старые',
      row: 812,
      groupCode: 'i9a',
      groupId: null,
      lessonNumber: 14,
      problemNumber: 7,
      item: 'б',
      title: 'Старая задача',
      problemText: '',
      problemType: 2,
      answerType: null,
      answerValidation: null,
      validationError: null,
      correctAnswer: null,
      correctAnswerChecker: null,
      wrongAnswer: null,
      congratulation: null,
      action: 'invalid',
      problemId: null,
      diagnostics: [
        {
          sheet: 'Старые',
          row: 812,
          field: 'level',
          code: 'group_unknown',
          message: 'Такой группы нет в выбранном курсе.',
        },
      ],
    },
  ],
  requestId: 'storybook-problem-import',
})

function ProblemImportStory() {
  const [preview, setPreview] = useState<typeof problemImportPreview>()
  return (
    <div className="min-h-screen bg-background p-4">
      <ProblemImportView
        courses={[directoryCourse]}
        onPreview={() => setPreview(problemImportPreview)}
        pending={false}
        {...(preview ? { preview } : {})}
      />
    </div>
  )
}

export const ProblemWorkbookPreview: Story = {
  name: 'Настройки задач · dry-run XLSX',
  render: () => <ProblemImportStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.upload(
      canvas.getByLabelText('XLSX-файл'),
      new File(['xlsx'], 'tasks.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      }),
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Проверить файл' }))
    await expect(canvas.getByRole('heading', { name: 'Результат проверки' })).toBeVisible()
    await expect(canvas.getByText('Такой группы нет в выбранном курсе.')).toBeVisible()
  },
}
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
export const ClassroomDelivery: Story = {
  name: 'Аудитории · явная рассылка после подтверждения',
  render: () => (
    <StaffClassroomsPage
      students={
        <ClassroomDeliveryPanel
          onSend={() => undefined}
          preview={classroomDeliveryPreviewResponseSchema.parse(deliveryPreviewFixture).preview}
        />
      }
      tab="students"
    />
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByRole('button', { name: 'Разослать аудитории' })).toBeEnabled()
    await expect(canvas.getByText(/Семье уведомление не отправляется/)).toBeInTheDocument()
  },
}
export const BroadcastPhaseTwo: Story = { render: () => <BroadcastComposerPage /> }

function StudentDirectoryStory() {
  const [search, setSearch] = useState({ query: '' })
  const [saved, setSaved] = useState(false)
  const directory = adminStudentEnrollmentDirectoryResponseSchema.parse(studentDirectoryFixture)
  return (
    <div className="min-h-screen bg-background p-4">
      <StudentDirectoryView
        accountId="storybook-admin"
        courses={[directoryCourse]}
        onSave={() => setSaved(true)}
        onSearchChange={setSearch}
        search={search}
        storageNamespace="vmsh-179:v1:staff:storybook"
        students={directory.students}
      />
      {saved ? (
        <p className="mt-3 text-small" role="status">
          Изменение подготовлено к отправке.
        </p>
      ) : null}
    </div>
  )
}

export const StudentCourseAccess: Story = {
  name: 'Участники · курсы и группы',
  render: () => <StudentDirectoryStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.type(canvas.getByLabelText('Поиск по имени'), 'алексеи')
    await expect(canvas.getAllByText('Тестовый-Онлайн Алексей Петрович')).toHaveLength(2)
    await userEvent.selectOptions(
      canvas.getByLabelText('Активная группа'),
      'group-fixture-continuing',
    )
    await expect(canvas.getByText(/Несохранённые изменения хранятся/)).toBeInTheDocument()
    await userEvent.click(canvas.getByRole('button', { name: 'Сохранить изменения' }))
    await expect(canvas.getByText('Изменение подготовлено к отправке.')).toBeInTheDocument()
  },
}

function TeacherStudentDirectoryStory() {
  const [search, setSearch] = useState({ query: '' })
  const [saved, setSaved] = useState(false)
  const directory = adminStudentEnrollmentDirectoryResponseSchema.parse(studentDirectoryFixture)
  const student = directory.students[0]!
  return (
    <div className="min-h-screen bg-background p-4">
      <StudentDirectoryView
        accountId="storybook-teacher"
        canEditGroup={() => true}
        canManageEnrollment={false}
        courses={[]}
        onSave={() => setSaved(true)}
        onSearchChange={setSearch}
        search={search}
        showPrivateAccounts={false}
        storageNamespace="vmsh-179:v1:staff:storybook-teacher"
        students={[{ ...student, webAccount: null, familyAccounts: [] }]}
      />
      {saved ? (
        <p className="mt-3 text-small" role="status">
          Новая активная группа подготовлена к отправке.
        </p>
      ) : null}
    </div>
  )
}

export const TeacherScopedStudentAccess: Story = {
  name: 'Участники · область преподавателя',
  render: () => <TeacherStudentDirectoryStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.queryByText('Семейные аккаунты')).not.toBeInTheDocument()
    await expect(canvas.getByLabelText('Формат занятий')).toBeDisabled()
    await userEvent.selectOptions(
      canvas.getByLabelText('Активная группа'),
      'group-fixture-continuing',
    )
    await userEvent.click(canvas.getByRole('button', { name: 'Сохранить изменения' }))
    await expect(canvas.getByText('Новая активная группа подготовлена к отправке.')).toBeVisible()
  },
}

const teacherAccessFixture: StaffAccessMember = {
  staffUserId: 'teacher-storybook',
  name: 'Мария',
  surname: 'Учитель',
  middleName: null,
  role: 'teacher',
  account: {
    accountId: 'account-teacher-storybook',
    username: 'm.teacher',
    status: 'active',
  },
  scopes: [
    {
      courseId: directoryCourse.courseId,
      courseCode: directoryCourse.code,
      courseName: directoryCourse.name,
      courseStatus: directoryCourse.status,
      groupId: directoryCourse.groups[0]!.groupId,
      groupCode: directoryCourse.groups[0]!.shortCode,
      groupName: directoryCourse.groups[0]!.name,
      groupStatus: directoryCourse.groups[0]!.status,
      version: 2,
    },
  ],
}

function StaffAccessStory() {
  const [saved, setSaved] = useState(false)
  return (
    <div className="min-h-screen bg-background p-4">
      <StaffAccessView
        accountId="storybook-admin"
        courses={[directoryCourse]}
        members={[teacherAccessFixture]}
        onSave={() => setSaved(true)}
        storageNamespace="vmsh-179:v1:staff:storybook-access"
      />
      {saved ? (
        <p className="mt-3 text-small" role="status">
          Доступы подготовлены к отправке.
        </p>
      ) : null}
    </div>
  )
}

export const TeacherCourseScopes: Story = {
  name: 'Участники · доступы преподавателя',
  render: () => <StaffAccessStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getAllByText('Учитель Мария')).toHaveLength(2)
    const course = within(
      canvas.getByRole('group', { name: `Доступ к курсу «${directoryCourse.name}»` }),
    )
    await userEvent.click(course.getByRole('checkbox', { name: 'Весь курс' }))
    await expect(canvas.getByText(/Несохранённые изменения хранятся/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Сохранить доступы' }))
    await expect(canvas.getByText('Доступы подготовлены к отправке.')).toBeVisible()
  },
}

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
