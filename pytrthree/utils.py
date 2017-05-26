import datetime
import io
import logging
import os
import re
import sys
import time
from zeep.exceptions import Fault

import pandas as pd
import yaml
from zeep.xsd.valueobjects import CompoundValue

logger = logging.getLogger('pytrthree')


def make_logger(name, config=None) -> logging.Logger:
    log_path = os.path.expanduser(config['log']) if config else os.getcwd()
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    fname = os.path.join(log_path, f'{name}.log')
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(fmt='{asctime} | {name} | {levelname}: {message}',
                                  datefmt='%Y-%m-%d %H:%M:%S', style='{')

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    file_handler = logging.FileHandler(filename=fname, mode='a')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def load_config(config_path):
    if isinstance(config_path, io.IOBase):
        file = config_path
    else:
        file = open(os.path.expanduser(config_path))
    config = yaml.load(file)
    config_keys = {'credentials'}
    if config_keys - set(config.keys()):
        raise ValueError(f'Config keys missing: {config_keys - set(config.keys())}')
    else:
        return config


def base_parser(resp):
    if isinstance(resp, dict):
        keys = list(resp.keys())
        if len(keys) == 1:
            return base_parser(resp[keys[0]])
        else:
            return resp
    else:
        return resp


parse_ArrayOfData = base_parser
parse_ArrayOfMessageType = base_parser


def parse_ArrayOfInstrument(resp):
    arr = base_parser(resp)
    return [base_parser({k: v for k, v in instr.items() if v}) for instr in arr]


def make_ArrayOfData(param, factory):
    """Generates ArrayOfData if input is a dictionary for list of dictionaries"""
    if isinstance(param, dict):
        return factory.ArrayOfData([{'field': field, 'value': value} for field, value in param.items()])
    elif isinstance(param, list):
        data = [[{'field': field, 'value': value}
                 for field, value in i.items()][0] for i in param]
        return factory.ArrayOfData(data)
    else:
        return param


def make_ArrayOfInstrument(param, factory):
    """Generates ArrayOfInstrument from a list of RICs"""
    if isinstance(param, str):
        param = [param]
    if isinstance(param, list):
        return factory.ArrayOfInstrument([{'code': ric} for ric in param])
    else:
        return param


def make_Instrument(param, factory):
    if isinstance(param, str):
        return factory.Instrument(code=param)
    else:
        return param


def make_DateRange(param, factory):
    """Returns default value for functions requiring dateRange input"""
    if param is None:
        now = datetime.datetime.utcnow()
        return dict(start=now - datetime.timedelta(days=1), end=now)
    else:
        return param


def make_TimeRange(param, factory):
    """Returns default value for functions requiring timeRange input"""
    if param is None:
        return dict(start='00:00', end='23:59')
    else:
        return param


def make_RequestSpec(param, factory):
    if isinstance(param, CompoundValue):
        return param
    else:
        return factory.RequestSpec(**yaml.load(open(param)))


def make_LargeRequestSpec(param, factory):
    if isinstance(param, CompoundValue):
        return param
    else:
        return factory.LargeRequestSpec(**yaml.load(open(param)))


def parse_RequestResult(resp):
    """Generates DataFrame from RequestResult"""
    if resp['result']['status'] != 'Complete':
        logger.info(resp['result'])
        return resp
    df = pd.read_csv(io.BytesIO(resp['result']['data']), compression='gzip')
    df.dropna(axis=1, how='all', inplace=True)  # Dropping all completely empty columns
    return df


output_parsers = [parse_RequestResult, parse_ArrayOfData, parse_ArrayOfInstrument]
input_parsers = [make_ArrayOfData, make_ArrayOfInstrument, make_DateRange, make_TimeRange]


def parse_rid_type(x):
    return re.findall('-(N\d{9})-?(\w*)\.(?:csv|txt)', x)[0]


def retry(func, *args, n=sys.maxsize, sleep=3, exp_base=1, exception_cls=Fault, **kwargs):
    """
    Retries calling wrapee function `n` times,
    waiting `sleep * exp_base ** trial` between each trial.
    Can be used as exception logger with n=1.

    :param func: Wrapee function
    :param n: Maximum number of retries allowed. Defaults to 2^63 - 1.
    :param sleep: Multiplier of the exponential delayer
    :param exp_base: Base of the exponential delayer. Defaults to 1 (=constant delay).
    """

    def retry_processing(trial, e, args, kwargs):
        if trial < n - 1:
            delay = sleep * exp_base ** trial
            logger.info(f'Retrying in {delay} seconds (#{trial+1})...')
            time.sleep(delay)
        else:
            raise e

    def wrapper(func, *args, **kwargs):
        for trial in range(n):
            try:
                return func(*args, **kwargs)
            except exception_cls as e:
                retry_processing(trial, e, args, kwargs)
        return wrapper

    return wrapper(func, *args, **kwargs)
