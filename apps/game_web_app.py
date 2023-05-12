'''
Здесь совершенно ужасный код.
Это стартовая версия веб-приложения в очень зачаточном состоянии.
Требуется большой рефакторинг
'''

from __future__ import annotations

import logging
import re
import weakref

from aiohttp import web, WSMsgType, WSCloseCode
from operator import itemgetter
from time import perf_counter
from typing import List, Dict

from helpers.config import config, logger, DEBUG, APP_PATH
from helpers.obj_classes import db, Webtoken, User, Problem
from helpers.nats_brocker import vmsh_nats
from helpers.consts import NATS_GAME_MAP_UPDATE, NATS_GAME_STUDENT_UPDATE, USER_TYPE
from helpers.bot import bot

__ALL__ = ['routes', 'on_startup', 'on_shutdown']

NATS_SERVER = f"nats://127.0.0.1:4222"

routes = web.RouteTableDef()
routes.static('/static', 'templates/static')

STRICT_COOKIE = dict(domain=None, path='/', max_age=2592000, secure=True, httponly=True, samesite='Strict')
DEBUG_COOKIE = dict(domain=None, path='/', max_age=2592000, secure=False, httponly=True, samesite='Strict')
COOKIE_NAME = 'l'
use_cookie = STRICT_COOKIE
SEND_OPEN_CHEST_TO_BOT = True


def prerate_template(template: str) -> str:
    # Удваиваем фигурные скобки
    template = template.replace('{', '{{').replace('}', '}}')
    # Заменяем двойные квадратные скобки на фигурные
    template = re.sub(r'\[\[(\w+)\]\]', r'{\1}', template)
    return template


templates = {
    'login': open(APP_PATH / 'templates/login.html', 'r', encoding='utf-8').read(),
    'game': open(APP_PATH / 'templates/mathgame.html', 'r', encoding='utf-8').read(),
}


def board_response(user: User):
    print('board_response')
    return web.Response(text=templates['game'], content_type='text/html')


@routes.get('/game')
async def get_online(request):
    print('get_online')
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        print('return login')
        return web.Response(text=templates['login'], content_type='text/html')
    else:
        print('return board')
        return board_response(user)


@routes.post('/game')
async def post_online(request):
    print('get_online')
    data = await request.post()
    token = data.get('password', None)
    user = User.get_by_token(token)
    cookie_webtoken = Webtoken.webtoken_by_user(user)
    if cookie_webtoken:
        print('return board')
        response = board_response(user)
        response.set_cookie(name=COOKIE_NAME, value=cookie_webtoken, **use_cookie)
        return response
    else:
        return web.Response(text=templates['login'], content_type='text/html')


# @routes.get('/gametimeline') ####убрать
# async def get_gametimeline(request):
#     print('gametimeline')
#     command_id = request.query['command_id']
#     cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
#     user = Webtoken.user_by_webtoken(cookie_webtoken)
#     if not user:
#         print('return login')
#         return web.Response(text=templates['login'], content_type='text/html')
#     else:
#         print('return board')
#         return board_response(user)


@routes.get('/game/webtoken/{webtoken}')
async def get_webtoken(request):
    webtoken = request.match_info['webtoken']
    user = Webtoken.user_by_webtoken(webtoken)
    response = web.HTTPSeeOther('/game')
    if user:
        response.set_cookie(name=COOKIE_NAME, value=webtoken, **use_cookie)
    return response


@routes.post('/game/buy')
async def post_game_buy(request):
    data = await request.json()
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'}, status=401)
    # todo validate
    command = db.get_student_command(user.id)
    command_id = command['command_id'] if command else -1
    x = data.get('x', None)
    y = data.get('y', None)
    amount = data.get('amount', None)
    if not amount or type(amount) != int or not (1 <= amount <= 10):
        logger.warning(f'post_game_buy {data=} ignored')
        return web.json_response(data={'ok': 'ignored'}, status=400)
    if not x or not y or type(x) != int or type(y) != int or not 0 <= x <= 200 or not 0 <= y <= 200:
        logger.warning(f'post_game_buy {data=} ignored')
        return web.json_response(data={'ok': 'ignored'}, status=400)
    if not (0 <= x <= 5 and 0 <= y <= 5) and not db.check_neighbours(command_id, x, y):
        return web.json_response(data={'ok': 'ignored'}, status=400)
    db.add_payment(user.id, command_id, x, y, amount)
    # Отправляем всем уведомление, что открылась новая ячейка на карте
    await vmsh_nats.publish(NATS_GAME_MAP_UPDATE, command_id)
    return web.json_response(data={'ok': 'sure'})


