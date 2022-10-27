'''
Здесь совершенно ужасный код.
Это стартовая версия веб-приложения в очень зачаточном состоянии.
Требуется большой рефакторинг
'''

import logging
import re
from aiohttp import web, WSMsgType

from helpers.config import config, logger, DEBUG
from helpers.obj_classes import db, Webtoken, User

__ALL__ = ['routes']

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
    'login': open('templates/login.html', 'r', encoding='utf-8').read(),
    'game': open('templates/game.html', 'r', encoding='utf-8').read(),
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


@routes.get('/online/webtoken/{webtoken}')
async def get_webtoken(request):
    webtoken = request.match_info['webtoken']
    user = Webtoken.user_by_webtoken(webtoken)
    response = web.HTTPSeeOther('/online')
    if user:
        response.set_cookie(name=COOKIE_NAME, value=webtoken, **use_cookie)
    return response


if __name__ == "__main__":
    # Включаем все отладочные сообщения
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(DEBUG)


    async def on_startup(app):
        logger.debug('on_startup')
        # Настраиваем БД
        db.setup(config.db_filename)


    async def on_shutdown(app):
        logger.warning('Shutting down..')
        db.disconnect()
        logger.warning('Bye!')


    use_cookie = DEBUG_COOKIE

    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    print('Open http://127.0.0.1:8080/game')
    web.run_app(app)
