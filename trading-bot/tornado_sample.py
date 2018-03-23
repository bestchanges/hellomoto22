#! /usr/bin/env python3
import asyncio

from tornado import gen, ioloop, process


async def ping(ip):
    p = process.Subprocess(['ping', ip], stdout=process.Subprocess.STREAM)
    await p.stdout.read_until_close(streaming_callback=print)
    await p.wait_for_exit()


async def main():
    await gen.multi([
        ping('8.8.8.8'),
        ping('8.8.4.4'),
    ])


if __name__ == '__main__':
    p = process.Subprocess(['ping', '8.8.8.8'], stdout=process.Subprocess.STREAM)
    exit(0)
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)

    main_loop = ioloop.IOLoop.instance()
    main_loop.run_sync(main)