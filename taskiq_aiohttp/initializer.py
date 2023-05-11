import asyncio
import inspect
from typing import Any, Awaitable, Callable

import yarl
from aiohttp import web
from aiohttp.http_writer import HttpVersion10
from aiohttp.web_protocol import RequestHandler
from aiohttp.web_request import RawRequestMessage
from aiohttp.web_urldispatcher import SystemRoute, UrlMappingMatchInfo
from multidict import CIMultiDict, CIMultiDictProxy
from taskiq import AsyncBroker, TaskiqEvents, TaskiqState
from taskiq.cli.utils import import_object


def startup_event_generator(
    broker: AsyncBroker,
    app_path: str,
    app: Any,
) -> Callable[[TaskiqState], Awaitable[None]]:
    """
    Creates an event to run on broker's startup.

    This function create a mock application for
    later use and updates broker's dependency context.

    Also we run application's startup event so it would
    act the same as the real application.

    :param broker: current broker.
    :param app_path: path to the application.
    :param app: current application or a fractory.

    :returns: a function that is called on startup.
    """

    async def startup(state: TaskiqState) -> None:
        loop = asyncio.get_event_loop()

        local_app = app

        if not isinstance(local_app, web.Application):
            local_app = local_app()

        if inspect.iscoroutine(local_app):
            local_app = await local_app
        if not isinstance(local_app, web.Application):
            raise ValueError(f"{app_path} is not an AioHTTP application.")

        # Starting the application.
        app_runner = web.AppRunner(local_app)
        await app_runner.setup()

        if app_runner.server is None:
            raise ValueError("Cannot construct aiohttp app to mock requests")

        # Creating mocked request
        handler = RequestHandler(app_runner.server, loop=loop)
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
        request._match_info._apps = local_app._subapps
        request._match_info._current_app = local_app

        broker.add_dependency_context(
            {
                web.Application: local_app,
                web.Request: request,
            },
        )

        state.aiohttp_runner = app_runner
        local_app.router._resources = []

    return startup


async def shutdown(state: TaskiqState) -> None:
    """
    Shuts down the app.

    It just gets the application
    we created in startup and shuts it down.

    :param state: current state.
    """
    await state.aiohttp_runner.shutdown()
    await state.aiohttp_runner.cleanup()


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
    if not broker.is_worker_process:
        return

    app = import_object(app_path)

    broker.add_event_handler(
        TaskiqEvents.WORKER_STARTUP,
        startup_event_generator(broker, app_path, app),
    )
    broker.add_event_handler(
        TaskiqEvents.WORKER_SHUTDOWN,
        shutdown,
    )
