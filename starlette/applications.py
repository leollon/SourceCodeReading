import typing

from starlette.datastructures import State, URLPath
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.errors import ServerErrorMiddleware
from starlette.middleware.exceptions import ExceptionMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import BaseRoute, Router
from starlette.types import ASGIApp, Receive, Scope, Send


class Starlette:
    """
    创建一个应用程序实例

    **参数**

    * **debug** - Boolean 表示假如产生错误，是否返回 debug tracebacks。
    * **routes** - 为来到的 HTTP 以及 WebSockets 请求提供服务的路由列表。
    * **middleware** - 对于每个请求，都要在上面跑的代码，比如，检测用户是否授权。

    starlette 应用程序总是字段包含两个中间件类。

        - `ServerErrorMiddleware` 是最外层的中间件，为的是处理发生在整个栈中任意地方还未被捕获的错误。
        - `ExceptionMiddleware` 是最内层的中间件，为的是处理发生在路由(routing) 或 端点(endpoints) 中的异常
    * **exception_handlers** - 一个整型状态码或处理异常的可调用对象的映射(mapping)。
        异常处理可调用对象应该是这样一种形式`handler(request, exc) -> response`, 并且这个可调用对象可以是普通函数或异步(async)函数。
    * **on_startup** - 应用程序启用时，要运行的可调用对象的列表。这些可调用对象不携带任何参数，并且能够时普通函数或异步(async)函数。
    * **on_shutdown** - 应用程序关闭时，要运行的可调用对象列表。这些可调用对象不携带任何参数，并且能够时普通函数或异步(async)函数。
    """

    def __init__(
        self,
        debug: bool = False,
        routes: typing.Optional[typing.Sequence[BaseRoute]] = None,
        middleware: typing.Optional[typing.Sequence[Middleware]] = None,
        exception_handlers: typing.Optional[
            typing.Mapping[
                typing.Any,
                typing.Callable[
                    [Request, Exception],
                    typing.Union[Response, typing.Awaitable[Response]],
                ],
            ]
        ] = None,
        on_startup: typing.Optional[typing.Sequence[typing.Callable]] = None,
        on_shutdown: typing.Optional[typing.Sequence[typing.Callable]] = None,
        lifespan: typing.Optional[
            typing.Callable[["Starlette"], typing.AsyncContextManager]
        ] = None,
    ) -> None:
        # lifespan 上下文函数是一种替代 on_startup / on_shutdown handlers 更新的风格。二者只能选择其中一个。
        assert lifespan is None or (
            on_startup is None and on_shutdown is None
        ), "Use either 'lifespan' or 'on_startup'/'on_shutdown', not both."

        self._debug = debug
        self.state = State()
        self.router = Router(
            routes, on_startup=on_startup, on_shutdown=on_shutdown, lifespan=lifespan
        )
        self.exception_handlers = (
            {} if exception_handlers is None else dict(exception_handlers)
        )
        self.user_middleware = [] if middleware is None else list(middleware)
        self.middleware_stack = self.build_middleware_stack()

    def build_middleware_stack(self) -> ASGIApp:
        debug = self.debug
        error_handler = None
        exception_handlers: typing.Dict[
            typing.Any, typing.Callable[[Request, Exception], Response]
        ] = {}

        for key, value in self.exception_handlers.items():
            if key in (500, Exception):
                error_handler = value
            else:
                exception_handlers[key] = value

        middleware = (
            [Middleware(ServerErrorMiddleware, handler=error_handler, debug=debug)]
            + self.user_middleware
            + [
                Middleware(
                    ExceptionMiddleware, handlers=exception_handlers, debug=debug
                )
            ]
        )

        app = self.router
        for cls, options in reversed(middleware):
            app = cls(app=app, **options)
        return app

    @property
    def routes(self) -> typing.List[BaseRoute]:
        return self.router.routes

    @property
    def debug(self) -> bool:
        return self._debug

    @debug.setter
    def debug(self, value: bool) -> None:
        self._debug = value
        self.middleware_stack = self.build_middleware_stack()

    def url_path_for(self, name: str, **path_params: typing.Any) -> URLPath:
        return self.router.url_path_for(name, **path_params)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope["app"] = self
        await self.middleware_stack(scope, receive, send)

    # The following usages are now discouraged in favour of configuration
    # during Starlette.__init__(...)
    def on_event(self, event_type: str) -> typing.Callable:  # pragma: nocover
        return self.router.on_event(event_type)

    def mount(
        self, path: str, app: ASGIApp, name: typing.Optional[str] = None
    ) -> None:  # pragma: nocover
        """
        We no longer document this API, and its usage is discouraged.
        Instead you should use the following approach:

        routes = [
            Mount(path, ...),
            ...
        ]

        app = Starlette(routes=routes)
        """

        self.router.mount(path, app=app, name=name)

    def host(
        self, host: str, app: ASGIApp, name: typing.Optional[str] = None
    ) -> None:  # pragma: no cover
        """
        We no longer document this API, and its usage is discouraged.
        Instead you should use the following approach:

        routes = [
            Host(path, ...),
            ...
        ]

        app = Starlette(routes=routes)
        """

        self.router.host(host, app=app, name=name)

    def add_middleware(
        self, middleware_class: type, **options: typing.Any
    ) -> None:  # pragma: no cover
        self.user_middleware.insert(0, Middleware(middleware_class, **options))
        self.middleware_stack = self.build_middleware_stack()

    def add_exception_handler(
        self,
        exc_class_or_status_code: typing.Union[int, typing.Type[Exception]],
        handler: typing.Callable,
    ) -> None:  # pragma: no cover
        self.exception_handlers[exc_class_or_status_code] = handler
        self.middleware_stack = self.build_middleware_stack()

    def add_event_handler(
        self, event_type: str, func: typing.Callable
    ) -> None:  # pragma: no cover
        self.router.add_event_handler(event_type, func)

    def add_route(
        self,
        path: str,
        route: typing.Callable,
        methods: typing.Optional[typing.List[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: bool = True,
    ) -> None:  # pragma: no cover
        self.router.add_route(
            path, route, methods=methods, name=name, include_in_schema=include_in_schema
        )

    def add_websocket_route(
        self, path: str, route: typing.Callable, name: typing.Optional[str] = None
    ) -> None:  # pragma: no cover
        self.router.add_websocket_route(path, route, name=name)

    def exception_handler(
        self, exc_class_or_status_code: typing.Union[int, typing.Type[Exception]]
    ) -> typing.Callable:  # pragma: nocover
        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_exception_handler(exc_class_or_status_code, func)
            return func

        return decorator

    def route(
        self,
        path: str,
        methods: typing.Optional[typing.List[str]] = None,
        name: typing.Optional[str] = None,
        include_in_schema: bool = True,
    ) -> typing.Callable:  # pragma: nocover
        """
        We no longer document this decorator style API, and its usage is discouraged.
        Instead you should use the following approach:

        routes = [
            Route(path, endpoint=..., ...),
            ...
        ]

        app = Starlette(routes=routes)
        """

        def decorator(func: typing.Callable) -> typing.Callable:
            self.router.add_route(
                path,
                func,
                methods=methods,
                name=name,
                include_in_schema=include_in_schema,
            )
            return func

        return decorator

    def websocket_route(
        self, path: str, name: typing.Optional[str] = None
    ) -> typing.Callable:  # pragma: nocover
        """
        We no longer document this decorator style API, and its usage is discouraged.
        Instead you should use the following approach:

        routes = [
            WebSocketRoute(path, endpoint=..., ...),
            ...
        ]

        app = Starlette(routes=routes)
        """

        def decorator(func: typing.Callable) -> typing.Callable:
            self.router.add_websocket_route(path, func, name=name)
            return func

        return decorator

    def middleware(self, middleware_type: str) -> typing.Callable:  # pragma: nocover
        """
        We no longer document this decorator style API, and its usage is discouraged.
        Instead you should use the following approach:

        middleware = [
            Middleware(...),
            ...
        ]

        app = Starlette(middleware=middleware)
        """

        assert (
            middleware_type == "http"
        ), 'Currently only middleware("http") is supported.'

        def decorator(func: typing.Callable) -> typing.Callable:
            self.add_middleware(BaseHTTPMiddleware, dispatch=func)
            return func

        return decorator
