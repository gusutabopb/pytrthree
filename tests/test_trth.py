import pytest
from pytrthree import TRTH
import functools
from zeep.exceptions import Fault

sprint = functools.partial(print, end='\n=====\n')


@pytest.fixture(scope="module")
def api():
    api = TRTH(config='~/plugaai/pytrthree/config_toba.yml')
    api.debug = True
    assert api.debug
    yield api


def test_permissions(api):
    sprint(api.get_look_back_period())
    sprint(api.get_quota())
    sprint(api.get_used_instruments(1, 10))
    with pytest.raises(Fault):
        sprint(api.get_ric_list())


def test_instrument_details():
    pass


def test_direct_request():
    pass


def test_http_request():
    pass


def test_retrieve_data():
    pass


def test_speed_guide():
    pass


def test_data_dictionary():
    pass


def test_no_missing_functions(api):
    wrapped = []
    for attr in dir(api):
        obj = getattr(api, attr)
        if isinstance(obj, functools.partial):
            wrapped.append(obj.keywords['function'])
            sprint(obj.__doc__)
    assert set(wrapped) == set(api.signatures.keys())
