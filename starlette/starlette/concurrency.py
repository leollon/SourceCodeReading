import functools
import sys
import typing
import warnings

import anyio

if sys.version_info >= (3, 10):  # pragma: no cover
    from typing import ParamSpec
else:  # pragma: no cover
    from typing_extensions import ParamSpec


T = typing.TypeVar("T")
P = ParamSpec("P")


async def run_until_first_complete(*args: typing.Tuple[typing.Callable, dict]) -> None:
    warnings.warn(
        "run_until_first_complete is deprecated "
        "and will be removed in a future version.",
        DeprecationWarning,
    )

    async with anyio.create_task_group() as task_group:

        async def run(func: typing.Callable[[], typing.Coroutine]) -> None:
            await func()
            task_group.cancel_scope.cancel()

        for func, kwargs in args:
            task_group.start_soon(run, functools.partial(func, **kwargs))


async def run_in_threadpool(
    func: typing.Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    if kwargs:  # pragma: no cover
        # run_sync 不接收 'kwargs', 所以在这里将 kwargs 和 func 绑定在一起
        func = functools.partial(func, **kwargs)
    return await anyio.to_thread.run_sync(func, *args)


class _StopIteration(Exception):
    pass


def _next(iterator: typing.Iterator[T]) -> T:
    # 不能从 threadpool 迭代器范围内引起(raise) `StopIteration`，并且在那个迭代器范围之外进行 catch,
    # 所以强制将它们进入到其他的异常类型中。
    try:
        return next(iterator)
    except StopIteration:
        raise _StopIteration


async def iterate_in_threadpool(
    iterator: typing.Iterator[T],
) -> typing.AsyncIterator[T]:
    while True:
        try:
            yield await anyio.to_thread.run_sync(_next, iterator)
        except _StopIteration:
            break
