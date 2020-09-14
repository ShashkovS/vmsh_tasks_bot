# Бот для проведения кружка по математике

## Секреты
- creds/vmsh_bot_sheets_creds.json — ключи для google API (см. https://console.developers.google.com/iam-admin/serviceaccounts/)
- creds/telegram_bot_key — ключ телеграм-бота
- creds/settings_sheet_key — ключ гугль-таблицы с настройками

### Как получить секреты для google API
Попросите Сережу Шашкова, либо поищите в чате.

### Как получить секреты для google API, если вы хотите создать свои
- идем по адресу https://console.developers.google.com/iam-admin/serviceaccounts/
- выбираем кнопку СОЗДАТЬ ПРОЕКТ
- в поле название проекта вводим VmshTasksBot (название может быть любым), жмём создать
- переходим в проект, слева нажимаем на "API и сервисы"
- слева нажимаем "Учетные данные"
- ищем сверху по центру кнопку "+ СОЗДАТЬ УЧЕТНЫЕ ДАННЫЕ", выбираем "Сервисный аккаунт"
- вводим название сервисного аккаунта VmshTasksBotServiceAccount (название может быть любым), жмём "создать"
- в поле "Выберите роль" нажимаем Проект > Редактор, следом "Продолжить"
- жмём "Готово"
- в списке сервисных аккаунтов должен появиться созданный сервисный аккаунт. Над ним справа-сверху ищем ссылку "Управление сервисными аккаунтами", переходим по ней
- находим в списке наш аккаунт, справа от него нажимаем на вертикальное троеточие ("Действия"), выбираем "Создать ключ".
- выбираем json, "создать".
- кладём этот файл в проект с кодом по адресу creds/vmsh_bot_sheets_creds.json
- запускаем бота python main.py
- в телеграме пишем боту /hello, затем любой пароль
- интерпретатор выкинет полотно с ошибкой, в полотне будет url типа https://console.developers.google.com/apis/api/sheets.googleapis.com/overview?project=xxxx, переходим туда
- там будет на выбор ВКЛЮЧИТЬ и ПОПРОБОВАТЬ ЭТОТ АПИ. нажимаем ВКЛЮЧИТЬ, ждем несколько минут (изменения подхватываются не сразу).
- готово


### Запуск тестов
Перед запуском тестов убедитесь, что у вас установлены зависимости для тестов:
```bash
pip install -r requirements-text.txt
```
Чтобы запустить тесты (unix), просто запустите скрипт run_tests.sh:
```bash
./run_tests.sh
```
Если у вас не unix система или вам лень, запускайте команду `pytest -vvs tests/` напрямую.

### Рулим хендлерами

Мы не используем декораторы, а регистрируем все хендлеры в 

    async def on_startup(app):
        logging.warning('Start up!')
        if USE_WEBHOOKS:
            await check_webhook()
        dispatcher.register_message_handler(start, commands=['start'])
        dispatcher.register_message_handler(update_all_internal_data, commands=['update_all_quaLtzPE'])
        dispatcher.register_message_handler(process_regular_message, content_types=["photo", "document", "text"])
        dispatcher.register_callback_query_handler(inline_kb_answer_callback_handler)
        
### Рулим состояниями

Под каждый state мы пишем функцию-обработчик. Добавляем её в словарь

    state_processors = {
        GET_USER_INFO_STATE: prc_get_user_info_state,
        GET_TASK_INFO_STATE: prc_get_task_info_state,
        SENDING_SOLUTION_STATE: prc_sending_solution_state,
    }


Обычные сообщения обрабатываются так:

    async def process_regular_message(message: types.Message):
        cur_chat_state = get_state(message.chat.id)
        state_processor = state_processors.get(cur_chat_state, prc_WTF)
        await state_processor(message)

То есть определили state, вызвали соответствующую функцию.
Здесь в нормальной ситуации мы ничего не дорабатываем