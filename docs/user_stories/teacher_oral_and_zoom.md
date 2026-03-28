# Teacher Stories: Oral Checking And Zoom

## Scope
Stories in this file cover live oral interactions, manual oral grading, and Zoom-related operational views.

## Important note
The old waitlist code is not treated as a live scenario. Current stories focus on actual oral/Zoom behavior visible in the code and traces.

## Stories

### T-ORAL-01. Search for a student and start oral marking manually
As a teacher, I want to find a student by surname or token and open oral marking, so that I can record oral outcomes even when the flow starts outside the bot.

Main flow:
- Teacher enters the oral-marking path.
- The bot asks for a surname fragment.
- Teacher types a name.
- The bot shows the best matching students within the teacher's accessible groups.
- Teacher selects the student and receives the oral-marking keyboard.

### T-ORAL-02. Open oral marking for a student and lesson by command
As a teacher, I want to open oral marking for a specific student and lesson using a command, so that I can quickly record pluses after a circle or manual oral session.

Main flow:
- Teacher runs `/edtplus_<lesson>_<token>`.
- The bot resolves the student and lesson.
- The bot opens the oral-marking keyboard directly.

### T-ORAL-03. Toggle pluses and minuses for several oral problems in one round
As a teacher, I want to mark several oral tasks as solved or unsolved before finalizing, so that one oral interaction can update all relevant problems at once.

Main flow:
- Teacher is on the oral-marking keyboard for a student.
- Each click cycles a problem through neutral -> plus -> minus -> neutral.
- The keyboard is updated after every click.

### T-ORAL-04. Finish one oral round and save all marks together
As a teacher, I want to finalize the oral round in one action, so that the student receives a coherent result summary.

Main flow:
- Teacher presses the finish action.
- The system creates a Zoom or school result for each marked problem.
- Solved written queue items for the same problems are removed if needed.
- The student keyboard is refreshed.
- The teacher sees a summary of pluses and minuses.
- The student receives a summary message.

Notes:
- The result type depends on teacher mode: `ZOOM` for online, `SCHOOL` for in-school mode.

### T-ORAL-05. Create and use a Zoom conversation record
As a teacher, I want one oral round to be associated with a Zoom conversation record, so that reactions and analytics can refer to the whole interaction.

Main flow:
- Teacher finishes an oral round with at least one marked problem.
- The system creates a `zoom_conversation` entry.
- Results from that round reference the same conversation where appropriate.

### T-ORAL-06. Leave a reaction to an oral interaction
As a teacher, I want to rate the oral submission session, so that organizers can later analyze oral quality and load.

Main flow:
- After finishing an oral round, the bot offers an oral reaction keyboard.
- Teacher picks a reaction.
- The reaction is saved for the Zoom conversation.

### T-ORAL-07. View the current Zoom queue
As a teacher, I want to inspect who is waiting in the Zoom conference and for how long, so that I can manage the live evening flow.

Main flow:
- Teacher runs `/zoom_queue` or `/z`.
- The bot shows visible participants, waiting times, and status notes.
- The bot also reports the total number of people currently in queue.

Alternative flow:
- Teacher runs `/zall`.
- The bot shows the extended queue view.

### T-ORAL-08. Use student mode information during oral checking
As a teacher, I want oral marking to respect whether the student is online or in-school, so that result types and expectations match the context.

Main flow:
- Teacher works in online or school mode.
- The oral-marking UI reflects that mode.
- Final saved results use the matching result type.

### T-ORAL-09. Resume teacher mode after temporary detours
As a teacher, I want to force the bot back into teacher mode after temporary student-like testing or navigation, so that I do not get stuck in the wrong state.

Main flow:
- Teacher uses `/set_teacher`.
- The bot restores the teacher action state and shows the teacher workbench again.

### T-ORAL-10. Use oral checking for both evening Zoom and daytime school workflows
As a teacher, I want the same oral-marking capability to work for remote and in-person teaching, so that I do not need two separate tools.

Main flow:
- Teacher switches between `/online` and `/in_school`.
- The oral flow continues to work, but saved result types and hints adapt to the selected mode.
