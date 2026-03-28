# Weekly Actor Journeys

## Student Journey

### Monday opening journey
Typical sequence:
- open bot;
- choose or confirm level/group;
- choose online vs in-school mode;
- enter lesson `N`;
- solve several test tasks;
- optionally submit one or more written tasks;
- optionally enter oral/Zoom flow.

Observed real detail:
- some students switch level multiple times during the same week;
- some students keep mixing test and written tasks inside one session;
- some students receive negative written feedback and then resubmit.

### Midweek continuation journey
Typical sequence:
- return to the same lesson `N`;
- continue unsolved tasks;
- receive written verdicts from teachers;
- react to verdicts;
- ask SOS if blocked;
- potentially attend one oral Zoom round.

### End-of-week journey
Typical sequence:
- use hints after Saturday publication;
- finish remaining submissions before Sunday cutoff;
- inspect `/results`;
- compare own work with published solutions.

## Teacher Journey

### Written-review conveyor journey
Typical sequence:
- open teacher workbench;
- inspect queue counts;
- request written queue;
- lock one problem family or pick a concrete item;
- read forwarded discussion;
- write comments;
- save verdict;
- immediately continue with the next task.

This is the strongest repeated teacher workflow in traces.

### Oral evening journey
Typical sequence:
- monitor Zoom queue;
- take one student/session;
- run oral interaction outside or alongside bot UI;
- mark pluses/minuses in bot;
- finish oral round;
- optionally rate the interaction;
- continue with next student.

### Student-management journey
Typical sequence:
- find student;
- inspect results;
- change group or attendance mode if needed;
- possibly recheck a task or reopen a written discussion.

## Admin Journey

### Weekly orchestration journey
Typical sequence:
- sync data from sheets;
- switch problem modes (`oral2written` / `written2oral`);
- wake or sleep all students depending on the calendar phase;
- refresh keyboards if the UI state drifted.

### Communication journey
Typical sequence:
- send broadcast to a cohort;
- assign survey to target audience;
- inspect delivery failures;
- possibly use forensic commands to inspect message history.

## Cross-actor interactions

### Student -> Teacher -> Student written loop
- student sends written solution;
- queue entry appears;
- teacher comments and saves verdict;
- student receives discussion and verdict;
- student may react or resubmit.

### Student -> Zoom -> Teacher oral loop
- student selects oral task;
- joins Zoom with structured display name;
- system observes queue events;
- teacher completes oral round;
- student receives oral result summary and may leave a reaction.

### Admin -> Whole cohort loop
- admin changes system state or content;
- teachers see updated queues or commands;
- students see updated keyboard, blocked state, or new surveys/broadcasts.
