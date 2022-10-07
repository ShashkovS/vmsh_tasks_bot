import re
import weakref
from aiohttp import web, WSMsgType, WSCloseCode
from datetime import datetime, timedelta
from helpers.consts import *
from helpers.config import logger, config, logging
from helpers.obj_classes import db, Webtoken, User, Problem
from json import dumps, loads

routes = web.RouteTableDef()
routes.static('/tags/static', 'tags')
__ALL__ = ['routes']

STRICT_COOKIE = dict(domain=None, path='/tag', max_age=2592000, secure=True, httponly=True, samesite='Strict')
DEBUG_COOKIE = dict(domain=None, path='/tag', max_age=2592000, secure=False, httponly=True, samesite='Strict')
COOKIE_NAME = 'tags'
use_cookie = STRICT_COOKIE  # Устанавливается в момент старта приложения

tag_regex = re.compile(r'tag_(\d+)_([а-яa-z])_(\d+)(?:_(\d+))?')
PUNCTS = 'абвгдежзиклмнопрстуфхцчшщъыьэюя'


@routes.get('/tagst')
async def get_tst(request):
    return web.Response(text='Yup! It works!', content_type='text/html')


def prerate_template(template: str) -> str:
    # Удваиваем фигурные скобки
    template = template.replace('{', '{{').replace('}', '}}')
    # Заменяем двойные квадратные скобки на фигурные
    template = re.sub(r'\[\[(\w+)\]\]', r'{\1}', template)
    return template


templates = {
    'login': open('tags/login.tags.html', 'r', encoding='utf-8').read(),
    'tags0': open('tags/tags0.html', 'r', encoding='utf-8').read(),
    'tags1': open('tags/tags1.html', 'r', encoding='utf-8').read().replace('src="Сайт_Баз/', r'src="https://shashkovs.ru/cdn/Сайт_Баз/'),
    'tags2': open('tags/tags2.html', 'r', encoding='utf-8').read().replace('src="Сайт_Баз/', r'src="https://shashkovs.ru/cdn/Сайт_Баз/'),
    'tags3': open('tags/tags3.html', 'r', encoding='utf-8').read().replace('src="Сайт_Баз/', r'src="https://shashkovs.ru/cdn/Сайт_Баз/'),
    'tags4': open('tags/tags4.html', 'r', encoding='utf-8').read().replace('src="Сайт_Баз/', r'src="https://shashkovs.ru/cdn/Сайт_Баз/'),
}


def add_tags_page_response(user: User, page=0):
    return web.Response(text=templates['tags' + str(page)], content_type='text/html')


@routes.get('/tag/p/{page}')
async def get_tags(request):
    page = request.match_info['page']
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.Response(text=templates['login'], content_type='text/html')
    else:
        return add_tags_page_response(user, page)


@routes.post('/tag/p/{page}')
async def post_tags(request):
    page = request.match_info['page']
    data = await request.post()
    token = data.get('password', None)
    user = User.get_by_token(token)
    cookie_webtoken = Webtoken.webtoken_by_user(user)
    if cookie_webtoken:
        response = add_tags_page_response(user, page)
        response.set_cookie(name=COOKIE_NAME, value=cookie_webtoken, **use_cookie)
        return response
    else:
        return web.Response(text=templates['login'], content_type='text/html')


@routes.get('/tag/get_tags')
async def get_tags(request):
    cookie_webtoken = request.cookies.get(COOKIE_NAME, None)
    user = Webtoken.user_by_webtoken(cookie_webtoken)
    if not user:
        return web.Response(text=templates['login'], content_type='text/html')
    problems = Problem.get_all_tags()
    # p.id, p.level, p.lesson, p.prob, p.item, pt.tags
    data = {}
    for problem in problems:
        item = '' if not problem['item'] else f'_{PUNCTS.index(problem["item"]) + 1:02}'
        tags = [] if not problem["tags"] else loads(problem["tags"])
        id = f'tag_{problem["lesson"]:02}_{problem["level"]}_{problem["prob"]:02}{item}'
        data[id] = tags
    return web.json_response(data=data)


def update_tags(payload: str, user: User) -> bool:
    # Тупо рассылаем всем «свежие» теги
    try:
        obj = loads(payload)
    except:
        return False
    id = obj.get('id', '')
    tags = obj.get('tags', None)
    if tags is None or type(tags) != list:
        return False
    match = tag_regex.fullmatch(id)
    if not match:
        return False
    lesson, level, prob, item = match.groups()
    problem = Problem.get_by_key(level, int(lesson), int(prob), PUNCTS[int(item)-1] if item else '')
    if not problem:
        return False
    problem.update_tags(dumps(tags, ensure_ascii=False), user)
    return True


ws_connections = weakref.WeakSet()


@routes.get('/tag/ws')
async def websocket(request):
    user = Webtoken.user_by_webtoken(request.cookies.get(COOKIE_NAME, None))
    # Без правильной куки прибиваем
    if not user:
        return
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    ws_connections.add(ws)
    # Этот цикл «зависает» до тех пор, пока коннекшн не сдохнет
    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
                    break
                else:
                    success = update_tags(msg.data, user)
                    if not success:
                        continue
                    for other_ws in ws_connections:
                        await other_ws.send_str(msg.data)
            elif msg.type == WSMsgType.ERROR:
                print(ws.exception())
    finally:
        ws_connections.discard(ws)
    print('websocket connection closed')

    return ws


async def on_startup(app):
    logger.debug('on_startup')
    # Настраиваем БД
    db.setup(config.db_filename)


async def on_shutdown(app):
    logger.warning('Shutting down..')
    db.disconnect()
    for ws in ws_connections:
        await ws.close(code=WSCloseCode.GOING_AWAY, message='Server shutdown')
    logger.warning('Bye!')


if __name__ == "__main__":
    # Включаем все отладочные сообщения
    app = web.Application()
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(logging.DEBUG)
    use_cookie = DEBUG_COOKIE
    print('Test on http://127.0.0.1:8080/tagst')
    web.run_app(app)
else:
    pass
