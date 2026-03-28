# Teacher Requirements

## 1. Teacher workspace entry
- A teacher must have a dedicated workspace, not just scattered student-facing screens with hidden controls.
- On entry, the teacher must see:
  - current lesson;
  - current weekly stage;
  - written queue state;
  - oral acceptance state;
  - unresolved student questions;
  - moderation items if assigned.

## 2. Student lookup and context
- A teacher must be able to find a student quickly by:
  - name;
  - token or internal identifier;
  - level;
  - lesson activity;
  - recent submissions.
- A teacher must be able to open a student profile and see:
  - current level;
  - current mode;
  - task status for current lesson;
  - submission history;
  - previous teacher interactions;
  - current unresolved issues.

## 3. Written review workflow

### 3.1 Queue access
- A teacher must be able to open the written queue.
- The queue must support filters by:
  - level or group;
  - task;
  - lesson;
  - student;
  - age of submission;
  - status;
  - SOS or priority markers if used.

### 3.2 Review process
- A teacher must be able to open the next written submission with full context:
  - task statement;
  - student's text;
  - attachments;
  - previous attempts;
  - earlier comments and verdicts.
- A teacher must be able to record a verdict.
- A teacher must be able to add a comment or remark.
- A teacher must be able to request revision rather than only accept/reject in a binary way.
- A teacher must be able to see whether another teacher is already handling the same item if concurrent review is possible.

### 3.3 Queue state changes
- The system must support explicit item states in the review queue.
- Teachers must be able to distinguish:
  - waiting for review;
  - taken into work;
  - commented;
  - finished;
  - returned for revision.

## 4. Oral acceptance workflow

### 4.1 Live oral dashboard
- During oral windows, a teacher must have a live dashboard for oral activity.
- The dashboard must show:
  - students currently trying to submit oral tasks;
  - selected tasks;
  - level context;
  - session status;
  - teacher assignment if already assigned.

### 4.2 Oral checking
- A teacher must be able to conduct an oral check and then record:
  - result;
  - time spent if needed;
  - linked task;
  - linked student;
  - optional comment;
  - session metadata when relevant.
- The teacher must be able to process multiple oral outcomes in sequence without losing the queue overview.

### 4.3 Zoom or video integration
- If live oral acceptance continues to depend on an external video tool, the teacher workspace must integrate with it operationally.
- The system must preserve the jobs currently covered by the Zoom-related flow:
  - seeing who has joined;
  - mapping participant names to students;
  - understanding queue state;
  - recording conversation/check results.

## 5. Task and result management
- A teacher must be able to see all results for a task or lesson.
- A teacher must be able to correct or recheck an earlier result when allowed.
- A teacher must be able to move between oral and written handling modes where current operations require it.
- A teacher must be able to see unresolved submissions that still block student progress.

## 6. Communication with students
- A teacher must be able to send private comments attached to a submission or task.
- A teacher must be able to answer private student questions.
- A teacher must be able to publish clarifications visible to all students of a lesson or level when that is more efficient than repeating the same answer.

## 7. Community participation and moderation
- A teacher must be able to participate in the community discussion area.
- A teacher must be able to answer general questions without exposing unpublished solutions.
- If moderation rights are granted, a teacher must be able to:
  - edit or hide inappropriate comments;
  - freeze a thread;
  - escalate an issue to admin.

## 8. Teacher operational safety
- The interface must reduce accidental wrong verdicts, duplicate checks, and context loss.
- A teacher must always see enough context before saving a result.
- Important teacher actions must be auditable.
