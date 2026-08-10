# Карта «этап разработки → дизайн → Storybook»

Эта карта связывает вертикальные этапы `04`–`15` с UI-компонентами, page compositions и проверяемыми Storybook stories. Уже реализованные anchors ссылаются на файлы, а новые обязательные, но ещё не реализованные anchors помечены явно и не считаются proof. Карта дополняет [спецификацию страниц](../design-system/05-pages-and-flows.md), [матрицу Storybook](../design-system/06-storybook-and-testing.md) и [текущий design gate](../design-system/STATUS.md).

Storybook-ссылка ниже рассчитана на human runtime `http://localhost:6006`. Агент использует тот же `path`, заменяя порт на `6106`. Story — дизайн-контракт и fixture для разработки, но не доказательство готовности backend/API этапа. Если компонент или story переименовываются, одновременно обновляются эта карта, затронутый phase-файл и `dev/design-system/STATUS.md`.

<a id="phase-0-design"></a>

## Этап 0 — базовая линия

Компоненты и исходники:

- [`AppShell`](../../packages/app-shell/src/app-shell.tsx), [`PageLayout`, `PageSection`, `PageStatePanel`](../../packages/app-shell/src/page-layout.tsx);
- [semantic tokens и density](../../packages/ui/src/styles/globals.css), [Base UI/shadcn primitives](../../packages/ui/src/components);
- [production E2E shell/visual checks](../../e2e/shells.spec.ts) и [версионируемые baselines](../../e2e/__screenshots__/shells.spec.ts).

Storybook:

