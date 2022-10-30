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

from helpers.config import config, logger, DEBUG
from helpers.obj_classes import db, Webtoken, User, Problem
from helpers.nats_brocker import vmsh_nats

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
async def post_online(request):
    data = await request.json()
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'})
    # todo validate
    db.add_payment(user.id, data['x'], data['y'], data['amount'])
    return web.json_response(data={'ok': 'sure'})


@routes.post('/game/me')
async def post_online(request):
    st = perf_counter()
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.json_response(data={'error': 'relogin'})
    # Нужно получить
    # - список решённых задач с timestamp'ами
    # - список покупок с timestamp'ами
    # - текущую карту
    # - команду студента
    solved = db.get_student_solved(user.id, Problem.last_lesson_num(user.level))  # ts, title
    payments = db.get_student_payments(user.id)  # ts, amount
    opened = db.get_opened_cells(user.id)  # x, y
    student_command = db.get_student_command(user.id)
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
    opened = [[r['x'], r['y']] for r in opened]
    en = perf_counter()
    print(en - st, 'seconds')  # TODO Удалить
    return web.json_response(data={'events': events, 'opened': opened})


user_id_to_websocket = {}


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
            else:
                for other_user_id, other_ws in user_id_to_websocket.items():
                    if other_user_id == user.id:
                        continue
                    await other_ws.send_str(msg.data + '/' + user.surname)
        elif msg.type == WSMsgType.ERROR:
            print(ws.exception())
        print(msg)
    print('websocket connection closed')
    return ws


async def nats_message_handler(data):
    print(f"Received '{data=}")


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
        await vmsh_nats.subscribe(nats_message_handler)


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
