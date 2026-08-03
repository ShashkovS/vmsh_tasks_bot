import { useQuery } from '@tanstack/react-query'

import {
  ApiResponseError,
  accountProvisioningPreviewResponseSchema,
  accountProvisioningReceiptSchema,
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
  adminStudentEnrollmentDirectoryResponseSchema,
  adminStudentEnrollmentResponseSchema,
  adminStudentEnrollmentsQueryKey,
  apiErrorSchema,
  createAdminCourseRequestSchema,
  createStudentAccountRequestSchema,
  createFamilyAccountRequestSchema,
  familyAccountLinkResponseSchema,
  familyProvisioningApplyRequestSchema,
  familyProvisioningPreviewRequestSchema,
  linkFamilyAccountRequestSchema,
  managedAccountResponseSchema,
  parseRuntimeConfigForAudience,
  problemImportPreviewResponseSchema,
  problemImportReceiptSchema,
  publicIdSchema,
  replaceStaffScopesRequestSchema,
  replaceManagedAccountCredentialRequestSchema,
  saveAdminGroupRequestSchema,
  saveAdminGroupScheduleOverrideSchema,
  saveAdminCourseScheduleRuleSchema,
  staffAccessDirectoryResponseSchema,
  staffAccessMemberResponseSchema,
  staffAccessQueryKey,
  studentProvisioningApplyRequestSchema,
  studentProvisioningPreviewRequestSchema,
  updateAdminCourseRequestSchema,
  updateAdminStudentEnrollmentRequestSchema,
  updateManagedAccountStatusRequestSchema,
  unlinkFamilyAccountResponseSchema,
  type AdminCourseCatalogResponse,
  type AdminCourseResponse,
  type AdminCourseScheduleDraftResponse,
  type AdminCourseScheduleResponse,
  type AdminCourseScheduleRuleResponse,
  type AdminGroupScheduleOverrideResponse,
  type AdminGroupScheduleResponse,
  type AdminGroupResponse,
  type AdminStudentEnrollmentDirectoryResponse,
  type AdminStudentEnrollmentResponse,
  type AccountProvisioningPreviewResponse,
  type AccountProvisioningReceipt,
  type CreateAdminCourseRequest,
  type CreateStudentAccountRequest,
  type CreateFamilyAccountRequest,
  type FamilyAccountLinkResponse,
  type FamilyProvisioningApplyRequest,
  type FamilyProvisioningPreviewRequest,
  type LinkFamilyAccountRequest,
  type ManagedAccountResponse,
  type ManagedAccountStatus,
  type PrincipalQueryScope,
  type ProblemImportPreviewResponse,
  type ProblemImportReceipt,
  type RuntimeConfig,
  type ReplaceStaffScopesRequest,
  type SaveAdminGroupRequest,
  type SaveAdminGroupScheduleOverride,
  type SaveAdminCourseScheduleRule,
  type StaffAccessDirectoryResponse,
  type StaffAccessMemberResponse,
  type StudentProvisioningApplyRequest,
  type StudentProvisioningPreviewRequest,
  type UpdateAdminCourseRequest,
  type UpdateAdminStudentEnrollmentRequest,
  type UnlinkFamilyAccountResponse,
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
  listStudentEnrollments(signal?: AbortSignal): Promise<AdminStudentEnrollmentDirectoryResponse>
  updateStudentEnrollment(
    enrollmentId: string,
    version: number,
    input: UpdateAdminStudentEnrollmentRequest,
  ): Promise<AdminStudentEnrollmentResponse>
  updateAccountStatus(
    accountId: string,
    version: number,
    status: ManagedAccountStatus,
  ): Promise<ManagedAccountResponse>
  replaceAccountCredential(
    accountId: string,
    version: number,
    credential: string,
  ): Promise<ManagedAccountResponse>
  createStudentAccount(
    studentId: string,
    input: CreateStudentAccountRequest,
  ): Promise<ManagedAccountResponse>
  createFamilyAccount(
    studentId: string,
    input: CreateFamilyAccountRequest,
  ): Promise<FamilyAccountLinkResponse>
  linkFamilyAccount(
    studentId: string,
    input: LinkFamilyAccountRequest,
  ): Promise<FamilyAccountLinkResponse>
  unlinkFamilyAccount(studentId: string, accountId: string): Promise<UnlinkFamilyAccountResponse>
  previewStudentAccounts(
    input: StudentProvisioningPreviewRequest,
  ): Promise<AccountProvisioningPreviewResponse>
  applyStudentAccounts(input: StudentProvisioningApplyRequest): Promise<AccountProvisioningReceipt>
  previewFamilyAccounts(
    input: FamilyProvisioningPreviewRequest,
  ): Promise<AccountProvisioningPreviewResponse>
  applyFamilyAccounts(input: FamilyProvisioningApplyRequest): Promise<AccountProvisioningReceipt>
  listStaffAccess(signal?: AbortSignal): Promise<StaffAccessDirectoryResponse>
  replaceStaffScopes(
    staffUserId: string,
    input: ReplaceStaffScopesRequest,
  ): Promise<StaffAccessMemberResponse>
  previewProblemImport(courseId: string, workbook: File): Promise<ProblemImportPreviewResponse>
  applyProblemImport(
    courseId: string,
    workbook: File,
    sourceSha256: string,
    previewSha256: string,
  ): Promise<ProblemImportReceipt>
  rollbackProblemImport(importId: string, expectedVersion: number): Promise<ProblemImportReceipt>
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
          ...(init.body === undefined || init.body instanceof FormData
            ? {}
            : { 'Content-Type': 'application/json' }),
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
    async listStudentEnrollments(signal) {
      return adminStudentEnrollmentDirectoryResponseSchema.parse(
        await request('/student-enrollments', {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async updateStudentEnrollment(rawEnrollmentId, version, input) {
      const enrollmentId = publicIdSchema.parse(rawEnrollmentId)
      return adminStudentEnrollmentResponseSchema.parse(
        await request(`/course-enrollments/${encodeURIComponent(enrollmentId)}`, {
          method: 'PUT',
          headers: { 'If-Match': `"${enrollmentId}:v${version}"` },
          body: JSON.stringify(updateAdminStudentEnrollmentRequestSchema.parse(input)),
        }),
      )
    },
    async updateAccountStatus(rawAccountId, version, status) {
      const accountId = publicIdSchema.parse(rawAccountId)
      return managedAccountResponseSchema.parse(
        await request(`/accounts/${encodeURIComponent(accountId)}/status`, {
          method: 'PATCH',
          headers: { 'If-Match': `"${accountId}:v${version}"` },
          body: JSON.stringify(
            updateManagedAccountStatusRequestSchema.parse({ schemaVersion: 1, status }),
          ),
        }),
      )
    },
    async replaceAccountCredential(rawAccountId, version, credential) {
      const accountId = publicIdSchema.parse(rawAccountId)
      return managedAccountResponseSchema.parse(
        await request(`/accounts/${encodeURIComponent(accountId)}/credential`, {
          method: 'POST',
          headers: { 'If-Match': `"${accountId}:v${version}"` },
          body: JSON.stringify(
            replaceManagedAccountCredentialRequestSchema.parse({
              schemaVersion: 1,
              credential,
            }),
          ),
        }),
      )
    },
    async createStudentAccount(rawStudentId, input) {
      const studentId = publicIdSchema.parse(rawStudentId)
      return managedAccountResponseSchema.parse(
        await request(`/students/${encodeURIComponent(studentId)}/student-account`, {
          method: 'POST',
          body: JSON.stringify(createStudentAccountRequestSchema.parse(input)),
        }),
      )
    },
    async createFamilyAccount(rawStudentId, input) {
      const studentId = publicIdSchema.parse(rawStudentId)
      return familyAccountLinkResponseSchema.parse(
        await request(`/students/${encodeURIComponent(studentId)}/family-accounts`, {
          method: 'POST',
          body: JSON.stringify(createFamilyAccountRequestSchema.parse(input)),
        }),
      )
    },
    async linkFamilyAccount(rawStudentId, input) {
      const studentId = publicIdSchema.parse(rawStudentId)
      return familyAccountLinkResponseSchema.parse(
        await request(`/students/${encodeURIComponent(studentId)}/family-links`, {
          method: 'POST',
          body: JSON.stringify(linkFamilyAccountRequestSchema.parse(input)),
        }),
      )
    },
    async unlinkFamilyAccount(rawStudentId, rawAccountId) {
      const studentId = publicIdSchema.parse(rawStudentId)
      const accountId = publicIdSchema.parse(rawAccountId)
      return unlinkFamilyAccountResponseSchema.parse(
        await request(
          `/students/${encodeURIComponent(studentId)}/family-links/${encodeURIComponent(accountId)}`,
          { method: 'DELETE' },
        ),
      )
    },
    async previewStudentAccounts(input) {
      return accountProvisioningPreviewResponseSchema.parse(
        await request('/imports/student-accounts/preview', {
          method: 'POST',
          body: JSON.stringify(studentProvisioningPreviewRequestSchema.parse(input)),
        }),
      )
    },
    async applyStudentAccounts(input) {
      return accountProvisioningReceiptSchema.parse(
        await request('/imports/student-accounts/apply', {
          method: 'POST',
          body: JSON.stringify(studentProvisioningApplyRequestSchema.parse(input)),
        }),
      )
    },
    async previewFamilyAccounts(input) {
      return accountProvisioningPreviewResponseSchema.parse(
        await request('/imports/family-accounts/preview', {
          method: 'POST',
          body: JSON.stringify(familyProvisioningPreviewRequestSchema.parse(input)),
        }),
      )
    },
    async applyFamilyAccounts(input) {
      return accountProvisioningReceiptSchema.parse(
        await request('/imports/family-accounts/apply', {
          method: 'POST',
          body: JSON.stringify(familyProvisioningApplyRequestSchema.parse(input)),
        }),
      )
    },
    async listStaffAccess(signal) {
      return staffAccessDirectoryResponseSchema.parse(
        await request('/staff-access', {
          method: 'GET',
          ...(signal === undefined ? {} : { signal }),
        }),
      )
    },
    async replaceStaffScopes(rawStaffUserId, input) {
      const staffUserId = publicIdSchema.parse(rawStaffUserId)
      return staffAccessMemberResponseSchema.parse(
        await request(`/staff-members/${encodeURIComponent(staffUserId)}/scopes`, {
          method: 'PUT',
          body: JSON.stringify(replaceStaffScopesRequestSchema.parse(input)),
        }),
      )
    },
    async previewProblemImport(rawCourseId, workbook) {
      const courseId = publicIdSchema.parse(rawCourseId)
      if (!(workbook instanceof File) || workbook.size < 1 || workbook.size > 10 * 1024 * 1024) {
        throw new TypeError('Problem workbook must be a non-empty XLSX file up to 10 MiB')
      }
      const body = new FormData()
      body.set('courseId', courseId)
      body.set('workbook', workbook, workbook.name)
      return problemImportPreviewResponseSchema.parse(
        await request('/problem-imports/preview', { method: 'POST', body }),
      )
    },
    async applyProblemImport(rawCourseId, workbook, sourceSha256, previewSha256) {
      const courseId = publicIdSchema.parse(rawCourseId)
      if (!(workbook instanceof File) || workbook.size < 1 || workbook.size > 10 * 1024 * 1024) {
        throw new TypeError('Problem workbook must be a non-empty XLSX file up to 10 MiB')
      }
      if (!/^[a-f0-9]{64}$/.test(sourceSha256) || !/^[a-f0-9]{64}$/.test(previewSha256)) {
        throw new TypeError('Problem import confirmation hashes are invalid')
      }
      const body = new FormData()
      body.set('courseId', courseId)
      body.set('workbook', workbook, workbook.name)
      body.set('sourceSha256', sourceSha256)
      body.set('previewSha256', previewSha256)
      return problemImportReceiptSchema.parse(
        await request('/problem-imports/apply', { method: 'POST', body }),
      )
    },
    async rollbackProblemImport(rawImportId, expectedVersion) {
      const importId = publicIdSchema.parse(rawImportId)
      if (!Number.isInteger(expectedVersion) || expectedVersion < 1) {
        throw new TypeError('Problem import version must be a positive integer')
      }
      return problemImportReceiptSchema.parse(
        await request(`/problem-imports/${encodeURIComponent(importId)}/rollback`, {
          method: 'POST',
          body: JSON.stringify({ expectedVersion }),
        }),
      )
    },
  }
}

export function useAdminCourseCatalogQuery(
  client: AdminCourseClient,
  principal: PrincipalQueryScope,
  seasonId?: string,
  enabled = true,
) {
  return useQuery({
    queryKey: adminCourseCatalogQueryKey(principal, seasonId),
    queryFn: ({ signal }) => client.list({ ...(seasonId ? { seasonId } : {}), signal }),
    enabled,
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

export function useAdminStudentEnrollmentsQuery(
  client: AdminCourseClient,
  principal: PrincipalQueryScope,
) {
  return useQuery({
    queryKey: adminStudentEnrollmentsQueryKey(principal),
    queryFn: ({ signal }) => client.listStudentEnrollments(signal),
  })
}

export function useStaffAccessQuery(
  client: AdminCourseClient,
  principal: PrincipalQueryScope,
  enabled = true,
) {
  return useQuery({
    queryKey: staffAccessQueryKey(principal),
    queryFn: ({ signal }) => client.listStaffAccess(signal),
    enabled,
  })
}