- [`Foundations/Tokens — Light`](http://localhost:6006/?path=/story/foundations-tokens--light), [`Dark`](http://localhost:6006/?path=/story/foundations-tokens--dark), [`Staff density`](http://localhost:6006/?path=/story/foundations-tokens--staff-density) — [source](../../packages/ui/src/styles/foundations.stories.tsx);
- [`UI/Primitives — Gallery`](http://localhost:6006/?path=/story/ui-primitives--gallery) — [source](../../packages/ui/src/components/primitives.stories.tsx);
- [`Product/App shells — Student mobile`](http://localhost:6006/?path=/story/product-app-shells--student-mobile), [`Family mobile`](http://localhost:6006/?path=/story/product-app-shells--family-mobile), [`Staff desktop`](http://localhost:6006/?path=/story/product-app-shells--staff-desktop), [`Loading/empty/error/offline`](http://localhost:6006/?path=/story/product-app-shells--loading-empty-error-offline) — [source](../../packages/app-shell/src/app-shell.stories.tsx).

<a id="phase-1-design"></a>

## Этап 1 — вход, сессии и права

Компоненты и страницы:

- [`StudentLoginPage`](../../apps/student/src/pages.tsx), [`FamilyLoginPage`](../../apps/family/src/pages.tsx), [`StaffLoginPage`](../../apps/staff/src/pages.tsx);
- [`AccountSessionManager`, `SessionManagementView`, `SessionOfflineWorkGuard`](../../packages/app-shell/src/session-management.tsx), подключённые к [`StudentProfilePage`](../../apps/student/src/pages.tsx) и [`FamilyProfilePage`](../../apps/family/src/pages.tsx); Staff profile route намеренно не придуман;
- domain-neutral [`Field`, `Input`, `Button`](../../packages/ui/src) и audience-specific login shells в [`student`](../../apps/student/src/routes/__root.tsx), [`family`](../../apps/family/src/routes/__root.tsx), [`staff`](../../apps/staff/src/routes/__root.tsx).

Storybook:

- [`Pages/Student — Login`](http://localhost:6006/?path=/story/pages-student--login), [`Login errors`](http://localhost:6006/?path=/story/pages-student--login-errors), [`Student login state matrix`](http://localhost:6006/?path=/story/pages-student--login-state-matrix) — [source](../../apps/student/src/pages.stories.tsx);
- [`Pages/Family — Login`](http://localhost:6006/?path=/story/pages-family--login), [`Family login state matrix`](http://localhost:6006/?path=/story/pages-family--login-state-matrix) — [source](../../apps/family/src/pages.stories.tsx);
- [`Pages/Staff — Login`](http://localhost:6006/?path=/story/pages-staff--login), [`Staff login state matrix`](http://localhost:6006/?path=/story/pages-staff--login-state-matrix), [`Teacher forbidden`](http://localhost:6006/?path=/story/pages-staff--teacher-forbidden) — [source](../../apps/staff/src/pages.stories.tsx);
- [`Product/Account sessions — Current device`](http://localhost:6006/?path=/story/product-account-sessions--current-device), [`Multiple devices`](http://localhost:6006/?path=/story/product-account-sessions--multiple-devices), [`Revoke pending`](http://localhost:6006/?path=/story/product-account-sessions--revoke-pending), [`Revoke error`](http://localhost:6006/?path=/story/product-account-sessions--revoke-error), [`Empty fails closed`](http://localhost:6006/?path=/story/product-account-sessions--empty-fails-closed), [`Corrupt fails closed`](http://localhost:6006/?path=/story/product-account-sessions--corrupt-fails-closed), [`Offline queue warning`](http://localhost:6006/?path=/story/product-account-sessions--logout-with-offline-queue-warning) — [source](../../packages/app-shell/src/session-management.stories.tsx);
- [`UI/Controls — Form validation`](http://localhost:6006/?path=/story/ui-controls--form-validation) — [source](../../packages/ui/src/components/controls.stories.tsx).

Три audience-specific state matrices являются exact Phase-1 proof: invalid,
rate-limited, account-unavailable, network/error и pending покрыты у Student,
Family и Staff; Student дополнительно показывает blocked, а reveal остаётся в
соответствующих Login stories.

Session UI уже имеет явный `SessionOfflineWorkGuard`: непустой outbox даёт
предупреждение, ошибка его чтения блокирует logout, cleanup вызывается после
server confirmation. Реальный Dexie adapter пока намеренно не подключён и
состояние очереди не имитируется. [`AuthenticationProvider`](../../packages/app-shell/src/auth-context.tsx)
уже реализует безопасное ядро: prior-verified transient offline state действует
только до абсолютного `sessionExpiresAt`, после чего private shell
размонтируется. Durable account-scoped cold start и его визуальные доказательства
ещё не реализованы: `OfflineUnverifiedSession`
(`packages/app-shell/src/offline-unverified-session.tsx`) и stories
`Product/Connectivity--offline-unverified-session`,
`Pages/Student--offline-cold-start`, `Pages/Family--offline-cold-start`.

<a id="phase-2-design"></a>

## Этап 2 — LaTeX-контент и публикация

Компоненты и страницы:

- [`SemanticMathDocument`, compatibility `MathHtml`](../../packages/content/src/index.tsx), bounded [`WebContentDocument v1`](../../packages/contracts/src/content.ts), [`ZoomableAssetFigure`](../../packages/content/src/zoomable-asset-figure.tsx), legacy prototype [`ZoomableFigure`](../../packages/product/src/zoomable-figure.tsx), [`HintDisclosure`, `SolutionDisclosure`](../../packages/product/src/conscious-disclosure.tsx);
- [`PublicationControl`, `LatexUpload`, `MissingAssetsFlow`](../../packages/product/src/staff-publishing.tsx), [`MetadataGrid`](../../packages/product/src/metadata-grid.tsx);
- [`StaffLessonsPage`, `StaffLessonDetailPage`](../../apps/staff/src/pages.tsx).

Storybook:

- [`Semantic document`](http://localhost:6006/?path=/story/product-mathematical-document--semantic-document), [`safe legacy HTML + client KaTeX`](http://localhost:6006/?path=/story/product-mathematical-document--client-ka-te-x), [`long sheet`](http://localhost:6006/?path=/story/product-mathematical-document--long-sheet), [`responsive table`](http://localhost:6006/?path=/story/product-mathematical-document--responsive-table), [`unsafe HTML rejected`](http://localhost:6006/?path=/story/product-mathematical-document--unsafe-html-rejected), [`invalid formula`](http://localhost:6006/?path=/story/product-mathematical-document--invalid-formula), [`missing asset`](http://localhost:6006/?path=/story/product-mathematical-document--missing-asset), [`zoom canvas`](http://localhost:6006/?path=/story/product-mathematical-document--zoom-canvas), [`dark theme`](http://localhost:6006/?path=/story/product-mathematical-document--dark-theme) — [source](../../packages/content/src/math-document.stories.tsx);
- [`Product/Reading — Figure`](http://localhost:6006/?path=/story/product-reading--figure), [`Task reading`](http://localhost:6006/?path=/story/product-reading--task-reading) — [source](../../packages/product/src/reading.stories.tsx);
- [`Product/Staff admin — Publication`](http://localhost:6006/?path=/story/product-staff-admin--publication), [`Publication scheduling`](http://localhost:6006/?path=/story/product-staff-admin--publication-scheduling), [`LaTeX`](http://localhost:6006/?path=/story/product-staff-admin--latex), [`Missing assets`](http://localhost:6006/?path=/story/product-staff-admin--missing-assets) — [source](../../packages/product/src/staff-admin.stories.tsx);
- [`Product/Staff data — Metadata`](http://localhost:6006/?path=/story/product-staff-data--metadata) — [source](../../packages/product/src/staff-data.stories.tsx);
- [`Pages/Staff — Lessons and publication`](http://localhost:6006/?path=/story/pages-staff--lessons-and-publication), [`Lesson import`](http://localhost:6006/?path=/story/pages-staff--lesson-import) — [source](../../apps/staff/src/pages.stories.tsx).

<a id="phase-3-design"></a>

## Этап 3 — Student «Сейчас» и чтение

Компоненты и страницы:

- [`StudentTodayPage`, `StudentTasksPage`, `StudentTaskPage`](../../apps/student/src/pages.tsx);
- [`TaskListItem`](../../packages/product/src/task-list-item.tsx), [`ProblemHeader`](../../packages/product/src/problem-header.tsx), [`DeadlineNotice`](../../packages/product/src/deadline-notice.tsx), [`MathDocument`](../../packages/content/src/index.tsx), [`ConsciousDisclosure`](../../packages/product/src/conscious-disclosure.tsx).

Storybook:

- [`Pages/Student — Today`](http://localhost:6006/?path=/story/pages-student--today), [`Tasks`](http://localhost:6006/?path=/story/pages-student--tasks) — [source](../../apps/student/src/pages.stories.tsx);
- [`Product/Task — List`](http://localhost:6006/?path=/story/product-task--list), [`Types`](http://localhost:6006/?path=/story/product-task--types) — [source](../../packages/product/src/task.stories.tsx);
- [`Product/Reading — Header`](http://localhost:6006/?path=/story/product-reading--header), [`Disclosure`](http://localhost:6006/?path=/story/product-reading--disclosure), [`Task reading`](http://localhost:6006/?path=/story/product-reading--task-reading) — [source](../../packages/product/src/reading.stories.tsx);
- [`Pages/Student — Page states`](http://localhost:6006/?path=/story/pages-student--page-states) — [source](../../apps/student/src/pages.stories.tsx).

<a id="phase-4-design"></a>

## Этап 4 — тестовые задачи

Компоненты и страницы:

- [`TestAnswer`](../../packages/product/src/test-answer.tsx), [answer specifications](../../packages/product/src/answer-spec.ts), [legacy-compatible validation](../../packages/product/src/answer-validation.ts);
- test-variant [`StudentTaskPage`](../../apps/student/src/pages.tsx).

Storybook:

- [`Scalar`](http://localhost:6006/?path=/story/product-test-answer--scalar), [`Tuple`](http://localhost:6006/?path=/story/product-test-answer--tuple), [`Partial compound format`](http://localhost:6006/?path=/story/product-test-answer--partial-compound-format), [`Weekday`](http://localhost:6006/?path=/story/product-test-answer--weekday), [`List`](http://localhost:6006/?path=/story/product-test-answer--list), [`Choice`](http://localhost:6006/?path=/story/product-test-answer--choice), [`Gallery`](http://localhost:6006/?path=/story/product-test-answer--gallery) — [source](../../packages/product/src/test-answer.stories.tsx);
- [`Pages/Student — Test task`](http://localhost:6006/?path=/story/pages-student--test-task) — [source](../../apps/student/src/pages.stories.tsx).

<a id="phase-5-design"></a>

## Этап 5 — письменная сдача

Компоненты и страницы:

- [`SubmissionComposer`](../../packages/product/src/submission-composer.tsx), [`AttachmentItem`, `AttachmentList`](../../packages/product/src/attachment.tsx);
- [`WrittenMaterialReassignment`](../../packages/product/src/written-material-reassignment.tsx)
  и typed Staff transport
  [`written-material-reassignment-client.ts`](../../packages/app-shell/src/written-material-reassignment-client.ts);
- [`SyncIndicator`](../../packages/product/src/sync-indicator.tsx), [`ConnectionBanner`](../../packages/product/src/connection-banner.tsx), written-variant [`StudentTaskPage`](../../apps/student/src/pages.tsx).

Storybook:

- [`Product/Submission — Composer`](http://localhost:6006/?path=/story/product-submission--composer), [`Offline`](http://localhost:6006/?path=/story/product-submission--offline), [`Closed`](http://localhost:6006/?path=/story/product-submission--closed) — [source](../../packages/product/src/submission.stories.tsx);
- [`Product/Connectivity — Sync`](http://localhost:6006/?path=/story/product-connectivity--sync), [`Connection`](http://localhost:6006/?path=/story/product-connectivity--connection) — [source](../../packages/product/src/connectivity.stories.tsx);
- [`Pages/Student — Written task`](http://localhost:6006/?path=/story/pages-student--written-task) — [source](../../apps/student/src/pages.stories.tsx).
- [`Product/Review — Material reassignment`](http://localhost:6006/?path=/story/product-review--material-reassignment),
  [`Post-review warning`](http://localhost:6006/?path=/story/product-review--material-reassignment-post-review)
  — [source](../../packages/product/src/written-material-reassignment.stories.tsx).

<a id="phase-6-design"></a>

## Этап 6 — проверка, тред и вопросы

Компоненты и страницы:

- [`ReviewQueue`](../../packages/product/src/review-queue.tsx), [`ThreePaneReview`](../../packages/product/src/three-pane-review.tsx), [`ReviewFeedbackForm`](../../packages/product/src/review-feedback-form.tsx), [`VerdictActions`](../../packages/product/src/review-verdict-actions.tsx), [`ReviewLock`](../../packages/product/src/review-lock.tsx);
- [`FeedbackThread`](../../packages/product/src/feedback-thread.tsx), [`AnnotationOverlay`](../../packages/product/src/annotation-overlay.tsx), [`ReactionPicker`](../../packages/product/src/reaction-picker.tsx);
- [`ReviewQueuePage`, `ReviewWorkspacePage`](../../apps/staff/src/pages.tsx), [`StudentResultPage`](../../apps/student/src/pages.tsx).

Обязательный, но ещё не реализованный anchor: расширенный `AnnotationOverlay` с
карандашом, ластиком, текстом, стрелкой, прямоугольником и поворотом, где
zoom/pan остаются только в viewer. Reusable material-reassignment UI уже
реализован в Phase 5; production review page wiring остаётся задачей этого
этапа.

Storybook:

- [`Product/Review — Queue`](http://localhost:6006/?path=/story/product-review--queue), [`Feedback plus`](http://localhost:6006/?path=/story/product-review--feedback-plus), [`Feedback guard`](http://localhost:6006/?path=/story/product-review--feedback-guard), [`Internal reaction hotkeys`](http://localhost:6006/?path=/story/product-review--feedback-reaction-shortcuts), [`Lock`](http://localhost:6006/?path=/story/product-review--lock), [`Workspace`](http://localhost:6006/?path=/story/product-review--workspace) — [source](../../packages/product/src/review.stories.tsx);
- [`Product/Feedback — Result`](http://localhost:6006/?path=/story/product-feedback--result), [`Teacher reaction`](http://localhost:6006/?path=/story/product-feedback--teacher-reaction), [`Annotations`](http://localhost:6006/?path=/story/product-feedback--annotations) — [source](../../packages/product/src/feedback.stories.tsx);
- [`Pages/Staff — Review queue`](http://localhost:6006/?path=/story/pages-staff--review-queue), [`Review workspace`](http://localhost:6006/?path=/story/pages-staff--review-workspace) — [source](../../apps/staff/src/pages.stories.tsx);
- [`Pages/Student — Result and thread`](http://localhost:6006/?path=/story/pages-student--result-and-thread) — [source](../../apps/student/src/pages.stories.tsx).

Требуемые stories, ещё не реализованные:
`Pages/Staff--review-material-reassignment`,
`Pages/Student--reassigned-material-timeline`,
`Product/Feedback--annotation-toolbox`,
`Product/Feedback--annotation-local-view`. Existing
`Product/Review--synonym-combined-case` нужен новый interaction proof: concrete
verdict target выбирается по последней server-received посылке, не по client
clock; этот proof ещё не реализован.

<a id="phase-7-design"></a>

## Этап 7 — устный контур и аудитории

Компоненты и страницы:

- oral/written [`SubmissionComposer`](../../packages/product/src/submission-composer.tsx) и oral-variant [`StudentTaskPage`](../../apps/student/src/pages.tsx);
- [`ClassroomCatalog`, `ClassroomGroupLayout`, `ClassroomStudentPlanner`, `ClassroomAssignmentStatus`](../../packages/product/src/classroom-planning.tsx);
- [`StaffClassroomsPage`](../../apps/staff/src/pages.tsx) и [runtime-validated classrooms route](../../apps/staff/src/routes/classrooms.tsx).

Storybook:

- [`Pages/Student — Oral task`](http://localhost:6006/?path=/story/pages-student--oral-task), [`Product/Submission — Oral written`](http://localhost:6006/?path=/story/product-submission--oral-written);
- [`Pages/Staff — Classrooms`](http://localhost:6006/?path=/story/pages-staff--classrooms) — [source](../../apps/staff/src/pages.stories.tsx);
- [`Catalog active`](http://localhost:6006/?path=/story/product-classrooms--catalog-active), [`Hidden and restore`](http://localhost:6006/?path=/story/product-classrooms--catalog-hidden-and-restore), [`Duplicate`](http://localhost:6006/?path=/story/product-classrooms--catalog-duplicate), [`Inherited layout`](http://localhost:6006/?path=/story/product-classrooms--layout-inherited-typical-counts), [`Materialized layout`](http://localhost:6006/?path=/story/product-classrooms--layout-materialized-and-confirm), [`Optimistic conflict`](http://localhost:6006/?path=/story/product-classrooms--layout-optimistic-conflict) — [source](../../packages/product/src/classroom-planning.stories.tsx);
- [`Plan preview`](http://localhost:6006/?path=/story/product-classrooms--plan-preview-and-confirm), [`Stale`](http://localhost:6006/?path=/story/product-classrooms--plan-stale), [`Reassigning/no room`](http://localhost:6006/?path=/story/product-classrooms--plan-reassigning-and-no-room), [`Local draft restored`](http://localhost:6006/?path=/story/product-classrooms--plan-local-draft-restored), [`15 rooms / 200 students`](http://localhost:6006/?path=/story/product-classrooms--plan-dense-two-hundred-students), [`Public states`](http://localhost:6006/?path=/story/product-classrooms--public-assignment-states), [`Mobile Staff`](http://localhost:6006/?path=/story/product-classrooms--mobile-staff-layout) — [source](../../packages/product/src/classroom-planning.stories.tsx).

Обязательно, но ещё не реализовано: `ClassroomDeliveryPreview` (`packages/product/src/classroom-delivery-preview.tsx`) с owner-confirmed per-channel aggregate counts и expandable partial lists. Implementation-default explicit retry повторяет только failed channel–recipient pairs без дублирования success; stories `Product/Classrooms--delivery-preview`, `--delivery-changed-after-send`, `--delivery-partial-report`, `--delivery-retry-failed`, `Pages/Staff--classroom-delivery`.

<a id="phase-8-design"></a>

## Этап 8 — новости, realtime и уведомления

Компоненты и страницы:

- [`TelegramRichPost`](../../packages/product/src/telegram-rich-post.tsx), [`ConnectionBanner`](../../packages/product/src/connection-banner.tsx), [`SyncIndicator`](../../packages/product/src/sync-indicator.tsx), [`UpdatePrompt`](../../packages/product/src/update-prompt.tsx), [`PushPermissionCard`](../../packages/product/src/push-permission-card.tsx);
- production [`RealtimeProvider`](../../packages/app-shell/src/realtime.tsx) и
  его domain-neutral state hook; unit proof:
  [`realtime-client.test.ts`](../../packages/app-shell/src/realtime-client.test.ts)
  и
  [`realtime-provider.test.tsx`](../../packages/app-shell/src/realtime-provider.test.tsx),
  browser proof:
  [`runtime-isolation.spec.ts`](../../e2e/runtime-isolation.spec.ts). Provider
  сам ничего не рисует; его visible consumers — `ConnectionBanner` и
  `SyncIndicator`;
- news/notification pages в [`Student`](../../apps/student/src/pages.tsx) и [`Family`](../../apps/family/src/pages.tsx).

Storybook:

- [`Product/News — Post`](http://localhost:6006/?path=/story/product-news--post), [`Previews`](http://localhost:6006/?path=/story/product-news--previews), [`Card`](http://localhost:6006/?path=/story/product-news--card), [`States`](http://localhost:6006/?path=/story/product-news--states) — [source](../../packages/product/src/news.stories.tsx);
- [`Product/Connectivity — Connection`](http://localhost:6006/?path=/story/product-connectivity--connection), [`Sync`](http://localhost:6006/?path=/story/product-connectivity--sync), [`Update`](http://localhost:6006/?path=/story/product-connectivity--update), [`Push`](http://localhost:6006/?path=/story/product-connectivity--push) — [source](../../packages/product/src/connectivity.stories.tsx);
- [`Pages/Student — News`](http://localhost:6006/?path=/story/pages-student--news), [`Notifications`](http://localhost:6006/?path=/story/pages-student--notifications) — [source](../../apps/student/src/pages.stories.tsx);
- [`Pages/Family — News`](http://localhost:6006/?path=/story/pages-family--news), [`Notifications`](http://localhost:6006/?path=/story/pages-family--notifications) — [source](../../apps/family/src/pages.stories.tsx).

<a id="phase-9-design"></a>

## Этап 9 — Family и прогресс

Компоненты и страницы:

- Family compositions в [`apps/family/src/pages.tsx`](../../apps/family/src/pages.tsx), production child/progress view и course achievements в [`apps/family/src/family-children-page.tsx`](../../apps/family/src/family-children-page.tsx);
- [`StudentProgress`](../../packages/product/src/student-progress.tsx), [`DistributionViolin`, `TrendWithBand`, `StrengthTrend`](../../packages/product/src/progress-charts.tsx), Student progress page в [`apps/student/src/pages.tsx`](../../apps/student/src/pages.tsx).
- Общие локализованные подписи initial achievement rules: [`course-achievements.ts`](../../packages/product/src/course-achievements.ts); неизвестные server codes не просачиваются в UI.

Storybook:

- [`Pages/Family — Current lesson`](http://localhost:6006/?path=/story/pages-family--current-lesson), [`Child switcher`](http://localhost:6006/?path=/story/pages-family--child-switcher), [`Child activity`](http://localhost:6006/?path=/story/pages-family--child-activity), [`Course achievements`](http://localhost:6006/?path=/story/pages-family--course-achievements), [`Read-only task`](http://localhost:6006/?path=/story/pages-family--read-only-task), [`Page states`](http://localhost:6006/?path=/story/pages-family--page-states) — [source](../../apps/family/src/pages.stories.tsx);
- [`Pages/Student — Progress`](http://localhost:6006/?path=/story/pages-student--progress) — [source](../../apps/student/src/pages.stories.tsx);
- [`Product/Progress — Charts`](http://localhost:6006/?path=/story/product-progress--charts), [`Confidence band`](http://localhost:6006/?path=/story/product-progress--confidence-band), [`Personal`](http://localhost:6006/?path=/story/product-progress--personal), [`Empty`](http://localhost:6006/?path=/story/product-progress--empty-state) — [source](../../packages/product/src/progress.stories.tsx). Ни один Student/Family chart не отмечает ребёнка внутри группового распределения.

<a id="phase-10-design"></a>

## Этап 10 — администрирование и отказ от Google

Компоненты и страницы:

- [`DenseDataTable`](../../packages/product/src/dense-data-table.tsx), [`MetadataGrid`](../../packages/product/src/metadata-grid.tsx), [`PublicationControl`, `LatexUpload`, `MissingAssetsFlow`](../../packages/product/src/staff-publishing.tsx);
- Staff admin compositions в [`apps/staff/src/pages.tsx`](../../apps/staff/src/pages.tsx); [`BroadcastComposer`](../../packages/product/src/staff-outreach.tsx) остаётся Phase-2 design placeholder, а не v1 Google-cutover scope.
- course/group-scoped [`StaffStatisticsView`](../../apps/staff/src/staff-statistics-page.tsx), runtime route [`/statistics`](../../apps/staff/src/routes/statistics.tsx), strict [`staff statistics contract`](../../packages/contracts/src/staff-statistics.ts) и transport [`staff-statistics-client.ts`](../../packages/app-shell/src/staff-statistics-client.ts). Страница использует готовый immutable analytics snapshot и не получает индивидуальные student rows.

Storybook:

- [`Product/Staff data — Data table`](http://localhost:6006/?path=/story/product-staff-data--data-table), [`Metadata`](http://localhost:6006/?path=/story/product-staff-data--metadata) — [source](../../packages/product/src/staff-data.stories.tsx);
- [`Product/Staff admin — Publication`](http://localhost:6006/?path=/story/product-staff-admin--publication), [`Publication scheduling`](http://localhost:6006/?path=/story/product-staff-admin--publication-scheduling), [`LaTeX`](http://localhost:6006/?path=/story/product-staff-admin--latex), [`Missing assets`](http://localhost:6006/?path=/story/product-staff-admin--missing-assets) — [source](../../packages/product/src/staff-admin.stories.tsx);
- [`Pages/Staff — Weekly dashboard`](http://localhost:6006/?path=/story/pages-staff--weekly-dashboard), [`Lessons and publication`](http://localhost:6006/?path=/story/pages-staff--lessons-and-publication), [`Lesson import`](http://localhost:6006/?path=/story/pages-staff--lesson-import), [`Broadcast phase two`](http://localhost:6006/?path=/story/pages-staff--broadcast-phase-two) — [source](../../apps/staff/src/pages.stories.tsx).
- [`Pages/Staff/Statistics — Historical course`](http://localhost:6006/?path=/story/pages-staff-statistics--historical-course), [`No completed run`](http://localhost:6006/?path=/story/pages-staff-statistics--no-completed-run) — [source](../../apps/staff/src/staff-statistics-page.stories.tsx). Violin является только Staff-агрегатом и не отмечает отдельного школьника.
- [`Pages/Staff/Dashboard — Current week`](http://localhost:6006/?path=/story/pages-staff-dashboard--current-week), [`Teacher scoped`](http://localhost:6006/?path=/story/pages-staff-dashboard--teacher-scoped), [`No current lessons`](http://localhost:6006/?path=/story/pages-staff-dashboard--no-current-lessons) — [production view](../../apps/staff/src/staff-dashboard-page.tsx), [stories](../../apps/staff/src/staff-dashboard-page.stories.tsx), [wire contract](../../packages/contracts/src/staff-dashboard.ts). Это реальная `/staff/`-сводка; старый `Pages/Staff--weekly-dashboard` остаётся только историческим prototype.

<a id="phase-11-design"></a>

## Этап 11 — hardening и запуск

Компоненты, tests и pages:

- [`AppShell`](../../packages/app-shell/src/app-shell.tsx), [`PageStatePanel`](../../packages/app-shell/src/page-layout.tsx), [`ConnectionBanner`](../../packages/product/src/connection-banner.tsx), [`UpdatePrompt`](../../packages/product/src/update-prompt.tsx);
- all-audience page states: [`Student`](../../apps/student/src/pages.stories.tsx), [`Family`](../../apps/family/src/pages.stories.tsx), [`Staff`](../../apps/staff/src/pages.stories.tsx);
- [Playwright production-preview suite](../../e2e/shells.spec.ts) и [Chromium/WebKit/Firefox baselines](../../e2e/__screenshots__/shells.spec.ts).

Storybook:

- [`Product/App shells — Loading/empty/error/offline`](http://localhost:6006/?path=/story/product-app-shells--loading-empty-error-offline) — [source](../../packages/app-shell/src/app-shell.stories.tsx);
- [`Product/Connectivity — Connection`](http://localhost:6006/?path=/story/product-connectivity--connection), [`Update`](http://localhost:6006/?path=/story/product-connectivity--update), [`Push`](http://localhost:6006/?path=/story/product-connectivity--push) — [source](../../packages/product/src/connectivity.stories.tsx);
- [`Pages/Student — Page states`](http://localhost:6006/?path=/story/pages-student--page-states), [`Pages/Family — Page states`](http://localhost:6006/?path=/story/pages-family--page-states), [`Pages/Staff — Page states`](http://localhost:6006/?path=/story/pages-staff--page-states).

## Многокурсовый инкремент

### Course context и страницы

- [`Product/Courses — Student multiple courses`](http://localhost:6006/?path=/story/product-courses--student-multiple-courses), [`Active and allowed groups`](http://localhost:6006/?path=/story/product-courses--active-and-allowed-groups) — [CourseCard/CourseContext/CourseGroupSwitcher](../../packages/product/src/course-context.tsx), [stories](../../packages/product/src/courses.stories.tsx);
- [`Pages/Student — Сейчас · несколько курсов`](http://localhost:6006/?path=/story/pages-student--today-multiple-courses), [`Задачи · курс и группа`](http://localhost:6006/?path=/story/pages-student--tasks-course-and-group), [`Прогресс · курсы раздельно`](http://localhost:6006/?path=/story/pages-student--progress-by-course) — [student pages](../../apps/student/src/pages.tsx);
- [`Pages/Family — Активность · несколько курсов`](http://localhost:6006/?path=/story/pages-family--activity-by-course) — [family pages](../../apps/family/src/pages.tsx).

### Staff settings

- [`Product/Staff admin — Course and group catalog`](http://localhost:6006/?path=/story/product-staff-admin--course-and-group-catalog), [`Independent schedules`](http://localhost:6006/?path=/story/product-staff-admin--independent-schedules), [`Telegram bindings`](http://localhost:6006/?path=/story/product-staff-admin--telegram-bindings) — [course admin](../../packages/product/src/course-admin.tsx), [stories](../../packages/product/src/multi-course-admin.stories.tsx);
- [`Pages/Staff — Курсы, группы и независимые настройки`](http://localhost:6006/?path=/story/pages-staff--course-and-group-administration) — [StaffCoursesPage](../../apps/staff/src/pages.tsx), route [`/courses`](../../apps/staff/src/routes/courses.tsx).

### Синонимы и проверка

- [`Product/Staff data — Synonym merge and split`](http://localhost:6006/?path=/story/product-staff-data--synonym-merge-and-split) — [preview](../../packages/product/src/synonym-context.tsx), [story](../../packages/product/src/synonym-data.stories.tsx);
- [`Product/Feedback — Synonym merged timeline`](http://localhost:6006/?path=/story/product-feedback--synonym-merged-timeline) — [timeline/story](../../packages/product/src/synonym-feedback.stories.tsx);
- [`Product/Review — Synonym combined case`](http://localhost:6006/?path=/story/product-review--synonym-combined-case) — [combined review story](../../packages/product/src/synonym-review.stories.tsx). Текущая story реализована, но required server-receive-time target assertion ещё не реализована.

### Очные события и progress

- [`Product/Classrooms — Multi-course inherited event`](http://localhost:6006/?path=/story/product-classrooms--multi-course-inherited-event) — [composer](../../packages/product/src/in-person-event.tsx), [story](../../packages/product/src/classroom-event.stories.tsx);
- [`Pages/Staff — Очное событие · несколько курсов`](http://localhost:6006/?path=/story/pages-staff--multi-course-classroom-event) — [StaffClassroomsPage](../../apps/staff/src/pages.tsx);
- Delivery stories и `ClassroomDeliveryPreview` из этапа 7 выше также обязаны работать в multi-course in-person event; **весь delivery increment ещё не реализован**. API contract: [`03-api-events-and-files.md`](03-api-events-and-files.md);
- [`Product/Progress — Courses separated`](http://localhost:6006/?path=/story/product-progress--courses-separated) — [story](../../packages/product/src/course-progress.stories.tsx), pure projection tests [multi-course-projection.test.ts](../../packages/product/src/multi-course-projection.test.ts).

Эти stories являются prototype proof только для интерфейса и детерминированной projection logic. Backend endpoints, migrations и production wiring закрываются соответствующими Phase 1–11.

## Публичная стартовая страница

- [`Product/Landing — Home`](http://localhost:6006/?path=/story/product-landing--home) — [LandingPage](../../apps/landing/src/landing-page.tsx), [story](../../apps/landing/src/landing-page.stories.tsx). Страница использует только публичные semantic tokens и содержит ссылки на `/student/` и `/family/`; Staff намеренно не показывается.
- Production bundle собирается из [`apps/landing`](../../apps/landing), публикуется в `landing/`, а root gateway/nginx обслуживает его через `/`.

## Правило использования карты в этапах

Перед началом frontend-части этапа разработчик:

1. открывает все перечисленные page/component stories и сверяет их с актуальным accepted gate;
2. фиксирует в phase proof точные story IDs, которые используются как fixtures;
3. при изменении поведения сначала обновляет authoritative product/development decision, затем компонент, story interaction test и эту карту;
4. не считает prototype callback или fixture в `pages.tsx` готовым API — production wiring и permission tests закрываются только внутри соответствующего вертикального этапа.
