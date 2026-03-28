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

## 6. Survey and campaign operations
- An admin must be able to create, enable, disable, and assign surveys.
- The application must support token-based or audience-based survey assignment if the current operating model depends on it.

## 7. Moderation and community governance
- An admin must be able to moderate public community spaces.
- Admin moderation must cover:
  - deleting or hiding inappropriate content;
  - locking threads;
  - pinning important announcements;
  - enforcing the rule against publishing full solutions before allowed time;
  - handling abuse or spam.

## 8. Reporting and statistics
- An admin must have access to operational statistics for the week and historically.
- Reporting must cover:
  - submission counts;
  - checked versus pending volumes;
  - teacher workload;
  - oral activity;
  - publication reach if tracked;
  - lesson progress and plus counts where relevant.

## 9. Audit and troubleshooting
- An admin must be able to investigate what happened for a specific student, teacher, task, lesson, or publication.
- The application must provide a usable audit trail for:
  - important state changes;
  - results saved;
  - moderation actions;
  - broadcasts;
  - imports;
  - role changes.

## 10. Operational continuity
- Admin operations must not depend on obscure chat commands or operator memory alone.
- The web application must replace command knowledge with explicit interfaces, permissions, and status screens.
