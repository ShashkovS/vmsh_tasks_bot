import type { Meta, StoryObj } from '@storybook/react-vite'
import { useState } from 'react'
import { expect, userEvent, within } from 'storybook/test'

import deliveryPreviewFixture from '@vmsh/contracts/fixtures/classrooms/delivery-preview.v1.json'
import studentDirectoryFixture from '@vmsh/contracts/fixtures/admin-enrollments/directory.v1.json'
import {
  adminStudentEnrollmentDirectoryResponseSchema,
  classroomDeliveryPreviewResponseSchema,
  problemImportPreviewResponseSchema,
  problemImportReceiptSchema,
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
  summary: { rows: 3, create: 2, update: 0, unchanged: 0, invalid: 1 },
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
      sheet: 'Задачи',
      row: 31,
      groupCode: 'п',
      groupId: directoryCourse.groups[1]!.groupId,
      lessonNumber: 41,
      problemNumber: 5,
      item: '',
      title: 'Орехи и клетки',
      problemText: '',
      problemType: 2,
      answerType: null,
      answerValidation: null,
      validationError: null,
      correctAnswer: null,
      correctAnswerChecker: null,
      wrongAnswer: null,
      congratulation: null,
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
  synonymCandidates: [
    {
      lessonNumber: 41,
      normalizedTitle: 'орехи и клетки',
      displayTitle: 'Орехи и клетки',
      hasGroupConflict: false,
      members: [
        {
          sheet: 'Задачи',
          row: 24,
          groupCode: 'н',
          groupId: directoryCourse.groups[0]!.groupId,
          problemNumber: 3,
          item: '',
          problemId: null,
          problemType: 1,
          answerType: 2,
        },
        {
          sheet: 'Задачи',
          row: 31,
          groupCode: 'п',
          groupId: directoryCourse.groups[1]!.groupId,
          problemNumber: 5,
          item: '',
          problemId: null,
          problemType: 2,
          answerType: null,
        },
      ],
    },
  ],
  requestId: 'storybook-problem-import',
})
const problemImportReceipt = problemImportReceiptSchema.parse({
  schemaVersion: 1,
  importId: 'problem-import.storybook',
  state: 'applied',
  source: problemImportPreview.source,
  previewSha256: problemImportPreview.previewSha256,
  summary: { rows: 3, created: 2, updated: 0, unchanged: 0, skippedInvalid: 1 },
  appliedAt: '2026-07-30T10:00:00+00:00',
  rolledBackAt: null,
  version: 1,
  replayed: false,
  requestId: 'storybook-problem-import-apply',
})

