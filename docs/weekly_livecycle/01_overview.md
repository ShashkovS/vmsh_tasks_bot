# Weekly Lifecycle Overview

## Core concept
The product is not just a bot with isolated commands. It is an operational shell around a repeating weekly educational cycle.

Each week revolves around one lesson `N`:
- tasks are published;
- students choose a level/group;
- students solve and submit tasks;
- oral tasks are accepted in fixed windows;
- written tasks are checked asynchronously;
- hints and solutions are published later in the week;
- then the cycle resets for lesson `N+1`.

## Weekly phases

### Phase 1. Lesson opening
Time:
- Monday 16:30 to 16:40

Meaning:
- lesson `N` becomes visible;
- students enter the new task set;
- some students switch level before serious work starts.

Main product surfaces:
- main task keyboard;
- group switching commands;
- attendance mode commands.

### Phase 2. Synchronous acceptance window
Time:
- Monday 16:40 to 19:00
- Tuesday 16:40 to 19:00
- Wednesday 16:40 to 19:00

Meaning:
- oral acceptance happens via Zoom;
- in-school acceptance also happens on Monday;
- students still continue test and written work around those windows.

Main product surfaces:
- oral-task entry via task selection;
- Zoom event ingestion and queue tracking;
- teacher oral marking;
- student attendance mode switching;
- SOS support questions.

### Phase 3. Asynchronous written checking
Time:
- starts Monday after oral window;
- continues through the week

Meaning:
- written tasks accumulate in queue;
- teachers process them in batches;
- students receive verdicts and may resubmit improved solutions.

Main product surfaces:
- written queue;
- discussion threads;
- teacher verdict flow;
- student reactions to feedback.

### Phase 4. Hint publication
Time:
- Saturday 12:00

Meaning:
- hints for lesson `N` are published outside the bot;
- after that, students may continue submitting through the bot, but under different pedagogical conditions.

### Phase 5. Submission cutoff and publication of full solutions
Time:
- Sunday 13:00 submission cutoff;
- Sunday 14:00 or 15:00 publication of solutions, depending on publication text version

Meaning:
- bot intake for lesson `N` effectively closes;
- official solutions are published;
- student work on the current lesson transitions into post-mortem review rather than active acceptance.

## Main entity flows

### Student-facing
- access/login;
- level selection;
- online/in-school mode selection;
- choosing problems;
- test answer submission;
- written solution submission;
- oral participation via Zoom instructions;
- SOS/help flow;
- receiving verdicts and leaving reactions;
- viewing result history.

### Teacher-facing
- teacher workbench;
- written queue browsing and locking;
- written discussion and verdicting;
- oral marking by student;
- Zoom queue monitoring;
- student lookup and profile fixes.

### Admin-facing
- weekly state switches;
- data sync from sheets;
- broadcasts;
- surveys;
- keyboard resets;
- maintenance and forensic commands.

## What traces confirm
Observed traces support this lifecycle strongly:
- student flow is dominated by `student.problem.selected`, `student.test_answer.submitted`, `student.written_solution.submitted`;
- teacher flow is dominated by `teacher.written_queue.requested`, `teacher.written_check.started`, `teacher.written_verdict.saved`;
- oral windows are visible as `zoom.webhook.received`, `zoom.queue.changed`, `zoom.conversation.started`, `teacher.oral_round.finished`;
- weekly orchestration appears through `admin.command.invoked`, `admin.broadcast.completed`, `admin.sleep_state.set`, `admin.state.mass_reset`.
