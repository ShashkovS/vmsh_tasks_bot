# Student Requirements

## 1. Access and onboarding

### 1.1 Account access
- A student must be able to sign in without Telegram.
- The system must support invitation or password-based onboarding compatible with the current registration model.
- The student must be able to recover access without operator-level manual debugging.
- The application must clearly show whether the account is active, blocked, or missing required profile data.

### 1.2 Profile context
- A student must see:
  - own name;
  - current level;
  - current participation mode;
  - current lesson number;
  - current submission window status.
- A student must be able to switch level between beginner/continuing/expert equivalents.
- A student must be able to switch participation mode between online and in-school.
- The application must explain the consequences of mode changes when relevant.

## 2. Weekly home screen
- The student home screen must show the current weekly state.
- The student must immediately understand:
  - whether new tasks are already published;
  - whether oral acceptance is open now;
  - whether written submission is still open;
  - whether hints are published;
  - whether solutions are published;
  - whether the student is in online or in-school mode.
- The home screen must surface the next relevant action, not just static content.

## 3. Tasks and lesson navigation

### 3.1 Current lesson
- A student must be able to open the current lesson directly.
- The lesson page must list all tasks relevant to the student's current level.
- Each task must visibly indicate:
  - task number;
  - task type;
  - level;
  - whether the task is already attempted;
  - whether the task is solved;
  - whether review is pending;
  - whether there is teacher feedback.

### 3.2 Task detail
- A student must be able to open a task and see:
  - statement;
  - illustrations;
  - task type explanation;
  - submission rules;
  - current deadline state;
  - hints, if already published;
  - solutions, if already published.
- The task page must show the student's own history for that task:
  - submitted attempts;
  - timestamps;
  - verdicts;
  - teacher comments;
  - whether resubmission is possible.

### 3.3 Archive and search
- A student must be able to browse previous lessons.
- A student must be able to search by:
  - lesson;
  - task number;
  - level;
  - type;
  - tag;
  - status.

## 4. Test task submission
- A student must be able to submit a numeric or structured short answer for a test task.
- The system must validate answer format before final submission.
- The system must return an immediate verdict.
- The system must keep attempt history.
- The student must see whether an incorrect answer can be retried.
- The system must protect against accidental double-submit.

## 5. Written task submission
- A student must be able to submit a written solution:
  - as text;
  - as one or more photos;
  - as other supported file attachments if enabled.
- The application must support mobile-friendly photo upload.
- The application must support resubmission after remarks.
- The student must see that the submission was accepted into review.
- The student must see whether the submission is:
  - pending review;
  - under review;
  - checked successfully;
  - rejected or needs revision.

## 6. Oral task flow
- During oral acceptance windows, a student must be able to choose an oral task and enter the oral submission flow.
- The application must clearly explain:
  - whether oral acceptance is open now;
  - how to join the live session;
  - how to identify oneself correctly;
  - whether there is queue or waiting;
  - what to prepare before joining.
- After oral windows close, the application must explain that the task can still be submitted in written form if that is allowed by current rules.
- The student must be able to see the outcome of an oral check after it is recorded.

## 7. Progress and status visibility
- A student must have a personal progress page.
- The page must show, for the current lesson and optionally for all lessons:
  - all tasks;
  - current status per task;
  - pluses/minuses or other result semantics;
  - pending checks;
  - solved/unsolved counts by type;
  - latest teacher feedback.
- The student must be able to distinguish:
  - "not started";
  - "submitted";
  - "checked positively";
  - "checked negatively";
  - "needs revision";
  - "already solved earlier", if relevant.

## 8. Feedback, questions, and support
- A student must be able to receive teacher feedback inside the application.
- A student must be able to ask a private question about a task or submission.
- A student must be able to ask a public question in the community area when the question is suitable for public discussion.
- The application must preserve the rule that public discussion must not leak full solutions before official publication.
- The student must have an SOS-like support path for urgent confusion if this flow remains product-relevant.

## 9. Notifications and reminders
- A student must receive notifications about important events:
  - new lesson published;
  - hints published;
  - solutions published;
  - submission checked;
  - teacher comment added;
  - oral window opening soon;
  - weekly deadline approaching.
- Notifications must be available both in-app and through optional external delivery channels if later configured.

## 10. Content consumption
- A student must be able to read announcements, task publications, hints, solutions, statistics, links, and other circle content inside the same product.
- Content must be searchable by tags and filters, because this is one of the key jobs currently done by the Telegram channel.

## 11. Mobile usability
- The student experience must work well on a phone.
- The critical mobile flows are:
  - opening current tasks quickly;
  - uploading solution photos;
  - reading comments and feedback;
  - joining oral acceptance flow;
  - checking what is still pending this week.
