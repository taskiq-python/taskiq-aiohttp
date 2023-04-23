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