@routes.post('/game/flag')
async def post_game_flag(request):
    data = await request.json()
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'}, status=401)
    # todo validate
    command = db.get_student_command(user.id)
    command_id = command['command_id'] if command else -1
    x = data.get('x', None)
    y = data.get('y', None)
    if not x or not y or type(x) != int or type(y) != int or not 0 <= x <= 200 or not 0 <= y <= 200:
        logger.warning(f'post_game_buy {data=} ignored')
        return web.json_response(data={'ok': 'ignored'})
    db.set_student_flag(user.id, command_id, x, y)
    # Отправляем всем уведомление, что открылась новая ячейка на карте (или появился флаг)
    await vmsh_nats.publish(NATS_GAME_MAP_UPDATE, command_id)
    return web.json_response(data={'ok': 'sure'})


@routes.post('/game/chest')
async def post_game_chest(request):
    data = await request.json()
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'}, status=401)
    command = db.get_student_command(user.id)
    command_id = command['command_id'] if command else -1
    x = data.get('x', None)
    y = data.get('y', None)
    bonus = data.get('bonus', None)
    if not x or not y or type(x) != int or type(y) != int or not 0 <= x <= 200 or not 0 <= y <= 200 or not bonus or type(bonus) != int or not 1 <= bonus <= 10:
        logger.warning(f'post_game_buy {data=} ignored')
        return web.json_response(data={'ok': 'ignored'}, status=400)
    db.add_student_chest(user.id, command_id, x, y, bonus)
    # Отправляем всем уведомление, что у студента появились новые «деньги»
    await vmsh_nats.publish(NATS_GAME_STUDENT_UPDATE, user.id)
    if SEND_OPEN_CHEST_TO_BOT:
        if bonus % 10 == 1 and bonus % 100 != 11:
            suffix = f'{bonus} балл'
        elif 2 <= bonus % 10 <= 4 and not 11 <= bonus % 100 <= 14:
            suffix = f'{bonus} балла'
        else:
            suffix = f'{bonus} баллов'
        try:
            await bot.send_message(chat_id=user.chat_id, text=f'Вы открыли сундук, там на дне {suffix}')
        except:
            pass
    return web.json_response(data={'ok': 'sure'})


def get_map_opened(command_id) -> List[List]:
    # TODO Кеширование!
    opened = db.get_opened_cells(command_id)  # x, y
    opened = [[r['x'], r['y']] for r in opened]
    return opened


def get_map_flags(command_id) -> List[List]:
    # TODO Кеширование!
    flags = db.get_flags_by_command(command_id)  # x, y
    flags = [[r['x'], r['y']] for r in flags]
    return flags


def get_game_data(student: User) -> dict:
    # Нужно получить
    # - список решённых задач с timestamp'ами
    # - список покупок с timestamp'ами
    # - текущую карту
    # - команду студента
    # - список флагов на карте
    # - личный флаг студента
    # - список открытых сундуков
    st = perf_counter()
    command = db.get_student_command(student.id)
    student_command = command['command_id'] if command else -1
    solved = db.get_student_solved(student.id, Problem.last_lesson_num(student.level))  # ts, title
    payments = db.get_student_payments(student.id, student_command)  # ts, amount
    opened = get_map_opened(student_command)
    flags = get_map_flags(student_command)
    my_flag = db.get_flag_by_student_and_command(student.id, student_command)
    chests_rows = db.get_student_chests(student.id, student_command)
    # Собираем из решённых задач и оплат event'ы
    events = []
    for paym in payments:
        events.append([paym['ts'], -paym['amount']])
    for chest in chests_rows:
        events.append([chest['ts'], chest['bonus']])
    chests = [[r['x'], r['y']] for r in chests_rows]
    used_titles = set()
    for solv in solved:
        if '⚡' not in solv['title']:
            continue
        score, clear_title = solv['title'].split('⚡')
        score = int(score) if score.strip().isdecimal() else 2
        if clear_title in used_titles:
            continue
        else:
            used_titles.add(clear_title)
        # Защита от продолжающих, которые решают задачи начинающих. Они получают в 1.5 раза меньше баллов
        if solv['level'] == 'н' and command['level'] != 'н':
            score = int(round(score / 1.5))
        events.append([solv['ts'], score])
    events.sort(key=itemgetter(0))
    events = [ev[1] for ev in events]
    # Собираем карту  TODO Сделать минимальное кеширование
    data = {'events': events, 'opened': opened, 'flags': flags, 'myFlag': my_flag, 'chests': chests}
    en = perf_counter()
    # logger.warning(f'get_game_data {en - st:0.3f} seconds')  # TODO Удалить
    return data


