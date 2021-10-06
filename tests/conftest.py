import os
from collections import namedtuple

import pytest
import ubii_interact
import json
from pathlib import Path


@pytest.fixture(scope='session', autouse=True)
def service_url_env():
    import os
    from ubii_interact.util.constants import UBII_SERVICE_URL
    old = os.environ.get(UBII_SERVICE_URL)
    os.environ[UBII_SERVICE_URL] = 'localhost:8102/services'
    yield
    if old:
        os.environ[UBII_SERVICE_URL] = old


@pytest.fixture(scope='session')
def data_dir() -> Path:
    yield Path(__file__).parent / 'data'


def write_json(file, data, indent=4, sort_keys=True, **kwargs):
    with file.open('w', encoding='utf-8') as stream:
        json.dump(data, fp=stream, sort_keys=sort_keys, indent=indent, **kwargs)


def load_json(file):
    with file.open('r') as f:
        try:
            return json.load(fp=f)
        except json.JSONDecodeError as e:
            return {}


@pytest.fixture(scope='session')
def make_file(data_dir):
    def touch(path: os.PathLike):
        path = Path(path)
        try:
            relative = path.relative_to(data_dir)
        except ValueError as e:
            relative = None

        if not relative:
            path = data_dir / path

        path.touch(exist_ok=True)
        return path

    yield touch


@pytest.fixture(scope='session')
def get_json_data(data_dir):

    def load_data_for_type(msg_type):
        files = data_dir.glob(f'{msg_type.lower()}.json')
        return {f: load_json(f) for f in files}

    yield load_data_for_type


@pytest.fixture
def write_json_data():
    backup = {}

    def write(file, data):
        nonlocal backup
        backup[file] = load_json(file)
        write_json(file, data)
        del backup[file]

    yield write

    if backup:
        for file, contents in backup.items():
            write_json(file, contents)





@pytest.fixture
def enable_debug():
    ubii_interact.enable_debug()


@pytest.fixture
async def ubii_instance(event_loop):
    instance = ubii_interact.Ubii.instance
    await instance.initialize()
    yield instance
    await instance.shutdown()
