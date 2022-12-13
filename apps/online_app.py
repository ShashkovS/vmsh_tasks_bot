'''
Здесь совершенно ужасный код.
Это стартовая версия веб-приложения в очень зачаточном состоянии.
Требуется большой рефакторинг
'''

import logging
import re
from aiohttp import web, WSMsgType

from helpers.config import config, logger, DEBUG, APP_PATH
from helpers.obj_classes import db, Webtoken, User
from web import trash_print_results

__ALL__ = ['routes', 'on_startup', 'on_shutdown']

routes = web.RouteTableDef()
routes.static('/online/static', 'templates')

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
    'login': open(APP_PATH / 'templates/login.html', 'r', encoding='utf-8').read(),
    'login_res': open(APP_PATH / 'templates/login_res.html', 'r', encoding='utf-8').read(),
    'socket': open(APP_PATH / 'templates/socket.html', 'r', encoding='utf-8').read(),
    'board': prerate_template(open(APP_PATH / 'templates/board.html', 'r', encoding='utf-8').read())
}


def board_response(user: User):
    print('board_response')
    room = 'mysecretroomhere'
    return web.Response(text=templates['board'].format(room=repr(room)), content_type='text/html')


@routes.get('/online')
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


@routes.post('/online')
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


@routes.get('/res')
async def print_res(request):
    print('res')
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.Response(text=templates['login_res'], content_type='text/html')
    else:
        return web.Response(text=trash_print_results.get_html(), content_type='text/html')


@routes.post('/res')
async def login_res(request):
    print('login_res')
    data = await request.post()
    token = data.get('password', None)
    user = User.get_by_token(token)
    cookie_webtoken = Webtoken.webtoken_by_user(user)
    if cookie_webtoken:
        response = web.Response(text=trash_print_results.get_html(), content_type='text/html')
        response.set_cookie(name=COOKIE_NAME, value=cookie_webtoken, **use_cookie)
        return response
    return web.Response(text=templates['login_res'], content_type='text/html')


@routes.get('/online/webtoken/{webtoken}')
async def get_webtoken(request):
    webtoken = request.match_info['webtoken']
    user = Webtoken.user_by_webtoken(webtoken)
    response = web.HTTPSeeOther('/online')
    if user:
        response.set_cookie(name=COOKIE_NAME, value=webtoken, **use_cookie)
    return response


@routes.get('/online/teacher/{teachertoken}/student/{studenttoken}')
async def for_teacher(request):
    teachertoken = request.match_info['teachertoken']
    teacher = Webtoken.user_by_webtoken(teachertoken)
    studenttoken = request.match_info['studenttoken']
    student = Webtoken.user_by_webtoken(teachertoken)
    response = web.HTTPSeeOther('/online')
    if teacher:
        response.set_cookie(name=COOKIE_NAME, value=teachertoken, **use_cookie)
    return response


@routes.post('/online/heartbeat')
async def heartbeat(request):
    user = Webtoken.user_by_webtoken(request.cookies.get(COOKIE_NAME, None))
    pass


@routes.get('/online/socket')
async def getsocket(request):
    user = Webtoken.user_by_webtoken(request.cookies.get(COOKIE_NAME, None))
    return web.Response(text=templates['socket'], content_type='text/html')


user_id_to_websocket = {}


@routes.get('/online/ws')
async def websocket(request):
    user = Webtoken.user_by_webtoken(request.cookies.get(COOKIE_NAME, None))
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    user_id_to_websocket[user.id] = ws

    # Этот цикл «зависает» до тех пор, пока коннекшн не сдохнет
    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == 'close':
                await ws.close()
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


async def on_startup(app):
    logger.debug('online on_startup')
    # Настраиваем БД
    if __name__ == "__main__":
        db.setup(config.db_filename)


async def on_shutdown(app):
    logger.warning('online on_shutdown')
    if __name__ == "__main__":
        db.disconnect()
    logger.warning('online Bye!')


def configue(app):
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


if __name__ == "__main__":
    # Включаем все отладочные сообщения
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(DEBUG)
    use_cookie = DEBUG_COOKIE
    app = web.Application()
    configue(app)
    web.run_app(app)
