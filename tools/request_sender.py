#!/usr/bin/env python
import argparse
import datetime

import pandas as pd
import yaml
from pytrthree import TRTH
from pytrthree.utils import retry


def make_request(daterange, criteria):
    request = api.factory.LargeRequestSpec(**template)
    short_dates = sorted([x.replace('-', '') for x in daterange.values()])
    search_result = api.search_rics(daterange, criteria['ric'], refData=False)
    ric_list = [{'code': i['code']} for i in search_result]
    request['friendlyName'] = '{}-{}_{}'.format(name, *short_dates)
    request['instrumentList']['instrument'] = ric_list
    request['dateRange'] = daterange
    if 'fields' in criteria:
        request['messageTypeList']['messageType'][0]['fieldList']['string'] = criteria['fields']
    return request


def parse_daterange(s):
    return dict(start=str(s.iloc[0].date()), end=str(s.iloc[-1].date()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Tool to send a series of requests to TRTH.')
    parser.add_argument('--config', action='store', type=argparse.FileType('r'), required=True,
                        help='TRTH API configuration (YAML file)')
    parser.add_argument('--template', action='store', type=argparse.FileType('r'), required=True,
                        help='Base template for the requests (YAML file)')
    parser.add_argument('--criteria', action='store', type=argparse.FileType('r'), required=True,
                        help='Criteria for searching RICs and modifying queried fields (YAML file)')
    parser.add_argument('--start', action='store', type=str, required=True,
                        help='Start date (ISO-8601 datetime string)')
    parser.add_argument('--end', action='store', type=str, default=str(datetime.datetime.now().date()),
                        help='End date (ISO-8601 datetime string). Default to today\'s date.')
    parser.add_argument('--group', action='store', type=str, default='1A',
                        help='Pandas datetime frequency string for grouping requests. Defaults to "1A".')
    args = parser.parse_args()

    api = TRTH(config=args.config)
    api.options['raise_exception'] = True
    criteria = yaml.load(args.criteria)
    template = yaml.load(args.template)

    dates = pd.date_range(args.start, args.end).to_series()
    dateranges = [parse_daterange(i) for _, i in dates.groupby(pd.TimeGrouper(args.group))]
    for daterange in dateranges:
        for name, crit in criteria.items():
            request = make_request(daterange, crit)
            rid = retry(api.submit_ftp_request, request, sleep=30, exp_base=2)
            api.logger.info(rid['requestID'])
    api.logger.info('All requests sent!')
