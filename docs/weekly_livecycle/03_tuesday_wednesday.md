# Tuesday And Wednesday Lifecycle

## Business meaning
Tuesday and Wednesday are continuation days for the same lesson `N`.

They are not "light" days. They combine:
- another synchronous oral acceptance window;
- continued student solving and submission;
- heavy asynchronous teacher review of written work.

## Fixed time window
Time:
- 16:40 to 19:00

Public rule:
- distance oral acceptance continues through Zoom;
- tasks should be submitted orally only on one of these days, because staff capacity is limited.

## Main student behaviors

### Continue solving lesson `N`
Students come back to the same lesson:
- solve more test tasks;
- continue written tasks;
- re-open older tasks from the same lesson;
- sometimes change level after seeing the real difficulty.

### Enter Zoom oral acceptance
Students:
- select an oral task;
- get the Zoom entry instructions;
- join with a level-prefixed display name;
- may wait a long time while solving other tasks in parallel.

### Ask for help
Some students use:
- generic SOS;
- problem-specific SOS;
- reactions after teacher feedback.

## Main teacher behaviors

### Continue oral work in the evening window
Teacher-side live flow:
- observe Zoom queue;
- pick or receive students for oral work;
- run one oral round;
- record pluses and minuses in batch;
- optionally leave oral reaction.

### Process written queue in parallel
Teacher-side asynchronous flow continues:
- request written queue;
- open one student's discussion;
- comment;
- save verdict;
- move to the next item.

This is important:
- oral and written work are not cleanly separated by day.
- the same teacher may do both on the same evening.

## Trace-backed operational picture
For selected real users, Tuesday/Wednesday repeatedly show:
- `zoom.webhook.received`
- `zoom.queue.changed`
- `zoom.conversation.started`
- `teacher.oral_round.finished`
- alongside
- `teacher.written_queue.requested`
- `teacher.written_check.started`
- `teacher.written_verdict.saved`

This means web migration must support multi-tasking operator behavior, not a single narrow mode.

## Lifecycle implications

### Student experience implication
A student should be able to:
- keep working on written/test tasks while waiting for oral acceptance;
- switch back into the main task workspace after oral flow;
- receive oral results and still continue with the rest of the lesson.

### Teacher experience implication
A teacher should be able to:
- move between queue monitoring and concrete checking quickly;
- inspect students across modes;
- finish one oral or written interaction and immediately continue with the next.

### Analytics implication
Tuesday/Wednesday are continuation days for the same lesson `N`, not a new lesson. All weekly analytics should preserve lesson identity across these days.