@routes.post('/game/me')
async def post_online(request):
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'}, status=401)
    data = get_game_data(user)
    return web.json_response(data=data)


@routes.post('/game/timeline/{command_id}')
async def post_timeline(request):
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if (not user) or (not user.type == USER_TYPE.TEACHER):
        return web.json_response(data={'error': 'relogin'}, status=401)
    command_id = request.match_info['command_id']
    data = db.get_opened_cells_timeline(command_id)
    return web.json_response(data=data)


# В этом словаре мы храним список слабых ссылок на вебсокеты пользователей
_user_id_to_websocket: Dict[int, List[weakref.ReferenceType[web.WebSocketResponse]]] = {}


@routes.get('/game/ws')
async def websocket(request):
    user = Webtoken.user_by_webtoken(request.cookies.get(COOKIE_NAME, None))
    if not user:
        return
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    if user.id not in _user_id_to_websocket:
        _user_id_to_websocket[user.id] = []
    cur_user_websockets = _user_id_to_websocket[user.id]
    cur_user_websockets.append(weakref.ref(ws))

    # Этот цикл «зависает» до тех пор, пока коннекшн не сдохнет
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
                    for ws_ind in range(len(cur_user_websockets) - 1, -1, -1):
                        ref = cur_user_websockets[ws_ind]()
                        if ref is None or ref is ws:
                            cur_user_websockets.pop(ws_ind)
            elif msg.type == WSMsgType.ERROR:
                print(ws.exception())
    finally:
        # Удаляем все ссылки на текущй коннекшн
        for ws_ind in range(len(cur_user_websockets) - 1, -1, -1):
            ref = cur_user_websockets[ws_ind]()
            if ref is None or ref is ws:
                cur_user_websockets.pop(ws_ind)
    return ws


async def nats_handle_map_update(command_id):
    # logger.warning(f"nats_handle_map_update {command_id=}, {os.getpid()=}, {len(user_id_to_websocket)=}")
    students = db.get_all_students_by_command(command_id)
    for student_id in students:
        for ws in set(_user_id_to_websocket.get(student_id, [])):
            data = get_game_data(User.get_by_id(student_id))
            try:
                await ws().send_json(data)
            except Exception as e:
                logger.exception('Отправка данных через websocket отвалилась')


async def nats_handle_student_update(student_id):
    # logger.warning(f"nats_handle_student_update {student_id=}, {os.getpid()=}, {len(user_id_to_websocket)=}")
    student = User.get_by_id(student_id)
    if not student:
        return
    data = None
    for ws in set(_user_id_to_websocket.get(student_id, [])):
        if data is None:
            data = get_game_data(User.get_by_id(student_id))
        try:
            await ws().send_json(data)
        except Exception as e:
            logger.exception('Отправка данных через websocket отвалилась')


async def on_startup(app):
    logger.debug('game on_startup')
    if __name__ == "__main__":
        # Настраиваем БД
        db.setup(config.db_filename)
    # Подключаемся к NATS
    await vmsh_nats.setup()
    await vmsh_nats.subscribe(NATS_GAME_MAP_UPDATE, nats_handle_map_update)
    await vmsh_nats.subscribe(NATS_GAME_STUDENT_UPDATE, nats_handle_student_update)


async def on_shutdown(app):
    logger.warning('game on_shutdown')
    if __name__ == "__main__":
        db.disconnect()
    await vmsh_nats.disconnect()
    # Останавливаем все websocket'ы
    for user_id, websockets in _user_id_to_websocket.items():
        for ws in set(websockets):
            ref = ws()
            if ref:
                await ref.close(code=WSCloseCode.GOING_AWAY, message='Server shutdown')
    logger.warning('game web app Bye!')


def configue(app):
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


# Откладка по конкретному студенту
# db.setup(config.db_filename)
# print(get_game_data(User.get_by_token('be9fu3ha')))
# exit()


if __name__ == "__main__":
    # Включаем все отладочные сообщения
    SEND_OPEN_CHEST_TO_BOT = False
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(DEBUG)
    use_cookie = DEBUG_COOKIE
    app = web.Application()
    configue(app)
    print('Open http://127.0.0.1:8080/game')
    web.run_app(app)
