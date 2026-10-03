# Monday Lifecycle

## Business meaning
Monday is the densest and most multi-modal day of the week:
- a new lesson is published;
- students enter the fresh task set;
- oral and in-school acceptance are both active;
- after the synchronous window, the system falls back to asynchronous written flow.

## Timeline

### 16:30. Tasks for lesson `N` are published
External/public behavior:
- lesson `N` appears on the site and in the channel.

Product consequences:
- the main keyboard should resolve the current latest lesson correctly;
- students may switch level immediately after publication;
- all references to "current lesson" effectively move from `N-1` to `N`.

Migration implication:
- web must have a canonical notion of "current lesson" and show it by default.

### 16:40. Distance acceptance starts
Main student behavior:
- students start selecting tasks from the new lesson;
- test tasks are submitted and checked immediately;
- written tasks start flowing into queue;
- oral tasks now lead to Zoom instructions;
- SOS requests may also start.

Main teacher behavior:
- oral acceptance and written review may both happen in parallel;
- some teachers work inside Zoom-related flows;
- some immediately process written queue.

Trace-backed observations:
- Mondays show mixed clusters of:
  - `student.problem.selected`
  - `student.test_answer.submitted`
  - `student.written_solution.submitted`
  - `zoom.queue.changed`
  - `zoom.conversation.started`
  - `teacher.oral_round.finished`

### Before 16:50. Classroom plan is confirmed
Admin behavior:
- the reusable classroom catalog is checked for active rooms;
- the latest confirmed room-to-group layout is inherited unless this lesson needs a change;
- if edited, a lesson draft is materialized, previewed, and confirmed;
- the student assignment plan is calculated, manually corrected where necessary, and confirmed.

Assignment rules:
- one room contains students from one group only, while one group may use several rooms;
- rooms have no configured capacity; the planner shows actual counts;
- a previous eligible room is kept where possible, otherwise the least-loaded room is selected with natural room-name ordering for ties;
- an in-person student without an eligible room is a blocking incident, not a silently omitted row.

Product consequences:
- Student and Family see only the confirmed assignment;
- Student receives PWA notifications when a room is assigned, withdrawn, or changed; Family does not receive a classroom push;
- a late group or attendance-mode change immediately recalculates that student's assignment;
- hiding an assigned room immediately shows “Аудитория переназначается” for affected current students and requires a new confirmed plan.

### 16:50. In-school circle starts
Pedagogical meaning:
- students physically present in school interact with teachers live;
- the bot still matters because it tracks mode, later submissions, and some oral/written outcomes.

Product consequences:
- students explicitly switch themselves to `/in_school`;
- teachers may record oral outcomes with `RES_TYPE.SCHOOL`;
- after school, those same students can continue through the bot.
- the student's current room comes from the confirmed versioned assignment plan, not directly from a spreadsheet cell.

Migration implication:
- "attendance mode" is a real weekly-state parameter, not just a user preference.

### 16:40 to 18:50. Oral queue builds and is gradually processed
Current live oral behavior:
- selecting an oral task sends Zoom instructions;
- Zoom events are received from the conference side;
- teachers observe the queue and run oral rounds;
- after each oral round, pluses/minuses are saved together.

Important nuance:
- current oral acceptance is not just "student clicks join".
- it is a multi-system process:
  - task selection in bot;
  - joining Zoom with correct display name;
  - queue/event tracking from Zoom;
  - teacher-side oral marking.

### 19:00. In-school session ends
Business meaning:
- live school acceptance ends;
- after that, the remaining path is primarily asynchronous via bot.

Product consequences:
- students can still submit written solutions through the bot;
- oral tasks may be submitted in writing later if pedagogically allowed;
- teachers move more heavily into written queue review.

### After 19:00. Monday turns into asynchronous written phase
Main flows:
- students continue sending written solutions;
- students continue solving test tasks;
- teachers process written queue;
- students receive verdicts and may resubmit.

Observed real patterns:
- after synchronous periods, the dominant pattern becomes:
  - `teacher.written_queue.requested`
  - `teacher.written_check.started`
  - `queue.written.discussion_added`
  - `teacher.written_verdict.saved`
  - `result.saved`
  - `queue.written.dequeued`

## Monday risks for migration

### Risk 1. Mixing lesson start with live acceptance
If web launch design treats Monday only as "new tasks published", it will miss the fact that this is also the heaviest live operational period.

### Risk 2. Losing mode switching
Students really do switch between online and in-school mode around Monday. This must remain fast and obvious.

### Risk 3. Treating oral and written as separate products
In practice, Monday is one blended workflow. A student may:
- switch level;
- solve tests;
- submit written work;
- then go to Zoom for oral acceptance;
- then come back and continue written work.
