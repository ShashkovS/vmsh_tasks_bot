import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  adminCourseCatalogQueryKey,
  adminCourseCatalogResponseSchema,
  adminCourseScheduleDraftResponseSchema,
  adminCourseScheduleQueryKey,
  adminCourseScheduleResponseSchema,
  adminCourseScheduleRuleResponseSchema,
  adminCourseResponseSchema,
  adminGroupScheduleOverrideResponseSchema,
  adminGroupScheduleQueryKey,
  adminGroupScheduleResponseSchema,
  adminGroupResponseSchema,
  apiErrorSchema,
  createAdminCourseRequestSchema,
  parseRuntimeConfigForAudience,
  publicIdSchema,
  saveAdminGroupRequestSchema,
  saveAdminGroupScheduleOverrideSchema,
  saveAdminCourseScheduleRuleSchema,
  updateAdminCourseRequestSchema,
  type AdminCourseCatalogResponse,
  type AdminCourseResponse,
  type AdminCourseScheduleDraftResponse,
  type AdminCourseScheduleResponse,
  type AdminCourseScheduleRuleResponse,
  type AdminGroupScheduleOverrideResponse,
  type AdminGroupScheduleResponse,
  type AdminGroupResponse,
  type CreateAdminCourseRequest,
  type PrincipalQueryScope,
  type RuntimeConfig,
  type SaveAdminGroupRequest,
  type SaveAdminGroupScheduleOverride,
  type SaveAdminCourseScheduleRule,
  type UpdateAdminCourseRequest,
} from '@vmsh/contracts'

export interface AdminCourseClient {
  list(options?: { seasonId?: string; signal?: AbortSignal }): Promise<AdminCourseCatalogResponse>
  createCourse(input: CreateAdminCourseRequest): Promise<AdminCourseResponse>
  updateCourse(
    courseId: string,
    version: number,
    input: UpdateAdminCourseRequest,
  ): Promise<AdminCourseResponse>
  createGroup(courseId: string, input: SaveAdminGroupRequest): Promise<AdminGroupResponse>
  updateGroup(
    groupId: string,
    version: number,
    input: SaveAdminGroupRequest,
  ): Promise<AdminGroupResponse>
  getCourseSchedule(courseId: string, signal?: AbortSignal): Promise<AdminCourseScheduleResponse>
  createCourseScheduleDraft(
    courseId: string,
    input: SaveAdminCourseScheduleRule,
  ): Promise<AdminCourseScheduleDraftResponse>
  confirmCourseScheduleRule(
    ruleId: string,
    version: number,
  ): Promise<AdminCourseScheduleRuleResponse>
  getGroupSchedule(groupId: string, signal?: AbortSignal): Promise<AdminGroupScheduleResponse>
  createGroupScheduleDraft(
    groupId: string,
    input: SaveAdminGroupScheduleOverride,
  ): Promise<AdminGroupScheduleOverrideResponse>
  confirmGroupScheduleOverride(
    overrideId: string,
    version: number,
  ): Promise<AdminGroupScheduleOverrideResponse>
}

