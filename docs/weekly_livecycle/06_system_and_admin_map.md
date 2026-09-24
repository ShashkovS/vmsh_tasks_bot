# System And Admin Lifecycle Map

## Scope
This file focuses on system-level transitions and operational controls that shape the weekly lifecycle.

## Core system levers

### Current lesson resolution
The system always needs a canonical "current latest lesson" per group.

Used by:
- default task keyboard;
- result views;
- oral/written transitions;
- game-related calculations.

### Group and level selection
The system treats novice / pro / expert as groups, not as a separate concept.

Implication:
- "level change" is actually a group change with:
  - its own commands;
  - access checks;
  - switch messages;
  - effect on the visible task set.

### Attendance mode
Students and teachers both have an online vs in-school mode.

Implication:
- it affects teacher UX;
- it affects saved result types for oral interactions;
- it matters operationally on Mondays in particular.

### Classroom planning
The system distinguishes a global classroom catalog, an inherited room-to-group layout, and a versioned student assignment plan for a lesson.

Implication:
- a classroom is not a per-student free-text field and is never hard-deleted;
- a room belongs to no more than one group in one layout, while a group may use multiple rooms;
- the latest confirmed layout is effective for later lessons until the first edit materializes a new draft;
- plans become stale when their layout changes and must be recalculated and confirmed;
- room counts are observations, not capacities or weights.

### Global student state
The weekly lifecycle actively uses mass state changes:
- active task state;
- sleeping state.

These are not edge cases. They are part of weekly orchestration.

## Weekly admin operations

### Before or during lesson opening
Typical admin tasks:
- update data from sheets;
- refresh group definitions;
- refresh problems;
- refresh students and teachers;
- ensure command sets are current.
- check the classroom catalog, confirm the effective room-to-group layout, and resolve every in-person student in the assignment preview.

### During the active week
Typical admin tasks:
- send broadcasts;
- assign surveys;
- refresh stale keyboards;
- inspect stats and specific student histories;
- fix checker errors through problem-wide recheck.

### During oral/written phase transition
Typical admin tasks:
- switch task types with `oral2written` or `written2oral`;
- reset stuck written checks;
- wake or sleep all students depending on the stage of the week.

## Operational observations from traces

### Weekly orchestration really happens
Trace logs show repeated use of:
- `admin.command.invoked`
- `admin.broadcast.completed`
- `admin.data.sync`
- `admin.sleep_state.set`
- `admin.state.mass_reset`

So the lifecycle is not only pedagogical. It is actively driven by operator commands.

### The system is multi-surface
The weekly cycle spans:
- task site and channel publication;
- Telegram chat interaction;
- Zoom events;
- web pages for stats/results;
- Google Sheets as an upstream source of truth.

Migration implication:
- "move bot to web" must preserve the operational graph, not only re-skin task submission.

## Migration-critical lifecycle invariants

### Invariant 1. One lesson spans many channels and many days
Lesson `N` starts Monday but remains live across the whole week.

### Invariant 2. Synchronous and asynchronous work overlap
Oral, written, tests, support, and admin operations coexist in the same calendar slices.

### Invariant 3. Teachers need low-friction operational throughput
The written-review conveyor and oral marking flow are operational tools, not just user-facing UI.

### Invariant 4. Student identity has three important dimensions
- who the student is;
- which group/level they are in now;
- whether they are online or in school now.

### Invariant 5. Weekly deadlines matter
Hint publication, oral window close, submission cutoff, and solution publication are lifecycle boundaries that should become explicit configuration in the web product.

### Invariant 6. Classroom history is versioned
Renaming a room updates its global display name with audit history, but layout and assignment records for past lessons are not rewritten. Archiving a currently used room withdraws only current affected assignments, marks them for reassignment, and never silently restores them later.

### Invariant 7. One classroom never mixes groups
Confirmation is rejected if a room contains students from different groups, a student is assigned to a room mapped to another group, or an in-person student has no room. An active but unused classroom is valid.
