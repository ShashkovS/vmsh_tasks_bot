import nats
import nats.errors
import nats.aio.client
import nats.aio.subscription
import orjson

from helpers.config import config, logger, DEBUG

__all__ = ['vmsh_nats']

NATS_SERVER = config.nats_server  # "nats://127.0.0.1:4222"


class NATS:
    """Класс, реализующий все взаимодействия с БД"""
    nc: nats.aio.client.Client

    def __init__(self):
        self.nats_is_working = False
        self.subsciptions = {}

    async def setup(self, nats_server_url=NATS_SERVER):
        self.nats_server_url = nats_server_url
        try:
            nc = await nats.connect(self.nats_server_url, connect_timeout=0.5, reconnect_time_wait=0.5, max_reconnect_attempts=2)
        except nats.errors.NoServersError:
            logger.critical(f'Не удалось подключиться к nats-server по адресу {self.nats_server_url!r}.')
            logger.critical(f'Работаем без nats-server.')
            logger.critical(f'В таком режиме работа с несколькими процессами может быть некорректной')
            return
        logger.warning(f'Успешно подключились к nats на {self.nats_server_url}')
        nc.connect_timeout = 0.5
        nc.reconnect_time_wait = 0.5
        nc.max_reconnect_attempts = 100
        self.nc = nc
        self.nats_is_working = True

    async def subscribe(self, topic: str, callback):
        async def wrapped_callback(msg):
            print(repr(msg))
            data = orjson.loads(msg.data)
            await callback(data)

        if self.nats_is_working:
            self.subsciptions[topic] = await self.nc.subscribe(topic, cb=wrapped_callback)
        else:
            self.subsciptions[topic] = callback

    async def publish(self, topic: str, obj):
        # В тестовых целях работаем напрямую без NATS
        if self.nats_is_working:
            await self.nc.publish(topic, orjson.dumps(obj))
        else:
            await self.subsciptions[topic](obj)

    async def disconnect(self):
        for topic, sub in self.subsciptions.items():
            await sub.unsubscribe()
            del self.subsciptions[topic]
        if self.nc:
            await self.nc.drain()
        self.nats_is_working = False


vmsh_nats = NATS()