export function createAdminCourseClient(
  runtime: RuntimeConfig,
  options: {
    fetchImplementation?: typeof globalThis.fetch
    refreshSession?: () => Promise<unknown>
  } = {},
): AdminCourseClient {
  const configured = parseRuntimeConfigForAudience('staff', runtime)
  const fetchImplementation = options.fetchImplementation ?? globalThis.fetch

  async function request(path: string, init: RequestInit): Promise<unknown> {
    const send = () =>
      fetchImplementation(`${configured.apiBase}${path}`, {
        cache: 'no-store',
        credentials: 'include',
        redirect: 'error',
        ...init,
        headers: {
          Accept: 'application/json',
          ...(init.body === undefined ? {} : { 'Content-Type': 'application/json' }),
          ...init.headers,
        },
      })
    let response = await send()
    if (response.status === 401 && options.refreshSession) {
      await response.body?.cancel()
      await options.refreshSession()
      response = await send()
    }
    const payload: unknown = await response.json()
    if (!response.ok) throw new ApiResponseError(response.status, apiErrorSchema.parse(payload))
    return payload
  }

  return {
    async list({ seasonId, signal } = {}) {
      const query = new URLSearchParams()
      if (seasonId !== undefined) query.set('seasonId', publicIdSchema.parse(seasonId))
      const suffix = query.size === 0 ? '' : `?${query}`
      return adminCourseCatalogResponseSchema.parse(
        await request(`/courses${suffix}`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async createCourse(input) {
      return adminCourseResponseSchema.parse(
        await request('/courses', {
          method: 'POST',
          body: JSON.stringify(createAdminCourseRequestSchema.parse(input)),
        }),
      )
    },
    async updateCourse(rawCourseId, version, input) {
      const courseId = publicIdSchema.parse(rawCourseId)
      return adminCourseResponseSchema.parse(
        await request(`/courses/${encodeURIComponent(courseId)}`, {
          method: 'PUT',
          headers: { 'If-Match': `"${courseId}:v${version}"` },
          body: JSON.stringify(updateAdminCourseRequestSchema.parse(input)),
        }),
      )
    },
    async createGroup(rawCourseId, input) {
      const courseId = publicIdSchema.parse(rawCourseId)
      return adminGroupResponseSchema.parse(
        await request(`/courses/${encodeURIComponent(courseId)}/groups`, {
          method: 'POST',
          body: JSON.stringify(saveAdminGroupRequestSchema.parse(input)),
        }),
      )
    },
    async updateGroup(rawGroupId, version, input) {
      const groupId = publicIdSchema.parse(rawGroupId)
      return adminGroupResponseSchema.parse(
        await request(`/groups/${encodeURIComponent(groupId)}`, {
          method: 'PUT',
          headers: { 'If-Match': `"${groupId}:v${version}"` },
          body: JSON.stringify(saveAdminGroupRequestSchema.parse(input)),
        }),
      )
    },
    async getCourseSchedule(rawCourseId, signal) {
      const courseId = publicIdSchema.parse(rawCourseId)
      return adminCourseScheduleResponseSchema.parse(
        await request(`/courses/${encodeURIComponent(courseId)}/schedule-rules`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async createCourseScheduleDraft(rawCourseId, input) {
      const courseId = publicIdSchema.parse(rawCourseId)
      return adminCourseScheduleDraftResponseSchema.parse(
        await request(`/courses/${encodeURIComponent(courseId)}/schedule-rules`, {
          method: 'PUT',
          body: JSON.stringify(saveAdminCourseScheduleRuleSchema.parse(input)),
        }),
      )
    },
    async confirmCourseScheduleRule(rawRuleId, version) {
      const ruleId = publicIdSchema.parse(rawRuleId)
      return adminCourseScheduleRuleResponseSchema.parse(
        await request(`/course-schedule-rules/${encodeURIComponent(ruleId)}/confirm`, {
          method: 'POST',
          headers: { 'If-Match': `"${ruleId}:v${version}"` },
          body: JSON.stringify({ schemaVersion: 1 }),
        }),
      )
    },
    async getGroupSchedule(rawGroupId, signal) {
      const groupId = publicIdSchema.parse(rawGroupId)
      return adminGroupScheduleResponseSchema.parse(
        await request(`/groups/${encodeURIComponent(groupId)}/schedule-overrides`, {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async createGroupScheduleDraft(rawGroupId, input) {
      const groupId = publicIdSchema.parse(rawGroupId)
      return adminGroupScheduleOverrideResponseSchema.parse(
        await request(`/groups/${encodeURIComponent(groupId)}/schedule-overrides`, {
          method: 'PUT',
          body: JSON.stringify(saveAdminGroupScheduleOverrideSchema.parse(input)),
        }),
      )
    },
    async confirmGroupScheduleOverride(rawOverrideId, version) {
      const overrideId = publicIdSchema.parse(rawOverrideId)
      return adminGroupScheduleOverrideResponseSchema.parse(
        await request(`/group-schedule-overrides/${encodeURIComponent(overrideId)}/confirm`, {
          method: 'POST',
          headers: { 'If-Match': `"${overrideId}:v${version}"` },
          body: JSON.stringify({ schemaVersion: 1 }),
        }),
      )
    },
  }
}

export function useAdminCourseCatalogQuery(
  client: AdminCourseClient,
  principal: PrincipalQueryScope,
  seasonId?: string,
) {
  return useQuery({
    queryKey: adminCourseCatalogQueryKey(principal, seasonId),
    queryFn: ({ signal }) => client.list({ ...(seasonId ? { seasonId } : {}), signal }),
  })
}

export function useAdminCourseScheduleQuery(
  client: AdminCourseClient,
  principal: PrincipalQueryScope,
  courseId: string | null,
) {
  return useQuery({
    queryKey:
      courseId === null
        ? ['admin-course-schedule', 'disabled']
        : adminCourseScheduleQueryKey(principal, courseId),
    queryFn: ({ signal }) => client.getCourseSchedule(courseId!, signal),
    enabled: courseId !== null,
  })
}

export function useAdminGroupScheduleQuery(
  client: AdminCourseClient,
  principal: PrincipalQueryScope,
  groupId: string | null,
) {
  return useQuery({
    queryKey:
      groupId === null
        ? ['admin-group-schedule', 'disabled']
        : adminGroupScheduleQueryKey(principal, groupId),
    queryFn: ({ signal }) => client.getGroupSchedule(groupId!, signal),
    enabled: groupId !== null,
  })
}
