export function problemReviewDraftStorageKey(
  draftNamespace: string,
  kind: 'matching' | 'metadata',
  groupLessonId: string,
  revisionId: string,
): string {
  // `draftNamespace` is runtime-instance + Staff account. Phase 10 requires
  // one shared browser profile never to expose one teacher's unsaved grid to
  // another account; the entity and revision keep stale drafts recoverable.
  return `vmshpwa:staff:content:${draftNamespace}:${kind}:v1:${groupLessonId}:${revisionId}`
}
