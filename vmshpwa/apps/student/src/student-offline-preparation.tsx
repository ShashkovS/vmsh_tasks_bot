import { useRouter } from '@tanstack/react-router'
import { t } from '@lingui/core/macro'
import { useQuery } from '@tanstack/react-query'
import { useAuthentication, authenticationStatePrincipal } from '@vmsh/app-shell'
import {
  ApiResponseError,
  courseQueryKeys,
  studentCourseAccessResponseSchema,
  studentLessonSummarySchema,
} from '@vmsh/contracts'
import {
  clearLessonAssetCaches,
  readLessonBundle,
  verifyLessonBundle,
  useOfflineDatabase,
} from '@vmsh/offline'
import { Button } from '@vmsh/ui'
import { prepareOfflineLessons } from './prepare-offline-lessons'

async function waitForOfflineShell(signal: AbortSignal): Promise<void> {
  if (!import.meta.env.PROD) return
  if (!('serviceWorker' in navigator)) throw new Error('Offline application shell is unavailable')
  let timeout: ReturnType<typeof setTimeout> | undefined
  let abort: () => void = () => undefined
  const unavailable = new Promise<never>((_resolve, reject) => {
    abort = () =>
      reject(
        signal.reason instanceof Error
          ? signal.reason
          : new DOMException('Cancelled', 'AbortError'),
      )
    if (signal.aborted) abort()
    else signal.addEventListener('abort', abort, { once: true })
    timeout = setTimeout(() => reject(new Error('Offline shell preparation timed out')), 15_000)
  })
  try {
    await Promise.race([navigator.serviceWorker.ready, unavailable])
  } finally {
    clearTimeout(timeout)
    signal.removeEventListener('abort', abort)
  }
}

/** docs/offline-current-lessons.md: mount under Student shell, including Now and direct links. */
export function StudentOfflinePreparation() {
  const authentication = useAuthentication()
  const principal = authenticationStatePrincipal(authentication.state)
  return principal ? <Preparation ownerId={principal.accountId} /> : null
}

function Preparation({ ownerId }: { ownerId: string }) {
  const database = useOfflineDatabase()
  const router = useRouter()
  const authentication = useAuthentication()
  const principal = authenticationStatePrincipal(authentication.state)!
  const verified = authentication.state.status === 'authenticated'
  const query = useQuery({
    queryKey: [...courseQueryKeys.offlineLessons(principal), verified],
    networkMode: 'always',
    retry: false,
    staleTime: 30_000,
    refetchOnReconnect: 'always',
    refetchOnWindowFocus: true,
    queryFn: async ({ signal }) => {
      if (!navigator.onLine || !verified) {
        const saved = await readLessonBundle(database, ownerId)
        return saved && (await verifyLessonBundle(saved)) ? saved : null
      }
      try {
        const bundle = await prepareOfflineLessons({
          database,
          ownerId,
          runtime: authentication.client.runtime,
          signal,
        })
        // Preparation includes route modules, before the student ever visits Tasks.
        await waitForOfflineShell(signal)
        await router.preloadRoute({ to: '/tasks' })
        const access = studentCourseAccessResponseSchema.parse(
          bundle.documents.find((entry) => entry.kind === 'student-course-access')?.payload,
        )
        for (const entry of bundle.documents.filter((entry) => entry.kind === 'student-lesson')) {
          const lesson = studentLessonSummarySchema.parse(entry.payload)
          const enrollment = access.enrollments.find(
            (value) => value.course.courseId === lesson.courseId,
          )!
          const group = enrollment.allowedGroups.find((value) => value.groupId === lesson.groupId)!
          await router.preloadRoute({
            to: '/tasks/$courseCode/$groupCode/$lessonNumber',
            params: {
              courseCode: enrollment.course.code,
              groupCode: group.code,
              lessonNumber: String(lesson.lessonNumber),
            },
          })
        }
        return bundle
      } catch (error) {
        if (!signal.aborted && error instanceof ApiResponseError && error.status === 403) {
          await database.documents.where('ownerId').equals(ownerId).delete()
          await clearLessonAssetCaches(database.name, ownerId)
        }
        authentication.handleApiError(error)
        throw error
      }
    },
  })
  return (
    <div role="status" className="mb-4 text-small text-muted-foreground">
      {query.isFetching && navigator.onLine && verified
        ? t`Сохраняем задачи для просмотра без интернета`
        : query.isError
          ? t`Не все задачи сохранены для просмотра без интернета`
          : query.data
            ? t`Задачи всех уровней сохранены`
            : t`Материал ещё не сохранён на устройстве`}
      {query.isError && verified ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => void query.refetch()}
        >{t`Повторить`}</Button>
      ) : null}
      {!verified &&
      authentication.state.status === 'offline-unverified' &&
      authentication.state.sessionExpired === true ? (
        <p>{t`Для отправки ответов и других действий войдите снова при наличии интернета.`}</p>
      ) : null}
    </div>
  )
}
