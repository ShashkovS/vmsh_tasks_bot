# Teacher Stories: Written Review

## Scope
Stories in this file cover the teacher workbench for written tasks and SOS questions.

## Stories

### T-WRITTEN-01. Open the teacher workbench and see queue sizes
As a teacher, I want the main teacher screen to show how many written tasks and SOS questions are waiting, so that I can choose what to process next.

Main flow:
- Teacher enters teacher mode.
- The bot shows a keyboard with teacher actions.
- The header includes counts of pending written tasks and SOS requests visible to that teacher.

### T-WRITTEN-02. Request the written queue grouped by problem family
As a teacher, I want to see written tasks grouped by synonymous problems, so that I can efficiently review one topic in a batch.

Main flow:
- Teacher chooses written checking.
- The bot shows a list of problem groups with counts and waiting time information.
- Teacher chooses one problem family.
- The system locks the topic for that teacher and starts pulling matching student submissions.

### T-WRITTEN-03. Pull the next SOS question for review
As a teacher, I want to open the queue of SOS questions, so that I can answer support requests in the same workflow as written checking.

Main flow:
- Teacher chooses the SOS queue action.
- The system finds visible SOS requests for that teacher's groups.
- Teacher picks a question and opens its discussion.

### T-WRITTEN-04. Start checking one student's written problem
As a teacher, I want the bot to open the full submission context for one student and one problem, so that I can judge the current state of the work accurately.

Main flow:
- Teacher starts a concrete written review item.
- The bot sends a header with student and problem context.
- The bot forwards the latest discussion history, including previous comments and student resubmissions.
- The teacher is switched into the checking state with a dedicated verdict keyboard.

### T-WRITTEN-05. Add one or several comments before deciding the verdict
As a teacher, I want to send multiple review comments before finalizing the verdict, so that I can explain what is wrong or encourage the student properly.

Main flow:
- While in the checking state, the teacher sends one or more plain messages.
- Each message is stored in the written discussion thread.
- After every message, the bot returns a fresh verdict keyboard.

Notes:
- This is an important real flow: teachers often comment first and only then approve or reject.

### T-WRITTEN-06. Approve a written solution
As a teacher, I want to mark a written solution as solved or partially solved, so that the student's progress is recorded immediately.

Main flow:
- Teacher presses an approving verdict button.
- The system creates a result with `RES_TYPE.WRITTEN`.
- The queue item is removed.
- The teacher sees updated personal checking stats and milestone messages if applicable.
- The student receives the forwarded verdict and comments.

### T-WRITTEN-07. Reject a written solution and invalidate earlier pluses if needed
As a teacher, I want to reject a written solution and downgrade earlier credit for the same problem, so that the student's status remains consistent.

Main flow:
- Teacher presses a rejecting verdict button.
- The system creates a negative written result.
- Earlier positive written credit for the same task may be replaced by a rejected-answer marker.
- The queue item is removed.
- The student receives the thread and the negative verdict.

### T-WRITTEN-08. Cancel the current check without finalizing it
As a teacher, I want to abandon the current checking attempt, so that I can safely back out of a mistaken start.

Main flow:
- Teacher presses cancel in the checking UI.
- The system returns the teacher to the main teacher state.
- Temporary draft discussion entries may be deleted if they were marked as removable.

### T-WRITTEN-09. Reopen a concrete student's problem for recheck
As a teacher, I want to force a specific student's written problem back into my review flow, so that I can fix a bad past decision or continue an interrupted conversation.

Main flow:
- Teacher uses `/recheck token problem`.
- The system resolves the student and the problem reference.
- The matching discussion is reopened in the same written-review interface.

Notes:
- Problem references can be given by id or by textual problem reference.

### T-WRITTEN-10. Leave a final reaction to my own checking experience
As a teacher, I want to leave a reaction after finishing a review, so that meta-feedback about the checking experience is also captured.

Main flow:
- After saving a verdict, the bot may offer a teacher reaction keyboard.
- Teacher picks a reaction.
- The reaction is stored against the written result.

### T-WRITTEN-11. Process long review sessions as a conveyor
As a teacher, I want the bot to automatically return me to the next relevant written item after each verdict, so that I can check many tasks in sequence with minimal friction.

Main flow:
- Teacher finishes one item.
- The bot returns to the teacher action or locked-topic flow.
- If a topic lock exists, the next matching item is pulled automatically.

Migration note:
- This conveyor behavior is one of the strongest teacher workflows seen in traces and should be preserved in web.

### T-WRITTEN-12. Answer an SOS question without creating a normal written result
As a teacher, I want to answer a student's SOS question in the same threaded review flow, so that support requests can be handled without pretending they are normal submissions.

Main flow:
- Teacher opens an SOS item from the SOS queue.
- The bot forwards the existing question thread.
- Teacher writes one or more answer messages.
- Teacher presses the dedicated answer action.
- The queue item is removed.
- The answer thread is copied back to the student.

Notes:
- This flow is distinct from ordinary verdict saving because it does not create a normal result for a solved task.
