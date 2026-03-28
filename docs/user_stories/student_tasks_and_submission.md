# Student Stories: Tasks, Attempts, Submission

## Scope
Stories in this file cover browsing lessons, choosing tasks, solving tests, sending written solutions, and handling oral-task entry points.

## Stories

### S-TASK-01. Open the latest lesson by default
As a student, I want the main screen to show the latest active lesson first, so that I can start with the current weekly material.

Main flow:
- Student opens the main keyboard.
- The system resolves the latest lesson number for the current group.
- The keyboard shows the problems of that lesson.

### S-TASK-02. Browse older lessons
As a student, I want to open the list of all available lessons and switch to an older lesson, so that I can revisit past material.

Main flow:
- Student opens the "all lessons" view.
- The bot shows the list of available lesson numbers for the current group.
- Student selects a lesson.
- The task keyboard is rebuilt for that lesson.

### S-TASK-03. Select a task and get the correct input UI
As a student, I want the bot to adapt the next step to the selected task type, so that I always know how to submit a valid answer.

Main flow:
- Student clicks a task in the keyboard.
- The system resolves the task and checks access.
- Depending on task type, the bot opens one of the dedicated flows:
  - test answer by text;
  - test answer by predefined options;
  - written submission by text/photo/file;
  - oral task via Zoom instructions.

### S-TASK-04. Answer a test problem with free text
As a student, I want to send a text answer to a test problem, so that the bot can check it immediately.

Main flow:
- Student selects a test problem that expects free-form text.
- The bot shows answer-format guidance and a cancel button.
- Student sends the answer.
- The bot validates the answer format and checks correctness.
- The bot saves the result and returns the student to the task list.

Notes:
- Validation rules may come from built-in answer types or per-problem regex.
- Some problems use a custom Python checker rather than a plain answer comparison.

### S-TASK-05. Answer a test problem by choosing one option
As a student, I want to answer some test problems by clicking a variant, so that I do not have to type predefined options manually.

Main flow:
- Student selects a multiple-choice or weekday-style test problem.
- The bot shows a button keyboard with options.
- Student presses one option.
- The bot checks the selected answer and saves the result.

### S-TASK-06. Get immediate feedback on a test answer
As a student, I want to see whether a test answer is correct or wrong right after submission, so that I can continue working without waiting for a teacher.

Main flow:
- Student submits a test answer.
- The bot stores a result with a positive or negative verdict.
- The bot sends a congratulation or error message.
- The task keyboard is shown again.

Notes:
- There is also a config mode where the bot may hide correctness details after submission; the capability exists and should remain configurable.

### S-TASK-07. Be told when my answer format is invalid
As a student, I want a clear validation message when I send an answer in the wrong format, so that I can fix the format instead of guessing.

Main flow:
- Student sends an answer that does not match the required format.
- The bot does not save a normal result.
- The bot sends the problem-specific validation error or option hint.

### S-TASK-08. Be rate-limited on excessive guessing
As a student, I want the system to stop me after too many attempts, so that brute-force answering is discouraged consistently.

Main flow:
- Student keeps sending test answers to the same problem.
- The system counts attempts per hour and per day.
- After the configured threshold, the bot refuses further attempts and returns the student to the main state.

### S-TASK-09. Submit a written solution as text
As a student, I want to send a textual written solution, so that a teacher can review my reasoning later.

Main flow:
- Student selects a written problem.
- The bot asks for text or photo.
- Student sends text.
- The system appends the message to the written discussion thread for that student and problem.
- The problem is enqueued for teacher review.

### S-TASK-10. Submit a written solution as photo or document
As a student, I want to send one or more images or a document with my written work, so that I can submit handwritten solutions.

Main flow:
- Student selects a written problem.
- Student sends photo(s) or a file.
- The bot stores metadata, may optionally save files to disk, appends the message to the discussion thread, and enqueues the task.

Notes:
- Media groups are explicitly supported and stitched together by `media_group_id`.
- Oversized files can be rejected.

### S-TASK-11. Submit several messages as one written discussion
As a student, I want to send follow-up comments or corrected versions for the same written problem, so that the teacher sees the whole context.

Main flow:
- Student stays in the written-submission state.
- Student sends several messages or files.
- Each message is appended to the per-problem discussion.
- The queue entry remains attached to the same problem.

### S-TASK-12. Cancel a task submission
As a student, I want to cancel the current answer flow, so that I can safely go back to the task list without sending junk.

Main flow:
- Student presses the cancel button while answering.
- The bot resets the state to the main task screen.
- The task keyboard is shown again.

### S-TASK-13. Be rejected when I send unsupported content in the wrong state
As a student, I want explicit feedback when I send a file or long text at the wrong time, so that I understand why the message was not accepted.

Main flow:
- Student sends an image, file, or long text while not being in the matching submission state.
- The bot explains that the content is not accepted in the current context.
- The bot restores the normal keyboard.

### S-TASK-14. Open an oral problem and receive the Zoom submission instructions
As a student, I want oral problems to lead me into the evening oral workflow instead of a normal text answer flow, so that I know how to submit them.

Main flow:
- Student selects an oral problem.
- The bot sends the Zoom-oriented instructions.
- The student returns to the main task state.

Notes:
- `waitlist` is present in legacy code but is not a live product flow now.
- Current live behavior is instruction-driven Zoom participation, not a bot-managed oral waitlist.
