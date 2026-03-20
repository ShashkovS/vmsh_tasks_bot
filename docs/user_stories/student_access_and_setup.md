# Student Stories: Access, Identity, Setup

## Scope
Stories in this file cover login, identity binding, group selection, mode selection, and entry into the main student workspace.

## Stories

### S-ACCESS-01. Start as a known student
As a registered student, I want to open the bot and authenticate myself, so that I can see the tasks that belong to me.

Main flow:
- Student opens the bot and uses `/start`.
- If registration is required, the bot asks for the student's password/token.
- Student sends the token.
- The bot binds the Telegram chat to the student record and switches the user into student mode.
- The bot shows the current keyboard with tasks.

Notes:
- Failed authentication must not silently continue into the task flow.
- The same person may re-bind their chat after reinstalling Telegram or changing device.

### S-ACCESS-02. Start in open-registration mode
As a new student in an open-registration mode, I want the bot to create a usable account for me automatically, so that I can start solving without manual operator help.

Main flow:
- Student opens the bot and uses `/start`.
- The bot creates a student user from Telegram profile data.
- The bot assigns a default group and default game command.
- The bot immediately shows the task keyboard.

Notes:
- This mode exists in code and must be preserved as a configurable system mode.

### S-ACCESS-03. Understand that my token is invalid or blocked
As a student, I want clear feedback when my token is unknown or blocked, so that I know whether to retry or contact organizers.

Main flow:
- Student submits an invalid token.
- The bot tells the student that the token is not accepted and sends them back to the start flow.

Alternative flow:
- Student submits a blocked token.
- The bot explicitly says that the password is blocked.

### S-ACCESS-04. Stay in a deactivated state until the organizers enable me
As a deactivated student, I want the bot to explain that I cannot use the task flow yet, so that I do not misinterpret the silence as a bug.

Main flow:
- Student is recognized as deactivated.
- The bot puts the user into a dedicated inactive state.
- Any further messages get a consistent explanation that the account is not activated.

### S-ACCESS-05. Recover or view my current password
As an authenticated user, I want to request my password/token, so that I can reuse it in other workflows or share it with an organizer when debugging access.

Main flow:
- User sends `/password`.
- The bot sends the current password/token.

### S-ACCESS-06. See my current group and mode in the main screen
As a student, I want the home screen to reflect my current group and attendance mode, so that I understand which tasks and policies currently apply to me.

Main flow:
- Student opens or refreshes the task keyboard.
- The header shows group-specific text and online/offline mode hints.
- The keyboard is built for the student's active group and latest lesson by default.

Notes:
- Group-specific header templates are configurable.
- The header can depend on group metadata such as public name or conditions URL.

### S-ACCESS-07. Switch my attendance mode between online and in-school
As a student, I want to declare whether I am online or in school, so that teachers and scoring logic can treat my work correctly.

Main flow:
- Student sends `/online` or `/in_school`.
- The bot confirms the new mode.
- The user profile is updated.
- Future task screens use the new mode.

Notes:
- Traces show that students really use both mode switches.

### S-ACCESS-08. Switch myself between allowed groups
As a student, I want to move between allowed groups or levels, so that I can solve the correct variant of the weekly material.

Main flow:
- Student uses a group command such as a level command.
- The bot checks that the group is active and self-switch is allowed.
- The student profile is moved to the selected group.
- The bot sends the group's switch message and rebuilds the task keyboard.

Notes:
- This is an important live scenario, not a rare admin edge case.
- Trace logs show repeated switching between novice/pro/expert levels.

### S-ACCESS-09. Be denied access to an unavailable or forbidden group
As a student, I want a clear refusal when I try to access a group that is inactive or forbidden for me, so that I do not accidentally enter the wrong track.

Main flow:
- Student tries to switch into or open tasks from an inaccessible group.
- The bot refuses with a clear "no access" message.

### S-ACCESS-10. See a survey instead of the task keyboard when I have one assigned
As a student, I want the bot to surface an assigned survey before normal tasks, so that operational surveys are not missed.

Main flow:
- Student opens the main screen.
- The system detects an active assigned survey.
- Instead of the normal tasks keyboard, the bot shows the survey question and answer controls.
- Student can answer immediately from the same chat.

Notes:
- This matters for migration because the home screen can be conditionally replaced by a survey.
