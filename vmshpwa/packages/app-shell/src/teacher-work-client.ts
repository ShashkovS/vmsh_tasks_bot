import type { z } from 'zod'
import {
  ApiResponseError,
  apiErrorSchema,
  pwaFetch,
  parseRuntimeConfigForAudience,
  teacherWorkCatalogSchema,
  teacherWorkReportSchema,
  teacherWorkInputsSchema,
  teacherWorkPreviewSchema,
  teacherWorkDetailsSchema,
  teacherWorkCommandSchema,
  teacherWorkReceiptSchema,
  teacherWorkStatusSchema,
  type RuntimeConfig,
  type TeacherWorkCommand,
} from '@vmsh/contracts'

/** Staff only; docs/teacher-work.md, teacher-work-page.tsx. */
export function createTeacherWorkClient(
  runtime: RuntimeConfig,
  refreshSession: () => Promise<unknown>,
) {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  async function request<T>(
    path: string,
    schema: z.ZodType<T>,
    body?: unknown,
    signal?: AbortSignal,
  ): Promise<T> {
    const perform = () =>
      pwaFetch(`${configured.apiBase}/teacher-work${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        ...(signal ? { signal } : {}),
      })
    let response = await perform()
    if (response.status === 401) {
      await response.body?.cancel()
      await refreshSession()
      response = await perform()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return schema.parse(payload)
  }
  return {
    catalog: (signal?: AbortSignal) =>
      request('/catalog', teacherWorkCatalogSchema, undefined, signal),
    report: (
      courseId: string,
      filters: { first?: number | undefined; last?: number | undefined; q?: string | undefined },
      signal?: AbortSignal,
    ) =>
      request(
        `/report?${new URLSearchParams({
          courseId,
          ...Object.fromEntries(
            Object.entries(filters)
              .filter(([, v]) => v !== undefined)
              .map(([k, v]) => [k, String(v)]),
          ),
        })}`,
        teacherWorkReportSchema,
        undefined,
        signal,
      ),
    inputs: (courseId: string, signal?: AbortSignal) =>
      request(
        `/inputs?${new URLSearchParams({ courseId })}`,
        teacherWorkInputsSchema,
        undefined,
        signal,
      ),
    details: (courseId: string, cellKey: string, signal?: AbortSignal) =>
      request(
        `/details?${new URLSearchParams({ courseId, cellKey })}`,
        teacherWorkDetailsSchema,
        undefined,
        signal,
      ),
    preview: (courseId: string, rawText: string) =>
      request('/roster-preview', teacherWorkPreviewSchema, { courseId, rawText }),
    command: (body: TeacherWorkCommand) =>
      request('/command', teacherWorkReceiptSchema, teacherWorkCommandSchema.parse(body)),
    status: (courseId: string, signal?: AbortSignal) =>
      request(
        `/recalculate?${new URLSearchParams({ courseId })}`,
        teacherWorkStatusSchema,
        undefined,
        signal,
      ),
    recalculate: (courseId: string, idempotencyKey: string) =>
      request('/recalculate', teacherWorkStatusSchema, { courseId, idempotencyKey }),
  }
}
