'''
Здесь совершенно ужасный код.
Это стартовая версия веб-приложения в очень зачаточном состоянии.
Требуется большой рефакторинг
'''

import logging
import re
from aiohttp import web, WSMsgType

from helpers.config import config, logger, DEBUG, APP_PATH
import db_methods as db
from models import Webtoken, User
from web import trash_print_results

__ALL__ = ['routes']

routes = web.RouteTableDef()

STRICT_COOKIE = dict(domain=None, path='/', max_age=2592000, secure=True, httponly=True, samesite='Strict')
DEBUG_COOKIE = dict(domain=None, path='/', max_age=2592000, secure=False, httponly=True, samesite='Strict')
COOKIE_NAME = 'l'
use_cookie = STRICT_COOKIE

templates = {
    'login_res': open(APP_PATH / 'templates/login_res.html', 'r', encoding='utf-8').read(),
}


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


async def on_startup(app):
    logger.debug('results on_startup')
    # Настраиваем БД
    if __name__ == "__main__":
        db.sql.setup(config.db_filename)


async def on_shutdown(app):
    logger.warning('results on_shutdown')
    if __name__ == "__main__":
        db.sql.disconnect()
    logger.warning('results Bye!')


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
