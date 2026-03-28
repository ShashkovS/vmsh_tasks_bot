# Teacher Stories: Access, Mode, Visibility

## Scope
Stories in this file cover teacher authentication, entry into the teacher workspace, personal mode selection, and group-based visibility rules.

## Stories

### T-ACCESS-01. Authenticate as a teacher and open the teacher workbench
As a teacher, I want the bot to recognize my token and land me in the teacher workspace, so that I can immediately start operational work.

Main flow:
- Teacher uses `/start`.
- Teacher enters the token.
- The bot binds the Telegram chat to the teacher record.
- The teacher state is set to the teacher action screen.
- The bot shows the teacher workbench.

### T-ACCESS-02. Return to the teacher workbench after interruptions
As a teacher, I want to get back to the main teacher action screen after any detour or partial flow, so that I can continue checking work without resetting the chat manually.

Main flow:
- Teacher cancels the current operation or uses `/set_teacher`.
- The bot restores the teacher action state.
- The teacher workbench is shown again.

### T-ACCESS-03. Set my own working mode to online
As a teacher, I want to switch myself into online mode, so that oral checking and result typing use the Zoom-oriented semantics.

Main flow:
- Teacher runs `/online`.
- The bot confirms the mode change.
- The profile is updated.

### T-ACCESS-04. Set my own working mode to in-school
As a teacher, I want to switch myself into in-school mode, so that oral checking records in-person work correctly.

Main flow:
- Teacher runs `/in_school`.
- The bot confirms the mode change.
- The profile is updated.

### T-ACCESS-05. See only groups that I am allowed to access
As a teacher, I want every queue, search result, and student operation to respect my allowed groups, so that I do not accidentally work outside my permissions.

Main flow:
- Teacher opens queues, searches for students, changes groups, or rechecks problems.
- The system filters visible students and tasks to the teacher's accessible groups.
- Any forbidden operation is rejected with a clear message.

Migration note:
- Group visibility is a core permission model, not a cosmetic filter.
