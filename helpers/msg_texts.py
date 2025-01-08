# from helpers.msg_texts import msgs

class Msgs:

    # handlers\common_handlers.py
    reaction_accepted = 'Принято'
    your_password = "🤖 Ваш пароль:\n<pre>{user.token}</pre>"

    # handlers\group_and_channel_handlers.py
    here_is_your_answer = 'Вот ответ на этот вопрос:'
    this_message_is_for_bot = 'Кажется, это сообщение лично для меня. Заходите: @{username}'

    # handlers\main_handlers.py
    start_if_reg_needed = (
        "🔁 Привет! Это бот для сдачи задач на ВМШ. Пожалуйста, введите свой пароль.\n"
        "Пароль был вам выслан по электронной почте, он имеет вид «pa1ro2ll»\n"
        "(см. также https://shashkovs.ru/vmsh/2024/n/about.html#application)"
    )
    start_if_reg_anybody = (
        "🤖 Привет! Это бот для сдачи задач, вот этих: https://shashkovs.ru/vmsh/2024/n/#09-n.\n"
        "Если задачи окажутся простоватыми, то можно выполнить команду /level_pro и решать вот эти "
        "задачи https://shashkovs.ru/vmsh/2024/p/#09-p, они сложнее и их больше."
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
        "Подробно про оформление: https://shashkovs.ru/vmsh/2024/n/about.html#application"
    )
    bot_internal_error = "☢️ Всё сломалось, бот запутался в текущей ситации :(. Начнём сначала!"
    error_only_compressed_images = '❗❗❗ Бот принимает только сжатые фото: отправляйте картинки по одной, ставьте галочку «Сжать/Compress»'
    error_only_images_and_texts = '❗❗❗ Бот принимает только текстовые сообщения и фотографии решений.'
    you_are_in_online_mode_now = "Теперь вы работаете в режиме «Онлайн»"
    you_are_in_offline_mode_now = "Теперь вы работаете в режиме «Очно в школе»"

    # handlers\student_handlers.py
    auth_needed = 'Необходимо авторизоваться и ввести пароль'
    online_mode_hint = "📡дистанционно📡"
    offline_mode_hint = "🏫в школе🏫"
    problems_keyboard_header = (
        "❓ <b>Нажимайте на задачу, чтобы сдать её</b>\n"
        "{student.name} {student.surname}\n"
        "уровень «{student.level.slevel}», режим {mode_hint}\n"
        "<a href=\"{student.level.url}\">условия</a>, <a href=\"https://t.me/vmsh_179_5_7_2024\">канал кружка</a>"
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
    poly_check_error_hint = 'При n={x} получилось {stv}, а должно было получиться {crv}'
    error_select_one_of = "❌ Выберите один из вариантов: {variants}"
    results_after_answer_accepted = 'Ответ принят на проверку.'
    student_is_sleeping_state_msg = (
        "🤖 Приём задач ботом окончен до начала следующего занятия.\n"
        "Заходите в канал @vmsh_179_5_7_2024 кружка за новостями и решениями."
    )
    you_are_in_novice_now = (
        "Вы переведены в группу начинающих. "
        "Успехов в занятиях! "
        "Вопросы можно задавать в группе @vmsh_179_5_7_2024_chat."
    )
    you_are_in_testing_now = "Вы переведены в тестируемых"
    you_are_in_pro_now = (
        "Вы переведены в группу продолжающих. "
        "Следите за сложностью, если не получается больше половины задач, то лучше перейти в группу «начинающих». "
        "Это будет комфортнее и полезнее!"
    )
    you_are_expert_now = (
        "Вы переведены в группу экспертов. "
        "Здесь будут сложные задачи, не переборщите со сложностью :) "
        "Успехов!"
    )
    you_are_grade8_now = (
        "Вы переведены в группу 8 класса. "
        "Здесь будут сложные задачи, не переборщите со сложностью :) "
        "Успехов!"
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
        "\nИдентификатор конференции: <pre>{87196763644}</pre>"
        "\nкод доступа: <pre>{179179179}</pre></b>"
        "\n\nПожалуйста, при входе поставьте подпись:"
        "\n<b><pre>{student.level} {student.surname} {student.name}</pre></b>"
        "\n(<a href=\"{https://t.me/vmsh_179_5_7_2024/78}\">инструкция</a>)"
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

    # handlers\teacher_handlers.py
    verdict_plus_no_comments = "проверили и поставили плюсик!"
    verdict_plus_with_comments = "проверили и поставили плюсик!\nВот комментарии:\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    verdict_minus_no_comments = "проверили и не засчитали без комментариев :(\nПересылаю всю переписку.\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    verdict_minus_with_comments = "проверили и сделали замечания:\nПересылаю всю переписку.\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    verdict_tick_no_comments = "проверили и поставили {verdict_tick} без комментариев"
    verdict_tick_with_comments = "проверили и поставили {verdict_tick}\n⬇⬇⬇⬇⬇⬇⬇⬇⬇⬇"
    problem_question_answer = (
        "Есть ответ на вопрос по задаче {problem.lesson}{problem.level}.{problem.prob}{problem.item} ({problem.title}).\n"
        "Пересылаю всю переписку.\n"
        "⬇⬇⬇⬇"
    )
    oral_accepted_problems = "В результате устного приёма вам поставили плюсики за задачи: {pluses_list}"
    your_level_changed_to = "Вам изменён уровень на «{level.slevel}»"

msgs = Msgs()
