import nats
import nats.errors
import nats.aio.client
import nats.aio.subscription
import orjson

__all__ = ['vmsh_nats']

TOPIC = 'vmsh179bot'
NATS_SERVER = "nats://127.0.0.1:4222"


class NATS:
    """Класс, реализующий все взаимодействия с БД"""
    nc: nats.aio.client.Client
    sub: nats.aio.subscription.Subscription

    def __init__(self):
        self.nats_is_working = False
        self.subsciptions = {}

    async def setup(self, nats_server_url=NATS_SERVER):
        self.nats_server_url = nats_server_url
        nc = await nats.connect(self.nats_server_url, connect_timeout=0.5, reconnect_time_wait=0.5, max_reconnect_attempts=2)
        nc.connect_timeout = 0.5
        nc.reconnect_time_wait = 0.5
        nc.max_reconnect_attempts = 100
        self.nc = nc
        self.nats_is_working = True

    async def subscribe(self, callback, topic=TOPIC):
        async def wrapped_callback(msg):
            print(repr(msg))
            data = orjson.loads(msg.data)
            await callback(data)

        self.subsciptions[topic] = callback
        self.sub = await self.nc.subscribe(topic, cb=wrapped_callback)

    async def publish(self, obj, topic=TOPIC):
        '''В тестовых целях работаем напрямую без NATS'''
        if self.nats_is_working:
            await self.nc.publish(topic, orjson.dumps(obj))
        else:
            await self.subsciptions[topic](obj)

    async def disconnect(self):
        if self.sub:
            await self.sub.unsubscribe()
        if self.nc:
            await self.nc.drain()
        self.nats_is_working = False


vmsh_nats = NATS()
