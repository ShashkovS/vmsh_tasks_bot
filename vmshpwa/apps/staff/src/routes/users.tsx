import { createFileRoute } from '@tanstack/react-router'
import { z } from 'zod'

import { StaffStudentDirectoryPage } from '../staff-student-directory-page'
import { StaffAccessPage } from '../staff-access-page'
import { StaffAccountProvisioningPage } from '../account-provisioning-page'

const searchSchema = z.object({
  tab: z.enum(['students', 'teachers', 'imports']).optional().catch(undefined),
  q: z.string().trim().max(100).optional().catch(undefined),
  student: z.string().trim().min(1).optional(),
  course: z.string().trim().min(1).optional(),
})

export const Route = createFileRoute('/users')({
  validateSearch: searchSchema,
  component: UsersRoute,
})

function UsersRoute() {
  const search = Route.useSearch()
  const navigate = Route.useNavigate()
  const section = search.tab ?? 'students'
  const changeSection = (tab: 'students' | 'teachers' | 'imports') =>
    void navigate({
      replace: true,
      search: tab === 'students' ? {} : { tab },
    })
  if (section === 'teachers') {
    return <StaffAccessPage onSectionChange={changeSection} />
  }
  if (section === 'imports') {
    return <StaffAccountProvisioningPage onSectionChange={changeSection} />
  }
  return (
    <StaffStudentDirectoryPage
      onSectionChange={changeSection}
      onSearchChange={(next) =>
        void navigate({
          replace: true,
          search: {
            ...(search.tab ? { tab: search.tab } : {}),
            ...(next.query ? { q: next.query } : {}),
            ...(next.studentId ? { student: next.studentId } : {}),
            ...(next.courseId ? { course: next.courseId } : {}),
          },
        })
      }
      search={{
        query: search.q ?? '',
        ...(search.student ? { studentId: search.student } : {}),
        ...(search.course ? { courseId: search.course } : {}),
      }}
    />
  )
}
