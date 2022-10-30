'''
Здесь совершенно ужасный код.
Это стартовая версия веб-приложения в очень зачаточном состоянии.
Требуется большой рефакторинг
'''

import logging
import re

from aiohttp import web, WSMsgType
from operator import itemgetter
from time import perf_counter
from typing import List, Dict

from helpers.config import config, logger, DEBUG
from helpers.obj_classes import db, Webtoken, User, Problem
from helpers.nats_brocker import vmsh_nats
from helpers.consts import NATS_GAME_MAP_UPDATE, NATS_GAME_STUDENT_UPDATE

__ALL__ = ['routes']

NATS_SERVER = f"nats://127.0.0.1:4222"

routes = web.RouteTableDef()
routes.static('/static', 'templates/static')

STRICT_COOKIE = dict(domain=None, path='/', max_age=2592000, secure=True, httponly=True, samesite='Strict')
DEBUG_COOKIE = dict(domain=None, path='/', max_age=2592000, secure=False, httponly=True, samesite='Strict')
COOKIE_NAME = 'l'
use_cookie = STRICT_COOKIE


def prerate_template(template: str) -> str:
    # Удваиваем фигурные скобки
    template = template.replace('{', '{{').replace('}', '}}')
    # Заменяем двойные квадратные скобки на фигурные
    template = re.sub(r'\[\[(\w+)\]\]', r'{\1}', template)
    return template


templates = {
    'login': open('templates/login.html', 'r', encoding='utf-8').read(),
    'game': open('templates/mathgame.html', 'r', encoding='utf-8').read(),
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
        return web.json_response(data={'error': 'relogin'})
    # todo validate
    command_id = db.get_student_command(user.id)
    db.add_payment(user.id, command_id, data['x'], data['y'], data['amount'])
    # Отправляем всем уведомление, что открылась новая ячейка на карте
    await vmsh_nats.publish(NATS_GAME_MAP_UPDATE, command_id)
    return web.json_response(data={'ok': 'sure'})


@routes.post('/game/flag')
async def post_game_flag(request):
    data = await request.json()
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'})
    # todo validate
    command_id = db.get_student_command(user.id)
    db.set_student_flag(user.id, command_id, data['x'], data['y'])
    # Отправляем всем уведомление, что открылась новая ячейка на карте (или появился флаг)
    await vmsh_nats.publish(NATS_GAME_MAP_UPDATE, command_id)
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
    st = perf_counter()
    student_command = db.get_student_command(student.id)
    solved = db.get_student_solved(student.id, Problem.last_lesson_num(student.level))  # ts, title
    payments = db.get_student_payments(student.id)  # ts, amount
    opened = get_map_opened(student_command)
    flags = get_map_flags(student_command)
    my_flag = db.get_flag_by_student_and_command(student.id, student_command)
    # Собираем из решённых задач и оплат event'ы
    events = []
    for paym in payments:
        events.append([paym['ts'], -paym['amount']])
    for solv in solved:
        score = solv['title'][:2].rstrip('⚡')
        score = int(score) if score.isdecimal() else 1
        events.append([solv['ts'], score])
    events.sort(key=itemgetter(0))
    events = [ev[1] for ev in events]
    # Собираем карту  TODO Сделать минимальное кеширование
    data = {'events': events, 'opened': opened, 'flags': flags, 'myFlag': my_flag}
    en = perf_counter()
    print(f'get_game_data {en - st:0.3f} seconds')  # TODO Удалить
    return data


@routes.post('/game/me')
async def post_online(request):
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'})
    data = get_game_data(user)
    return web.json_response(data=data)


user_id_to_websocket: Dict[int, web.WebSocketResponse] = {}


@routes.get('/game/ws')
async def websocket(request):
    user = Webtoken.user_by_webtoken(request.cookies.get(COOKIE_NAME, None))
    if not user:
        return
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    user_id_to_websocket[user.id] = ws

    # Этот цикл «зависает» до тех пор, пока коннекшн не сдохнет
    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == 'close':
                await ws.close()
                user_id_to_websocket.pop(user.id, None)
        elif msg.type == WSMsgType.ERROR:
            print(ws.exception())
        print(msg)
    user_id_to_websocket.pop(user.id, None)
    print('websocket connection closed')
    return ws


async def nats_handle_map_update(command_id):
    logger.debug(f"nats_handle_map_update {command_id=}")
    students = db.get_all_students_by_command(command_id)
    for student_id in students:
        ws = user_id_to_websocket.get(student_id, None)
        if ws is not None:
            data = get_game_data(User.get_by_id(student_id))
            try:
                await ws.send_json(data)
            except Exception as e:
                logger.exception('Отправка данных через websocket отвалилась')


async def nats_handle_student_update(student_id):
    logger.debug(f"nats_handle_student_update {student_id=}")
    student = User.get_by_id(student_id)
    if not student:
        return
    ws = user_id_to_websocket.get(student_id, None)
    if ws is None:
        return
    data = get_game_data(User.get_by_id(student_id))
    try:
        await ws.send_json(data)
    except Exception as e:
        logger.exception('Отправка данных через websocket отвалилась')


if __name__ == "__main__":
    # Включаем все отладочные сообщения
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(DEBUG)


    async def on_startup(app):
        logger.debug('on_startup')
        # Настраиваем БД
        db.setup(config.db_filename)
        # Подключаемся к NATS
        await vmsh_nats.setup()
        await vmsh_nats.subscribe(NATS_GAME_MAP_UPDATE, nats_handle_map_update)
        await vmsh_nats.subscribe(NATS_GAME_STUDENT_UPDATE, nats_handle_student_update)


    async def on_shutdown(app):
        logger.warning('Shutting down..')
        db.disconnect()
        await vmsh_nats.disconnect()
        logger.warning('Bye!')


    use_cookie = DEBUG_COOKIE

    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    print('Open http://127.0.0.1:8080/game')
    web.run_app(app)
