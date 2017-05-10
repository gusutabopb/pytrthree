import functools
import datetime
import time
import subprocess

import pytest
import yaml
from zeep.exceptions import Fault


sprint = functools.partial(print, end='\n=====\n')


def test_permissions(api):
    sprint(api.get_look_back_period())
    sprint(api.get_quota())
    sprint(api.get_used_instruments(1, 10))
    with pytest.raises(Fault):
        sprint(api.get_ric_list())


def test_instrument_details(api):
    resp = api.expand_chain('0#.N225', requestInGMT=True)
    assert len(resp) == 226

    long_daterange = dict(start=datetime.datetime(1996, 1, 1), end=datetime.datetime(2017, 1, 1))
    resp = api.get_ric_symbology('RIO.AX', long_daterange)
    assert resp

    criteria = dict(Exchange='TYO', RICRegex='^720[0-9]{1}\.T$')
    resp = api.search_rics(criteria=criteria, refData=True)
    assert resp[0]['code'] == '7201.T'

    resp = api.verify_rics(instrumentList=['7203.T'], refData=True)
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
            df = api.get_request_result(**rid)
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


def test_speed_guide(api):
    r1 = api.get_page('THOMSONREUTERS', '2017-04-26', '12:00')
    assert r1['page']['data']

    r2 = api.get_snapshot_info()
    page_time = datetime.datetime.strptime(r2['dateTime'], '%Y-%m-%d %H:%M:%S')
    assert page_time < datetime.datetime.now()

    r3 = api.search_page('EQUITY', 1)
    assert len(r3['searchPageResults']['page'][0]['data']) > 1000


def test_data_dictionary(api):
    assert api.get_asset_domains()
    assert api.get_bond_types()
    assert api.get_countries()
    assert api.get_credit_ratings()

    r = api.get_currencies(dict(Country='Japan'))
    assert r[0]['value'] == 'JPY'

    domain = dict(Domain='COM')
    r = api.get_exchanges(domain)
    exchanges = [e['value'] for e in r]
    assert 'CME' in exchanges
    assert 'TYO' not in exchanges

    assert api.get_futures_delivery_months()
    assert api.get_option_expiry_months()
    assert api.get_instrument_types(domain)
    assert api.get_restricted_pes()
    assert api.get_message_types(domain, 'TimeAndSales')


def test_no_missing_functions(api):
    wrapped = []
    for attr in dir(api):
        obj = getattr(api, attr)
        if isinstance(obj, functools.partial):
            wrapped.append(obj.keywords['function'])
            sprint(obj.__doc__)
    assert set(wrapped) == set(api.signatures.keys())
