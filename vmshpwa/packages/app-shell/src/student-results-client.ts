import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  studentResultsDirectorySchema,
  studentResultsOverviewSchema,
  studentResultsLessonSchema,
  studentResultHistorySchema,
  studentResultsConditionSchema,
  type RuntimeConfig,
} from '@vmsh/contracts'

export function createStudentResultsClient(
  runtime: RuntimeConfig,
  refresh?: () => Promise<unknown>,
) {
  const base = `${parseRuntimeConfigForAudience('staff', runtime).apiBase}/student-results`
  const enc = encodeURIComponent
  async function request(path: string): Promise<unknown> {
    const send = () =>
      fetch(`${base}${path}`, {
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: { Accept: 'application/json' },
      })
    let response = await send()
    if (response.status === 401 && refresh) {
      await response.body?.cancel()
      await refresh()
      response = await send()
    }
    const value: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(value))
    return value
  }
  return {
    directory: async () => studentResultsDirectorySchema.parse(await request('/directory')),
    overview: async (student: string, course?: string) =>
      studentResultsOverviewSchema.parse(
        await request(`/${enc(student)}/overview${course ? `?course=${enc(course)}` : ''}`),
      ),
    lesson: async (student: string, course: string, number: number) =>
      studentResultsLessonSchema.parse(
        await request(`/${enc(student)}/lessons/${enc(course)}/${number}`),
      ),
    history: async (student: string, problem: string, cursor?: string) =>
      studentResultHistorySchema.parse(
        await request(
          `/${enc(student)}/problems/${enc(problem)}/history${cursor ? `?cursor=${enc(cursor)}` : ''}`,
        ),
      ),
    condition: async (student: string, problem: string, revision: string) =>
      studentResultsConditionSchema.parse(
        await request(`/${enc(student)}/problems/${enc(problem)}/condition/${enc(revision)}`),
      ),
  }
}
export type StudentResultsClient = ReturnType<typeof createStudentResultsClient>
