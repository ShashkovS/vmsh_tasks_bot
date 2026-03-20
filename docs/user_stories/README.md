# User Stories For Web Migration

This folder captures the current product behavior of the bot in a form suitable for web migration planning.

Sources used:
- current handlers and models;
- existing operator docs;
- trace logs collected during March 2026;
- current cleaned database snapshot.

Conventions:
- stories are grouped by role and by workflow, not by source file;
- each story is phrased from the actor's point of view;
- notes include important constraints, edge cases, and migration implications.

Important assumptions:
- `waitlist` exists in code but is not treated as a live product flow now;
- current live oral flow is centered around Zoom sessions and manual oral marking;
- admin is an elevated teacher role;
- stories reflect current behavior, including some awkward legacy UX, because migration must preserve capabilities before redesigning them.

Files:
- `teacher_access_and_mode.md`
- `student_access_and_setup.md`
- `student_tasks_and_submission.md`
- `student_feedback_and_progress.md`
- `teacher_written_review.md`
- `teacher_oral_and_zoom.md`
- `teacher_student_management.md`
- `admin_cycle_and_data.md`
- `admin_communications_and_surveys.md`
