import io
import re
from typing import Sequence, Union

import numpy as np
import pandas as pd
import pytz

from . import utils

logger = utils.make_logger('pytrthree')

TRTHFile = Union[str, io.TextIOWrapper]


class TRTHIterator:
    """
    Helper class to parse a set of TRTH .csv.gz files
    and yield DataFrame grouped by RIC.
    """

    def __init__(self, files, chunksize=10 ** 6):
        """
        Validates input files and initializes iterator.
        :param files: Compressed CSV files downloaded from the TRTH API
        :param chunksize: Number of rows to be parsed per iteration.
                          Higher number causes higher memory usage.
        """
        self.files = self._validate_input(files)
        self.chunksize = chunksize
        self.iter = self.make_next()

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.iter)

    @staticmethod
    def _validate_input(files: Union[TRTHFile, Sequence[TRTHFile]]) -> Sequence[TRTHFile]:
        if isinstance(files, (str, io.TextIOWrapper)):
            files = [files]
        for f in files:
            if not isinstance(f, (str, io.TextIOWrapper)):
                raise ValueError(f'Invalid input: {f}')

        output = []
        for file in files:
            fname = file.name if isinstance(file, io.TextIOWrapper) else file
            try:
                _, ftype = utils.parse_rid_type(fname)
            except (IndexError, ValueError):
                logger.debug(f'Ignoring {fname}')
                continue
            if ftype in {'confirmation', 'report'}:
                logger.debug(f'Ignoring {fname}')
                continue
            else:
                output.append(file)

        return sorted(output)

    def make_next(self):
        """Iterates over input files and generates single-RIC DataFrames"""
        for file in self.files:
            lastrow = None
            chunks = pd.read_csv(file, iterator=True, chunksize=self.chunksize)
            for i, chunk in enumerate(chunks):
                fname = file.name if isinstance(file, io.TextIOWrapper) else file
                logger.info('{} chunk #{}'.format(fname.split('/')[-1], i+1))
                for ric, df in chunk.groupby('#RIC'):
                    processed_df = self.pre_process(df.copy(), lastrow)
                    yield (ric, processed_df)
                    lastrow = None
                lastrow = processed_df.iloc[-1]

    @staticmethod
    def pre_process(df, lastrow=None) -> pd.DataFrame:
        """Generates a unique DateTimeIndex and drops datetime-related columns"""
        def find_columns(df, pattern):
            try:
                return [i for i in df.columns if re.search(pattern, i)][0]
            except IndexError:
                return None

        # Remove characters that cause problems in MongoDB/Pandas (itertuples)
        df.columns = [re.sub('\.|-|#', '', col) for col in df.columns]
        df = df.dropna(axis=1, how='all')

        # Make DateTimexIndex
        date_col = find_columns(df, 'Date')
        time_col = find_columns(df, 'Time')
        gmt_col = find_columns(df, 'GMT')
        if time_col:
            df.index = pd.to_datetime(df[date_col].astype(str) + ' ' + df[time_col])
            df.drop([date_col, time_col], axis=1, inplace=True)
        else:
            df.index = pd.to_datetime(df[date_col].astype(str))
            df.drop(date_col, axis=1, inplace=True)
            return df

        # Add small offset to repeated timestamps to make timeseries index unique.
        offset = pd.DataFrame(df.index).groupby(0).cumcount() * np.timedelta64(1, 'us')
        df.index += offset.values

        # Make DateTimeIndex timezone-aware
        if gmt_col:
            assert len(df[gmt_col].value_counts()) == 1
            df.index = df.index + pd.Timedelta(hours=df.ix[0, gmt_col])
            df.index = df.index.tz_localize(pytz.FixedOffset(9 * 60))
            df.drop(gmt_col, axis=1, inplace=True)
        else:
            df.index = df.index.tz_localize(pytz.timezone('utc'))

        # Make sure rows separated by chunks have different timestamps
        if lastrow is not None:
            if lastrow['RIC'] == df.ix[0, 'RIC'] and lastrow.name == df.index[0]:
                logger.debug(f'Adjusting first row timestamp: {df.ix[0, "RIC"]}')
                df.index.values[0] += np.timedelta64(1, 'us')

        return df
