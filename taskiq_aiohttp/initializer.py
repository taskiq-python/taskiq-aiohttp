import asyncio
import inspect
from typing import Awaitable, Callable
from taskiq import AsyncBroker, TaskiqEvents, TaskiqState
from taskiq.cli.utils import import_object
from aiohttp import web
from aiohttp.web_request import RawRequestMessage
from aiohttp.web_urldispatcher import UrlMappingMatchInfo, ResourceRoute
from aiohttp.http_writer import HttpVersion10
from aiohttp.web_protocol import RequestHandler
import yarl

# def _startup(state: Context):
#     state.broker.add_dependency_context()


async def _mocked_handler(request: web.Request) -> web.Response:
    return web.Response()


def startup_event_generator(
    app: web.Application,
) -> Callable[[TaskiqState], Awaitable[None]]:
    async def startup(state: TaskiqState) -> None:
        state.aiohttp_app = app
        app.router._resources = []
        await app.startup()

    return startup


def shutdown_event_generator(
    app: web.Application,
) -> Callable[[TaskiqState], Awaitable[None]]:
    async def shutdown(_: TaskiqState) -> None:
        await app.shutdown()
        await app.cleanup()

    return shutdown


def init(broker: AsyncBroker, app_path: str) -> None:
    loop = asyncio.get_event_loop()
    if not broker.is_worker_process:
        return

    app = import_object(app_path)

    if not isinstance(app, web.Application):
        app = app()

    if inspect.isawaitable(app):
        app = asyncio.run(app)

    if not isinstance(app, web.Application):
        raise ValueError(f"'{app_path}' is not an AioHTTP application.")

    handler = RequestHandler(app._make_handler(), loop=loop)
    handler.transport = asyncio.Transport()
    request = web.Request(
        RawRequestMessage(
            "GET",
            "/",
            HttpVersion10,
            headers={},
            raw_headers=tuple(),
            should_close=False,
            upgrade=False,
            chunked=False,
            compression=None,
            url=yarl.URL.build(
                scheme="https",
                host="test.com",
                path="/",
            ),
        ),
        None,
        handler,
        None,
        None,
        None,
    )

    request._match_info = UrlMappingMatchInfo(
        match_dict={},
        route=ResourceRoute("GET", _mocked_handler, None),
    )
    request._match_info._apps = app._subapps
    request._match_info._current_app = app

    broker.add_dependency_context(
        {
            web.Application: app,
            web.Request: request,
        }
    )

    broker.add_event_handler(
        TaskiqEvents.WORKER_STARTUP,
        startup_event_generator(app),
    )
    broker.add_event_handler(
        TaskiqEvents.WORKER_SHUTDOWN,
        shutdown_event_generator(app),
    )
