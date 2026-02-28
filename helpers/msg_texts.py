# from helpers.msg_texts import msgs

class Msgs:
    # ------------------------------------------------------------------
    # Common / shared messages (both roles)
    # ------------------------------------------------------------------

    # handlers\common_handlers.py
    reaction_accepted = 'Принято'
    your_password = "🤖 Ваш пароль:\n<pre>{user.token}</pre>"

    # handlers\group_and_channel_handlers.py
    here_is_your_answer = 'Вот ответ на этот вопрос:'
    this_message_is_for_bot = 'Кажется, это сообщение лично для меня. Заходите: @{username}'

    # handlers\main_handlers.py
    start_if_reg_needed = (
        "🔁 Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль.\n"
        "Пароль высылается по электронной почте, указанной на mosru. Он имеет вид «pa1ss2wo3rd»\n"
        "(см. также https://shashkovs.ru/vmsh/2025/n/about.html#application)"
    )
    start_if_reg_anybody = (
        "🤖 Привет! Это бот для сдачи задач.\n"
        "После входа вы увидите список задач вашей группы."
    )
    this_password_is_blocked = (
        "🔁 Этот пароль был заблокирован.\n"
        "Скорее всего новый пароль был выслан по электронной почте, не забудьте проверить спам."
    )
    welcome_user = "🤖 ОК, Добро пожаловать, {user.name} {user.surname}"
    user_is_not_activated = (
        "🔁 Привет!\n"
        "Для начала обучения нужно оставить заявку на обучение на кружке на mos,ru.\n"
        "Через несколько рабочих дней на почту придёт инструкция, а ваш аккаунт будет активирован.\n"
        "Подробно про оформление: https://shashkovs.ru/vmsh/2025/n/about.html#application"
    )
    bot_internal_error = "☢️ Всё сломалось, бот запутался в текущей ситации :(. Начнём сначала!"
    error_only_compressed_images = '❗❗❗ Бот принимает только сжатые фото: отправляйте картинки по одной, ставьте галочку «Сжать/Compress»'
    error_only_images_and_texts = '❗❗❗ Бот принимает только текстовые сообщения и фотографии решений.'
    you_are_in_online_mode_now = "Теперь вы работаете в режиме «Онлайн»"
    you_are_in_offline_mode_now = "Теперь вы работаете в режиме «Очно в школе»"
    no_access_to_group = "У вас нет доступа к этой группе."

    # handlers\student_handlers.py
    auth_needed = 'Необходимо авторизоваться и ввести пароль'
    online_mode_hint = "📡дистанционно📡"
    offline_mode_hint = "🏫в школе🏫"
    problems_keyboard_header = (
        "❓ <b>Нажимайте на задачу, чтобы сдать её</b>\n"
        "{student.name} {student.surname}\n"
        "группа «{group.public_name}», режим {mode_hint}\n"
        "<a href=\"{group.conditions_url}\">условия</a>, <a href=\"https://t.me/vmsh_179_5_7_2025\">канал кружка</a>"
    )
    solutions_are_not_accepted_now = "🤖 Приём задач ботом окончен до начала следующего занятия."
    error_file_is_not_accepted = (
        '❗❗❗ Файл НЕ ПРИНЯТ на проверку! Сначала выберите задачу!\n'
        '(Можно посылать несколько фотографий решения в виде галереи, либо каждый раз нужно выбирать задачу.)'
    )
    error_text_is_not_accepted_now = '❗❗❗ Текст НЕ ПРИНЯТ на проверку! Сначала выберите задачу!\n'
    error_file_is_too_large = "❌ Размер файла превышает ограничение в 5 мегабайт"
    sol_accepted = "Принято на проверку"
    question_accepted = "Вопрос записан"
    hour_rate_limit_error = '💤⌛ В течение одного часа бот не принимает больше 3 ответов. Отправьте ваш ответ в начале следующего часа.'
    dayly_rate_limit_error = '💤⌛ В течение одного дня бот не принимает больше 6 ответов. Отправьте ваш ответ завтра.'
    poly_check_error_hint = 'В точке {x} получилось {stv}, а должно было получиться {crv}'
    error_select_one_of = "❌ Выберите один из вариантов: {variants}"
    results_after_answer_accepted = 'Ответ принят на проверку.'
    student_is_sleeping_state_msg = (
        "🤖 Приём задач ботом окончен до начала следующего занятия.\n"
        "Заходите в канал @vmsh_179_5_7_2025 кружка за новостями и решениями."
    )
    error_sos_without_auth = (
        "🤖 Привет! Без пароля мы не знаем, как вас зовут...\n"
        "Поэтому сначала напишите ФИО ученика, о котором идёт речь.\n"
        "И потом — вопрос."
    )
    sos_what_is_your_question = "🤖 Какой у вас вопрос?"
    sos_which_problem_question = "🤖 По какой задаче у вас вопрос❓"
    sos_other_question = "Напишите ваш вопрос"
    sos_problem_selected = "Выбрана задача {problem}.\nТеперь отправьте текст 📈 или фотографии 📸 с вашим вопросом."
    answer_select_one_of = "Выбрана задача {problem}.\nВыберите ответ — один из следующих вариантов:"
    answer_select_day_of_week = "Выбрана задача {problem}.\nВыберите ответ — день недели:"
    answer_now_enter_answer = 'Теперь введите ответ{problem.ans_type.descr}'
    answer_follow_recommendations = "Выбрана задача {problem}.\n{answer_recommendation}"
    answer_send_text_or_photo = "Выбрана задача {problem}.\nТеперь отправьте текст 📈 или фотографии 📸 вашего решения."
    zoom_instruction = (
        "Выбрана устная задача. "
        "\n<b>Заходите в zoom-конференцию («Войти» в zoom)"
        "\nИдентификатор конференции: <pre>87196763644</pre>"
        "\nкод доступа: <pre>179179179</pre></b>"
        "\n\nПожалуйста, при входе поставьте подпись:"
        "\n<b><pre>{student.group_code} {student.surname} {student.name}</pre></b>"
        "\n(<a href=\"https://t.me/vmsh_179_5_7_2025/78\">инструкция</a>)"
        "\n\nКак только один из преподавателей освободится, вас пустят в конференцию и переведут в комнату к преподавателю. "
        "После окончания сдачи нужно выйти из конференции. "
        "Когда у вас появится следующая устная задача, этот путь нужно будет повторить заново. "
        "Мы постараемся выделить время каждому, но ожидание может быть достаточно долгим."
    )
    list_of_all_topics = "Вот список всех листков:"
    select_one_of_answer_selected = "Выбран вариант {selected_answer}."
    left_zoom_queue = "Вы успешно покинули очередь на устную сдачу."
    error_nothing_was_sent = 'Нет ни одной посылки (или что-то пошло не так)'
    game_for_chest = '{diff:+}⚡ за сундук'
    game_for_problem = '{diff:+}⚡ за задачу «{title}»'

    # handlers\student_keyboards.py
    open_game = "🕹🎲 Открыть командную игру 🎉🏆"
    problem_question = "Вопрос по задаче"
    other_question = "Другой вопрос"
    to_list_of_topics = "К списку всех листков"
    topic_hint = "Листок {lesson_num}"
    cancel = "Отмена"

    # ------------------------------------------------------------------
    # Teacher / admin UI messages (prefix t_ / a_)
    # These keys can be overridden via _BotUIMsgs sheet.
    # ------------------------------------------------------------------

    # handlers\teacher_handlers.py
    t_verdict_plus_no_comments = "проверили и поставили плюсик!"
    t_verdict_plus_with_comments = "проверили и поставили плюсик!\nВот комментарии:\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    t_verdict_minus_no_comments = "проверили и не засчитали без комментариев :(\nПересылаю всю переписку.\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    t_verdict_minus_with_comments = "проверили и сделали замечания:\nПересылаю всю переписку.\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    t_verdict_tick_no_comments = "проверили и поставили {verdict_tick} без комментариев"
    t_verdict_tick_with_comments = "проверили и поставили {verdict_tick}\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    t_problem_question_answer = (
        "Есть ответ на вопрос по задаче {problem.lesson}{problem.group_code}.{problem.prob}{problem.item} ({problem.title}).\n"
        "Пересылаю всю переписку.\n"
        "⬇⬇⬇⬇"
    )

    t_oral_accepted_problems = "В результате устного приёма вам поставили плюсики за задачи: {pluses_list}"
    t_your_group_changed_to = "Вам изменена группа на «{public_name}»"
    t_all_written_checked = "Ничего себе! Все эти письменные задачи проверены!"
    t_no_sos_questions = "Ничего себе! Вопросов нет"
    t_choose_question = "Выберите вопрос"
    t_choose_student_for_pluses = "Выберите школьника для внесения задач"
    t_mark_oral_tasks_intro = (
        "Отметьте задачи, за которые нужно поставить плюсики (и нажмите «Готово»)"
        "\n(у вас сейчас режим «{mode_label}», /online и /school для переключения)"
    )
    t_edtplus_format_hint = "🤖 Пришлите запрос на простановку плюсов в формате\n«/edtplus_lesson_token», например «/edtplus_12_aa9bb4»"
    t_recheck_format_hint = "🤖 Пришлите запрос на перепроверку в формате\n«/recheck token problem», например «/recheck aa9bb4 3н.11а»"
    t_student_with_token_not_found = "🤖 Студент с токеном {token} не найден"
    t_problem_not_found_ref = "🤖 Задача {problem_ref} не найдена"
    t_problem_ambiguous_ref = "🤖 Задача {problem_ref} неоднозначна. Укажите формат group_id:lesson.probitem."
    t_problem_not_found_id = "🤖 Задача с id {prob_id} не найдена"
    t_resend_for_checking = "Переотправили на проверку"
    t_set_group_usage = "/set_group token <group_id|short_code>"
    t_group_not_exists = "Группа {new_group} не существует."
    t_student_group_changed = "Студент с токеном {token} переведён в группу «{public_name}»"
    t_select_problem_to_check_counts = "Выберите задачу для проверки ({prb_count}✏️, {sos_count}❓)"
    t_teacher_set_online_usage = "/set_online token online/school"
    t_student_online_changed = "Студент с токеном {token} переведён"
    t_message_deleted = "Сообщение было удалено..."
    t_task_already_being_checked = "Эту задачу уже кто-то взялся проверять."
    t_answer_recorded = "Ответ записан"
    t_queue_empty_retry = "Сейчас очередь пуста. Повторите через пару минут."
    t_bot_broken_result_not_saved = "Что-то в боте сломалось и результат оценки не засчитан. :( Попробуйте ещё раз."
    t_rate_oral_submission = "Оцените устную сдачу:"
    t_find_student_hint = "🤖 Введите часть фамилии"
    t_no_students_found = "Не нашлось ни одного студента"

    # handlers\teacher_keyboards.py
    t_btn_answer_question = "Ответить на вопрос (всего {sos_count})"
    t_btn_check_written = "Проверять письменные (всего {prb_count})"
    t_btn_insert_oral_pluses = "Внести плюсы за устную сдачу"
    t_btn_cancel = "Отмена"
    t_btn_accept_task = "👍 Засчитать задачу {problem_str}"
    t_btn_reject_task = "❌ Отклонить и переслать все сообщения выше студенту {student_name}"
    t_btn_tick_task = "{verdict_tick} за задачу {problem_str}"
    t_btn_refuse_checking = "Отказаться от проверки и вернуться назад"
    t_btn_send_answer = "Отправить ответ на вопрос"
    t_btn_skip_answer = "Не отвечать на вопрос и вернуться назад"
    t_btn_level_template = "Группа: {short_code} «{public_name}»"
    t_btn_ready_oral = "Готово (завершить сдачу и внести в кондуит)"
    t_btn_cancel_oral = "Отмена (ничего не трогать и выйти)"
    t_select_action = "Выберите действие ({prb_count}✏️, {sos_count}❓)"
    t_ok_saved = 'Ок, записал'
    t_question_on_problem = (
        "Вопрос по задаче {problem.lesson}{problem.group_code}.{problem.prob}{problem.item} ({problem.title})\n"
        "{student.name_for_teacher}\n"
        "/recheck_{student.token}_{problem.id}\n"
        "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    )
    t_checking_problem = (
        "Проверяем задачу {problem.lesson}{problem.group_code}.{problem.prob}{problem.item} ({problem.title})\n"
        "{student.name_for_teacher}\n"
        "⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    )
    t_write_answer = (
        '⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n'
        'Напишите ответ (можно приложить картинку)'
    )
    t_write_checking_comment = (
        '⬆⬆⬆⬆⬆⬆⬆⬆⬆⬆\n'
        'Напишите комментарий или скриншот 📸 вашей проверки (или просто поставьте плюс)'
    )
    t_forward_discussion_to_student_word = 'Задачу'
    t_verdict_plus_text = (
        '👍 Отлично, поставили плюсик за задачу {problem.lesson}{problem.group_code}.{problem.prob}{problem.item} школьнику {student.token} {student.surname} {student.name}!'
        '\nВсего проверено задач: {tot_checked} (+{plus}, −{minus}){milestone}'
        '\nДля исправления:'
        ' /recheck_{student.token}_{problem.id}'
    )
    t_verdict_some_text = (
        '👍 Поставили {verdict_text} за задачу {problem.lesson}{problem.group_code}.{problem.prob}{problem.item} школьнику {student.token} {student.surname} {student.name}! '
        '\nВсего проверено задач: {tot_checked} (+{plus}, −{minus}){milestone}'
        '\nДля исправления:'
        ' /recheck_{student.token}_{problem.id}'
    )
    t_verdict_minus_text = (
        '❌ Эх, поставили минусик за задачу {problem.lesson}{problem.group_code}.{problem.prob}{problem.item} '
        'школьнику {student.token} {student.surname} {student.name}!'
        '\nВсего проверено задач: {tot_checked} (+{plus}, −{minus}){milestone}'
        '\nДля исправления:'
        ' /recheck_{student.token}_{problem.id}'
    )
    t_oral_plus_give_surname = "Введите фамилию школьника (можно начало фамилии), чтобы внести плюсы"
    t_putting_plusses = "Вносим плюсики школьнику:\n{student.name_for_teacher}"
    t_online_mode_school = 'В ШКОЛЕ'
    t_online_mode_online =  'ОНЛАЙН'
    t_written_res_1 = "Школьник: {student.token} {student.surname} {student.name}\n"
    t_written_res_2 = "\nПоставлены плюсы 👍 за задачи: {human_readable_pluses_joined}"
    t_written_res_3 = "\nПоставлены минусы ❌ за задачи: {human_readable_minuses_joined}"
    t_written_res_4 = '\nДля исправления /edtplus_{lesson}_{student.token}'
    t_stundent_name_not_found = "Студент с токеном {token} не найден"
    t_cmd_online = 'Дистанционный приём'
    t_cmd_in_school = 'Очный приём'
    t_cmd_find_student = 'Найти студента'
    t_cmd_set_group = 'Поставить студенту группу'
    t_cmd_set_online = 'Поменять студенту режим очно/дистант'
    t_cmd_set_teacher = 'Снова стать учителем'
    t_cmd_statw = 'Посмотреть статистику'
    t_cmd_student_results = 'Посмотреть результаты школьника'
    t_cmd_all_student_results = 'Посмотреть ВСЕ результаты школьника'
    # check milestones
    t_check_milestone1 = '🌟 — старт положен: первая проверка! Спасибо ❤️'
    t_check_milestone10 = '🔟✨ — 10 задач: отличный темп, так держать ❤️'
    t_check_milestone50 = '🏅🎉 — 50 проверок: мощный вклад в прогресс ребят ❤️'
    t_check_milestone100 = '💯🏆 — 100 задач: вау, это уже система ❤️'
    t_check_milestone200 = '2️⃣🎖️✨ — 200: стабильность и качество, спасибо ❤️'
    t_check_milestone300 = '3️⃣🥉🎆 — 300 задач: выдержка уровня “профи” ❤️'
    t_check_milestone400 = '4️⃣🥈🌠 — 400: очень сильная дистанция, продолжаем ❤️'
    t_check_milestone500 = '5️⃣🥇💫 — 500: половина тысячи! впечатляет ❤️'
    t_check_milestone600 = '6️⃣🏵️🌈 — 600: вот это регулярность, супер ❤️'
    t_check_milestone700 = '7️⃣🌟🎇 — 700: держите ритм — это реально важно ❤️'
    t_check_milestone800 = '8️⃣🏆✨ — 800: почти тысяча, отличный марафон ❤️'
    t_check_milestone900 = '9️⃣💖🎊 — 900: финишная прямая до 1000 ❤️'
    t_check_milestone1000 = '1️⃣0️⃣0️⃣0️⃣👑🎉 — 1000 задач! легендарная отметка ❤️'
    t_check_milestone1100 = '1️⃣1️⃣0️⃣0️⃣🌠✨ — 1100: темп не сбавляется, огонь ❤️'
    t_check_milestone1200 = '1️⃣2️⃣0️⃣0️⃣🏅🌈 — 1200: столько полезной обратной связи ❤️'
    t_check_milestone1300 = '1️⃣3️⃣0️⃣0️⃣🥉💫 — 1300: уровень “железная дисциплина” ❤️'
    t_check_milestone1400 = '1️⃣4️⃣0️⃣0️⃣🥈🎆 — 1400: впечатляющая дистанция, спасибо ❤️'
    t_check_milestone1500 = '1️⃣5️⃣0️⃣0️⃣🥇🎇 — 1500: полторы тысячи — мощно ❤️'
    t_check_milestone1600 = '1️⃣6️⃣0️⃣0️⃣🏵️✨ — 1600: стабильная работа на результат ❤️'
    t_check_milestone1700 = '1️⃣7️⃣0️⃣0️⃣🌟🎊 — 1700: вы реально тащите ❤️'
    t_check_milestone1800 = '1️⃣8️⃣0️⃣0️⃣🏆🌠 — 1800: почти 2000, очень круто ❤️'
    t_check_milestone1900 = '1️⃣9️⃣0️⃣0️⃣💖✨ — 1900: ещё чуть-чуть до 2000 ❤️'
    t_check_milestone2000 = '2️⃣0️⃣0️⃣0️⃣👑🎉 — 2000 задач! это уже история ❤️'
    t_check_milestone2100 = '2️⃣1️⃣0️⃣0️⃣🌠🌈 — 2100: невероятная выносливость ❤️'
    t_check_milestone2200 = '2️⃣2️⃣0️⃣0️⃣🏅💫 — 2200: спасибо за такой объём и точность ❤️'
    t_check_milestone2300 = '2️⃣3️⃣0️⃣0️⃣🥉🎆 — 2300: сильнейший вклад в обучение ❤️'
    t_check_milestone2400 = '2️⃣4️⃣0️⃣0️⃣🥈🎇 — 2400: держите планку — впечатляет ❤️'
    t_check_milestone2500 = '2️⃣5️⃣0️⃣0️⃣🥇✨ — 2500: 2.5k проверок — браво ❤️'

    # handlers\group_and_channel_handlers.py (admin/teacher-side)
    a_reply_only_to_forwarded = "Отвечайте на пересланные сообщения с вопросом"
    a_forwarded_ok = "Переслал."
    a_forward_failed = "Не получилось послать ответ. Попробуйте указать токен первым словом или ответить вручную."

    # handlers\admin_handlers.py
    a_all_data_updated = "Все данные обновлены"
    a_teachers_updated = "Учителя обновлены"
    a_students_updated = "Студенты обновлены"
    a_problems_updated = "Задачи обновлены"
    a_groups_updated = "Группы обновлены"
    a_error_list = "Ошибки:"
    a_ui_messages_updated = 'UI messages updated\nRestart bot to apply them'
    a_survey_created = 'Опрос с id={survey_id} создан.\n{survey_type=}\n{question=}\n{choices=}'
    a_broadcast_task_created = "Создано задание рассылки сообщений"
    a_broadcast_done = "Все сообщения разосланы ({sent} штук). Проблемы возникли с {bad_tokens!r}"
    a_forward_all_start = "Начинаем пересылать"
    a_forward_all_errors = "Ошибки: {errors_text}"
    a_create_survey_usage = "/create_survey r/c\nВопрос\n- Один\n- Два"
    a_assign_survey_usage = "/assign_survey_to_tokens surv_id\ntok1 tok2 tok3"
    a_survey_assigned = "Назначен опрос {survey_id} {done} пользователям"
    a_survey_disabled = "Опрос {survey_id} отключён"
    a_problem_not_found = "Задача не найдена"
    a_no_submissions = "Нет ни одной посылки (или что-то пошло не так)"
    a_bad_group = "Кривая группа, не парсится"
    a_done = "Готово"
    a_set_game_usage = "/set_game_command token number"
    a_admin_rights_gained = "Admin rights gained!"
    a_teachers_commands_updated = "Команды учителей обновлены"
    a_teachers_commands_task_created = "Создано задание обновления статусов"
    a_recheck_task_created = "Создано задание по перепроверке тестовой задачи"
    a_recheck_summary = "Задача {problem} перепроверена. {oks} плюсов, {errs} минусов. Исправлено {changes} посылок"
    a_all_students_awakened = "Все школьники переведены в режим сдачи задач"
    a_pluses_refreshed = "Все плюсики обновлены: {num_updated} обновлено, {not_updated} не обновлено, {errors_count} ошибок."
    a_pluses_errors = "Ошибки по: `{errors_joined}`"
    a_pluses_task_created = "Создано задание по обновлению плюсиков, force={force}"
    a_awaken_task_created = "Создано задание по переводу в режим сдачи задач"
    a_all_students_sleeping = "Все школьники переведены в статус SLEEPING"
    a_sleep_task_created = "Создано задание по переводу в статус SLEEPING"
    a_teacher_password = "Ваш пароль:\n<code>{user.token}</code>"
    a_student_not_found = "🤖 Студент {token} не найден"
    a_game_command_update = "Студент с токеном {token} переведён в команду {command_id}"
    a_moderate_could_not_delete = 'Сообщение выше удалить не удалось :('
    a_moderate_could_not_ban = 'Юзера выше не удалось забанить :('
    a_moderate_banned = 'Пользователь {message.from_user!r} забанен'
    a_spam_regex = (
        r'бонанз|играю в этом казино|КТО ХОЧЕТ ЗАРАБОТАТЬ|онлайн казик|\bинтим\b'
        r'|срочно.*требу.тся.*человек|лучшее казино|официальное казино|(?:доход|оплата).*от.*рублей.*(?:месяц|день)'
        r'|пишите в лс|казино|в личные сообщения|доходность от|доход от.*день'
    )

    def update_from_dict(self, ui_messages_dict: dict):
        for key, value in ui_messages_dict.items():
            setattr(self, key, value)


msgs = Msgs()

if __name__ == '__main__':
    import re
    1; cur_code = open(__file__, encoding='utf-8').read()
    1; attrs = re.findall(r'(?<=^    )\w+(?=\s*=)', cur_code, flags=re.MULTILINE)
    for attr in attrs:
        msg = getattr(msgs, attr)
        if type(msg) is not str:
            continue
        msg = msg.replace('"', '""')
        print(attr, '"' + msg + '"', sep='\t')
