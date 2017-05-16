#!/usr/bin/env python
import asyncio
import argparse
import io
import re

import aiohttp
import pandas as pd
import requests
from pytrthree import TRTH
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TRTH_HTTP_LIST = 'http://tickhistory.thomsonreuters.com/HttpPull/List'
TRTH_HTTP_DWLD = 'https://tickhistory.thomsonreuters.com/HttpPull/Download'


class Downloader:

    def __init__(self, config):
        api = TRTH(config=config)
        self.credentials = {'user': api.config['credentials']['username'],
                            'pass': api.config['credentials']['password']}
        self.results = self.list_results()
        z = zip(self.results['name'].apply(self.parse_fname2), self.results['size'])
        self.progress = {fname: dict(downloaded=0, total=total, state=None) for fname, total in z}
        self.loop = asyncio.get_event_loop()
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.print_progress, 'interval', seconds=5)

    @staticmethod
    def parse_fname(x):
        return re.findall('-(N\d{9})-?(\w*)\.(?:csv|txt)', x)[0]

    @staticmethod
    def parse_fname2(x):
        return '-'.join(x.split('-')[2:])

    def list_results(self):
        params = {'dir': '/api-results', 'mode': 'csv', **self.credentials}
        r = requests.get(TRTH_HTTP_LIST, params=params)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        df.columns = ['type', 'name', 'size', 'date']
        types = df['name'].apply(self.parse_fname).apply(pd.Series)
        df['id'] = types[0]
        df['type'] = types[1].replace('', 'part000')
        return df

    async def download(self, file):
        async with aiohttp.ClientSession() as session:
            params = {'file': file, **self.credentials}
            async with session.get(TRTH_HTTP_DWLD, params=params, timeout=None) as resp:
                await self.save_stream(resp, file)

    async def save_stream(self, resp, file):
        filename = self.parse_fname2(file)
        print(f'Downloading {filename}')
        self.progress[filename]['state'] = 'D'
        with open(filename, 'wb') as f:
            while True:
                chunk = await resp.content.read(256*1024)
                self.progress[filename]['downloaded'] += len(chunk)
                if not chunk:
                    self.progress[filename]['downloaded'] = self.progress[filename]['size']
                    self.progress[filename]['state'] += 'C'
                    print(f'Finished downloading {filename}')
                    break
                f.write(chunk)

    def print_progress(self):
        for fname, progress in self.progress.items():
            if progress['state']:
                pct = progress['downloaded'] / progress['total']
                print(f'{fname}: {pct:.1%}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download TRTH files from HTTP.')
    parser.add_argument('--config', action='store', type=argparse.FileType('r'), required=True)
    args = parser.parse_args()
    downloader = Downloader(args.config)
    fut = asyncio.gather(*[downloader.download(f) for f in downloader.results['name'][:3]])
    downloader.scheduler.start()
    downloader.loop.run_until_complete(fut)
