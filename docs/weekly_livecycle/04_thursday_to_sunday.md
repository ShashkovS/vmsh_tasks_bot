# Thursday To Sunday Lifecycle

## Business meaning
The second half of the week is less synchronous, but still product-heavy.

The center of gravity shifts to:
- asynchronous written review;
- continued student submissions through the bot;
- pedagogical phase changes caused by hints and final solutions.

## Thursday and Friday

### Main operational mode
Predominantly asynchronous:
- students continue test and written submissions;
- teachers continue written review;
- students receive verdicts and may iterate on written work.

### Product consequences
The important surfaces are:
- task keyboard for lesson `N`;
- result history and student reactions;
- teacher written-review conveyor;
- admin maintenance commands if something drifts.

### Migration implication
Even outside the oral windows, the product is not idle. Thursday and Friday are still active workflow days.

## Saturday

### 12:00. Hints are published
Public meaning:
- hints for all problems of lesson `N` are published.

Product meaning:
- the bot itself does not become inactive;
- students may continue solving and submitting;
- however, the pedagogical state of the lesson changes because hints are now public.

Migration implication:
- web should ideally understand or at least support "hint published" as a lifecycle marker, even if hints themselves are hosted elsewhere.

## Sunday

### 13:00. Submission cutoff
Public meaning:
- submission through the bot ends for lesson `N`.

Product meaning:
- after the cutoff, the active intake phase ends;
- the system transitions from "ongoing weekly work" into "archive / published solutions" mode.

Migration implication:
- the system needs a clear concept of submission deadlines and lock behavior.

### 14:00 or 15:00. Full solutions are published
Observed documentation versions differ slightly:
- one publication text says 14:00;
- another says 15:00.

For lifecycle purposes, the key point is:
- full solutions are published on Sunday after submissions close.

Migration implication:
- this exact time should be configurable, not hardcoded into product logic.

## End-of-week state
By late Sunday, lesson `N` is effectively complete:
- official solutions are public;
- oral window is over;
- remaining teacher work is cleanup or late review;
- the next meaningful state transition is Monday lesson publication for `N+1`.

## What still remains active late in the week
From code and traces, the following may still happen:
- written verdicts continue to be saved;
- students read history and react to verdicts;
- admins may run maintenance commands;
- broadcasts may go out.

So the lifecycle is not a hard shutdown. It is a pedagogical cutoff plus a publication transition.
