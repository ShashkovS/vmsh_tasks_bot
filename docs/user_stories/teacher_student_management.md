# Teacher Stories: Student Management, Lookup, Inspection

## Scope
Stories in this file cover operational commands that teachers use to find students, inspect status, and adjust student settings.

## Stories

### T-MGMT-01. Find a student by fuzzy surname or token
As a teacher, I want to search students approximately, so that I can find the right child even with typos or partial names.

Main flow:
- Teacher runs `/find_student query`.
- The system ranks students by fuzzy similarity.
- The bot returns the best matches with group code, token, and online/school icon.

### T-MGMT-02. Change a student's group
As a teacher, I want to move a student into another allowed group, so that I can reflect pedagogical decisions or administrative corrections.

Main flow:
- Teacher runs `/set_group token group`.
- The system checks that the target group exists and is accessible to both teacher and student.
- The student's profile is updated.
- The teacher gets confirmation.
- The student may receive a switch message and a refreshed keyboard.

### T-MGMT-03. Change a student's online/school mode manually
As a teacher, I want to override a student's attendance mode, so that records match the real context even if the student forgot to update it.

Main flow:
- Teacher runs `/set_online token online|school`.
- The student's profile is updated.
- The teacher sees confirmation.

### T-MGMT-04. Inspect a student's current-lesson results
As a teacher, I want to see what a student submitted in the current lesson, so that I can understand their current state before helping them.

Main flow:
- Teacher runs `/student_results token`.
- The bot prints the student's submissions for the current lesson.

### T-MGMT-05. Inspect a student's full result history
As a teacher, I want to see the student's full result history, so that I can diagnose long-term patterns or resolve disputes.

Main flow:
- Teacher runs `/all_student_results token` or `/asr token`.
- The bot prints the student's submissions grouped by lesson.

### T-MGMT-06. Open the teacher statistics web view
As a teacher, I want a direct link and password for the statistics web page, so that I can use the browser-based dashboard without searching for credentials elsewhere.

Main flow:
- Teacher runs `/statw`.
- The bot sends the `/stat` URL and the password/token needed for the web page.

### T-MGMT-07. See aggregate statistics for the current lesson
As a teacher, I want to request current-lesson statistics in chat, so that I can quickly understand overall progress without leaving Telegram.

Main flow:
- Teacher runs `/stat`.
- The bot sends lesson-level statistics in one or more messages.

### T-MGMT-08. Recheck all automatic answers for a problem after fixing the checker
As a teacher or admin, I want to rerun test validation for one problem across all historical answers, so that checker bug fixes can be propagated.

Main flow:
- Teacher runs `/problem_recheck problem_ref`.
- The system recomputes verdicts for all saved answers to that problem.
- Changed student keyboards are refreshed.

### T-MGMT-09. Assign or inspect game command affiliation
As a teacher, I want to set a student's game command, so that the game layer stays aligned with the student's actual assignment.

Main flow:
- Teacher runs `/set_game_command [token] command_id`.
- The system updates the student's game assignment.
- The teacher receives confirmation.
