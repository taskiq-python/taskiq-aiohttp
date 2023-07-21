import asyncio
import inspect
from typing import Awaitable, Callable

import yarl
from aiohttp import web
from aiohttp.http_writer import HttpVersion10
from aiohttp.web_protocol import RequestHandler
from aiohttp.web_request import RawRequestMessage
from aiohttp.web_urldispatcher import SystemRoute, UrlMappingMatchInfo
from multidict import CIMultiDict, CIMultiDictProxy
from taskiq import AsyncBroker, TaskiqEvents, TaskiqState
from taskiq.cli.utils import import_object


def populate_context(
    broker: AsyncBroker,
    server: web.Server,
    app: web.Application,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """
    Function to add dependency context.

    This function adds base dependency,
    that you may need while working with AioHTTP application.

    :param broker: current broker.
    :param server: current server that handles requests.
    :param app: your application.
    :param loop: current event loop.
    """
    handler = RequestHandler(server, loop=loop)
    handler.transport = asyncio.Transport()
    request = web.Request(
        RawRequestMessage(
            "GET",
            "/",
            HttpVersion10,
            headers=CIMultiDictProxy(CIMultiDict()),
            raw_headers=(),
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
        route=SystemRoute(web.HTTPBadRequest()),
    )
    request._match_info._apps = app._subapps
    request._match_info._current_app = app

    broker.add_dependency_context(
        {
            web.Application: app,
            web.Request: request,
        },
    )


def startup_event_generator(  # noqa: C901
    broker: AsyncBroker,
    app_path: str,
) -> Callable[[TaskiqState], Awaitable[None]]:
    """
    Creates an event to run on broker's startup.

    This function create a mock application for
    later use and updates broker's dependency context.

    Also we run application's startup event so it would
    act the same as the real application.

    :param broker: current broker.
    :param app_path: path to the application.

    :returns: a function that is called on startup.
    """

    async def startup(state: TaskiqState) -> None:
        if not broker.is_worker_process:
            return

        app = import_object(app_path)

        if not isinstance(app, web.Application):
            app = app()

        if inspect.iscoroutine(app):
            app = await app
        if not isinstance(app, web.Application):
            raise ValueError(f"{app_path} is not an AioHTTP application.")

        # Starting the application.
        app_runner = web.AppRunner(app)
        await app_runner.setup()

        if app_runner.server is None:
            raise ValueError("Cannot construct aiohttp app to mock requests")

        loop = asyncio.get_running_loop()

        populate_context(
            broker=broker,
            server=app_runner.server,
            app=app,
            loop=loop,
        )

        # Creating mocked request
        state.aiohttp_runner = app_runner
        app.router._resources = []

    return startup


def shutdown_generator(broker: AsyncBroker) -> Callable[[TaskiqState], Awaitable[None]]:
    """
    Shuts down event generator.

    This function generates a shutdown broker

    :param broker: current broker.
    :returns: shutdown event handler.
    """

    async def shutdown(state: TaskiqState) -> None:
        if not broker.is_worker_process:
            return

        await state.aiohttp_runner.shutdown()
        await state.aiohttp_runner.cleanup()

    return shutdown


def init(broker: AsyncBroker, app_path: str) -> None:
    """
    Initialize dependencies for your taskiq.

    This function imports your application and tries to
    update broker's dependency context, so request and
    applicaiton will be available in all your taskiq
    dependencies.

    :param broker: current broker.
    :param app_path: string with a path to an application or a factory.
    """
    broker.add_event_handler(
        TaskiqEvents.WORKER_STARTUP,
        startup_event_generator(broker, app_path),
    )
    broker.add_event_handler(
        TaskiqEvents.WORKER_SHUTDOWN,
        shutdown_generator(broker),
    )
