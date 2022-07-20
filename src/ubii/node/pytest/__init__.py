"""
This is a pytest plugin that you can require in your pytest conftest.py
files to easier write python tests for the Ubi-Interact Python node.

More information:
https://docs.pytest.org/en/7.1.x/how-to/writing_plugins.html#requiring-loading-plugins-in-a-test-module-or-conftest-file

Example :

    In your root level `conftest.py` file, require the module like ::

        pytest_plugins = ['ubii.node.pytest']


"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import pathlib
import typing
import typing as t
import warnings

import proto.message
import pytest
import yaml

import codestare.async_utils

try:
    from importlib import metadata
except ImportError:  # for Python<3.8
    import importlib_metadata as metadata

import ubii.proto as ub
from ubii.framework.client import Devices, UbiiClient, InitProcessingModules, Sessions
from ubii.framework.logging import logging_setup
from ubii.node.protocol import DefaultProtocol

log = logging.getLogger(__name__)

__verbosity__: int | None = None
_error_marker = 'closes_loop'


def pytest_addoption(parser):
    """
    Adds command line option `--log-config` and .ini option `data_dir`
    """
    parser.addoption(
        "--log-config",
        action="store", default="./data/logging_config.yaml", help="path to yaml file containing log config"
    )
    parser.addini(
        'data_dir',
        default='./data', help='Relative path to directory with test data.'
    )
    parser.addini(
        'cli_entry_point',
        default='ubii-client', help='Entry point for CLI'
    )


def pytest_configure(config):
    """
    Sets verbosity and checks if the protobuf package is installed correctly
    """
    global __verbosity__
    __verbosity__ = logging.INFO - 10 * config.getoption('verbose')

    import ubii.proto
    assert ubii.proto.__proto_package__ is not None, "No proto package set, aborting test setup."

    # register an additional marker
    config.addinivalue_line(
        "markers",
        f"{_error_marker}: mark test which close the event loop"
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item: pytest.Item):
    yield
    marker = item.get_closest_marker(_error_marker)
    loop_scope = {n: v for n, v in item.user_properties}.get('event_loop_scope', None)
    if marker and loop_scope != 'function':
        raise pytest.UsageError(f"{item} is marked as closing the event loop, it needs to request"
                                f" a function scoped event_loop fixture to create a new loop for each call")


@pytest.fixture(scope='session', autouse=True)
def configure_logging(request):
    """
    Change log config if fixture is requested

    Args:
        request: will be passed if fixture is parametrized indirectly,
            `request.param` should contain the logging config as dictionary

    """
    from pathlib import Path
    log_config_path = Path(request.config.getoption('--log-config'))
    if log_config_path.exists():
        with log_config_path.open() as f:
            test_logging_config = yaml.safe_load(f)
            logging_setup.change(config=test_logging_config)

    custom = getattr(request, 'param', None)
    logging_setup.change(config=custom, verbosity=__verbosity__)

    with logging_setup:
        yield logging_setup


@pytest.fixture(scope='session', autouse=True)
def service_url_env(request):
    """
    Sets environment variable used for connection to broker node
    to default or requested value
    """
    import os
    from ubii.framework.constants import UBII_URL_ENV
    old = os.environ.get(UBII_URL_ENV)
    os.environ[UBII_URL_ENV] = getattr(request, 'param', None) or 'http://localhost:8102/services/json'
    yield
    if old:
        os.environ[UBII_URL_ENV] = old


@pytest.fixture(autouse=True, scope='session')
def debug_settings():
    """
    Enables debug mode, automatically
    """
    from ubii.framework import debug
    previous = debug()
    debug(enabled=True)
    yield
    debug(enabled=previous)


@pytest.fixture(scope='session')
def event_loop(request) -> asyncio.AbstractEventLoop:
    """
    We need better control over the asyn processing
    """

    loop = asyncio.get_event_loop_policy().new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    tasks = asyncio.all_tasks(loop=loop)
    if tasks:
        for nursery in codestare.async_utils.TaskNursery.registry.values():
            if any(t in nursery.tasks for t in tasks):
                loop.run_until_complete(nursery.__aexit__(None, None, None))

        tasks = asyncio.all_tasks(loop=loop)
        for task in tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                loop.run_until_complete(task)

    loop.close()


@pytest.fixture(scope='class')
async def base_client() -> UbiiClient:
    """
    We need more control over the client, so don't use the default client interface.
    """
    protocol = DefaultProtocol()
    client = UbiiClient(protocol=protocol)
    protocol.client = client

    yield client
    if not client.protocol.finished:
        await client
        await client.protocol.stop()


@pytest.fixture(scope='session')
def base_module():
    """
    Returns an empty processing module
    """
    yield ub.ProcessingModule()


@pytest.fixture(scope='session')
def base_session():
    """
    Returns an empty session
    """
    yield ub.Session()


@pytest.fixture(scope='class')
def register_device(client):
    """
    Get callable to register devices
    """

    async def _register(*args, **kwargs):
        _client = await client
        await _client.implements(Devices)
        _client[Devices].register_device(*args, **kwargs)

    yield _register


@pytest.fixture(scope='session')
def start_client(reset_client):
    async def start(client: UbiiClient):
        try:
            return await client
        except UserWarning as w:
            log.info(w)
            await reset_client(client)
            client.protocol.start()

            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=UserWarning, module='ubii.framework.client')
                return await client

    return start


@pytest.fixture(scope='session')
def stop_client():
    async def stop(client: UbiiClient):
        await client.protocol.stop()

    return stop


@pytest.fixture(scope='class')
async def start_session(client_spec):
    """
    Get callable to start a session.
    Session will be stopped automatically if test suite finishes
    """
    await client_spec.implements(Sessions)
    yield client_spec[Sessions].start_session
    to_stop = [session for session in client_spec[Sessions].sessions.values()]
    for session in to_stop:
        await client_spec[Sessions].stop_session(session)


P = t.TypeVar('P', bound=proto.message.Message)


def _change_specs(proto: P, *specs: P):
    base = type(proto).pb(proto)
    for change in specs:
        base.MergeFrom(type(change).pb(change))

    type(proto).copy_from(proto, base)


_get_param = (lambda request: request.param if hasattr(request, 'param') else ())


@pytest.fixture(scope='class')
def late_init_module_spec(request):
    """
    Yield the list of module types specified as the request
    """
    module_types = _get_param(request)
    yield module_types


@pytest.fixture(scope='class')
def module_spec(base_module, request):
    """
    Update the base module with all changes from the request
    """
    _change_specs(base_module, *_get_param(request))
    yield base_module


@pytest.fixture(scope='session')
def reset_client():
    """
    Reset the client if necessary
    """

    async def reset(client: UbiiClient):
        if client.protocol.finished:
            log.debug(f"{client} needs to be reset")
            module_types = client[InitProcessingModules].module_types
            await client.reset()
            client[InitProcessingModules] = InitProcessingModules(
                module_types=module_types, initialized=[]
            )
        else:
            log.warning(f"{client} not reset, protocol is not finished")

    yield reset


@pytest.fixture(scope='class')
async def client_spec(
        base_client,
        reset_client,
        stop_client,
        module_spec,
        late_init_module_spec,
        event_loop: asyncio.AbstractEventLoop,
        request
):
    """
    Update the base client with all changes from the request
    """
    _change_specs(base_client, *_get_param(request))
    base_client.initial_specs.update(type(base_client).to_dict(base_client))

    by_name = {pm.name: pm for pm in base_client.processing_modules}
    if module_spec.name in by_name:
        by_name[module_spec.name] = module_spec

    base_client.processing_modules = list(by_name.values())
    if late_init_module_spec:
        assert base_client.implements(InitProcessingModules)
        base_client[InitProcessingModules].module_types = late_init_module_spec

    yield base_client
    await stop_client(base_client)
    await reset_client(base_client)


@pytest.fixture(scope='class')
def session_spec(base_session, module_spec, request):
    """
    Update the base session with all changes from the request
    """
    _change_specs(base_session, *_get_param(request))
    module_names = [pm.name for pm in base_session.processing_modules]

    if module_spec.name and module_spec.name not in module_names:
        base_session.processing_modules += [module_spec]
    yield base_session


@pytest.fixture(scope='class')
def client(client_spec):
    """
    Convenience fixture with different name, always starts the client :func:`client_spec` result
    """
    yield client_spec


@pytest.fixture(scope='session')
def data_dir(pytestconfig) -> pathlib.Path:
    """
    Configures data directory and returns it so tests can write stuff to it
    """
    data_dir_config_value = pytestconfig.getini('data_dir')
    data_dir = pytestconfig.rootpath / data_dir_config_value
    assert data_dir.exists(), f"Wrong data dir: {data_dir.resolve()} does not exist."
    yield data_dir


@pytest.fixture(scope='session')
def cli_entry_point(pytestconfig) -> typing.Callable:
    """
    Load entry point for CLI, according to pytest config
    """
    entry_point = pytestconfig.getini('cli_entry_point')

    with warnings.catch_warnings():
        # this deprecation is discussed a lot
        warnings.simplefilter("ignore")
        loaded = [
            entry.load()
            for entry in metadata.entry_points().get('console_scripts', ())
            if entry.name == entry_point
        ]
    assert len(loaded) == 1, (f"{len(loaded)} entry point[s] for specification {entry_point} found in python path. "
                              f"Did you correctly install the [cli] extra?")
    assert callable(loaded[0]), f"Entry point {loaded[0]} is not callable."
    yield loaded[0]


def pytest_generate_tests(metafunc):
    """
    Automatically parametrizes tests in classes with class attributes `client_spec`, `module_spec` or
    `session_spec` that use the corresponding fixtures.
    """
    specs = [
        'client_spec',
        'module_spec',
        'session_spec',
        'late_init_module_spec'
    ]

    for spec in specs:
        if hasattr(metafunc.cls, spec) and spec in metafunc.fixturenames:
            metafunc.parametrize(spec, getattr(metafunc.cls, spec), indirect=[spec])
