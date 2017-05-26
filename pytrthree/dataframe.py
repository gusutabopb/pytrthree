import io
import re
from typing import Sequence, Union

import pandas as pd
import numpy as np

from . import utils

logger = utils.make_logger('pytrthree')

TRTHFile = Union[str, io.TextIOWrapper]


class TRTHIterator:
    """
    Helper class to parse a set of TRTH .csv.gz files
    and yield DataFrame grouped by RIC.
    """
    def __init__(self, files, chunksize=10 ** 6):
        self.files = self._validate_input(files)
        self.chunksize = chunksize

    def __iter__(self):
        return self.make_next()

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
                logger.warning(f'Ignoring {fname}')
                continue
            if ftype in {'confirmation', 'report'}:
                logger.debug(f'Ignoring {fname}')
                continue
            else:
                output.append(file)

        return sorted(output)

    def make_next(self):
        for file in self.files:
            chunks = pd.read_csv(file, iterator=True, chunksize=self.chunksize)
            for chunk in chunks:
                for _, df in chunk.groupby('#RIC'):
                    yield self.pre_process(df.copy())

    @staticmethod
    def pre_process(df) -> pd.DataFrame:
        def find_columns(df, pattern):
            try:
                return [i for i in df.columns if re.search(pattern, i)][0]
            except IndexError:
                return None

        # Remove characters that cause problems in MongoDB/Pandas (itertuples)
        df.columns = [re.sub('\.|-|#', '', col) for col in df.columns]
        date_col = find_columns(df, 'Date')
        time_col = find_columns(df, 'Time')
        gmt_col = find_columns(df, 'GMT')
        if time_col:
            df.index = pd.to_datetime(df[date_col].astype(str) + ' ' + df[time_col])
            df.drop([date_col, time_col], axis=1, inplace=True)
            if gmt_col:
                df.index = df.index + pd.Timedelta(hours=9)
                df.drop(gmt_col, axis=1, inplace=True)
        else:
            df.index = pd.to_datetime(df[date_col].astype(str))
            df.drop(date_col, axis=1)

        #Add 10 ns to repeated timestamps to make timeseries index unique.
        offset = pd.DataFrame(df.index).groupby(0).cumcount() * np.timedelta64(10, 'ns')
        df.index = df.index + offset.values
        return df
