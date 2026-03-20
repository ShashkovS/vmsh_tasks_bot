# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Any

from aiohttp import web

import db_methods as db
from helpers.config import config, logger, DEBUG

__ALL__ = ['pwa_routes']

pwa_routes = web.RouteTableDef()


@pwa_routes.post('/api/pwa/health')
async def health(request: web.Request):
    return web.json_response({"ok": True}, status=200)


async def on_startup(app):
    logger.debug('apis on_startup')
    if __name__ == "__main__":
        db.sql.setup(config.db_filename)


async def on_shutdown(app):
    logger.warning('apis on_shutdown')
    if __name__ == "__main__":
        db.sql.disconnect()
    logger.warning('apis Bye!')


def configue(app):
    app.add_routes(pwa_routes)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    logger.setLevel(DEBUG)
    app = web.Application()
    configue(app)
    web.run_app(app)
