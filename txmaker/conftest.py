from asyncio import AbstractEventLoop
from typing import Any, Awaitable, Callable, Iterable, List, Type

import aiohttp
import pytest
from _pytest.monkeypatch import MonkeyPatch
from aiohttp import web
from aiohttp.test_utils import TestClient
from aiohttp.web import AbstractRouteDef
from aiohttp.web_app import Application
from aioresponses import aioresponses

from .bitcoin import is_valid_address
from .server import make_app
from .testing import mocks

AIOHTTP_CLIENT_FIXTURE = Callable[[Application], Awaitable[TestClient]]


@pytest.fixture
def mock_aioresponse() -> aioresponses:
    with aioresponses() as m:
        yield m


@pytest.fixture
def loop(event_loop: AbstractEventLoop) -> AbstractEventLoop:
    return event_loop


@pytest.fixture
async def app(loop: AbstractEventLoop) -> Any:
    yield await make_app()


@pytest.fixture
async def client(app: Application, aiohttp_client: AIOHTTP_CLIENT_FIXTURE) -> TestClient:
    yield await aiohttp_client(app)


@pytest.fixture
async def mock_unspent_response(fake_server_client_factory: Any, monkeypatch: MonkeyPatch) -> Any:
    async def mock(mock_response: web.Response) -> None:
        def mock_handler(request: web.Request) -> web.Response:
            assert 'active' in request.query
            assert is_valid_address(request.query['active'])

            return mock_response
        fake_server_client = await fake_server_client_factory(
            hosts=['testnet.blockchain.info'],
            routes=[web.get('/unspent', mock_handler)],
        )
        monkeypatch.setattr('aiohttp.ClientSession', fake_server_client)
    yield mock


@pytest.fixture
async def fake_server_client_factory() -> Any:
    running_server = None

    async def factory(hosts: List[str], routes: Iterable[AbstractRouteDef]) -> Type[aiohttp.ClientSession]:
        nonlocal running_server
        running_server = mocks.FakeServer(hosts)
        running_server.add_routes(routes)
        info = await running_server.start()
        resolver = mocks.FakeResolver(info)
        connector = aiohttp.TCPConnector(resolver=resolver, verify_ssl=False)

        class FakeClientSession(aiohttp.ClientSession):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                kwargs['connector'] = connector
                super().__init__(*args, **kwargs)

        return FakeClientSession

    yield factory

    if running_server is not None:
        await running_server.stop()


def pytest_configure(config: Any) -> None:
    import sys

    setattr(sys, '_called_from_test', True)


def pytest_unconfigure(config: Any) -> None:
    import sys

    delattr(sys, '_called_from_test')
