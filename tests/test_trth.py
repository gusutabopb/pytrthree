import functools
import datetime
import time
import os
import subprocess

import pytest
import yaml
from zeep.exceptions import Fault

from pytrthree import TRTH, utils

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


def test_instrument_details(api):
    now = datetime.datetime.utcnow()
    long_daterange = dict(start=datetime.datetime(1996, 1, 1), end=datetime.datetime(2017, 1, 1))
    short_daterange = dict(start=now - datetime.timedelta(days=1), end=now)
    time_range = dict(start='00:00', end='23:59')
    criteria = api.factory.ArrayOfData([{'field': 'Exchange', 'value': 'TYO'},
                                        {'field': 'RICRegex', 'value': '^720[0-9]{1}\.T$'}])
    instrument_list = api.factory.ArrayOfInstrument([{'code': '7203.T'}])

    resp = api.expand_chain({'code': '0#.N225'}, short_daterange, time_range, requestInGMT=True)
    assert len(resp['instrumentList']['instrument']) == 226

    resp = api.get_ric_symbology({'code': 'RIO.AX'}, long_daterange)
    assert resp['instrumentList']

    resp = api.search_rics(short_daterange, criteria, refData=True)
    assert resp['SearchRICsResult']['instrument'][0]['code'] == '7201.T'

    resp = api.verify_rics(short_daterange, instrument_list, refData=True)
    assert resp['verifyRICsResult']['nonVerifiedList'] is None
    assert resp['verifyRICsResult']['verifiedList']['instrument'][0]['name']['string'][0] == 'TOYOTA MOTOR CO'


def test_direct_request(api):
    r = api.factory.RequestSpec(**yaml.load(open('../templates/RequestSpec.yml')))
    rid = api.submit_request(r)
    while True:
        if api.get_status()['status']['active']:
            time.sleep(3)
            continue
        else:
            resp = api.get_request_result(**rid)
            df = utils.parse_request(resp)
            break
    print(df)
    assert not df.empty

    api.submit_request(r)
    assert api.get_status()['status']['active'] > 0
    api.clean_up()
    assert api.get_status()['status']['active'] == 0


def test_ftp_request(api):
    api.set_ftp_details(**api.config['ftp'])
    api.test_ftp()
    r = api.factory.LargeRequestSpec(**yaml.load(open('../templates/LargeRequestSpec.yml')))
    rid1 = api.submit_ftp_request(r)
    rid2 = api.submit_ftp_request(r)
    sprint(rid1, rid2, sep='\n')
    api.cancel_request(**rid2)
    assert api.get_status()['status']['active'] == 1
    assert api.get_request_result(**rid1)['result']['status'] == 'Processing'
    assert api.get_request_result(**rid2)['result']['status'] == 'Aborted'

    # Test if rid1 has been properly downloaded
    time.sleep(5)
    req_id = rid1['requestID'].split('-')[-1]
    for i in range(10):
        cmd = api.config['ftp_ls_cmd']
        dirlist = subprocess.check_output(cmd, shell=True).decode('utf-8').split('\n')
        if any([req_id in fname for fname in dirlist]):
            assert True
            break
        elif i == 9:
            assert False
        else:
            print('sleeping')
            time.sleep(5)


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
