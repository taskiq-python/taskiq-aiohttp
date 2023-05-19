# Taskiq + AioHTTP

This project is used to create mocked application and request
that you can use as a dependencies in your taskiq application.


It's useful because it runs all startup events of your application
and everything that you might expect in your application's state is
available inside of your tasks.

We suggest to use this library along with [taskiq-python/aiohttp-deps](https://github.com/taskiq-python/aiohttp-deps), because it might be super handy to reuse same dependencies of your application in your tasks.

To add an integration, you need to call the function `init` in your broker's module.

```python
import taskiq_aiohttp

broker = ...

taskiq_aiohttp.init(broker, "project.module:app")

```

## How does it work?

It adds startup functions to the broker, so it imports your aiohttp application and creates a single worker-wide Request and Application objects that you can depend on.

THIS REQUEST IS NOT RELATED TO THE ACTUAL REQUESTS IN AioHTTP! This request won't have actual data about the request you were handling while sending a task.


## Manual context updates

Sometimes it's required to update context manually. For example, for tests.
If you need to add context in your broker by hand, please use function populate_context.

Imagine, you want to use InMemoryBroker for testing and your broker file looks like this:

```python
broker = MyBroker()

if env == "pytest":
    broker = InMemoryBroker()
```

In this case your context won't be updated, because inmemory brokers cannot run as workers.
To solve this issue, we have a populate context function. It's a bit complex and takes lots of
parmeters. But here's a fixture that creates aiohttp test client and populates context of inmemory broker.

```python
import asyncio
from typing import AsyncGenerator

import pytest
from aiohttp import web
from aiohttp.test_utils import BaseTestServer, TestClient, TestServer
from taskiq_aiohttp import populate_context


@pytest.fixture
async def test_client(
    app: web.Application,
) -> AsyncGenerator[TestClient, None]:
    """
    Create a test client.

    This function creates a TestServer
    and a test client for the application.

    Also this fixture populates context
    with needed variables.

    :param app: current application.
    :yield: ready to use client.
    """
    loop = asyncio.get_running_loop()
    server = TestServer(app)
    client = TestClient(server, loop=loop)

    await client.start_server()

    # This is important part.
    # Since InMemoryBroker doesn't
    # run in worker_process, we have to populate
    # broker's context manually.
    populate_context(
        broker=broker,
        server=server.runner.server,
        app=app,
        loop=None,
    )

    yield client

    await client.close()

```
