import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import {
  PageLayout,
  PageStatePanel,
  createAdminCourseClient,
  useAdminCourseCatalogQuery,
  useAuthenticatedPrincipal,
  useAuthentication,
} from '@vmsh/app-shell'
import {
  ApiResponseError,
  adminCourseCatalogQueryKey,
  type AdminCourse,
  type AdminCourseResponse,
  type AdminGroup,
  type AdminGroupResponse,
  type CreateAdminCourseRequest,
  type SaveAdminGroupRequest,
  type UpdateAdminCourseRequest,
} from '@vmsh/contracts'
import { CourseGroupCatalog, type ManagedCourse } from '@vmsh/product'
import { Alert, AlertContent, AlertDescription, AlertTitle } from '@vmsh/ui'

import { clearCatalogDraft } from './course-catalog-draft'
import { CourseCatalogEditor, GroupCatalogEditor } from './course-catalog-editors'

type Editor =
  | { kind: 'course'; course: AdminCourse | null }
  | { kind: 'group'; courseId: string; group: AdminGroup | null }

type Command =
  | { kind: 'create-course'; input: CreateAdminCourseRequest; draftKey: string }
  | {
      kind: 'update-course'
      course: AdminCourse
      input: UpdateAdminCourseRequest
      draftKey: string
    }
  | {
      kind: 'create-group'
      courseId: string
      input: SaveAdminGroupRequest
      draftKey: string
    }
  | {
      kind: 'update-group'
      group: AdminGroup
      input: SaveAdminGroupRequest
      draftKey: string
    }
  | { kind: 'toggle-course'; course: AdminCourse }

function errorMessage(error: Error): string {
  return error instanceof ApiResponseError
    ? error.message
    : 'Проверьте соединение и повторите попытку.'
}

function colorIndex(sortOrder: number, system: boolean): 0 | 1 | 2 | 3 | 4 {
  if (system) return 0
  const normalized = Math.abs(sortOrder) % 4
  return (normalized === 0 ? 4 : normalized) as 1 | 2 | 3 | 4
}

function courseView(courses: AdminCourse[]): ManagedCourse[] {
  return courses.map((course, index) => ({
    course: {
      id: course.courseId,
      code: course.code,
      name: course.name,
      subjectCode: course.subjectCode,
      accentIndex: (index % 5) as 0 | 1 | 2 | 3 | 4,
    },
    status: course.status,
    groups: course.groups.map((group) => ({
      id: group.groupId,
      courseId: course.courseId,
      code: group.shortCode,
      name: group.name,
      colorIndex: colorIndex(group.sortOrder, group.isSystem),
      status: group.status,
      activeStudents: group.activeStudents,
      scheduleLabel: 'расписание группы',
    })),
  }))
}

/**
 * Real Staff course catalog for design-system page flow 5.3 and Phase 10.
 * See dev/design-system/05-pages-and-flows.md and dev/development-plan/14-phase-10-admin-and-google-exit.md.
 */
