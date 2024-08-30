"""This module implememts a generic background event loop fed by a queue
which effectively conveys procedure calls and their parameters. The purpose
of the procedure calls is to execute some comparatively long running or blocking
operation, such as saving a file or outputting log messages.
"""

import asyncio

from uidgid.app import app

# -------------------------------------------------------------------------------------

background_queue: asyncio.Queue = asyncio.Queue()


async def background_worker():
    while True:
        (func, args, keys) = await background_queue.get()
        try:
            func(*args, **keys)
        except Exception as e:
            print(f"Background error {e}")
        finally:
            background_queue.task_done()


@app.before_serving
async def startup():
    app.background_task = asyncio.create_task(background_worker())


@app.after_serving
async def shutdown():
    await background_queue.join()
    app.background_task.cancel()
    try:
        await app.background_task
    except asyncio.CancelledError:
        pass


def run_background(func, args, keys):
    try:
        background_queue.put_nowait((func, args, keys))
    except asyncio.QueueFull:
        print(f"UIDGID ERROR Background queue overflow on {func.__name__}")
