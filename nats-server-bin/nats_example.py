"""
Для экпериментов нужно запустить параллельно несколько процессов
"""

import asyncio
import nats
import nats.errors
import os

NATS_IP = '127.0.0.1'
NATS_PORT = 4222
NATS_SERVER = f"nats://{NATS_IP}:{NATS_PORT}"

async def message_handler(msg):
    subject = msg.subject
    reply = msg.reply
    data = msg.data.decode()
    print(f"Received a message on '{subject=} {reply=}': {data=}, my pid={os.getpid()}")


async def super_sleep(n):
    print(f'going to sleep for {n} secs, pid={os.getpid()}')
    for i in range(n):
        await asyncio.sleep(1)
        print(f'spleeping {i}/{n}, pid={os.getpid()}')
    print(f'sleeping for {n} secs done!, pid={os.getpid()}')


async def connect_to_nats():
    nc = await nats.connect(NATS_SERVER, connect_timeout=0.01, reconnect_time_wait=0.01, max_reconnect_attempts=2)
    nc.connect_timeout = 0.5
    nc.reconnect_time_wait = 0.5
    nc.max_reconnect_attempts = 100
    return nc


async def main():
    try:
        nc = await connect_to_nats()
    except nats.errors.NoServersError:
        print(f'No nats server found on {NATS_SERVER}')
        raise

    print('*' * 1000)
    sub = await nc.subscribe("foo", cb=message_handler)
    for i in range(100):
        s = 10
        await nc.publish("foo", f'Going to sleep for {s}s, pid={os.getpid()}'.encode())
        await super_sleep(s)
    await sub.unsubscribe()
    await nc.drain()


if __name__ == '__main__':
    asyncio.run(main())
