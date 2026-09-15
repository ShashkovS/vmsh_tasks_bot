import { useMemo, useState } from 'react'

import {
  createStudentOralWindowClient,
  useAuthenticatedPrincipal,
  useAuthentication,
  useStudentOralWindowsQuery,
} from '@vmsh/app-shell'
import { ApiResponseError, type OralWindowJoin } from '@vmsh/contracts'
import { OralAdmission } from '@vmsh/product'

export function StudentOralAdmission({
  courseId,
  groupLessonId,
}: {
  courseId: string
  groupLessonId: string
}) {
  const authentication = useAuthentication()
  const principal = useAuthenticatedPrincipal()
  if (principal.audience !== 'student') throw new Error('Oral admission requires Student auth')
  const client = useMemo(
    () =>
      createStudentOralWindowClient(authentication.client.runtime, {
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
  const query = useStudentOralWindowsQuery(
    client,
    { audience: 'student', accountId: principal.accountId },
    courseId,
    groupLessonId,
  )
  const [joiningWindowId, setJoiningWindowId] = useState<string | null>(null)
  const [join, setJoin] = useState<OralWindowJoin | null>(null)
  const [joinError, setJoinError] = useState<string | null>(null)

  if (query.error instanceof ApiResponseError && query.error.status === 404) return null

  if (query.isPending) {
    return <p className="mt-5 text-small text-muted-foreground">Загружаем окна устного приёма…</p>
  }

  if (query.error) {
    return (
      <p className="mt-5 text-small text-muted-foreground">
        Не удалось загрузить окна устного приёма. Письменная сдача доступна ниже.
      </p>
    )
  }

  const reveal = async (windowId: string) => {
    setJoiningWindowId(windowId)
    setJoinError(null)
    try {
      const response = await client.join(courseId, groupLessonId, windowId)
      setJoin(response.join)
    } catch (error) {
      authentication.handleApiError(error)
      setJoinError(
        error instanceof ApiResponseError
          ? error.message
          : 'Не удалось получить ссылку. Попробуйте ещё раз.',
      )
    } finally {
      setJoiningWindowId(null)
    }
  }

  return (
    <OralAdmission
      className="mt-5"
      errorMessage={joinError}
      joiningWindowId={joiningWindowId}
      onRevealJoin={(windowId) => void reveal(windowId)}
      revealedJoin={join}
      windows={query.data.items}
    />
  )
}
