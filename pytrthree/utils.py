import functools
import logging
import os
import io

import yaml
import pandas as pd

logger = logging.getLogger('pytrthree')


def make_logger(name, config) -> logging.Logger:
    if not os.path.exists(config['log']):
        os.makedirs(config['log'])
    fname = os.path.join(config['log'], f'{name}.log')
    logger = logging.getLogger(name)
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
    config = yaml.load(open(os.path.expanduser(config_path)))
    config_keys = {'credentials'}
    if config_keys - set(config.keys()):
        raise ValueError(f'Config keys missing: {config_keys - set(config.keys())}')
    else:
        return config

def parse_request(resp):
    if resp['result']['status'] != 'Complete':
        logger.info(resp['result'])
        return
    df = pd.read_csv(io.BytesIO(resp['result']['data']), compression='gzip')
    df.dropna(axis=1, how='all', inplace=True)  # Dropping all completely empty columns
    return df


