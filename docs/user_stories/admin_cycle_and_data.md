# Admin Stories: Weekly Cycle, Data, Operational Control

## Scope
Stories in this file cover data sync, weekly mode switching, mass state changes, and operational maintenance.

## Stories

### A-CYCLE-01. Refresh all spreadsheet-driven data at once
As an admin, I want to update all spreadsheet-driven entities in one command, so that the bot can be brought into sync before or during the weekly cycle.

Main flow:
- Admin runs `/update_all`.
- The system reloads groups, problems, students, teachers, settings, and UI messages from Google Sheets.
- The admin receives a completion message and any error list.

### A-CYCLE-02. Refresh one data domain independently
As an admin, I want to update only teachers, students, groups, problems, settings, or UI messages, so that I can perform targeted fixes without a full reload.

Main flow:
- Admin runs one of:
  - `/update_teachers`
  - `/update_students`
  - `/update_groups`
  - `/update_problems`
  - `/update_bot_settings`
  - `/update_ui_messages`
- The system reloads only that domain and reports errors.

### A-CYCLE-03. Publish dynamic group-switch commands after group updates
As an admin, I want group command changes to take effect after a groups sync, so that students can use the latest level/group commands without redeploy.

Main flow:
- Admin updates groups.
- The system registers or refreshes group switch commands for active groups.

### A-CYCLE-04. Switch the weekly problem mode from oral to written
As an admin, I want to convert current oral problems into written-before-oral ones, so that the weekly cycle can move from evening oral work into asynchronous written work.

Main flow:
- Admin runs `/oral2written [groups...]`.
- The system updates problem types for the selected groups or for all groups.

### A-CYCLE-05. Switch the weekly problem mode back from written to oral
As an admin, I want to restore written-before-oral tasks back to oral, so that the next cycle starts with the intended oral behavior.

Main flow:
- Admin runs `/written2oral [groups...]`.
- The system updates problem types accordingly.

### A-CYCLE-06. Wake all students into the active task state
As an admin, I want to return all students to the active task state and show them current tasks, so that a new active period can begin cleanly.

Main flow:
- Admin runs `/reset_state`.
- The system clears old keyboards, sets all students to `GET_TASK_INFO`, and pushes the current task keyboard where possible.

### A-CYCLE-07. Put all students into the sleeping state between circle periods
As an admin, I want to stop normal task intake and show a blocked screen to everyone, so that the bot behavior matches the calendar phase.

Main flow:
- Admin runs `/set_sleep_state` or `/set_sleep_state_quiet`.
- The system puts every student into the sleeping state.
- The bot sends the blocked-task screen, with optional quiet delivery.

Migration note:
- Trace logs show this is a real weekly orchestration action, not a dead command.

### A-CYCLE-08. Reset stuck written checks
As an admin, I want to clear the "being checked" flag from written tasks, so that abandoned teacher sessions do not permanently block the queue.

Main flow:
- Admin runs `/reset_checked`.
- The system clears the written-check lock state.

### A-CYCLE-09. Refresh student keyboards in place
As an admin, I want to refresh student keyboards without changing their underlying results, so that UI drift or stale buttons can be fixed remotely.

Main flow:
- Admin runs `/reset_keyboards` or `/reset_keyboards_force`.
- The system tries to edit existing keyboards, and optionally recreates missing ones.
- The admin receives a summary with updated, not updated, and error counts.

### A-CYCLE-10. Update teacher command menus in Telegram
As an admin, I want all teachers to receive the current bot command set, so that their Telegram UI stays aligned with the actual feature set.

Main flow:
- Admin runs `/update_teachers_commands`.
- The system updates Telegram bot commands for each teacher chat scope.

### A-CYCLE-11. Bootstrap admin rights with a secret
As a trusted operator, I want to turn my account into an admin using a secret, so that privileged operations can be granted without manual database edits.

Main flow:
- User runs `/set_admin secret`.
- If the secret matches config, the user is upgraded into the elevated role.

### A-CYCLE-12. Maintain the classroom catalog
As an admin, I want to maintain one reusable catalog of classrooms, so that room names are entered once and corrected consistently for every lesson.

Main flow:
- Admin opens `/staff/classrooms?tab=catalog`.
- Admin adds or renames a classroom, searches the catalog, and filters active or hidden rooms.
- The system trims outer whitespace, rejects an empty name, and detects duplicates using Unicode NFKC plus case-insensitive comparison while preserving the entered display name and internal spaces.
- Admin can hide and restore a room; hard delete is unavailable, and rename/archive/restore operations remain in audit history.

### A-CYCLE-13. Map classrooms to groups for an effective lesson
As an admin, I want to map active classrooms to groups and inherit the last confirmed mapping, so that a normal week needs no repetitive setup but a changed week can be prepared safely.

Main flow:
- Admin opens `/staff/classrooms?tab=groups&lesson=...` and sees the effective confirmed layout for that lesson.
- On the first edit, the system materializes a draft based on the inherited layout.
- Admin assigns zero or one group to each room; one group may use any number of rooms, but one room cannot contain students from different groups.
- Admin previews and confirms the layout with optimistic version checks. Rooms have no capacity or weight settings; displayed `6/5/2`-style values are actual room counts by group.

### A-CYCLE-14. Preview and confirm student classroom assignments
As an admin, I want to preview, adjust, recalculate, and confirm classroom assignments for an in-person lesson, so that every in-person student has a valid room before the circle starts.

Main flow:
- The system keeps a student's previous eligible room where possible, otherwise assigns the least-loaded room of the student's current group; ties use natural room-name order.
- Admin reviews students by group and room, moves a student with a select control, resolves `reassigning`/unassigned incidents, and confirms a versioned plan.
- A group or attendance-mode change triggers the same assignment rule immediately. A student who switches online loses the room assignment.
- Changing the room layout makes the current plan stale and requires preview, recalculation, and a new confirmation.
- Hiding an assigned room immediately withdraws affected current assignments and shows “Аудитория переназначается”; restoring the room does not restore assignments automatically and past lessons do not change.
- Confirmation is blocked by mixed groups, a student/room group mismatch, or any in-person student without a room. Unused active rooms are allowed.
- Student and Family see the confirmed result; only Student receives assignment, withdrawal, and reassignment notifications. Teacher access to classroom management is forbidden.
