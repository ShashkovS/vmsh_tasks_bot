# Admin Stories: Communications, Surveys, Forensics

## Scope
Stories in this file cover mass messaging, surveys, ad hoc chat forensics, and auxiliary operator tools.

## Stories

### A-COMMS-01. Send a broadcast to an explicit list of tokens
As an admin, I want to send one message to a chosen token list, so that I can contact a targeted subset of users quickly.

Main flow:
- Admin sends `/broadcast` with token list on the second line and message body below.
- The system resolves users and sends the message to reachable chats.
- The system reports delivery count and bad tokens.

### A-COMMS-02. Send a broadcast to dynamic cohorts
As an admin, I want to broadcast by cohort identifiers rather than explicit token lists, so that operational communication remains manageable at scale.

Supported cohort selectors:
- `all_students`
- `all_teachers`
- `all_online`
- `all_school`
- `all_group:<group_id>`
- configured group broadcast codes such as `all_novice`

### A-COMMS-03. Send a quiet broadcast
As an admin, I want to send a broadcast without notifications, so that low-priority operational messages do not create unnecessary noise.

Main flow:
- Admin uses `/broadcast_quiet` or `/broadcast_html_quiet`.
- The system sends messages with notification suppression.

### A-COMMS-04. Send an HTML-formatted broadcast
As an admin, I want to send formatted broadcasts, so that links and rich text survive delivery.

Main flow:
- Admin uses `/broadcast_html` or `/broadcast_html_quiet`.
- The system sends the body in HTML parse mode.

### A-COMMS-05. Rebroadcast by replying to an existing message
As an admin, I want to reuse an existing Telegram message as a broadcast payload, so that I can forward polished content without retyping it.

Main flow:
- Admin replies to a message and invokes a broadcast command.
- The replied message body is copied to recipients.

### A-COMMS-06. Forward a raw slice of one student's message history
As an admin, I want to forward a range of historical Telegram message IDs from one student chat into my own chat, so that I can debug edge cases and reconstruct incidents.

Main flow:
- Admin runs `/forward_all token start end`.
- The system forwards all possible messages in that range and reports errors.

### A-COMMS-07. Create a survey with predefined choices
As an admin, I want to create a radio or checkbox survey from chat, so that I can collect structured answers without building a separate form.

Main flow:
- Admin uses `/create_survey` with survey type, question, and list of choices.
- The system creates the survey and returns the new survey ID.

### A-COMMS-08. Disable an active survey
As an admin, I want to stop a survey from appearing, so that time-bound surveys can be closed cleanly.

Main flow:
- Admin runs `/disable_survey survey_id`.
- The survey is marked inactive.

### A-COMMS-09. Assign a survey to a specific token list
As an admin, I want to target a survey at a specific audience, so that not every survey is shown to every student.

Main flow:
- Admin runs `/assign_survey_to_tokens`.
- The system assigns the survey to the listed users.
- Where possible, the students' main screens are refreshed so the survey appears immediately.

### A-COMMS-10. Audit student progress directly from Telegram
As an admin, I want to query student results, stats, and game state without leaving chat, so that urgent operational decisions do not depend on a browser workflow.

Examples:
- `/student_results`
- `/all_student_results`
- `/stat`
- `/statw`
- `/game_info`
