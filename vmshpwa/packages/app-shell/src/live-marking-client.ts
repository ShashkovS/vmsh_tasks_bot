import {
  ApiResponseError,
  apiErrorSchema,
  parseRuntimeConfigForAudience,
  liveBoardSchema,
  liveConditionSchema,
  liveCatalogSchema,
  liveCellsSchema,
  liveDirectorySchema,
  liveHistorySchema,
  liveVisitsSchema,
  liveReceiptSchema,
  liveSessionReceiptSchema,
  liveVisitReceiptSchema,
  liveCommandSchema,
  type RuntimeConfig,
  type LiveContext,
  type LiveCommand,
  type LiveCells,
} from '@vmsh/contracts'

// live-marking.md: HTTP writes with idempotency; existing WS invalidates scoped reads.
export function createLiveMarkingClient(runtime: RuntimeConfig, refresh?: () => Promise<unknown>) {
  const base = `${parseRuntimeConfigForAudience('staff', runtime).apiBase}/live-marking`
  async function request(path: string, body?: unknown): Promise<unknown> {
    const send = () =>
      fetch(`${base}${path}`, {
        method: body === undefined ? 'GET' : 'POST',
        credentials: 'include',
        cache: 'no-store',
        redirect: 'error',
        headers: {
          Accept: 'application/json',
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        keepalive: body !== undefined,
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
  const query = (context: LiveContext) =>
    new URLSearchParams(
      Object.entries(context).filter(
        (pair): pair is [string, string] => typeof pair[1] === 'string',
      ),
    ).toString()
  return {
    catalog: async () => liveCatalogSchema.parse(await request('/catalog')),
    directory: async (courseId: string) =>
      liveDirectorySchema.parse(
        await request(`/directory?courseId=${encodeURIComponent(courseId)}`),
      ),
    board: async (context: LiveContext) =>
      liveBoardSchema.parse(await request(`/board?${query(context)}`)),
    condition: async (context: LiveContext, problemId: string) =>
      liveConditionSchema.parse(
        await request(`/condition?${query(context)}&problemId=${encodeURIComponent(problemId)}`),
      ),
    cells: async (context: LiveContext, previous?: LiveCells) =>
      liveCellsSchema.parse(
        await request(
          `/cells?${query(context)}${previous ? `&after=${previous.cursor}&scope=${previous.scope}` : ''}`,
        ),
      ),
    history: async (context: LiveContext) =>
      liveHistorySchema.parse(await request(`/history?${query(context)}`)),
    visits: async (sessionId: string) =>
      liveVisitsSchema.parse(await request(`/sessions/${encodeURIComponent(sessionId)}/visits`)),
    start: async (courseId: string, sessionId = crypto.randomUUID()) =>
      liveSessionReceiptSchema.parse(await request('/sessions', { courseId, sessionId })),
    finish: async (sessionId: string) =>
      liveSessionReceiptSchema.parse(
        await request(`/sessions/${encodeURIComponent(sessionId)}/finish`, {}),
      ),
    visit: async (context: LiveContext) =>
      liveVisitReceiptSchema.parse(await request('/visits', context)),
    execute: async (command: LiveCommand) =>
      liveReceiptSchema.parse(await request('/operations', liveCommandSchema.parse(command))),
  }
}
export type LiveMarkingClient = ReturnType<typeof createLiveMarkingClient>
