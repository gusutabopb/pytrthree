#!/usr/bin/env python
import asyncio
import argparse
import io
import re

import aiohttp
import pandas as pd
import requests
import pytrthree
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TRTH_HTTP_LIST = 'http://tickhistory.thomsonreuters.com/HttpPull/List'
TRTH_HTTP_DWLD = 'https://tickhistory.thomsonreuters.com/HttpPull/Download'


class Downloader:

    def __init__(self, args):
        self.args = args
        self.api = pytrthree.TRTH(config=args.config)
        self.credentials = {'user': self.api.config['credentials']['username'],
                            'pass': self.api.config['credentials']['password']}
        self.results = self.list_results()
        z = zip(self.results['name'].apply(self.parse_fname), self.results['size'])
        self.progress = {fname: dict(downloaded=0, total=total, state=None) for fname, total in z}
        self.requests = {group: data['name'].apply(self.parse_fname).tolist()
                         for group, data in self.results.groupby('id')}
        self.loop = asyncio.get_event_loop()
        self.scheduler = AsyncIOScheduler()
        self.scheduler.add_job(self.print_progress, 'interval', seconds=5)
        self.semaphore = asyncio.Semaphore(args.max)

    def start(self):
        files = [f for f in self.results['name'] if re.search(args.regex, f)]
        file_list = '\n'.join([f.split('/')[-1] for f in files])
        self.api.logger.info(f'Downloading {len(files)} files:\n{file_list}')
        if not self.args.dryrun:
            fut = asyncio.gather(*[self.download(f) for f in files])
            self.scheduler.start()
            self.loop.run_until_complete(fut)

    @staticmethod
    def parse_fname(x):
        return '-'.join(x.split('-')[2:])

    def list_results(self):
        params = {'dir': '/api-results', 'mode': 'csv', **self.credentials}
        r = requests.get(TRTH_HTTP_LIST, params=params)
        df = pd.read_csv(io.StringIO(r.content.decode('utf-8')))
        df.columns = ['type', 'name', 'size', 'date']
        types = df['name'].apply(pytrthree.utils.parse_rid_type).apply(pd.Series)
        df['id'] = types[0]
        df['type'] = types[1].replace('', 'part000')
        return df

    async def download(self, file):
        async with aiohttp.ClientSession() as session:
            params = {'file': file, **self.credentials}
            async with self.semaphore, session.get(TRTH_HTTP_DWLD, params=params, timeout=None) as resp:
                await self.save_stream(resp, file)

    async def save_stream(self, resp, file):
        filename = self.parse_fname(file)
        self.api.logger.info(f'Downloading {filename}')
        self.progress[filename]['state'] = 'D'
        with open(filename, 'wb') as f:
            while True:
                chunk = await resp.content.read(256*1024)
                self.progress[filename]['downloaded'] += len(chunk)
                if not chunk:
                    break
                f.write(chunk)
        self.progress[filename]['downloaded'] = self.progress[filename]['total']
        self.progress[filename]['state'] = 'C'
        self.api.logger.info(f'Finished downloading {filename}')
        if self.args.cancel:
            self.maybe_cancel_request(filename)

    def maybe_cancel_request(self, filename):
        rid = pytrthree.utils.parse_rid_type(filename)[0]
        completed = [self.progress[fname]['state'] == 'C' for fname in self.requests[rid]]
        report = [pytrthree.utils.parse_rid_type(fname)[1] == 'report' for fname in self.requests[rid]]
        # print(completed)
        # print(report)
        if all(completed) and any(report):
            self.api.logger.info(f'Canceling {rid}')
            # self.api.cancel_request()
            # api.cancel

    def print_progress(self):
        completed = 0
        for fname, progress in self.progress.items():
            if progress['state'] == 'D':
                pct = progress['downloaded'] / progress['total']
                self.api.logger.info(f'{fname}: {pct:.1%}')
            elif progress['state'] == 'C':
                completed +=1
        if completed:
            self.api.logger.info(f'Completed: {completed}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download TRTH files from HTTP.')
    parser.add_argument('--config', action='store', type=argparse.FileType('r'), required=True,
                        help='TRTH API configuration (YAML file)')
    parser.add_argument('--max', action='store', type=int, default=10,
                        help='Maximum number of concurrent downloads. Default: 10.')
    parser.add_argument('--regex', action='store', type=str, default='.*',
                        help='Option regular expression to filter which files to download.')
    parser.add_argument('--cancel', action='store_true',
                        help='Whether or not to cancel requests after all parts have been downloaded.')
    parser.add_argument('--dryrun', action='store_true',
                        help='Dry run mode. Use this to test which files will be downloaded.')
    args = parser.parse_args()
    downloader = Downloader(args)
    downloader.start()
