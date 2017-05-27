import pytest

from pytrthree import TRTH


def pytest_addoption(parser):
    parser.addoption("--config", action="store", help="Path to YAML configuration file")


@pytest.fixture(scope="module")
def api(request):
    config = request.config.getoption("--config")
    print(f'Config file: {config}')
    api = TRTH(config=config)
    api.debug = True
    api.options['raise_exception'] = True
    assert api.debug
    yield api
