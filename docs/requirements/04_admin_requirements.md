# Admin Requirements

## 1. Weekly cycle orchestration
- An admin must be able to manage the weekly state of the circle from one place.
- The admin workspace must expose:
  - current lesson;
  - publication state of tasks;
  - oral acceptance availability;
  - written submission availability;
  - hint publication state;
  - solution publication state;
  - current announcements and active banners if used.

## 2. Lesson and publication management
- An admin must be able to publish and unpublish:
  - lesson tasks;
  - hints;
  - solutions;
  - announcements;
  - statistics;
  - links and reference materials.
- Publications must support:
  - tags;
  - audience targeting;
  - scheduling;
  - preview before publish;
  - archive placement.

## 3. Broadcasts and announcements
- An admin must be able to send mass communications to:
  - all participants;
  - only students;
  - only teachers;
  - selected levels;
  - selected lessons;
  - community feed only.
- Broadcasts must support:
  - plain text and rich text;
  - link blocks;
  - silent versus attention-demanding delivery if such modes remain useful;
  - logging of delivery result.

## 4. User and role administration
- An admin must be able to:
  - grant or revoke teacher/admin access;
  - inspect user status;
  - correct wrong profile state;
  - set or repair student group/level data;
  - reset broken workflow state when necessary.
- Role changes must be audited.

## 5. Data sync and imports
- An admin must be able to run data refresh and import operations that exist today in service-command form.
- This includes at least:
  - sync of teachers;
  - sync of students;
  - sync of groups;
  - sync of problem metadata;
  - sync of bot or UI messages if still relevant;
  - mass import of results from external files or APIs.
- Imports must have validation feedback and dry-run where feasible.

## 6. Classroom catalog and in-person planning
- Only an admin may manage classrooms; a teacher must receive `403` from the same routes even if navigation is hidden.
- The application must separate:
  - one global, reusable classroom catalog;
  - a versioned effective room-to-group layout inherited between lessons;
  - a versioned student assignment plan for a particular lesson.
- Classroom names must be trimmed at the edges, remain non-empty, preserve internal whitespace, and be unique after Unicode NFKC plus case-insensitive normalization.
- Classrooms are archived/restored rather than hard-deleted. Renames are global corrections and retain audit history.
- Each classroom may belong to at most one group in a layout; one group may use any number of classrooms. Capacity and weighting are not part of the model.
- The assignment preview must keep a previous eligible room where possible and otherwise choose the least-loaded room in natural name order. Manual movement uses explicit select/move controls rather than drag-and-drop.
- A changed layout makes an existing plan stale. Confirmation must be blocked while an in-person student is unassigned, a student is assigned outside the current group, or one room mixes groups.
- Hiding an in-use room must immediately move affected current assignments to a visible reassigning state without changing historical lessons.
- Student and Family may read the published room assignment. Student receives PWA notifications for assignment, withdrawal, and reassignment; Family receives no classroom push.
- The initial migration may use a one-time dry-run import from the existing Excel export with `IDd`, `Уровень`, and `Аудитория`. This is not a permanent spreadsheet workflow.

## 7. Survey and campaign operations
- An admin must be able to create, enable, disable, and assign surveys.
- The application must support token-based or audience-based survey assignment if the current operating model depends on it.

## 8. Moderation and community governance
- An admin must be able to moderate public community spaces.
- Admin moderation must cover:
  - deleting or hiding inappropriate content;
  - locking threads;
  - pinning important announcements;
  - enforcing the rule against publishing full solutions before allowed time;
  - handling abuse or spam.

## 9. Reporting and statistics
- An admin must have access to operational statistics for the week and historically.
- Reporting must cover:
  - submission counts;
  - checked versus pending volumes;
  - teacher workload;
  - oral activity;
  - publication reach if tracked;
  - lesson progress and plus counts where relevant.

## 10. Audit and troubleshooting
- An admin must be able to investigate what happened for a specific student, teacher, task, lesson, or publication.
- The application must provide a usable audit trail for:
  - important state changes;
  - results saved;
  - moderation actions;
  - broadcasts;
  - imports;
  - role changes.

## 11. Operational continuity
- Admin operations must not depend on obscure chat commands or operator memory alone.
- The web application must replace command knowledge with explicit interfaces, permissions, and status screens.