export function StaffCourseCatalogPage() {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'staff') throw new Error('Course catalog requires Staff auth')
  const client = useMemo(
    () =>
      createAdminCourseClient(authentication.client.runtime, {
        refreshSession: async () => {
          try {
            return await authentication.refresh()
          } catch (error) {
            authentication.handleApiError(error)
            throw error
          }
        },
      }),
    [authentication],
  )
  const scope = { audience: 'staff' as const, accountId: principal.accountId }
  const catalog = useAdminCourseCatalogQuery(client, scope)
  const queryClient = useQueryClient()
  const [editor, setEditor] = useState<Editor | null>(null)
  const mutation = useMutation<AdminCourseResponse | AdminGroupResponse, Error, Command>({
    mutationFn: (command: Command) => {
      if (command.kind === 'toggle-course') {
        const { course } = command
        return client.updateCourse(course.courseId, course.version, {
          schemaVersion: 1,
          code: course.code,
          name: course.name,
          subjectCode: course.subjectCode,
          status: course.status === 'archived' ? 'active' : 'archived',
          sortOrder: course.sortOrder,
          accentKey: course.accentKey,
        })
      }
      if (command.kind === 'create-course') return client.createCourse(command.input)
      if (command.kind === 'update-course') {
        return client.updateCourse(command.course.courseId, command.course.version, command.input)
      }
      if (command.kind === 'create-group') {
        return client.createGroup(command.courseId, command.input)
      }
      return client.updateGroup(command.group.groupId, command.group.version, command.input)
    },
    onSuccess: async (_, command) => {
      if ('draftKey' in command) clearCatalogDraft(command.draftKey)
      setEditor(null)
      await queryClient.invalidateQueries({ queryKey: adminCourseCatalogQueryKey(scope) })
    },
    onError: (error) => authentication.handleApiError(error),
  })

  if (catalog.isPending) {
    return (
      <PageLayout title="Курсы и группы" width="wide">
        <PageStatePanel state="loading" />
      </PageLayout>
    )
  }
  if (catalog.error) {
    return (
      <PageLayout title="Курсы и группы" width="wide">
        <PageStatePanel
          actionLabel="Повторить"
          onAction={() => void catalog.refetch()}
          state={
            catalog.error instanceof ApiResponseError && catalog.error.status === 403
              ? 'forbidden'
              : 'error'
          }
        />
      </PageLayout>
    )
  }

  const findCourse = (courseId: string) =>
    catalog.data.courses.find((course) => course.courseId === courseId)
  const findGroup = (groupId: string) =>
    catalog.data.courses
      .flatMap((course) => course.groups)
      .find((group) => group.groupId === groupId)
  const courseEditor = editor?.kind === 'course' ? editor : null
  const groupEditor = editor?.kind === 'group' ? editor : null
  const editingCourse = courseEditor?.course ?? null
  const editingGroup = groupEditor?.group ?? null
  const courseDraftKey = `${authentication.client.runtime.instance}:staff:${principal.accountId}:course-catalog:course:${editingCourse?.courseId ?? 'new'}:${editingCourse?.version ?? catalog.data.season.seasonId}`
  const groupDraftKey = `${authentication.client.runtime.instance}:staff:${principal.accountId}:course-catalog:group:${editingGroup?.groupId ?? groupEditor?.courseId ?? 'new'}:${editingGroup?.version ?? 0}`

  return (
    <PageLayout
      description="Курс задаёт общий учебный контекст. Группы внутри него могут иметь собственные расписания и публикации."
      eyebrow={catalog.data.season.title}
      title="Курсы и группы"
      width="wide"
    >
      <div className="space-y-4">
        {mutation.error ? (
          <Alert role="alert" tone="danger">
            <AlertContent>
              <AlertTitle>Изменение не сохранено</AlertTitle>
              <AlertDescription>{errorMessage(mutation.error)}</AlertDescription>
            </AlertContent>
          </Alert>
        ) : null}
        <CourseGroupCatalog
          courses={courseView(catalog.data.courses)}
          onAddCourse={() => setEditor({ kind: 'course', course: null })}
          onAddGroup={(courseId) => setEditor({ kind: 'group', courseId, group: null })}
          onArchiveCourse={(courseId) => {
            const course = findCourse(courseId)
            if (!course || mutation.isPending) return
            const action = course.status === 'archived' ? 'восстановить' : 'перенести в архив'
            if (globalThis.confirm(`Вы уверены, что хотите ${action} курс «${course.name}»?`)) {
              mutation.mutate({ kind: 'toggle-course', course })
            }
          }}
          onEditCourse={(courseId) => {
            const course = findCourse(courseId)
            if (course) setEditor({ kind: 'course', course })
          }}
          onEditGroup={(groupId) => {
            const group = findGroup(groupId)
            const course = catalog.data.courses.find((item) =>
              item.groups.some((candidate) => candidate.groupId === groupId),
            )
            if (group && course) setEditor({ kind: 'group', courseId: course.courseId, group })
          }}
        />
      </div>
      {courseEditor ? (
        <CourseCatalogEditor
          course={editingCourse}
          key={courseDraftKey}
          onOpenChange={(open) => {
            if (!open && !mutation.isPending) setEditor(null)
          }}
          onSave={(input) => {
            if (editingCourse) {
              mutation.mutate({
                kind: 'update-course',
                course: editingCourse,
                input,
                draftKey: courseDraftKey,
              })
            } else {
              mutation.mutate({
                kind: 'create-course',
                input: { ...input, seasonId: catalog.data.season.seasonId },
                draftKey: courseDraftKey,
              })
            }
          }}
          open
          saving={mutation.isPending}
          storageKey={courseDraftKey}
        />
      ) : null}
      {groupEditor ? (
        <GroupCatalogEditor
          group={editingGroup}
          key={groupDraftKey}
          onOpenChange={(open) => {
            if (!open && !mutation.isPending) setEditor(null)
          }}
          onSave={(input) => {
            if (editingGroup) {
              mutation.mutate({
                kind: 'update-group',
                group: editingGroup,
                input,
                draftKey: groupDraftKey,
              })
            } else {
              mutation.mutate({
                kind: 'create-group',
                courseId: groupEditor.courseId,
                input,
                draftKey: groupDraftKey,
              })
            }
          }}
          open
          saving={mutation.isPending}
          storageKey={groupDraftKey}
        />
      ) : null}
    </PageLayout>
  )
}
