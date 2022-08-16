import asyncio
import functools
import typing


def is_async_callable(obj: typing.Any) -> bool:
    while isinstance(obj, functools.partial):
        obj = obj.func

    # asyncio.iscoroutinefunction(obj):
    # obj 是一个函数对象
    # callable(obj) and asyncio.iscoroutinefunction(obj.__call__)
    # 是一个类，然后这个类定义了 __call__ 这个魔法方法。
    return asyncio.iscoroutinefunction(obj) or (
        callable(obj) and asyncio.iscoroutinefunction(obj.__call__)
    )