function ProblemImportStory() {
  const [preview, setPreview] = useState<typeof problemImportPreview>()
  const [reviewedWorkbook, setReviewedWorkbook] = useState<File>()
  const [receipt, setReceipt] = useState<typeof problemImportReceipt>()
  return (
    <div className="min-h-screen bg-background p-4">
      <ProblemImportView
        courses={[directoryCourse]}
        onApply={() => setReceipt(problemImportReceipt)}
        onPreview={(_courseId, workbook) => {
          setReviewedWorkbook(workbook)
          setReceipt(undefined)
          setPreview(problemImportPreview)
        }}
        onRollback={() =>
          setReceipt({
            ...problemImportReceipt,
            state: 'rolled_back',
            rolledBackAt: '2026-07-30T10:05:00+00:00',
            version: 2,
          })
        }
        pending={false}
        {...(preview ? { preview } : {})}
        {...(receipt ? { receipt } : {})}
        {...(reviewedWorkbook ? { reviewedWorkbook } : {})}
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
    await expect(canvas.getByText('Возможные синонимы · 1')).toBeVisible()
    await expect(canvas.getByText('н 3 · п 5')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Применить изменения · 2' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить применение' }))
    await expect(canvas.getByText('Изменения применены')).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Откатить импорт' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Подтвердить откат' }))
    await expect(canvas.getByText('Импорт отменён')).toBeVisible()
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
  const [accountSaved, setAccountSaved] = useState(false)
  const [familySaved, setFamilySaved] = useState<string | null>(null)
  const directory = adminStudentEnrollmentDirectoryResponseSchema.parse(studentDirectoryFixture)
  const [students, setStudents] = useState(directory.students)
  return (
    <div className="min-h-screen bg-background p-4">
      <StudentDirectoryView
        accountId="storybook-admin"
        courses={[directoryCourse]}
        onAccountChange={() => {
          setAccountSaved(true)
          return Promise.resolve()
        }}
        onFamilyChange={(command) => {
          setFamilySaved(command.kind)
          setStudents((current) =>
            current.map((student) => {
              if (student.studentId !== command.studentId) return student
              if (command.kind === 'unlink') {
                return {
                  ...student,
                  familyAccounts: student.familyAccounts.filter(
                    (account) => account.accountId !== command.accountId,
                  ),
                }
              }
              const nextAccount =
                command.kind === 'create'
                  ? {
                      accountId: 'storybook-family-create',
                      username: command.input.username,
                      displayName: command.input.displayName,
                      status: 'active' as const,
                      credentialVersion: 1,
                      relationshipLabel: command.input.relationshipLabel,
                      isPrimary: command.input.isPrimary,
                    }
                  : {
                      accountId: 'storybook-family-link',
                      username: command.input.familyUsername,
                      displayName: 'Существующая семья',
                      status: 'active' as const,
                      credentialVersion: 1,
                      relationshipLabel: command.input.relationshipLabel,
                      isPrimary: command.input.isPrimary,
                    }
              return {
                ...student,
                familyAccounts: [...student.familyAccounts, nextAccount],
              }
            }),
          )
          return Promise.resolve()
        }}
        onCreateStudentAccount={(studentId, input) => {
          setStudents((current) =>
            current.map((student) =>
              student.studentId === studentId
                ? {
                    ...student,
                    usernameSuggestion: null,
                    webAccount: {
                      accountId: 'storybook-student-account',
                      username: input.username,
                      status: 'active' as const,
                      credentialVersion: 1,
                    },
                  }
                : student,
            ),
          )
          setAccountSaved(true)
          return Promise.resolve()
        }}
        onCreateStudentAccounts={(commands) => {
          setStudents((current) =>
            current.map((student) => {
              const command = commands.find((item) => item.studentId === student.studentId)
              if (!command) return student
              return {
                ...student,
                usernameSuggestion: null,
                webAccount: {
                  accountId: `storybook-student-account-${student.studentId}`,
                  username: command.username,
                  status: 'active' as const,
                  credentialVersion: 1,
                },
              }
            }),
          )
          setAccountSaved(true)
          return Promise.resolve({
            createdStudentIds: commands.map((command) => command.studentId),
            failures: [],
          })
        }}
        onSave={() => setSaved(true)}
        onSearchChange={setSearch}
        search={search}
        storageNamespace="vmsh-179:v1:staff:storybook"
        students={students}
      />
      {saved ? (
        <p className="mt-3 text-small" role="status">
          Изменение подготовлено к отправке.
        </p>
      ) : null}
      {accountSaved ? (
        <p className="mt-3 text-small" role="status">
          Изменение аккаунта подготовлено к отправке.
        </p>
      ) : null}
      {familySaved ? (
        <p className="mt-3 text-small" role="status">
          Семейное действие подготовлено: {familySaved}.
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

export const StudentAccountLifecycle: Story = {
  name: 'Участники · блокировка и смена токена',
  render: () => <StudentDirectoryStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.selectOptions(canvas.getAllByLabelText('Состояние')[0]!, 'blocked')
    await userEvent.click(canvas.getAllByRole('button', { name: 'Сохранить состояние' })[0]!)
    await expect(canvas.getByText('Изменение аккаунта подготовлено к отправке.')).toBeVisible()
  },
}

export const FamilyAccountManagement: Story = {
  name: 'Участники · семейные аккаунты',
  render: () => <StudentDirectoryStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('family-testovye · родитель · основной контакт')).toBeVisible()

    await userEvent.click(canvas.getByRole('button', { name: 'Создать аккаунт' }))
    const login = canvas.getByLabelText('Логин')
    const displayName = canvas.getByLabelText('Имя аккаунта')
    await userEvent.clear(login)
    await userEvent.type(login, 'family-new')
    await userEvent.clear(displayName)
    await userEvent.type(displayName, 'Семья Новых')
    await userEvent.type(canvas.getByLabelText('Первый пароль'), 'family-password')
    await userEvent.click(canvas.getByRole('button', { name: 'Создать и привязать' }))
    await expect(canvas.getByText('Семейный аккаунт создан и привязан.')).toBeVisible()
    await expect(canvas.getByText('Семейное действие подготовлено: create.')).toBeVisible()

    const createdAccount = canvas
      .getByText('family-new · родитель · основной контакт')
      .closest('li')
    if (!createdAccount) throw new Error('Created Family account card is missing')
    await userEvent.click(
      within(createdAccount).getByRole('button', { name: 'Отвязать от школьника' }),
    )
    await userEvent.click(
      within(createdAccount).getByRole('button', { name: 'Подтвердить отвязку' }),
    )
    await expect(canvas.getByText(/Сам семейный аккаунт сохранён/)).toBeVisible()
    await expect(canvas.getByText('Семейное действие подготовлено: unlink.')).toBeVisible()
    await expect(
      canvas.queryByText('family-new · родитель · основной контакт'),
    ).not.toBeInTheDocument()
  },
}

