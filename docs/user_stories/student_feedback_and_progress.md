# Student Stories: Feedback, Support, Progress

## Scope
Stories in this file cover SOS/help requests, receiving teacher feedback, reactions, result history, and game-related progress views.

## Stories

### S-FEEDBACK-01. Ask a general SOS question
As a student, I want to ask a non-problem-specific question, so that I can get help when I am blocked by logistics or a broad issue.

Main flow:
- Student sends `/sos`.
- The bot offers a choice between a problem-specific and a generic question.
- Student chooses the generic branch.
- The bot switches into the SOS request state and asks for the question text.
- The question is forwarded to the operator/teacher channel.

### S-FEEDBACK-02. Ask a question about a specific problem
As a student, I want to ask for help on a concrete problem, so that the teacher sees the exact task context.

Main flow:
- Student sends `/sos`.
- Student chooses the "question about a problem" branch.
- The bot shows the current lesson's problems again, but in SOS mode.
- Student selects a problem.
- The question is stored and forwarded as a problem-linked help request.

Notes:
- In data, these requests are represented as negative problem IDs in the written discussion flow.

### S-FEEDBACK-03. Ask SOS even before normal authentication
As an unauthenticated student, I want to be able to send an SOS request anyway, so that I can still reach the organizers if login is the problem itself.

Main flow:
- Unknown user sends `/sos`.
- The bot creates a temporary unknown user record.
- The bot switches into the SOS state and asks for the question.

### S-FEEDBACK-04. Receive teacher comments on my written submission
As a student, I want to receive the teacher's comments and verdict for a written task, so that I know whether the solution is accepted and what to fix.

Main flow:
- Teacher checks the written solution.
- The system forwards the teacher's relevant discussion back to the student.
- The student sees whether the verdict is positive or negative.
- The student's task keyboard is refreshed.

Notes:
- If the task is solved, only the latest teacher comments may be forwarded.
- If the task is not solved, a larger slice of the thread is forwarded.

### S-FEEDBACK-05. React to a teacher's written verdict
As a student, I want to leave a reaction after receiving written feedback, so that teachers can later understand whether the feedback was useful or emotionally well received.

Main flow:
- Student receives a written verdict message with reaction buttons.
- Student clicks a reaction.
- The reaction is saved and the message text is updated to reflect the chosen reaction.

### S-FEEDBACK-06. React to an oral submission outcome
As a student, I want to leave a reaction after an oral round, so that organizers can evaluate the oral experience too.

Main flow:
- After an oral round, student receives a message about accepted oral tasks.
- The message contains oral reaction controls.
- Student clicks a reaction.
- The reaction is saved against the Zoom conversation.

### S-FEEDBACK-07. See my full history of sent results
As a student, I want to request my result history, so that I can reconstruct what I sent, when, and with which verdict.

Main flow:
- Student sends `/results`.
- The bot lists all sent results grouped by lesson.
- Each line shows time, problem reference, verdict symbol, and answer text if present.

### S-FEEDBACK-08. See game-related progress derived from solved tasks
As a student, I want to see how solved tasks and payments affect the game layer, so that I can understand the current in-game balance and benefits.

Main flow:
- Student sends `/game_info`.
- The bot loads solved tasks, command assignment, payments, and chest events.
- The bot builds a timeline-like report of gained and spent points.

Notes:
- Teachers can also inspect this report for a student by token.

### S-FEEDBACK-09. Receive a survey and answer it inline
As a student, I want to answer assigned surveys directly in my normal workspace, so that operational polling does not require a separate tool.

Main flow:
- Student opens the main screen.
- The survey replaces the normal task keyboard.
- Student clicks one or more options depending on survey type.
- The answer is saved immediately and the message markup is refreshed.
