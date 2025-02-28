# from helpers.msg_texts import msgs

class Msgs:

    # handlers\common_handlers.py
    reaction_accepted = 'Accepted'
    your_password = "🤖 Your password:\n<pre>{user.token}</pre>"

    # handlers\group_and_channel_handlers.py
    here_is_your_answer = 'Here’s the answer to your question:'
    this_message_is_for_bot = 'It seems this message is meant for me. Join me here: @{username}'

    # handlers\main_handlers.py
    start_if_reg_needed = (
        "🔁 Hi! This is the bot for Tech Leaders project admission.\n"
        "Please enter your password."
    )
    start_if_reg_anybody = (
        "🔁 Hi! This is the bot for Tech Leaders project support.\n"
        "You can ask your question and get answer here."
    )
    this_password_is_blocked = (
        "🔁 This password has been blocked. "
        "Most likely, a new password was sent to your email. Don’t forget to check your spam folder."
    )
    welcome_user = "🤖 Great, Welcome to the club, {user.name} {user.surname}"
    user_is_not_activated = (
        ValueError('NOT USED')
    )
    bot_internal_error = "☢️ Something went wrong, the bot got confused. Let’s start over!"
    error_only_compressed_images = '❗❗❗ The bot only accepts compressed images. Send pictures one by one and check the “Compress” option.'
    error_only_images_and_texts = '❗❗❗ The bot only accepts text messages and photos of solutions.'
    you_are_in_online_mode_now = "You are now working in 'Online' mode."
    you_are_in_offline_mode_now = "You are now working in 'In-School' mode."

    # handlers\student_handlers.py
    auth_needed = 'You need to log in and enter your password.'
    online_mode_hint = "📡remote📡"
    offline_mode_hint = "🏫in school🏫"
    # problems_keyboard_header = (
    #     "❓ <b>Click on a problem to submit it</b>\n"
    #     "{student.name} {student.surname}\n"
    # )
    problems_keyboard_header = (
        "❓ <b>Click a question button to ask a question.</b>\n"
        "{student.name} {student.surname}\n"
    )
    solutions_are_not_accepted_now = "🤖 Submission is closed now."
    error_file_is_not_accepted = (
        '❗❗❗ File NOT ACCEPTED! Please select a problem first! '
        'You can send multiple solution photos as a gallery or select a problem each time.'
    )
    error_text_is_not_accepted_now = '❗❗❗ Text NOT ACCEPTED! Please select a problem first!'
    error_file_is_too_large = "❌ File size exceeds the 5MB limit."
    sol_accepted = "Solution submitted for review."
    question_accepted = "Question recorded."
    hour_rate_limit_error = '💤⌛ The bot accepts no more than 3 answers per hour. Please try again at the beginning of the next hour.'
    dayly_rate_limit_error = '💤⌛ The bot accepts no more than 6 answers per day. Please try again tomorrow.'
    poly_check_error_hint = 'For n={x}, you got {stv}, but it should be {crv}.'
    error_select_one_of = "❌ Select one of the options: {variants}"
    results_after_answer_accepted = 'Answer submitted for review.'
    student_is_sleeping_state_msg = (
        "🤖 Submission is closed now."
    )
    you_are_in_novice_now = (
        ValueError('NOT USED')
    )
    you_are_in_testing_now = ValueError('NOT USED')
    you_are_in_pro_now = (
        ValueError('NOT USED')
    )
    you_are_expert_now = (
        ValueError('NOT USED')
    )
    you_are_grade8_now = (
        ValueError('NOT USED')
    )
    error_sos_without_auth = (
        "🤖 Hi! Without a password, we don’t know your name... "
        "So first, provide the full name of the student in question, "
        "then ask your question."
    )
    sos_what_is_your_question = "🤖 What’s your question?"
    sos_which_problem_question = "🤖 Which problem is your question about❓"
    sos_other_question = "Please write your question."
    sos_problem_selected = (
        "Problem {problem} selected. Now send the text 📈 or photos 📸 with your question."
    )
    answer_select_one_of = (
        "Problem {problem} selected. Choose an answer from the following options:"
    )
    answer_select_day_of_week = (
        "Problem {problem} selected. Choose an answer—day of the week:"
    )
    answer_now_enter_answer = 'Now enter your answer{problem.ans_type.descr}.'
    answer_follow_recommendations = (
        "Problem {problem} selected.\n{answer_recommendation}"
    )
    answer_send_text_or_photo = (
        "Problem {problem} selected. Now send photos 📸 of your solution."
    )
    zoom_instruction = (
        ValueError('NOT USED')
    )
    list_of_all_topics = ValueError('NOT USED')
    select_one_of_answer_selected = "Option {selected_answer} selected."
    left_zoom_queue = "You successfully left the queue for the oral session."
    error_nothing_was_sent = 'No submissions found (or something went wrong).'
    game_for_chest = '{diff:+}⚡ for a chest.'
    game_for_problem = '{diff:+}⚡ for problem “{title}”.'

    # handlers\student_keyboards.py
    open_game = "🕹🎲 Start a team game 🎉🏆"
    problem_question = "Question about the problem."
    other_question = "Ask a question"
    to_list_of_topics = "To the list of all worksheets."
    topic_hint = "Worksheet {lesson_num}."
    cancel = "Cancel."

    # handlers\teacher_handlers.py
    verdict_plus_no_comments = "Reviewed and approved!"
    verdict_plus_with_comments = "Reviewed and approved! Here are the comments:\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    verdict_minus_no_comments = (
        "Reviewed and not approved, no comments provided. Forwarding all correspondence.\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    )
    verdict_minus_with_comments = (
        "Reviewed and feedback provided:\nForwarding all correspondence.\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    )
    verdict_tick_no_comments = "Reviewed and marked as {verdict_tick} without comments."
    verdict_tick_with_comments = "Reviewed and marked as {verdict_tick}.\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    problem_question_answer = (
        "Here’s the answer to the question about problem {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}). "
        "Forwarding all correspondence.\n⬇⬇⬇⬇"
    )
    oral_accepted_problems = (
        "As a result of the oral session, you were approved for the following problems: {pluses_list}."
    )
    your_level_changed_to = "Your level has been changed to «{level.slevel}»."

msgs = Msgs()
