# Web Product Requirements

This folder contains product requirements for a web application that fully replaces the current Telegram-based operating model of the circle.

Scope covered here:
- the current Telegram bot;
- the current Telegram channel with tagged publications;
- the current Telegram discussion group;
- the real weekly operating cycle of the circle;
- operator workflows for teachers and admins.

Sources behind these requirements:
- current codebase and database structure;
- collected trace logs from March 2026;
- existing user stories in `/Users/sergeyshashkov/repos/vmsh_tasks_bot/docs/user_stories`;
- weekly lifecycle map in `/Users/sergeyshashkov/repos/vmsh_tasks_bot/docs/weekly_livecycle`;
- public-facing circle rules and publication format.

Important assumptions:
- `waitlist` is not treated as a live product flow and is not a required capability for the new web product;
- Zoom or an equivalent video tool is still needed for synchronous oral сдача unless explicitly replaced later;
- admin is a higher-privilege teacher role;
- parents are part of the content/discussion audience even if they are not primary task submitters.

Files:
- `01_scope_and_principles.md`
- `02_student_requirements.md`
- `03_teacher_requirements.md`
- `04_admin_requirements.md`
- `05_content_and_community_requirements.md`
- `06_cross_cutting_requirements.md`