export const StudentAccountCreation: Story = {
  name: 'Участники · создание web-входа школьника',
  render: () => <StudentDirectoryStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: /Новый Школьник/ }))
    const login = canvas.getByLabelText('Логин школьника')
    await expect(login).toHaveValue('novyi-12')
    await expect(canvas.getByText(/Логин предложен по фамилии/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Создать web-вход' }))
    await expect(canvas.getByText('Web-вход активен')).toBeVisible()
    await expect(canvas.getByText('novyi-12')).toBeVisible()
  },
}

export const StudentAccountBatchCreation: Story = {
  name: 'Участники · пакетное создание web-входов',
  render: () => <StudentDirectoryStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await userEvent.click(canvas.getByRole('button', { name: 'Выбрать школьников' }))
    await userEvent.click(canvas.getByRole('button', { name: 'Выбрать найденных · 1' }))
    await expect(canvas.getByText(/Выбрано: 1\. Выбор хранится/)).toBeVisible()
    await userEvent.click(canvas.getByRole('button', { name: 'Создать аккаунты · 1' }))
    await expect(canvas.getByText('Создано: 1. Ошибок: 0.')).toBeVisible()
    await expect(canvas.getByText('Готовы: 0')).toBeVisible()
  },
}

function DenseStudentDirectoryStory() {
  const [search, setSearch] = useState({ query: '' })
  const [students] = useState(() => {
    const source =
      adminStudentEnrollmentDirectoryResponseSchema.parse(studentDirectoryFixture).students[0]!
    return Array.from({ length: 1_500 }, (_, index) => ({
      ...source,
      studentId: `storybook-student-${index + 1}`,
      surname: `Школьник${String(index + 1).padStart(4, '0')}`,
      name: 'Тестовый',
      middleName: index === 1_498 ? 'Совершенноуникальныймаркер' : null,
      webAccount: null,
      familyAccounts: [],
    }))
  })
  return (
    <div className="min-h-screen bg-background p-4">
      <StudentDirectoryView
        accountId="storybook-admin"
        courses={[directoryCourse]}
        onSave={() => undefined}
        onSearchChange={setSearch}
        search={search}
        storageNamespace="vmsh-179:v1:staff:storybook-dense-directory"
        students={students}
      />
    </div>
  )
}

export const StudentDirectory1500: Story = {
  name: 'Участники · 1500 школьников',
  render: () => <DenseStudentDirectoryStory />,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    const list = within(canvas.getByRole('region', { name: 'Список школьников' }))
    await expect(canvas.getByText('Найдено: 1500')).toBeVisible()
    await expect(list.getAllByRole('button').length).toBeLessThan(50)
    await userEvent.type(canvas.getByLabelText('Поиск по имени'), 'Совершенноуникальныймаркер')
    await expect(canvas.getByText('Найдено: 1')).toBeVisible()
    await expect(list.getByRole('button', { name: /Школьник1499 Тестовый/ })).toBeVisible()
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
